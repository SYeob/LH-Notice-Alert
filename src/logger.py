import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .models import SEOUL
from datetime import datetime


class SeoulFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        return datetime.fromtimestamp(record.created, SEOUL).isoformat(timespec='seconds')


class Redact(logging.Filter):
    def __init__(self, secrets):
        super().__init__()
        self.secrets = [x for x in secrets if x]

    def filter(self, record):
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, '[REDACTED]')
        record.msg, record.args = message, ()
        return True


def setup_logging(root: Path, level='INFO', secrets=()):
    directory = root / 'logs'
    directory.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(), RotatingFileHandler(directory / 'lh_monitor.log',
                 maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')]
    for handler in handlers:
        handler.setFormatter(SeoulFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        handler.addFilter(Redact(secrets))
    logging.basicConfig(level=level, handlers=handlers, force=True)
    # Low-level HTTP debug logs can contain Telegram tokens in URLs.
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('filelock').setLevel(logging.WARNING)
