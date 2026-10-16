"""Parse the observed LH server-rendered table; fail closed on structural drift."""
from dataclasses import dataclass
from datetime import date
import re
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from .models import Notice


class ParseError(ValueError):
    pass


@dataclass
class Page:
    notices: list[Notice]
    total: int
    current: int
    paging: dict[str, str]


def clean_date(value: str, required: bool = False) -> str | None:
    value = value.strip()
    if not value or value in {'-', '미정'}:
        if required:
            raise ParseError('필수 게시일 누락')
        return None
    try:
        return date.fromisoformat(value.replace('.', '-')).isoformat()
    except ValueError:
        raise ParseError('날짜 형식 변경') from None


def parse_page(html: str) -> Page:
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('.bbs_ListA table')
    total_node = soup.select_one('.bbs_total strong')
    form = soup.select_one('form[name="pagingForm"]')
    if table is None or total_node is None:
        raise ParseError('목록 테이블/건수 누락 (오류·접근제한 또는 구조 변경)')
    headers = [x.get_text(strip=True) for x in table.select('thead th')]
    if headers != ['번호', '유형', '공고명', '지역', '첨부', '게시일', '마감일', '상태', '조회수']:
        raise ParseError('목록 열 구조 변경')
    try:
        total = int(total_node.get_text(strip=True).replace(',', ''))
        if total > 0 and form is None:
            raise ParseError('페이지 폼 누락')
        paging = {x['name']: x.get('value', '') for x in form.select('input[name]')} if form else {}
        current = int(paging.get('currPage', '1'))
        if total < 0 or current < 1:
            raise ValueError
    except (ValueError, KeyError):
        raise ParseError('페이지 메타데이터 오류') from None
    body = table.find('tbody')
    if body is None:
        raise ParseError('목록 tbody 누락')
    rows = body.find_all('tr', recursive=False)
    if total == 0:
        if (len(rows) != 1 or rows[0].select_one('.wrtancInfoBtn')
                or '없습니다' not in rows[0].get_text() or not rows[0].select_one('td[colspan]')):
            raise ParseError('0건 표시와 빈 목록 구조 불일치')
        return Page([], total, current, paging)
    if not rows:
        raise ParseError('양수 건수에 빈 목록')
    notices = []
    for row in rows:
        cells = row.find_all('td', recursive=False)
        if len(cells) != len(headers):
            raise ParseError('공고 행 필수 열 누락')
        link = cells[2].select_one('a.wrtancInfoBtn')
        if link is None:
            raise ParseError('상세 링크 누락')
        keys = [link.get(f'data-id{i}', '').strip() for i in range(1, 5)]
        if any(not re.fullmatch(r'\d+', x) for x in keys):
            raise ParseError('상세 URL에 필요한 공고 식별자 누락/변경')
        pan_id, system, upper, subtype = keys
        if upper not in {'06', '13', '39'} or (upper == '39' and subtype == '39'):
            raise ParseError('임대주택 범위 밖 유형이 응답에 포함됨')
        for badge in link.select('em.day, em.new, .hid'):
            badge.decompose()
        title = ' '.join(link.stripped_strings)
        rental_type = cells[1].get_text(' ', strip=True)
        region = cells[3].get_text(' ', strip=True)
        if not all((title, rental_type, region)):
            raise ParseError('공고명/유형/지역 누락')
        url = 'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?' + urlencode({
            'mi': '1026', 'panId': pan_id, 'ccrCnntSysDsCd': system,
            'uppAisTpCd': upper, 'aisTpCd': subtype,
        })
        notices.append(Notice(pan_id, title, region, rental_type,
                              clean_date(cells[5].get_text(strip=True), required=True),
                              clean_date(cells[6].get_text(strip=True)),
                              cells[7].get_text(' ', strip=True) or None, url))
    return Page(notices, total, current, paging)
