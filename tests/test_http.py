from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from unittest.mock import Mock
import requests
import pytest
from src.http import request, HTTPError, NetworkError, retry_delay
from conftest import response


def test_network_retries_exponential():
    """연결 타임아웃을 최대 3회 추가 재시도하고 1·2·4초 대기한다."""
    session, sleep = Mock(), Mock()
    session.request.side_effect = [requests.Timeout('secret URL')] * 4
    with pytest.raises(NetworkError, match='ネットワーク|네트워크'):
        request(session, 'GET', 'https://example.org', retries=3, sleep=sleep)
    assert [x.args[0] for x in sleep.call_args_list] == [1, 2, 4]


def test_retry_after_prioritized():
    """HTTP 429의 Retry-After를 기본 백오프보다 우선한다."""
    session, sleep = Mock(), Mock()
    session.request.side_effect = [response(429, headers={'Retry-After': '8'}), response()]
    assert request(session, 'GET', 'https://example.org', sleep=sleep).status_code == 200
    sleep.assert_called_once_with(8)


def test_retry_after_http_date():
    """Retry-After의 HTTP 날짜를 해석하고 잘못된 값은 기본값을 쓴다."""
    future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=20))
    assert 18 <= retry_delay(future, 1) <= 20
    assert retry_delay('invalid', 4) == 4


def test_http403_no_retry():
    """접근 금지 응답은 재시도하지 않는다."""
    session, sleep = Mock(), Mock()
    session.request.return_value = response(403)
    with pytest.raises(HTTPError, match='403'):
        request(session, 'GET', 'https://example.org', sleep=sleep)
    sleep.assert_not_called()
