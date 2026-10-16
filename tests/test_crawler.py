from datetime import date
from unittest.mock import Mock
from bs4 import BeautifulSoup
import pytest
from src.crawler import Crawler
from src.parser import ParseError
from conftest import response


def split_pages(html):
    first = BeautifulSoup(html, 'html.parser')
    second = BeautifulSoup(html, 'html.parser')
    first.select('tbody tr')[1].decompose()
    second.select('tbody tr')[0].decompose()
    second.select_one('form[name="pagingForm"] input[name="currPage"]')['value'] = '2'
    return str(first), str(second)


def test_pagination_preserves_observed_parameters(config, html):
    """검색 범위를 유지하며 2페이지까지 누락 없이 수집한다."""
    first, second = split_pages(html)
    session = Mock()
    session.request.side_effect = [response(text=first), response(text=second)]
    sleep = Mock()
    crawler = Crawler(config, session, sleep)
    notices = crawler.collect(today=date(2026, 10, 16))
    assert len(notices) == 2
    calls = session.request.call_args_list
    assert calls[0].args[0] == 'GET' and calls[1].args[0] == 'POST'
    params = calls[0].kwargs['params']
    assert params['cnpCd'] == '41' and params['panSs'] == ''
    assert params['startDt'] == '2026-07-18' and params['uppAisTpCd'] == '061339'
    assert calls[1].kwargs['data']['currPage'] == '2'
    assert calls[1].kwargs['data']['panStDt'] == '20260718'
    sleep.assert_called_once_with(1)


def test_repeated_page_detected(config, html):
    """다음 페이지 요청에 같은 페이지가 반환되면 실패로 처리한다."""
    first, _ = split_pages(html)
    session = Mock()
    session.request.return_value = response(text=first)
    with pytest.raises(ParseError, match='페이지 번호'):
        Crawler(config, session, Mock()).collect(date(2026, 10, 16))


def test_changing_count_discards_snapshot(config, html):
    """페이지 이동 중 총 공고 수가 바뀌면 불완전한 수집을 거부한다."""
    first, second = split_pages(html)
    session = Mock()
    session.request.side_effect = [response(text=first), response(text=second.replace('<strong>2</strong>', '<strong>3</strong>'))]
    with pytest.raises(ParseError, match='총 건수 변경'):
        Crawler(config, session, Mock()).collect(date(2026, 10, 16))


def test_duplicate_id_across_pages_rejected(config, html):
    """페이지 사이 ID 중복을 감지해 누락 가능성이 있는 결과를 거부한다."""
    first, second = split_pages(html)
    from src.parser import parse_page
    one = parse_page(first).notices[0].notice_id
    two = parse_page(second).notices[0].notice_id
    session = Mock()
    session.request.side_effect = [response(text=first), response(text=second.replace(two, one))]
    with pytest.raises(ParseError, match='중복 ID'):
        Crawler(config, session, Mock()).collect(date(2026, 10, 16))


def test_normal_empty_succeeds(config, empty_html):
    """실제 빈 목록 형태의 응답을 오류 없이 0건으로 수집한다."""
    session = Mock()
    session.request.return_value = response(text=empty_html)
    assert Crawler(config, session).collect(date(2026, 10, 16)) == []


def test_ignored_date_or_status_filter_rejected(config, html):
    """서버가 기간·상태 검색 조건을 적용하지 않으면 결과를 거부한다."""
    session = Mock()
    soup = BeautifulSoup(html, 'html.parser')
    soup.select_one('input[name="panSs"]')['value'] = '공고중'
    session.request.return_value = response(text=str(soup))
    with pytest.raises(ParseError, match='검색 범위'):
        Crawler(config, session).collect(date(2026, 10, 16))
