# LH 사이트 분석 기록

분석일: 2026-10-16 (Asia/Seoul). 명세의 임의 API 생성 금지 요구에 따라 실제 공개 페이지 HTML·인라인 JavaScript·검색 응답을 확인했다.

## 확인한 공식 자료

- [LH 임대주택 목록](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1026)
- [robots.txt](https://apply.lh.or.kr/robots.txt)
- [Telegram sendMessage](https://core.telegram.org/bots/api#sendmessage)

이번 조사에서는 목적에 맞는 공개 공식 API의 사용 계약을 확인하지 못했다. 서버 HTML만으로 필요한 데이터가 확인되어 requests + BeautifulSoup를 선택했다. 공식 API가 존재하지 않는다고 단정하는 것은 아니다.

## 요청 및 검색

목록 URL은 `/lhapply/apply/wt/wrtanc/selectWrtancList.do`, 응답은 UTF-8 HTML이다. 공개 목록은 비로그인 접근이 가능했다. `srchForm`의 기본 method는 POST, 사이트 JavaScript의 iOS 분기에서는 GET으로 바꾼다. 동일한 공개 필터를 GET으로 보내 실제 검색 응답을 검증했다. 페이지 이동은 `pagingForm`의 실제 hidden 값을 그대로 POST한다.

| 값 | 확인 근거 / 의미 |
|---|---|
| `mi=1026` | 임대주택 메뉴. 분양주택 1027, 토지 1062, 상가 1069와 구분 |
| `srchUppAisTpCd=061339`, `uppAisTpCd=061339` | 초기 검색 hidden, pagingForm의 임대 유형 전체 범위 |
| `cnpCd=41` | 지역 select의 경기도 option |
| `panSs=` | 상태 select 전체. 미지정 기본 화면은 공고중이므로 반드시 빈 값 전달 |
| `schTy=0` | 기간 select의 게시일 기준(1은 마감일) |
| `startDt`, `endDt` | 날짜 입력 `YYYY-MM-DD`. 기본 화면은 약 2개월이므로 프로그램이 90일을 명시 |
| `srchY=Y` | 검색 버튼 doSearch 함수에서 설정 |
| `listCo=100` | 페이지당 건수의 공식 option(15/30/50/100) |
| `currPage=1,2,...` | goPaging 함수가 바꾸는 페이지 값 |
| `panStDt`, `panEdDt` | 검색 후 pagingForm이 보존하는 `YYYYMMDD` 기간 |

기본 90일은 2026-07-18~2026-10-16(양 끝 포함)이었다. 경기도 서버 필터에도 `인천광역시 외`가 들어왔다. 따라서 결과의 지역 문자열을 별도로 검사해야 한다.

## 파싱 및 상세 링크

`.bbs_ListA table`의 헤더는 순서대로 번호·유형·공고명·지역·첨부·게시일·마감일·상태·조회수이다. 각 행의 `a.wrtancInfoBtn`에 다음 값이 있다.

- `data-id1` → `panId`: 공고 고유 ID, SQLite 기본키. 예 `2015122300020859`.
- `data-id2` → `ccrCnntSysDsCd`: 연계 시스템 식별자.
- `data-id3` → `uppAisTpCd`: 상위 유형(06/13/39).
- `data-id4` → `aisTpCd`: 세부 유형.

사이트 클릭 핸들러가 이 네 값을 srchForm에 복사하고 `/lhapply/apply/wt/wrtanc/selectWrtancInfo.do`로 이동한다. 프로그램도 동일한 네 값과 `mi=1026`을 쿼리에 넣는다. 값이 없으면 오류 처리한다. `netbgn` 같은 대기열 관련 플래그는 설정하지 않는다. 생성한 첫 공고 링크를 일반 GET으로 열어 HTTP 200과 동일 공고 제목을 확인했다.

제목의 `em.day` 같은 표시 배지는 제거하며, 게시일/마감일은 해당 td에서 추출해 ISO 날짜로 정규화한다. 선택 필드의 공백·`-`·`미정`은 None으로 저장한다. 공고 ID는 목록 순번·조회수·상태와 독립적이다.

## 빈 결과와 오류

총 건수는 `.bbs_total strong` 첫 값이다. 0건의 실제 응답은 헤더와 테이블을 유지하고 tbody에 `td colspan="9">검색하신 결과가 없습니다.</td>`를 출력하며 **pagingForm을 생략**한다. 존재하지 않는 검색어로 확인했다. 0건일 때도 테이블·정상 헤더·빈 결과 문구를 모두 요구한다.

양수 건수에는 pagingForm과 데이터 행을 요구한다. HTML 오류 페이지·로그인/접근 제한·테이블 소실·필수 필드 소실을 빈 목록으로 처리하지 않는다. 전체 페이지 건수와 고유 ID를 검증하고, 이동 중 총 건수 변경이나 ID 중복이 나타나면 그 조회의 저장을 포기한다.

## 정책 및 부담

확인한 robots.txt는 `/geoserver/web/`, `/apple/am/`, `/lhapply/apply/lo/login/`, `/lhapply/lhFile.do`, `/lhapply/apply/csvc/lhFile.do`를 금지했다. 수집하는 공개 목록 경로는 해당 금지 목록에 없었다. 이는 모든 자동 수집에 대한 포괄적 허가를 뜻하지 않으므로 운영 시 사이트 정책 변경을 확인해야 한다.

인증·CAPTCHA·NetFunnel 대기열을 우회하지 않는다. 현재 운영 설정은 목록을 매일 한국 시간 18:00에 1회 조회하며, 페이지 사이 1초 대기하며 첨부파일·상세본문 대량 수집은 하지 않는다. 일반 실행에는 상세페이지 조회가 필요하지 않다.

fixtures는 실제 HTML에서 목록·건수·페이지 폼만 발췌했다. `live_list.html`은 오프라인 소형 검증을 위해 앞의 2행만 남기고 총 건수를 2로 조정했다. `empty.html`은 실제 빈 검색 결과에서 같은 영역을 발췌했다.
