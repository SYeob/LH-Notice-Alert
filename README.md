# LH Notice Alert

경기도 LH 임대주택 신규 공고를 Telegram으로 알려주는 Python 프로그램입니다.

Python 3.11+로 LH 청약플러스 공개 임대주택 목록을 **매일 한국 시간 오후 6시(18:00)에 한 번** 조회합니다. 지역 필드가 정확히 `경기도`인 신규 ID만 Telegram으로 알립니다. SQLite에 최초 감지·마지막 조회·발송 결과를 보관합니다.

기본 첫 성공 조회는 기존 공고를 저장하며 **알리지 않습니다**. 조회 실패로 초기화되지는 않습니다. 상시 실행은 설치 후 직접 시작해야 하며, 이 프로젝트는 계정 생성이나 운영체제 자동 실행 등록을 대신하지 않습니다.

## 설치

macOS / Linux:

```sh
git clone https://github.com/SYeob/LH-Notice-Alert.git
cd LH-Notice-Alert
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Python 3.12 이상도 사용할 수 있습니다. 시스템의 `python3`가 3.9 등 구버전이면 Python 3.11+를 먼저 설치하세요. 운영 환경에 테스트가 필요 없다면 `requirements.txt`만 설치합니다.

Windows PowerShell:

```powershell
git clone https://github.com/SYeob/LH-Notice-Alert.git
cd LH-Notice-Alert
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

이하 `python` 명령은 위 가상환경의 Python을 가리킵니다. Windows에서는 `python` 대신 `.\.venv\Scripts\python.exe`를 사용해도 됩니다. `tzdata`가 Windows에서도 `Asia/Seoul`을 지원합니다.

## Telegram 설정

