"""Transactional snapshot ingestion and a durable notification outbox."""
from dataclasses import asdict
from pathlib import Path
import sqlite3
from .models import now

SCHEMA = '''
CREATE TABLE IF NOT EXISTS notices (
 notice_id TEXT PRIMARY KEY, title TEXT NOT NULL, region TEXT NOT NULL,
 rental_type TEXT NOT NULL, posted_date TEXT NOT NULL, deadline TEXT, status TEXT,
 detail_url TEXT NOT NULL, detected_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_history (
 notice_id TEXT PRIMARY KEY REFERENCES notices(notice_id),
 status TEXT NOT NULL CHECK(status IN ('pending','sent','failed')),
 sent_at TEXT, retry_count INTEGER NOT NULL DEFAULT 0, last_error TEXT,
 telegram_message_id TEXT
);
CREATE TABLE IF NOT EXISTS notification_attempts (
 id INTEGER PRIMARY KEY, notice_id TEXT NOT NULL REFERENCES notices(notice_id),
 attempted_at TEXT NOT NULL, status TEXT NOT NULL, error TEXT, telegram_message_id TEXT
);
CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''


class Database:
    def __init__(self, path, read_only=False):
        self.path = Path(path)
        if read_only and self.path.exists():
            self.conn = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)
        elif read_only:
            self.conn = sqlite3.connect(':memory:')
            self.conn.executescript(SCHEMA)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.path)
            self.conn.executescript(SCHEMA)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('PRAGMA busy_timeout=5000')

    def close(self):
        self.conn.close()

    def state(self, key, default=None):
        row = self.conn.execute('SELECT value FROM app_state WHERE key=?', (key,)).fetchone()
        return row[0] if row else default

    def set_state(self, key, value):
        self.conn.execute('INSERT INTO app_state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                          (key, str(value)))

    def initialized(self):
        return self.state('initialized') == 'true'

    def assert_can_init(self):
        if self.initialized() or self.conn.execute('SELECT COUNT(*) FROM notices').fetchone()[0]:
            raise ValueError('--init 거부: 기존 데이터 또는 초기화 상태가 있습니다. DB를 삭제하지 않았습니다.')

    def new_ids(self, notices):
        return [n.notice_id for n in notices if not self.conn.execute(
            'SELECT 1 FROM notices WHERE notice_id=?', (n.notice_id,)).fetchone()]

    def ingest(self, notices, notify_first=False, force_init=False):
        stamp = now()
        with self.conn:
            if force_init:
                self.assert_can_init()
            first = not self.initialized()
            new = set(self.new_ids(notices))
            for notice in notices:
                values = asdict(notice)
                values.update(detected_at=stamp, last_seen_at=stamp)
                self.conn.execute('''INSERT INTO notices VALUES (
                    :notice_id,:title,:region,:rental_type,:posted_date,:deadline,:status,
                    :detail_url,:detected_at,:last_seen_at)
                    ON CONFLICT(notice_id) DO UPDATE SET title=excluded.title,
                    region=excluded.region,rental_type=excluded.rental_type,
                    posted_date=excluded.posted_date,deadline=excluded.deadline,
                    status=excluded.status,detail_url=excluded.detail_url,
                    last_seen_at=excluded.last_seen_at''', values)
                if notice.notice_id in new and (not first or notify_first) and not force_init:
                    self.conn.execute("INSERT INTO notification_history(notice_id,status) VALUES (?,'pending')",
                                      (notice.notice_id,))
            self.set_state('initialized', 'true')
            self.set_state('last_successful_check', stamp)
            self.set_state('consecutive_failures', 0)
        return len(new), first

    def queued(self):
        return self.conn.execute('''SELECT n.* FROM notices n JOIN notification_history h USING(notice_id)
            WHERE h.status IN ('pending','failed') ORDER BY n.detected_at,n.notice_id''').fetchall()

    def record_delivery(self, notice_id, message_id=None, error=None):
        stamp = now()
        status = 'failed' if error else 'sent'
        with self.conn:
            self.conn.execute('''UPDATE notification_history SET status=?,sent_at=?,
                retry_count=retry_count+?,last_error=?,telegram_message_id=?
                WHERE notice_id=? AND status!='sent' ''',
                (status, None if error else stamp, int(error is not None), error, message_id, notice_id))
            self.conn.execute('''INSERT INTO notification_attempts
                (notice_id,attempted_at,status,error,telegram_message_id) VALUES (?,?,?,?,?)''',
                (notice_id, stamp, status, error, message_id))

    def record_failure(self):
        with self.conn:
            count = int(self.state('consecutive_failures', '0')) + 1
            self.set_state('consecutive_failures', count)
        return count

    def summary(self):
        states = dict(self.conn.execute('SELECT key,value FROM app_state'))
        counts = dict(self.conn.execute('SELECT status,COUNT(*) FROM notification_history GROUP BY status'))
        return {'database': str(self.path), 'notices': self.conn.execute('SELECT COUNT(*) FROM notices').fetchone()[0],
                'notifications': counts, 'state': states}
