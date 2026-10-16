from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import pytest
from src.models import SEOUL
from src.scheduler import next_run_time, run_forever, STATE_KEY


def seoul(day, hour=18, minute=0, second=0):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=SEOUL)


@pytest.mark.parametrize('current,last,expected', [
    (seoul(16, 9), None, seoul(16)),
    (seoul(16), None, seoul(16)),
    (seoul(16, 18, 0, 1), None, seoul(17)),
    (seoul(16), '2026-10-16', seoul(17)),
    (seoul(16, 9), '2026-10-16', seoul(17)),
    (datetime(2026, 10, 16, 8, tzinfo=timezone.utc), None, seoul(16)),
])
def test_next_seoul_6pm(current, last, expected):
    """정시 전후·당일 실행 여부·UTC 입력에 맞는 다음 한국 시간 18시를 계산한다."""
    assert next_run_time(current, last_run_date=last) == expected


class FakeEvent:
    def __init__(self, clock, on_wait=None):
        self.clock = clock
        self.stopped = False
        self.waits = []
        self.on_wait = on_wait

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, seconds):
        self.waits.append(seconds)
        if self.on_wait:
            self.on_wait(self, seconds)
        else:
            self.clock[0] += timedelta(seconds=seconds)


@pytest.fixture(autouse=True)
def signals(monkeypatch):
    monkeypatch.setattr('src.scheduler.signal.signal', Mock())


def test_waits_until_6pm_without_startup_query_and_claims_date(db):
    """시작 직후 조회하지 않고 18시까지 기다린 뒤 당일 실행을 먼저 기록한다."""
    clock = [seoul(16, 17, 59, 30)]
    event = FakeEvent(clock)
    monitor = Mock(db=db)

    def collect():
        assert clock[0] == seoul(16)
        assert db.state(STATE_KEY) == '2026-10-16'
        event.set()

    monitor.run_once.side_effect = collect
    run_forever(monitor, now_fn=lambda: clock[0], stop_event=event)
    monitor.run_once.assert_called_once()
    assert event.waits == [30]


def test_restart_after_6pm_waits_until_tomorrow(db):
    """오후 6시 이후 시작하면 즉시 조회하지 않고 다음 날까지 기다린다."""
    clock = [seoul(16, 19)]
    event = FakeEvent(clock, lambda stop, seconds: stop.set())
    monitor = Mock(db=db)
    run_forever(monitor, now_fn=lambda: clock[0], stop_event=event)
    monitor.run_once.assert_not_called()
    assert event.waits == [60]


def test_failure_is_not_rescheduled_same_day(db):
    """정기 조회가 실패해도 같은 날 자동으로 다시 조회하지 않는다."""
    clock = [seoul(16)]
    event = FakeEvent(clock, lambda stop, seconds: stop.set())
    monitor = Mock(db=db)
    monitor.run_once.return_value = False
    run_forever(monitor, now_fn=lambda: clock[0], stop_event=event)
    monitor.run_once.assert_called_once()
    assert db.state(STATE_KEY) == '2026-10-16'
    assert event.waits == [60]


def test_sleep_past_midnight_skips_old_day(db):
    """잠자기 중 날짜가 지나면 지난 날짜를 몰아서 조회하지 않는다."""
    clock = [seoul(16, 17, 59)]

    def wake(stop, seconds):
        if len(stop.waits) == 1:
            clock[0] = seoul(17, 9)
        else:
            stop.set()

    event = FakeEvent(clock, wake)
    monitor = Mock(db=db)
    run_forever(monitor, now_fn=lambda: clock[0], stop_event=event)
    monitor.run_once.assert_not_called()
    assert db.state(STATE_KEY) is None


def test_delayed_same_day_wakeup_runs_once(db):
    """같은 날 늦게 깨어나면 그날의 정기 조회를 한 번 수행한다."""
    clock = [seoul(16, 17, 59)]
    event = FakeEvent(clock, lambda stop, seconds: clock.__setitem__(0, seoul(16, 19)))
    monitor = Mock(db=db)
    monitor.run_once.side_effect = event.set
    run_forever(monitor, now_fn=lambda: clock[0], stop_event=event)
    monitor.run_once.assert_called_once()
