from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
import pytest
from config import Config
from src.database import Database
from src.parser import parse_page


@pytest.fixture
def html():
    return (Path(__file__).parent / 'fixtures/live_list.html').read_text()


@pytest.fixture
def empty_html():
    return (Path(__file__).parent / 'fixtures/empty.html').read_text()


@pytest.fixture
def notice(html):
    return parse_page(html).notices[0]


@pytest.fixture
def config(tmp_path):
    return Config(db_path=tmp_path / 'state.db', telegram_bot_token='123:secret-test',
                  telegram_chat_id='private-chat', max_retries=3)


@pytest.fixture
def db(config):
    store = Database(config.db_path)
    yield store
    store.close()


@pytest.fixture
def crawler():
    client = Mock()
    client.collect.return_value = []
    return client


@pytest.fixture
def telegram():
    client = Mock()
    client.send.return_value = '42'
    return client


def response(code=200, body=None, text='', headers=None):
    result = Mock(status_code=code, headers=headers or {}, text=text)
    result.json.return_value = body
    return result
