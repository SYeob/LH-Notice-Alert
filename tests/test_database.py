from dataclasses import replace
import sqlite3
import pytest
from filelock import FileLock, Timeout
from src.database import Database


def test_restart_retains_outbox_and_first_detection(config, notice):
    db = Database(config.db_path)
    db.ingest([])
    db.ingest([notice])
    detected = db.conn.execute('SELECT detected_at FROM notices').fetchone()[0]
    db.close()
    db = Database(config.db_path)
    try:
        assert db.initialized() and len(db.queued()) == 1
        db.record_delivery(notice.notice_id, message_id='42')
        db.ingest([replace(notice, status='변경')])
        assert not db.queued()
        assert db.conn.execute('SELECT detected_at FROM notices').fetchone()[0] == detected
        assert db.summary()['notifications'] == {'sent': 1}
    finally:
        db.close()


def test_transaction_rolls_back_entire_snapshot(db, notice):
    with pytest.raises(sqlite3.IntegrityError):
        db.ingest([notice, replace(notice, notice_id='invalid', title=None)])
    assert db.summary()['notices'] == 0
    assert not db.initialized()


def test_read_only_absent_db_creates_no_file(config):
    db = Database(config.db_path, read_only=True)
    assert db.summary()['notices'] == 0
    assert not config.db_path.exists()
    db.close()


def test_read_only_existing_db_cannot_mutate(config, db):
    reader = Database(config.db_path, read_only=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            reader.ingest([])
    finally:
        reader.close()


def test_duplicate_process_lock(config):
    with FileLock(str(config.db_path) + '.lock', timeout=0):
        with pytest.raises(Timeout):
            with FileLock(str(config.db_path) + '.lock', timeout=0):
                pass
