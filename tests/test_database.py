from dataclasses import replace
import sqlite3
import pytest
from filelock import FileLock, Timeout
from src.database import Database


def test_restart_retains_outbox_and_first_detection(config, notice):
    """DB 재연결 후 발송 대기·성공 상태와 최초 감지 시각을 유지한다."""
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
    """일부 공고 저장이 실패하면 조회 결과 전체를 롤백한다."""
    with pytest.raises(sqlite3.IntegrityError):
        db.ingest([notice, replace(notice, notice_id='invalid', title=None)])
    assert db.summary()['notices'] == 0
    assert not db.initialized()


def test_read_only_absent_db_creates_no_file(config):
    """없는 DB를 읽기 전용으로 확인해도 파일을 만들지 않는다."""
    db = Database(config.db_path, read_only=True)
    assert db.summary()['notices'] == 0
    assert not config.db_path.exists()
    db.close()


def test_read_only_existing_db_cannot_mutate(config, db):
    """읽기 전용 연결에서는 기존 DB 변경을 거부한다."""
    reader = Database(config.db_path, read_only=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            reader.ingest([])
    finally:
        reader.close()


def test_duplicate_process_lock(config):
    """동일 DB의 실행 잠금을 중복 획득할 수 없다."""
    with FileLock(str(config.db_path) + '.lock', timeout=0):
        with pytest.raises(Timeout):
            with FileLock(str(config.db_path) + '.lock', timeout=0):
                pass
