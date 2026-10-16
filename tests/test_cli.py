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
    """상태 확인과 dry-run 명령은 운영 DB 파일을 생성하지 않는다."""
    assert main(['--status']) == 0
    monkeypatch.setattr('src.crawler.Crawler.collect', lambda self: [notice])
    assert main(['--dry-run']) == 0
    assert not config.db_path.exists()


def test_init_preserves_existing_db(config, notice, monkeypatch):
    """CLI 최초 초기화 후 재초기화를 거부하고 DB 내용을 보존한다."""
    monkeypatch.setattr('src.crawler.Crawler.collect', lambda self: [notice])
    assert main(['--init']) == 0
    before = config.db_path.read_bytes()
    assert main(['--init']) == 2
    assert config.db_path.read_bytes() == before


def test_missing_telegram_fails_before_db(config, monkeypatch):
    """인증정보가 없으면 DB를 만들기 전에 명확히 종료한다."""
    monkeypatch.setattr(Config, 'load', lambda: replace(config, telegram_bot_token=''))
    assert main(['--once']) == 2
    assert not config.db_path.exists()


def test_test_telegram_mode(config, monkeypatch):
    """시험 발송 CLI가 테스트 메시지를 한 번 전송한다(mock 검증)."""
    send = Mock(return_value='22')
    monkeypatch.setattr('src.telegram.Telegram.send', send)
    assert main(['--test-telegram']) == 0
    send.assert_called_once()


def test_secret_log_redaction():
    """로그에서 비밀값을 가리고 시각에 한국 시간대 표기를 넣는다."""
    record = logging.LogRecord('test', 20, 'x', 1, 'failure token=%s', ('private-token',), None)
    assert Redact(['private-token']).filter(record)
    assert 'private-token' not in record.getMessage()
    assert '+09:00' in SeoulFormatter().formatTime(record)
