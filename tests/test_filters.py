from dataclasses import replace
import pytest
from src.filters import matches_region


@pytest.mark.parametrize('region,expected', [('경기도', True), ('  경기도\n', True),
    ('서울특별시', False), ('인천광역시', False), ('전국', False), ('경기도, 서울특별시', False)])
def test_region_requires_exact_field(notice, region, expected):
    """지역 필드가 경기도와 정확히 일치할 때만 대상에 포함한다."""
    assert matches_region(replace(notice, title='경기도 임대 공고', region=region)) is expected
