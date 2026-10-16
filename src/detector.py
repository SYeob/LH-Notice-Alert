from datetime import datetime
import logging
from .filters import matches_region
from .models import now
from .telegram import format_notice, TelegramError

log = logging.getLogger(__name__)


class Monitor:
    def __init__(self, config, db, crawler, telegram=None):
        self.config, self.db, self.crawler, self.telegram = config, db, crawler, telegram

    def run_once(self, dry_run=False, init=False):
        if init:
            self.db.assert_can_init()
        successful = True
        try:
            notices = self.crawler.collect()
        except Exception as exc:
            # Known collector failures have sanitized messages. Unknown exceptions are
            # identified by class only to avoid accidentally logging secret-bearing URLs.
            from .http import FetchError
            from .parser import ParseError
            reason = str(exc) if isinstance(exc, (FetchError, ParseError)) else type(exc).__name__
            log.error('수집 실패 [%s]: %s', type(exc).__name__, reason)
            if not dry_run:
                count = self.db.record_failure()
                self.warn(count)
            successful = False
        else:
            selected = [n for n in notices if matches_region(n, self.config.target_region)]
            if dry_run:
                count = len(self.db.new_ids(selected))
                log.info('DRY RUN: 전체=%d 지역 통과=%d DB 미등록=%d 초기화=%s (저장/발송 없음)',
                         len(notices), len(selected), count, self.db.initialized())
                return True
            count, first = self.db.ingest(selected, self.config.notify_on_first_run, init)
            log.info('조회 종료: 전체=%d 지역 통과=%d 신규=%d 최초=%s 마지막 정상 조회=%s',
                     len(notices), len(selected), count, first, self.db.state('last_successful_check'))
        # Previously queued notifications remain retryable even if LH is unavailable.
        if not dry_run and not init and self.telegram:
            successful = self.deliver() and successful
        return successful

    def deliver(self):
        successful = True
        for notice in self.db.queued():
            try:
                message_id = self.telegram.send(format_notice(notice))
            except TelegramError as exc:
                self.db.record_delivery(notice['notice_id'], error=str(exc))
                log.error('발송 실패 ID=%s: %s', notice['notice_id'], exc)
                successful = False
            else:
                # Commit each result immediately to minimize the external API crash window.
                self.db.record_delivery(notice['notice_id'], message_id=message_id)
                log.info('발송 성공 ID=%s message_id=%s', notice['notice_id'], message_id)
        return successful

    def warn(self, count):
        if not self.telegram or count < self.config.warning_threshold:
            return
        stamp = now()
        previous = self.db.state('last_warning_at')
        if previous and (datetime.fromisoformat(stamp) - datetime.fromisoformat(previous)).total_seconds() < self.config.warning_cooldown:
            return
        # Reserve the cooldown before delivery, including when Telegram itself is down.
        with self.db.conn:
            self.db.set_state('last_warning_at', stamp)
        try:
            self.telegram.send(f'[LH] 운영 경고: 공고 수집 연속 {count}회 실패. '
                               f'마지막 정상 조회: {self.db.state("last_successful_check", "없음")}. 로그를 확인하세요.')
        except TelegramError:
            log.error('운영 경고 발송 실패 (재알림 대기시간 적용)')
