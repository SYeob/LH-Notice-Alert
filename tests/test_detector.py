from dataclasses import replace
import pytest
from src.detector import Monitor
from src.http import NetworkError
from src.parser import ParseError
from src.telegram import TelegramError


def test_first_run_silent_and_restart_deduplicated(config, db, crawler, telegram, notice):
    crawler.collect.return_value = [notice]
    monitor = Monitor(config, db, crawler, telegram)
    assert monitor.run_once()
    assert db.initialized() and db.summary()['notices'] == 1
    assert not db.queued()
    assert monitor.run_once()
    telegram.send.assert_not_called()


@pytest.mark.parametrize('count', [1, 3])
def test_new_notices_send_individually(config, db, crawler, telegram, notice, count):
    db.ingest([])
    crawler.collect.return_value = [replace(notice, notice_id=str(i)) for i in range(count)]
    monitor = Monitor(config, db, crawler, telegram)
    assert monitor.run_once()
    assert telegram.send.call_count == count
    assert db.summary()['notifications'] == {'sent': count}
    monitor.run_once()
    assert telegram.send.call_count == count


def test_status_changes_silent_but_correction_new_id_notifies(config, db, crawler, telegram, notice):
    db.ingest([notice])
    crawler.collect.return_value = [replace(notice, status='접수중', title='변경된 공고')]
    monitor = Monitor(config, db, crawler, telegram)
    monitor.run_once()
    telegram.send.assert_not_called()
    crawler.collect.return_value.append(replace(notice, notice_id='new-correction', title='정정 공고'))
    monitor.run_once()
    telegram.send.assert_called_once()


def test_other_regions_and_nationwide_excluded(config, db, crawler, telegram, notice):
    db.ingest([])
    crawler.collect.return_value = [replace(notice, notice_id=str(i), region=region)
                                   for i, region in enumerate(['서울특별시', '전국', '경기도,서울특별시'])]
    Monitor(config, db, crawler, telegram).run_once()
    assert db.summary()['notices'] == 0
    telegram.send.assert_not_called()


def test_failed_delivery_retries_and_records_attempts(config, db, crawler, telegram, notice):
    db.ingest([])
    crawler.collect.return_value = [notice]
    telegram.send.side_effect = [TelegramError('HTTP 500'), '123']
    monitor = Monitor(config, db, crawler, telegram)
    assert not monitor.run_once()
    assert db.summary()['notifications'] == {'failed': 1}
    assert monitor.run_once()
    assert db.summary()['notifications'] == {'sent': 1}
    assert not db.queued()
    assert db.conn.execute('SELECT COUNT(*) FROM notification_attempts').fetchone()[0] == 2
    monitor.run_once()
    assert telegram.send.call_count == 2


@pytest.mark.parametrize('error', [NetworkError('연결 실패'), ParseError('구조 변경')])
def test_collection_failure_does_not_initialize_or_destroy(config, db, crawler, telegram, notice, error):
    crawler.collect.side_effect = error
    monitor = Monitor(config, db, crawler, telegram)
    assert not monitor.run_once()
    assert not db.initialized()
    db.ingest([notice])
    previous = db.state('last_successful_check')
    assert not monitor.run_once()
    assert db.summary()['notices'] == 1
    assert db.state('last_successful_check') == previous
    telegram.send.assert_not_called()


def test_successful_empty_initializes(config, db, crawler, telegram):
    assert Monitor(config, db, crawler, telegram).run_once()
    assert db.initialized()
    telegram.send.assert_not_called()


def test_dry_run_preserves_all_state_and_queued_messages(config, db, crawler, telegram, notice):
    db.ingest([])
    db.ingest([notice])
    before = '\n'.join(db.conn.iterdump())
    crawler.collect.return_value = [replace(notice, notice_id='another')]
    assert Monitor(config, db, crawler, telegram).run_once(dry_run=True)
    assert before == '\n'.join(db.conn.iterdump())
    crawler.collect.side_effect = NetworkError('연결 실패')
    assert not Monitor(config, db, crawler, telegram).run_once(dry_run=True)
    assert before == '\n'.join(db.conn.iterdump())
    telegram.send.assert_not_called()


def test_operational_warning_cooldown(config, db, crawler, telegram):
    crawler.collect.side_effect = NetworkError('연결 실패')
    monitor = Monitor(config, db, crawler, telegram)
    for _ in range(8):
        monitor.run_once()
    telegram.send.assert_called_once()
    assert db.state('consecutive_failures') == '8'


def test_queue_retried_even_when_lh_down(config, db, crawler, telegram, notice):
    db.ingest([])
    db.ingest([notice])
    crawler.collect.side_effect = NetworkError('연결 실패')
    assert not Monitor(config, db, crawler, telegram).run_once()
    assert db.summary()['notifications'] == {'sent': 1}


def test_explicit_init_ignores_first_run_notification_setting(config, db, crawler, telegram, notice):
    crawler.collect.return_value = [notice]
    assert Monitor(replace(config, notify_on_first_run=True), db, crawler, telegram).run_once(init=True)
    assert not db.queued()
    telegram.send.assert_not_called()
    with pytest.raises(ValueError, match='--init 거부'):
        Monitor(config, db, crawler, telegram).run_once(init=True)
