from dataclasses import asdict
from unittest.mock import Mock
import requests
import pytest
from src.telegram import Telegram, TelegramError, format_notice
from conftest import response


def client(config, *replies):
    session = Mock()
    session.request.side_effect = replies
    sleep = Mock()
    return Telegram(config, session, sleep), session, sleep


def test_plain_text_safe_special_characters(config, notice):
    """공고 제목의 특수문자를 평문으로 안전하게 보내고 상세 링크를 유지한다."""
    text = format_notice({**asdict(notice), 'title': '<b>&_*[] 공고'})
    api, session, _ = client(config, response(body={'ok': True, 'result': {'message_id': 5}}))
    assert api.send(text) == '5'
    payload = session.request.call_args.kwargs['json']
    assert 'parse_mode' not in payload
    assert '<b>&_*[]' in payload['text'] and notice.detail_url in payload['text']


@pytest.mark.parametrize('header', [True, False])
def test_429_uses_header_or_telegram_retry_after(config, header):
    """HTTP 429에서 헤더 또는 Telegram 응답의 지정 대기시간을 따른다."""
    api, session, sleep = client(config,
        response(429, body={'ok': False, 'parameters': {'retry_after': 9}},
                 headers={'Retry-After': '7'} if header else {}),
        response(body={'ok': True, 'result': {'message_id': 1}}))
    assert api.send('test') == '1'
    sleep.assert_called_once_with(7 if header else 9)


def test_json_level_429(config):
    """HTTP 성공이어도 Telegram 본문이 429이면 지정 시간 후 재시도한다."""
    api, _, sleep = client(config,
        response(body={'ok': False, 'error_code': 429, 'parameters': {'retry_after': 4}}),
        response(body={'ok': True, 'result': {'message_id': 1}}))
    api.send('test')
    sleep.assert_called_once_with(4)


@pytest.mark.parametrize('reply', [response(500), response(body={'ok': False, 'error_code': 500}),
                                   response(body={'ok': True, 'result': {}})])
def test_bounded_retries(config, reply):
    """서버 오류·잘못된 성공 응답을 제한된 횟수만큼 지수 백오프로 재시도한다."""
    api, session, sleep = client(config, reply, reply, reply, reply)
    with pytest.raises(TelegramError):
        api.send('test')
    assert session.request.call_count == 4
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4]


def test_permanent_error_does_not_retry(config):
    """Telegram 인증 오류는 불필요하게 재시도하지 않는다."""
    api, session, sleep = client(config, response(401))
    with pytest.raises(TelegramError, match='401'):
        api.send('test')
    assert session.request.call_count == 1
    sleep.assert_not_called()


def test_network_exception_never_leaks_token(config):
    """네트워크 오류 메시지에 봇 토큰과 Chat ID를 노출하지 않는다."""
    api, _, _ = client(config, *[requests.ConnectionError('https://api.telegram.org/bot123:secret-test/private-chat')] * 4)
    with pytest.raises(TelegramError) as error:
        api.send('test')
    assert 'secret-test' not in str(error.value)
    assert 'private-chat' not in str(error.value)
