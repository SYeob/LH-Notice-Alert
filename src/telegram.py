import logging
import time
import requests
from .http import request, FetchError, HTTPError, retry_delay

log = logging.getLogger(__name__)


class TelegramError(RuntimeError):
    pass


def format_notice(notice):
    return ('[LH] 경기도 신규 임대주택 공고\n\n'
            f'공고명: {notice["title"]}\n지역: {notice["region"]}\n'
            f'유형: {notice["rental_type"]}\n게시일: {notice["posted_date"]}\n'
            f'마감일: {notice["deadline"] or "미정"}\n상태: {notice["status"] or "미정"}\n\n'
            f'상세 공고 확인: {notice["detail_url"]}')


class Telegram:
    def __init__(self, config, session=None, sleep=time.sleep):
        self.config = config
        self.session = session or requests.Session()
        self.sleep = sleep

    def close(self):
        self.session.close()

    def send(self, text):
        # Plain text intentionally omits parse_mode: titles cannot inject Markdown/HTML.
        # Retain the detail URL at the end even for an unusually long title.
        if len(text.encode('utf-16-le')) // 2 > 4096:
            head, sep, tail = text.rpartition('\n\n상세 공고 확인: ')
            if not sep:
                raise TelegramError('텔레그램 메시지 길이 초과')
            text = head[:1000] + '…' + sep + tail
            if len(text.encode('utf-16-le')) // 2 > 4096:
                raise TelegramError('텔레그램 메시지 길이 초과')
        url = f'https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage'
        # One retry budget covers HTTP and Telegram's JSON-level errors together.
        for attempt in range(self.config.max_retries + 1):
            try:
                response = request(self.session, 'POST', url, timeout=self.config.request_timeout,
                                   retries=0, json={'chat_id': self.config.telegram_chat_id,
                                                    'text': text, 'link_preview_options': {'is_disabled': True}})
            except FetchError as exc:
                error = str(exc)
                # request() sanitizes exceptions; HTTP 429 is handled below for retry_after.
                delay = retry_delay(exc.retry_after if isinstance(exc, HTTPError) else None, 2 ** attempt)
                if error.startswith('HTTP 4') and error != 'HTTP 429':
                    raise TelegramError(error) from None
            else:
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
                if (isinstance(payload, dict) and payload.get('ok') is True
                        and isinstance(payload.get('result'), dict)
                        and isinstance(payload['result'].get('message_id'), int)
                        and not isinstance(payload['result']['message_id'], bool)):
                    return str(payload['result']['message_id'])
                code = payload.get('error_code') if isinstance(payload, dict) else None
                error = f'Telegram API 실패 (code={code if isinstance(code, int) else "invalid response"})'
                parameters = payload.get('parameters', {}) if isinstance(payload, dict) else {}
                delay = retry_delay(parameters.get('retry_after') if isinstance(parameters, dict) else None, 2 ** attempt)
                if isinstance(code, int) and 400 <= code < 500 and code != 429:
                    raise TelegramError(error)
            if attempt == self.config.max_retries:
                raise TelegramError(error) from None
            log.warning('%s; 텔레그램 재시도 %d/%d, %.1f초 대기', error,
                        attempt + 1, self.config.max_retries, delay)
            self.sleep(delay)
        raise AssertionError('unreachable')
