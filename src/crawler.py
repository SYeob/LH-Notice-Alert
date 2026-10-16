from datetime import datetime, timedelta, date
import logging
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl
import requests
from .http import request
from .models import SEOUL
from .parser import parse_page, ParseError

log = logging.getLogger(__name__)


class Crawler:
    def __init__(self, config, session=None, sleep=time.sleep):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': 'LH-Rental-Notice-Monitor/1.0 (personal notice monitoring)'})
        self.sleep = sleep

    def close(self):
        self.session.close()

    def collect(self, today=None):
        today = today or datetime.now(SEOUL).date()
        start = today - timedelta(days=self.config.lookback_days)
        parts = urlsplit(self.config.lh_url)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
        params = dict(parse_qsl(parts.query))
        params.update({'mi': '1026', 'srchY': 'Y', 'srchUppAisTpCd': '061339',
                       'uppAisTpCd': '061339', 'cnpCd': '41' if self.config.target_region == '경기도' else '',
                       'panSs': '', 'schTy': '0', 'startDt': start.isoformat(),
                       'endDt': today.isoformat(), 'listCo': '100', 'currPage': '1'})
        log.info('조회 시작: %s ~ %s', start, today)
        results = {}
        page_no = 1
        total = None
        raw_count = 0
        while True:
            response = request(self.session, 'GET' if page_no == 1 else 'POST', url,
                               timeout=self.config.request_timeout, retries=self.config.max_retries,
                               sleep=self.sleep, **({'params': params} if page_no == 1 else {'data': params}))
            response.encoding = 'utf-8'
            page = parse_page(response.text)
            if page.current != page_no or (total is not None and page.total != total):
                raise ParseError('페이지 번호/총 건수 변경: 불완전 수집을 저장하지 않습니다.')
            if page.total:
                scope = {'mi': '1026', 'uppAisTpCd': '061339', 'panSs': '',
                         'panStDt': start.strftime('%Y%m%d'), 'panEdDt': today.strftime('%Y%m%d'),
                         'cnpCd': '41' if self.config.target_region == '경기도' else ''}
                if any(page.paging.get(key) != value for key, value in scope.items()):
                    raise ParseError('응답의 검색 범위가 요청과 다릅니다 (필터 변경/미적용).')
            total = page.total
            raw_count += len(page.notices)
            if not page.notices and total:
                raise ParseError('중간 페이지가 비어 있습니다.')
            for notice in page.notices:
                if notice.notice_id in results:
                    raise ParseError('페이지 사이 중복 ID: 불완전 수집 가능성')
                results[notice.notice_id] = notice
            if raw_count > total:
                raise ParseError('표시 건수 초과')
            if raw_count == total:
                break
            if page_no >= 1000:
                raise ParseError('페이지 수 안전 한도 초과')
            params = page.paging.copy()
            required = {'currPage', 'cnpCd', 'panStDt', 'panEdDt', 'panSs', 'uppAisTpCd', 'listCo', 'mi'}
            if not required <= params.keys():
                raise ParseError('다음 페이지 조회 필수 파라미터 누락')
            page_no += 1
            params['currPage'] = str(page_no)
            self.sleep(1)
        log.info('전체 조회 수=%d, 페이지=%d', raw_count, page_no)
        return [n for n in results.values() if start <= date.fromisoformat(n.posted_date) <= today]
