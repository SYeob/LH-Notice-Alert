"""Bounded retries with safe errors (never include request URLs or response bodies)."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import time
import requests

log = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


class NetworkError(FetchError):
    pass


class HTTPError(FetchError):
    def __init__(self, status, retry_after=None):
        super().__init__(f'HTTP {status}')
        self.status = status
        self.retry_after = retry_after


def retry_delay(value, fallback):
    if value is None:
        return fallback
    try:
        return max(0, float(value))
    except (ValueError, TypeError):
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return fallback


def request(session, method, url, *, timeout=15, retries=3, sleep=time.sleep, **kwargs):
    for attempt in range(retries + 1):
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException:
            error = NetworkError('네트워크 연결 실패/타임아웃')
            delay = 2 ** attempt
        else:
            if 200 <= response.status_code < 300:
                return response
            wait = response.headers.get('Retry-After')
            if response.status_code == 429 and wait is None:
                try:
                    body = response.json()
                    wait = body.get('parameters', {}).get('retry_after')
                except (ValueError, AttributeError, TypeError):
                    pass
            error = HTTPError(response.status_code, wait)
            if response.status_code != 429 and response.status_code < 500:
                raise error
            delay = retry_delay(wait, 2 ** attempt)
        if attempt == retries:
            raise error from None
        log.warning('%s; 재시도 %d/%d, 대기 %.1f초', error, attempt + 1, retries, delay)
        sleep(delay)
    raise AssertionError('unreachable')
