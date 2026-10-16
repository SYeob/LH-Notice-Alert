from dataclasses import replace
import logging
from unittest.mock import Mock
import pytest
from config import Config, ROOT
from main import main
from src.database import Database
from src.logger import Redact, SeoulFormatter


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, config):
    monkeypatch.setattr(Config, 'load', lambda: config)
    monkeypatch.setattr('src.logger.setup_logging', Mock())


def test_status_and_dry_run_do_not_create_db(config, notice, monkeypatch):
    assert main(['--status']) == 0
    monkeypatch.setattr('src.crawler.Crawler.collect', lambda self: [notice])
    assert main(['--dry-run']) == 0
    assert not config.db_path.exists()


def test_init_preserves_existing_db(config, notice, monkeypatch):
    monkeypatch.setattr('src.crawler.Crawler.collect', lambda self: [notice])
    assert main(['--init']) == 0
    before = config.db_path.read_bytes()
    assert main(['--init']) == 2
    assert config.db_path.read_bytes() == before


def test_missing_telegram_fails_before_db(config, monkeypatch):
    monkeypatch.setattr(Config, 'load', lambda: replace(config, telegram_bot_token=''))
    assert main(['--once']) == 2
    assert not config.db_path.exists()


def test_test_telegram_mode(config, monkeypatch):
    send = Mock(return_value='22')
    monkeypatch.setattr('src.telegram.Telegram.send', send)
    assert main(['--test-telegram']) == 0
    send.assert_called_once()


def test_secret_log_redaction():
    record = logging.LogRecord('test', 20, 'x', 1, 'failure token=%s', ('private-token',), None)
    assert Redact(['private-token']).filter(record)
    assert 'private-token' not in record.getMessage()
    assert '+09:00' in SeoulFormatter().formatTime(record)
