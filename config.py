"""Validated settings; paths are always relative to the project, not the caller."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from datetime import time
import re
from urllib.parse import urlsplit, parse_qs
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DEFAULT_URL = 'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1026'


@dataclass(frozen=True)
class Config:
    lh_url: str = DEFAULT_URL
    target_region: str = '경기도'
    daily_check_time: str = '18:00'
    lookback_days: int = 90
    telegram_bot_token: str = field(default='', repr=False)
    telegram_chat_id: str = field(default='', repr=False)
    db_path: Path = ROOT / 'data/lh_notices.db'
    log_level: str = 'INFO'
    request_timeout: int = 15
    max_retries: int = 3
    notify_on_first_run: bool = False
    warning_threshold: int = 3
    warning_cooldown: int = 3600

    @classmethod
    def load(cls):
        load_dotenv(ROOT / '.env', override=False)
        values = {}
        for name in ('lookback_days', 'request_timeout', 'max_retries',
                     'warning_threshold', 'warning_cooldown'):
            raw = os.getenv(name.upper(), str(getattr(cls, name)))
            try:
                value = int(raw)
            except ValueError:
                raise ValueError(f'{name.upper()}는 정수여야 합니다.') from None
            if value < (0 if name == 'max_retries' else 1):
                raise ValueError(f'{name.upper()} 값이 유효하지 않습니다.')
            values[name] = value
        schedule = os.getenv('DAILY_CHECK_TIME', '18:00').strip()
        if not re.fullmatch(r'\d{2}:\d{2}', schedule):
            raise ValueError('DAILY_CHECK_TIME은 HH:MM 형식이어야 합니다.')
        try:
            time.fromisoformat(schedule)
        except ValueError:
            raise ValueError('DAILY_CHECK_TIME에 유효한 시간을 설정하세요.') from None
        values['daily_check_time'] = schedule
        for name in ('lh_url', 'target_region', 'telegram_bot_token', 'telegram_chat_id', 'log_level'):
            values[name] = os.getenv(name.upper(), getattr(cls, name)).strip()
        url = urlsplit(values['lh_url'])
        if (url.scheme != 'https' or url.netloc != 'apply.lh.or.kr'
                or url.path != '/lhapply/apply/wt/wrtanc/selectWrtancList.do'
                or parse_qs(url.query).get('mi') != ['1026']):
            raise ValueError('LH_URL은 공식 LH 임대주택 목록(mi=1026)의 HTTPS URL이어야 합니다.')
        if not values['target_region']:
            raise ValueError('TARGET_REGION이 비어 있습니다.')
        values['log_level'] = values['log_level'].upper()
        if values['log_level'] not in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
            raise ValueError('LOG_LEVEL이 유효하지 않습니다.')
        first = os.getenv('NOTIFY_ON_FIRST_RUN', 'false').lower().strip()
        if first not in {'true', 'false'}:
            raise ValueError('NOTIFY_ON_FIRST_RUN은 true 또는 false여야 합니다.')
        values['notify_on_first_run'] = first == 'true'
        path = os.getenv('DB_PATH', 'data/lh_notices.db').strip()
        if not path:
            raise ValueError('DB_PATH가 비어 있습니다.')
        values['db_path'] = (ROOT / Path(path).expanduser()).resolve()
        return cls(**values)

    def require_telegram(self):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            raise ValueError('TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID를 .env에 설정하세요. '
                             '인증정보 없이 확인하려면 --dry-run 또는 --init을 사용하세요.')
