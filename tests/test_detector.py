from dataclasses import replace
import pytest
from src.detector import Monitor
from src.http import NetworkError
from src.parser import ParseError
from src.telegram import TelegramError


def test_first_run_silent_and_restart_deduplicated(config, db, crawler, telegram, notice):
    """최초 성공 조회는 무알림으로 저장하고 재조회도 중복 발송하지 않는다."""
    crawler.collect.return_value = [notice]
    monitor = Monitor(config, db, crawler, telegram)
    assert monitor.run_once()
    assert db.initialized() and db.summary()['notices'] == 1
    assert not db.queued()
    assert monitor.run_once()
    telegram.send.assert_not_called()


@pytest.mark.parametrize('count', [1, 3])
def test_new_notices_send_individually(config, db, crawler, telegram, notice, count):
    """신규 공고 1건 또는 3건을 각각 한 번씩 알린다."""
    db.ingest([])
    crawler.collect.return_value = [replace(notice, notice_id=str(i)) for i in range(count)]
    monitor = Monitor(config, db, crawler, telegram)
    assert monitor.run_once()
    assert telegram.send.call_count == count
    assert db.summary()['notifications'] == {'sent': count}
    monitor.run_once()
    assert telegram.send.call_count == count


def test_status_changes_silent_but_correction_new_id_notifies(config, db, crawler, telegram, notice):
    """동일 ID의 내용 변경은 무알림, 새 ID의 정정공고는 발송한다."""
    db.ingest([notice])
    crawler.collect.return_value = [replace(notice, status='접수중', title='변경된 공고')]
    monitor = Monitor(config, db, crawler, telegram)
    monitor.run_once()
    telegram.send.assert_not_called()
    crawler.collect.return_value.append(replace(notice, notice_id='new-correction', title='정정 공고'))
    monitor.run_once()
    telegram.send.assert_called_once()


def test_other_regions_and_nationwide_excluded(config, db, crawler, telegram, notice):
    """서울·전국·복합 지역 공고는 저장 및 알림 대상에서 제외한다."""
    db.ingest([])
    crawler.collect.return_value = [replace(notice, notice_id=str(i), region=region)
                                   for i, region in enumerate(['서울특별시', '전국', '경기도,서울특별시'])]
    Monitor(config, db, crawler, telegram).run_once()
    assert db.summary()['notices'] == 0
    telegram.send.assert_not_called()


def test_failed_delivery_retries_and_records_attempts(config, db, crawler, telegram, notice):
    """발송 실패 이력을 보관하고 다음 조회에 재시도한 뒤 중복을 막는다."""
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
    """연결·파싱 실패 시 초기화하지 않고 기존 DB와 성공 시각을 보존한다."""
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
    """정상적인 0건 조회도 최초 초기화를 완료하고 알리지 않는다."""
    assert Monitor(config, db, crawler, telegram).run_once()
    assert db.initialized()
    telegram.send.assert_not_called()


def test_dry_run_preserves_all_state_and_queued_messages(config, db, crawler, telegram, notice):
    """dry-run 성공·실패 모두 DB와 발송 대기 상태를 변경하지 않는다."""
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
    """수집이 연속 실패해도 운영 경고를 과도하게 반복하지 않는다."""
    crawler.collect.side_effect = NetworkError('연결 실패')
    monitor = Monitor(config, db, crawler, telegram)
    for _ in range(8):
        monitor.run_once()
    telegram.send.assert_called_once()
    assert db.state('consecutive_failures') == '8'


def test_queue_retried_even_when_lh_down(config, db, crawler, telegram, notice):
    """LH 조회가 실패해도 기존 미발송 알림은 재시도한다."""
    db.ingest([])
    db.ingest([notice])
    crawler.collect.side_effect = NetworkError('연결 실패')
    assert not Monitor(config, db, crawler, telegram).run_once()
    assert db.summary()['notifications'] == {'sent': 1}


def test_explicit_init_ignores_first_run_notification_setting(config, db, crawler, telegram, notice):
    """명시적 초기화는 항상 무알림이며 기존 DB의 재초기화를 거부한다."""
    crawler.collect.return_value = [notice]
    assert Monitor(replace(config, notify_on_first_run=True), db, crawler, telegram).run_once(init=True)
    assert not db.queued()
    telegram.send.assert_not_called()
    with pytest.raises(ValueError, match='--init 거부'):
        Monitor(config, db, crawler, telegram).run_once(init=True)
