from urllib.parse import parse_qs, urlsplit
import pytest
from bs4 import BeautifulSoup
from src.parser import parse_page, ParseError


def test_observed_fields_and_detail_link(html):
    """실제 HTML에서 공고 필드와 정확한 상세 링크를 추출한다."""
    page = parse_page(html)
    n = page.notices[0]
    assert page.total == 2 and len(page.notices) == 2
    assert n.notice_id == '2015122300020859'
    assert n.region == '경기도' and n.rental_type == '행복주택(신혼희망)'
    assert n.posted_date == '2026-10-01' and n.deadline == '2026-10-14'
    assert '1일전' not in n.title
    assert parse_qs(urlsplit(n.detail_url).query) == {
        'mi': ['1026'], 'panId': [n.notice_id], 'ccrCnntSysDsCd': ['03'],
        'uppAisTpCd': ['39'], 'aisTpCd': ['42']}


def test_real_empty_without_paging_form(empty_html):
    """페이지 폼이 없는 정상 0건 응답을 성공으로 처리한다."""
    assert parse_page(empty_html).notices == []


@pytest.mark.parametrize('selector', ['.bbs_ListA', '.bbs_total', 'thead', 'tbody',
                                      'form[name="pagingForm"]', '.wrtancInfoBtn'])
def test_structural_changes_fail(html, selector):
    """목록의 필수 HTML 구조가 사라지면 파싱 실패로 처리한다."""
    soup = BeautifulSoup(html, 'html.parser')
    soup.select_one(selector).decompose()
    with pytest.raises(ParseError):
        parse_page(str(soup))


@pytest.mark.parametrize('attribute', ['data-id1', 'data-id2', 'data-id3', 'data-id4'])
def test_missing_detail_keys_fail(html, attribute):
    """상세 링크용 식별자가 없으면 잘못된 URL을 만들지 않는다."""
    soup = BeautifulSoup(html, 'html.parser')
    del soup.select_one('.wrtancInfoBtn')[attribute]
    with pytest.raises(ParseError):
        parse_page(str(soup))


def test_empty_claim_with_records_rejected(html):
    """0건 표시와 실제 공고 행이 모순되면 오류로 처리한다."""
    with pytest.raises(ParseError):
        parse_page(html.replace('<strong>2</strong>', '<strong>0</strong>'))


def test_empty_table_without_explicit_marker_rejected(empty_html):
    """오류 문구를 정상적인 빈 목록으로 오인하지 않는다."""
    with pytest.raises(ParseError):
        parse_page(empty_html.replace('검색하신 결과가 없습니다.', '시스템 오류'))


def test_non_rental_type_rejected(html):
    """임대주택 범위 밖의 공고 유형을 거부한다."""
    with pytest.raises(ParseError):
        parse_page(html.replace('data-id3="39"', 'data-id3="05"'))


def test_bad_required_date_rejected(html):
    """게시일이 잘못된 형식이면 수집 실패로 처리한다."""
    with pytest.raises(ParseError):
        parse_page(html.replace('2026.10.01</td>', '잘못된 날짜</td>'))