1. Telegram 공식 [@BotFather](https://t.me/BotFather)에서 `/newbot`을 보내 봇을 만들고 발급 토큰을 `.env`의 `TELEGRAM_BOT_TOKEN`에 저장합니다.
2. 생성한 봇과 개인 대화를 열어 `/start`와 메시지를 보냅니다. 그룹 수신이라면 봇을 그룹에 추가하고 봇에게 명령을 보냅니다.
3. [공식 getUpdates 문서](https://core.telegram.org/bots/api#getupdates)에 따라 응답의 `result[].message.chat.id`를 확인해 `TELEGRAM_CHAT_ID`에 저장합니다. 그룹 ID는 음수일 수 있습니다. 기존 webhook을 사용하는 봇에서는 getUpdates가 동작하지 않으므로 별도 봇을 권장합니다.

토큰이 브라우저 기록이나 셸 명령 인수에 남지 않도록, 프로젝트 루트에서 다음 코드를 실행할 수 있습니다. 토큰은 화면에 출력하지 않습니다.

```sh
python - <<'PY'
import os
import requests
from dotenv import load_dotenv
load_dotenv('.env')
r = requests.get('https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN'] + '/getUpdates', timeout=15)
try:
    body = r.json()
    if r.status_code == 200 and body.get('ok'):
        for item in body.get('result', []):
            message = item.get('message', {})
            if 'chat' in message:
                print('Chat ID:', message['chat']['id'])
    else:
        print('응답 실패. 토큰/webhook 설정을 확인하세요.')
except ValueError:
    print('JSON 응답이 아닙니다.')
PY
```

Windows에서는 이 Python 코드를 임시 `.py` 파일로 저장해 실행할 수 있습니다. 토큰은 커밋하거나 공유하지 마세요. `.env`와 DB·로그는 `.gitignore`에 포함되어 있습니다.

## 환경변수

프로젝트 루트의 `.env`를 읽습니다. 이미 설정된 프로세스 환경변수가 우선하며 상대 경로는 실행 위치와 무관하게 프로젝트 루트에서 해석합니다.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `LH_URL` | `.env.example`의 공식 URL | HTTPS LH 임대주택 목록 `mi=1026`만 허용 |
| `TARGET_REGION` | `경기도` | 공백 정리 후 지역 필드와 정확히 일치 |
| `DAILY_CHECK_TIME` | `18:00` | 매일 조회할 한국 시간, `HH:MM` 형식 |
| `LOOKBACK_DAYS` | `90` | 서울 시간 기준 오늘에서 N일 전까지, 양 끝 포함 |
| `TELEGRAM_BOT_TOKEN` | 빈 값 | 정상 실행·`--once`·시험 발송에 필수 |
| `TELEGRAM_CHAT_ID` | 빈 값 | 수신 개인/그룹/채널 ID |
| `DB_PATH` | `data/lh_notices.db` | SQLite 파일, 절대 경로도 가능 |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `REQUEST_TIMEOUT` | `15` | 요청별 연결·읽기 타임아웃(초) |
| `MAX_RETRIES` | `3` | 최초 시도 이후 추가 재시도 수(총 4번) |
| `NOTIFY_ON_FIRST_RUN` | `false` | true면 자동 최초 조회에도 발송. 기본 무알림 권장 |
| `WARNING_THRESHOLD` | `3` | 연속 수집 실패 운영 경고 시작 횟수 |
| `WARNING_COOLDOWN` | `3600` | 운영 경고 간 최소 간격(초) |

`MAX_RETRIES`는 0 이상, 나머지 숫자는 양의 정수입니다. 잘못된 설정은 시작 시 오류로 종료합니다. `TARGET_REGION`을 바꾸면 DB도 별도 경로로 분리하는 것을 권장합니다. 알림 제목은 이 버전의 경기도 전용 형식을 사용합니다.

## 첫 실행과 일상 사용

```sh
python main.py --dry-run        # 인증정보 없이 실제 조회·비교만 1회
python main.py --test-telegram  # 봇 연결 시험: 설정된 수신자에게 실제 메시지 전송
python main.py --init           # 현재 공고를 무알림으로 초기 저장
python main.py --status         # 상태 조회
python main.py                 # 매일 한국 시간 18:00까지 대기 후 1회 조회, Ctrl+C로 종료
```

일반 실행은 시작 직후 조회하지 않고 다음 18:00까지 기다립니다. 18:00이 지난 뒤 시작하면 다음 날부터 조회합니다. 기존 `CHECK_INTERVAL` 설정은 사용하지 않습니다. `.env`에는 `DAILY_CHECK_TIME=18:00`을 설정하세요.

하루의 정기 조회 시작 여부를 DB에 저장하므로 실패하거나 재시작해도 그날 자동으로 두 번 조회하지 않습니다. 수집·발송 주기 내부의 HTTP 재시도는 유지하며, 실패한 공고의 다음 정기 재시도는 다음 날 18:00입니다. `--once`·`--init`·`--dry-run` 같은 수동 명령은 실행 즉시 동작합니다.

`--init`은 선택 사항입니다. 실행하지 않아도 첫 성공 조회에서 자동 초기화됩니다. 이미 초기화되었거나 공고가 있는 DB에 `--init`을 실행하면 거부하며 데이터를 지우지 않습니다. `NOTIFY_ON_FIRST_RUN=true`여도 명시적 `--init`은 무알림입니다.

```sh
python main.py --once           # 1회 조회하고 새 공고 및 실패 이력을 발송/재시도
```

CLI 모드는 서로 함께 사용할 수 없습니다. `--dry-run`은 항상 1회 실행하며 공고·발송 이력·앱 상태를 변경하지 않습니다. DB가 없으면 메모리에서 비교하며 DB 파일을 생성하지 않습니다. 로그와 중복 실행 방지용 잠금 파일은 생성될 수 있습니다. `--status`도 DB를 읽기 전용으로 열며 없는 DB를 생성하지 않습니다.

정상 실행은 인증정보를 시작 전에 검사합니다. 인증정보가 없는 수집 검증은 `--dry-run` 또는 `--init`으로 가능합니다. 인증정보 부재 상태에서 공고가 발송 완료로 기록되는 일은 없습니다.

종료 코드: `0` 성공, `1` 수집·발송·실행 실패, `2` 설정 오류/중복 실행/초기화 거부, `130` 키보드 중단. 상시 실행은 일시적 수집·발송 실패를 기록하고 다음 주기에 다시 시도합니다. DB 오류 등 지속 가능성을 보장할 수 없는 오류는 종료합니다.

## macOS / VS Code에서 계속 실행하기

VS Code 터미널을 열어둔 상태로 사용하려면 프로젝트 폴더에서 실행합니다. `caffeinate -i`는 프로그램 실행 중 자동 잠자기를 막습니다.

```sh
caffeinate -i .venv/bin/python main.py
```

`run` 같은 추가 인수는 필요하지 않습니다. `Ctrl+C`로 종료합니다. 터미널을 닫아도 유지하려면:

```sh
nohup caffeinate -i .venv/bin/python main.py > logs/background.log 2>&1 < /dev/null &
echo $! > data/lh_monitor.pid
```

```sh
# 실행 상태 및 로그 확인
ps -p "$(cat data/lh_monitor.pid)" -o pid,command
tail -f logs/lh_monitor.log
```

`tail` 화면의 `Ctrl+C`는 로그 보기만 종료합니다. 모니터를 중지하려면 위 상태 확인으로 해당 PID가 모니터 프로세스인지 확인한 뒤 `kill "$(cat data/lh_monitor.pid)"`를 실행합니다. 이미 실행 중이면 먼저 중지하고 새로 실행하세요.

Mac 재부팅 후에는 다시 시작해야 합니다. `caffeinate -i`는 덮개를 닫거나 사용자가 직접 잠자기를 선택하는 동작까지 막지는 않습니다. 자동 시작이 필요하면 아래 launchd 예시를 사용합니다. `logs/background.log`는 셸 출력을 받는 일반 파일이고, 앱의 회전 로그는 `logs/lh_monitor.log`입니다.

## macOS launchd 예시

다음 내용을 `~/Library/LaunchAgents/kr.local.lh-rental-monitor.plist`로 저장합니다. `/Users/you/coding/LH_rental_notice`를 실제 **절대 경로**로 모두 바꿉니다. 먼저 수동 실행으로 설정과 시험 메시지를 확인하세요.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>kr.local.lh-rental-monitor</string>
  <key>ProgramArguments</key><array>
    <string>/Users/you/coding/LH_rental_notice/.venv/bin/python</string>
    <string>/Users/you/coding/LH_rental_notice/main.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/you/coding/LH_rental_notice</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>60</integer>
</dict></plist>
```

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/kr.local.lh-rental-monitor.plist
# 중단 및 등록 해제
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/kr.local.lh-rental-monitor.plist
```

LaunchAgent는 로그인 세션에서 실행됩니다. Mac이 잠들거나 네트워크가 끊기면 정시에 조회할 수 없습니다. 계속 실행 중인 프로그램이 같은 날 늦게 깨어나면 그날 조회를 1회 진행하고, 날짜가 지났으면 지난 날짜는 건너뜁니다. 자동 잠자기를 막으려면 `caffeinate -i .venv/bin/python main.py`로 실행할 수 있습니다. 앱 로그는 프로젝트의 회전 로그에서 확인합니다.

## Windows 작업 스케줄러 예시

작업 스케줄러에서 ‘작업 만들기’를 선택합니다.

- 트리거: 로그인 시 또는 시작 시, 운영 계정 선택.
- 동작: 프로그램에 `C:\path\LH_rental_notice\.venv\Scripts\python.exe`.
- 인수: `"C:\path\LH_rental_notice\main.py"`.
- 시작 위치: `C:\path\LH_rental_notice`.
- 설정: 이미 실행 중이면 ‘새 인스턴스를 시작하지 않음’, 실패 시 1분 후 다시 시작.
- 장기 실행을 위해 ‘작업이 다음 시간 이상 실행되면 중지’ 옵션 해제. 상시 모니터링에는 반복 트리거가 필요 없습니다.

작업 스케줄러의 일일 18:00 트리거에 `--once`를 실행하는 방식도 가능합니다. 이 경우 상시 프로세스를 함께 실행하지 마세요. ‘사용자 로그온 여부에 관계없이 실행’은 해당 사용자 계정의 Python·프로젝트·`.env` 읽기 권한이 필요합니다.

Linux는 같은 CLI를 systemd 등 프로세스 관리 도구로 실행할 수 있습니다. 이 프로그램이 전원 절전이나 부팅 설정을 직접 바꾸지는 않습니다.

## 상태와 장애 확인

```sh
python main.py --status
tail -n 100 logs/lh_monitor.log
sqlite3 data/lh_notices.db 'SELECT notice_id,title,region,posted_date FROM notices LIMIT 10;'
sqlite3 data/lh_notices.db 'SELECT * FROM notification_history;'
sqlite3 data/lh_notices.db 'SELECT * FROM notification_attempts ORDER BY id DESC LIMIT 10;'
sqlite3 data/lh_notices.db 'SELECT * FROM app_state;'
```

SQLite CLI가 없으면 Python `sqlite3` 모듈이나 SQLite 뷰어로 확인합니다. `--status`는 공고 수, 발송 상태별 건수, 마지막 정상 조회, 초기화 상태, 연속 실패 수를 보여줍니다. 시각은 `Asia/Seoul`의 ISO 8601(+09:00)입니다.

`logs/lh_monitor.log`는 5MiB마다 회전하며 백업 5개를 유지합니다. 콘솔에도 같은 주요 이벤트를 출력합니다. 토큰과 Chat ID는 로그 필터에서 가립니다. HTTP 원문·요청 URL·예외 traceback은 기록하지 않습니다.

수집 실패는 기존 공고·발송 상태·마지막 성공 시각을 보존합니다. 정상 빈 목록은 성공으로 처리합니다. 전체 페이지를 수집하기 전에는 신규 공고를 저장하지 않습니다. 페이지 이동 중 총 건수가 바뀌거나 ID가 겹치면 다음 주기에 전체 조회를 다시 시도합니다. 수집 실패 중에도 기존 미발송 메시지는 재시도합니다.

실패 공고는 `failed`로 유지하고 다음 주기에도 재시도합니다. 발송 성공은 `sent`로 즉시 커밋합니다. `retry_count`는 실패한 **발송 주기** 수이며, 주기 내부 HTTP 재시도 수는 로그에서 확인합니다. `notification_attempts`는 주기별 성공·실패를 추가 기록합니다. 운영 경고는 연속 실패 임계점 이후 cooldown마다 최대 한 번, 경고 전송 실패 시에도 같은 제한을 적용합니다.

동일한 실제 DB 경로를 사용하는 프로세스는 파일 잠금으로 하나만 허용하며 프로세스가 죽으면 OS 잠금이 풀립니다. 잠금 파일이 남아 있어도 수동 삭제할 필요가 없습니다. DB를 복제하거나 다른 경로로 실행하는 경우에는 별도 인스턴스로 취급됩니다. 로컬 파일시스템에서 운영하세요.

## 수집 구조와 제한

- `src/crawler.py`: 공식 폼 기반 기간·임대 유형·상태 검색, 다음 페이지 POST, 전체 건수 검증.
- `src/parser.py`: 목록 열·필수 값·공고 ID·상세 URL 검증. 구조 변경 시 가장 먼저 점검합니다.
- `src/filters.py`: 지역 필드 일치 여부. 제목의 지역명으로 판별하지 않습니다.
- `src/database.py`, `src/detector.py`: 트랜잭션, 초기화, 신규 ID 비교, outbox 및 발송 이력.
- `src/telegram.py`, `src/http.py`: 안전한 평문 메시지, 성공 응답 검증, 지수 백오프 및 429 대기.
- `src/scheduler.py`, `src/logger.py`: 주기 실행, 종료 신호, 서울 시간 회전 로그.

Selenium이나 로그인 없이 서버 HTML로 수집합니다. 페이지 사이에 1초 쉬며, 401/403 등 접근 제한을 재시도로 우회하지 않습니다. CAPTCHA·대기열이 나타나면 파싱 오류로 기록하며 인증·대기열 우회 기능은 없습니다. 상세 URL에는 사이트에서 확인된 식별자만 넣습니다. 파일 다운로드나 로그인 영역에는 접근하지 않습니다.

고유키는 공식 `panId`입니다. 조회수·상태·제목이 바뀌어도 같은 ID는 다시 알리지 않습니다. 다른 ID의 정정공고는 새 공고입니다. 지역 `전국`, `인천광역시 외` 등은 제외하므로 경기도 공급이 들어 있어도 복합 지역 공고는 놓칠 수 있습니다. 기본 90일을 벗어나 뒤늦게 게시된 공고, 하루 사이에 올라왔다 삭제된 공고 역시 감지할 수 없습니다.

Telegram에는 송신 중복을 완전히 막는 키가 없습니다. 성공 직후 DB 커밋 전 종료 또는 응답 유실 시, 다음 실행에서 같은 메시지가 다시 갈 수 있습니다. exactly-once는 보장하지 않습니다. 단일 프로세스·공고 ID 고유 제약·건별 즉시 커밋으로 가능성을 줄입니다.

## 테스트와 실제 검증

```sh
# 개발 의존성 설치 (HTML 보고서 플러그인 포함)
.venv/bin/python -m pip install -r requirements-dev.txt

# 전체 테스트: 터미널 진행 로그 + HTML/텍스트 보고서 자동 생성
.venv/bin/python -m pytest

# macOS에서 결과 보기
open reports/test-report.html
```

Windows에서는 `.venv/bin/python` 대신 `.\venv\Scripts\python.exe`를 사용하고 생성된 HTML을 더블클릭합니다.

| 생성 파일 | 내용 |
|---|---|
| `reports/test-report.html` | 기능별 한국어 테스트 목적, 결과, 소요 시간, 실행 기록과 실패 상세 |
| `reports/pytest.log` | 테스트별 시작·성공·실패 및 앱 동작 로그 |

보고서는 CSS와 스크립트를 포함한 단일 HTML 파일이라 별도 서버 없이 브라우저에서 열 수 있습니다. 결과 체크박스로 성공·실패를 필터링하고 각 행을 클릭해 상세 로그를 펼칩니다. 테스트명에는 매개변수별 입력 조건도 표시됩니다. 실패 상황을 의도적으로 검증하는 테스트의 상세 로그에 ERROR가 있어도, 행의 결과가 Passed면 검증 성공입니다.

같은 명령을 다시 실행하면 최신 보고서와 로그로 덮어씁니다. 실행 기록을 별도로 보관하려면 `reports` 안의 파일을 복사하거나 `--html=reports/원하는이름.html -o log_file=reports/원하는이름.log`를 지정합니다. 생성된 보고서와 로그는 Git에서 제외합니다.

```sh
# 오후 6시 예약 테스트만 실행하면서 별도 보고서 만들기
.venv/bin/python -m pytest tests/test_scheduler.py --html=reports/scheduler.html -o log_file=reports/scheduler.log

# 실제 LH 조회 검증 (자동 테스트와 별도, DB 저장/발송 없음)
.venv/bin/python main.py --dry-run
```

**자동 테스트 89개 통과.** pytest는 네트워크나 실제 Telegram 없이 HTML fixture와 mock으로 실행합니다. 최초 무알림, 여러 신규 공고, 재시작, 내용 변경, 지역 제외, 빈 목록과 파싱 실패, 페이지네이션, 상세 키 누락, outbox 재시도, 429 및 중복 잠금, DB 롤백과 dry-run 불변성을 검증합니다.

2026-10-16 실제 조회에서는 최근 90일 경기도 검색 결과 **85건**, 정확한 `경기도` **63건**, `인천광역시 외` **22건**을 확인했습니다. 15건 단위 1·2페이지 POST 조회와 상세 링크도 검증했습니다. 수치는 조회 시점에 따라 바뀝니다. 실제 경기도 공고 1건을 테스트 메시지로 전송하고 Telegram API 성공 응답까지 확인했습니다. 자동 테스트는 실제 계정 없이 mock으로 실행합니다. 세부 근거는 [사이트 분석 기록](docs/site-analysis.md)과 [검증 기록](docs/verification.md)을 참고하세요.
