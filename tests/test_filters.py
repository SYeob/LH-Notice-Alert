from dataclasses import replace
import pytest
from src.filters import matches_region


@pytest.mark.parametrize('region,expected', [('경기도', True), ('  경기도\n', True),
    ('서울특별시', False), ('인천광역시', False), ('전국', False), ('경기도, 서울특별시', False)])
def test_region_requires_exact_field(notice, region, expected):
    assert matches_region(replace(notice, title='경기도 임대 공고', region=region)) is expected
