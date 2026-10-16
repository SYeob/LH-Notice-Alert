"""Run once a day at a wall-clock time in Seoul, without a startup query."""
from datetime import datetime, time, timedelta
import logging
import signal
import threading
from .models import SEOUL

log = logging.getLogger(__name__)
STATE_KEY = 'last_daily_run_date'


def next_run_time(current, check_time='18:00', last_run_date=None):
    current = current.astimezone(SEOUL)
    target = datetime.combine(current.date(), time.fromisoformat(check_time), SEOUL)
    if target < current or last_run_date == current.date().isoformat():
        target += timedelta(days=1)
    return target


def run_forever(monitor, check_time='18:00', *, now_fn=None, stop_event=None):
    clock = now_fn or (lambda: datetime.now(SEOUL))
    stop = stop_event if stop_event is not None else threading.Event()
    previous = {}

    def shutdown(signum, frame):
        log.info('종료 신호 수신: %s', signum)
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, shutdown)
    try:
        while not stop.is_set():
            target = next_run_time(clock(), check_time, monitor.db.state(STATE_KEY))
            log.info('다음 정기 조회: %s (Asia/Seoul, 하루 1회)', target.isoformat())
            while not stop.is_set():
                current = clock().astimezone(SEOUL)
                remaining = (target - current).total_seconds()
                if current.date() > target.date():
                    # Skip missed days after suspension; never run several catch-up queries.
                    log.info('잠자기 등으로 지난 조회일 건너뜀: %s', target.date())
                    break
                if remaining > 0:
                    # Recheck wall time regularly for clock changes; shutdown stays immediate.
                    stop.wait(min(remaining, 60))
                    continue
                # Claim before collection: even failure/restart cannot cause a second
                # scheduled query that day. Manual --once remains an explicit override.
                with monitor.db.conn:
                    monitor.db.set_state(STATE_KEY, target.date().isoformat())
                monitor.run_once()
                break
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
