from pathlib import Path
import logging
from datetime import datetime
from html import escape
from unittest.mock import Mock
import pytest
from config import Config
from src.database import Database
from src.parser import parse_page
from src.models import SEOUL


@pytest.fixture
def html():
    return (Path(__file__).parent / 'fixtures/live_list.html').read_text()


@pytest.fixture
def empty_html():
    return (Path(__file__).parent / 'fixtures/empty.html').read_text()


@pytest.fixture
def notice(html):
    return parse_page(html).notices[0]


@pytest.fixture
def config(tmp_path):
    return Config(db_path=tmp_path / 'state.db', telegram_bot_token='123:secret-test',
                  telegram_chat_id='private-chat', max_retries=3)


@pytest.fixture
def db(config):
    store = Database(config.db_path)
    yield store
    store.close()


@pytest.fixture
def crawler():
    client = Mock()
    client.collect.return_value = []
    return client


@pytest.fixture
def telegram():
    client = Mock()
    client.send.return_value = '42'
    return client


def response(code=200, body=None, text='', headers=None):
    result = Mock(status_code=code, headers=headers or {}, text=text)
    result.json.return_value = body
    return result


# Keep readable test purposes next to each test (docstrings), and expose them
# through pytest-html's official report hooks. No external account is needed.
TEST_GROUPS = {
    'test_cli': '실행 명령', 'test_config': '환경설정', 'test_crawler': 'LH 공고 수집',
    'test_database': 'DB · 중복 방지', 'test_detector': '신규 공고 감지',
    'test_filters': '지역 필터', 'test_http': '네트워크 · 재시도',
    'test_parser': 'HTML 파싱', 'test_scheduler': '오후 6시 예약',
    'test_telegram': 'Telegram 알림',
}
TEST_LOG = logging.getLogger('tests.scenario')


def pytest_runtest_setup(item):
    item.test_started_at = datetime.now(SEOUL).isoformat(timespec='seconds')
    TEST_LOG.info('[시작] %s | %s | %s', item.function.__doc__ or item.name,
                  item.nodeid, item.test_started_at)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    report.description = (item.function.__doc__ or item.name).strip()
    report.test_group = TEST_GROUPS.get(item.module.__name__.split('.')[-1], '기타')
    if report.when == 'call' or report.failed or report.skipped:
        result = {'passed': '성공', 'failed': '실패', 'skipped': '건너뜀'}[report.outcome]
        message = (f'목적: {report.description}\n'
                   f'시작: {getattr(item, "test_started_at", "알 수 없음")} (Asia/Seoul)\n'
                   f'결과: {result} · 단계: {report.when} · 소요 시간: {report.duration:.4f}초\n'
                   f'테스트: {report.nodeid}')
        report.sections.append(('테스트 실행 기록', message))
        TEST_LOG.info('[%s] %s | %s | %.4f초', result, report.description,
                      report.nodeid, report.duration)


def pytest_html_report_title(report):
    report.title = 'LH Notice Alert · 테스트 보고서'


def pytest_html_results_summary(prefix, summary, postfix):
    stamp = datetime.now(SEOUL).strftime('%Y-%m-%d %H:%M:%S')
    prefix.extend([
        '<p class="report-intro">매일 오후 6시 공고 모니터링의 동작과 안전장치를 확인합니다.</p>',
        f'<p class="report-meta">생성 시각 {stamp} · Asia/Seoul · 실제 메시지 발송 없는 오프라인 테스트</p>',
        '<p class="report-guide">결과별 필터로 성공·실패를 선택하세요. '
        '각 행을 클릭하면 테스트 실행 기록, 로그 및 실패 원인을 펼칠 수 있습니다.</p>',
    ])


def pytest_html_results_table_header(cells):
    cells.insert(1, '<th>기능</th>')
    cells.insert(2, '<th>테스트 목적</th>')


def pytest_html_results_table_row(report, cells):
    cells.insert(1, f'<td class="col-group">{escape(getattr(report, "test_group", "수집/실행 오류"))}</td>')
    cells.insert(2, f'<td class="col-description">{escape(getattr(report, "description", "테스트 수집 또는 실행 중 오류가 발생했습니다."))}</td>')
