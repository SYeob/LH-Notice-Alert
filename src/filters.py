"""Keep exact region matching separate for future nationwide supply analysis."""
from .models import Notice


def normalize_region(value: str) -> str:
    return ' '.join(value.split())


def matches_region(notice: Notice, target: str = '경기도') -> bool:
    return normalize_region(notice.region) == normalize_region(target)
