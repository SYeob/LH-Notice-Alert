import os
import pytest
from config import Config, ROOT


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setattr('config.load_dotenv', lambda *a, **k: None)
    for name in Config.__dataclass_fields__:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.mark.parametrize('name,value', [('DAILY_CHECK_TIME', '24:00'), ('DAILY_CHECK_TIME', '18:60'),
    ('DAILY_CHECK_TIME', '6pm'), ('DAILY_CHECK_TIME', '18:00:00'), ('LOOKBACK_DAYS', '-1'),
    ('MAX_RETRIES', '-1'), ('REQUEST_TIMEOUT', 'abc'), ('NOTIFY_ON_FIRST_RUN', 'maybe'),
    ('TARGET_REGION', ''), ('LOG_LEVEL', 'verbose'), ('DB_PATH', ''),
    ('LH_URL', 'https://example.org/?mi=1026')])
def test_invalid_settings_fail(monkeypatch, name, value):
    """잘못된 시간·환경변수 값을 시작 단계에서 거부한다."""
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        Config.load()


def test_relative_paths_independent_of_cwd(monkeypatch, tmp_path):
    """실행 위치와 관계없이 상대 DB 경로를 프로젝트 루트에서 해석한다."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('DB_PATH', 'data/example.db')
    assert Config.load().db_path == ROOT / 'data/example.db'


def test_default_and_secret_repr(monkeypatch):
    """기본 오후 6시·90일·최초 무알림 설정과 토큰 비노출을 확인한다."""
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'do-not-show')
    cfg = Config.load()
    assert cfg.daily_check_time == '18:00' and cfg.lookback_days == 90
    assert not cfg.notify_on_first_run
    assert 'do-not-show' not in repr(cfg)
