from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo('Asia/Seoul')


def now():
    return datetime.now(SEOUL).isoformat(timespec='seconds')


@dataclass(frozen=True)
class Notice:
    notice_id: str
    title: str
    region: str
    rental_type: str
    posted_date: str
    deadline: str | None
    status: str | None
    detail_url: str
