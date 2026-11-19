# Excel Mapper (구 Excel Review) — 현재 작업 컨텍스트

갱신: **2026-11-03 (한국 시간)** · 엔진 **v0.35.0 / Native test0.5.0** · 이전0.1~0.3 보존. T70~T77·용량 축소 구현·Windows EXE 검증 완료,0.5 릴리스 게시 완료. 웹 실기 검증은 이전 실행 거절로 미완료.
이 문서는 재개에 필요한 현재 상태만 유지한다. 상세 요청은 [BACKLOG](docs/BACKLOG.md#pending), 이전 상세 원문은 [이력 보관본](docs/CONTEXT_HISTORY.md)을 필요할 때 읽는다. 접근하지 못한 다른 채팅을 복원한 기록이 아니다.

## 작업 규칙

- **앱/테스트 코드 수정은 사용자 메시지가 단독 `해`일 때만** 한다. 그 전에는 논의·조사·요청 기록. 문서 작성/갱신/정리는 별도 승인되어 있다. 이미 승인된 작업의 중단·환경 복구 후 재개에는 같은 허락을 다시 묻지 않는다.
- 한국어로 간결하게 설명하고 사용자 의견도 업무 관점에서 검토한다. 불필요한 검사/승인 요청을 늘리지 않는다. 별도 요청 없는 하위 에이전트/외부 메시지 전송/클라우드 환경 게시를 하지 않는다.
- 주요 구현/버그/설정/의사결정 완료, 압축·종료 전에 갱신한다. 완료 / 실패 / 현재 문제 / 다음 작업과 사실 / 추정 / 미확인을 구분한다.
- 대략 **100~150줄**의 안내를 목표로 한다. 작은 대기 요청은 한 줄, 상세 조건은 BACKLOG. 완료 요청은 대기 목록에서 빼고 이력에 남긴다. 긴 기록은 링크를 남겨 보존한다.
- 툴팁은 기존/신규 모두 기본 방식(웹 title/네이티브 GUI 기본)으로 통일하고 설명은 보존한다. 별도 디자인의 툴팁은 만들지 않는다.
- **2026-11-03 Claude Code 전환**: 기존 Codex용 `AGENTS.md`를 `CLAUDE.md`로 이름 변경(내용 동일). 앞으로 Claude Code 전용이며 지침은 `CLAUDE.md`에 둔다. 과거 문서의 `AGENTS.md`/Codex 언급은 이력으로 보존한다. `/workspace/...` 경로 등 옛 환경 정보는 현재 사실이 아닐 수 있다(미확인).
- 비밀번호·API 키·토큰·환경변수 값은 문서/로그에 기록하지 않는다. 사용자 원본/결과 파일을 커밋하지 않는다.

## 목적·저장소·현재 상태

범용 엑셀 비교·선택 반영·다중 부서 자료 취합 프로그램이다. CCTV는 샘플 소재일 뿐 일반 UI는 범용이다. 최종 목표는 **오프라인 Windows 독립 UI/포터블 EXE**이며 웹을 감싼 EXE는 원하지 않는다. **Streamlit 웹판은 2026-11-03 사용자 결정으로 제거**(app.py·components·.streamlit·.devcontainer·웹 전용 모듈·tests/browser·웹 스크린샷·pandas/streamlit 의존성 삭제, README 재작성). 과거 웹 기록은 docs/ 이력과 git 이력에만 남는다. PySide6 네이티브판만 유지한다. 네이티브는 웹을 내장하지 않으며 Windows EXE 자체 검증 완료. 첫 테스트판이고 웹 전체 동등성은 미완료다. 외부 AI API는 사용하지 않는다.

- 경로 `/workspace/ai-excel-compare-project`, 로컬 `work`, 원격 `https://github.com/BBulMushroom/Excel-Mapper`(2026-11-03 사용자가 저장소 이름을 변경, 옛 주소는 자동 연결됨. 이 세션의 GitHub 도구는 옛 이름으로만 허용되어 있었음), 배포 `main`.
- 공개 웹 앱(excelreview.streamlit.app)은 더 이상 유지하지 않는다. Streamlit Community Cloud 쪽 앱 삭제는 사용자가 직접 해야 한다(미확인).
- 네이티브 검증 소스8ff26dd은 main/codex/native-test-v01 및 native-test-v0.1.0 릴리스에 보존. 이후 main에는 배포/문서만 추가했다. v34 소스d98d855/문서d751f1d도 보존된다. 이전 v33 소스62568a1/문서256b618도 보존된다. 이전 v32 소스861ab21/문서15722e4도 보존된다. 이전 v31 소스70b5ca0/문서f1e7769도 보존된다. 이전 v30 소스1d9ac5a/문서d877b94, v29 소스3e79e00, v28 검증e719191도 보존된다. 복원261dd7d/이전main4f81a4e는 환경 중단 복구 이력이다.
- 환경 재연결 시 **이전 스냅샷으로 열릴 수 있다**. `git status`, `git log`, 원격을 먼저 확인한다. 로컬 미커밋 파일이 남았다고 가정하지 않는다.

## 현재 승인 작업·대기

**릴리스 게시 주의**: 태그가 가리키는 커밋(`--target`)이 워크플로 파일을 바꾸는 커밋이면 GITHUB_TOKEN이 403(`Resource not accessible by integration`)으로 거부된다. 워크플로 수정 직후 커밋이 아닌, 워크플로를 건드리지 않는 커밋으로 빌드·게시할 것.

**버전 체계(사용자 확정): 세 자리 0.012→0.013→0.014…, 릴리스 태그 `native-test-v0.013`. 릴리스 `0.013` 완료, `0.014` 완료, `0.015` 완료(T100), `0.016` 완료, `0.017` 완료, `0.018` 완료(T102 애니메이션 제거), `0.019` 완료(T103 병합 셀 1단계, 2~4단계 대기), `0.020` 완료(T104 오류 안내), `0.021` 완료(T105 열 연결 창), `0.022` 완료(T106 시트 변경), `0.023` 완료(T107 병합 모양 표시), `0.024` 완료(T103 2·4단계), **정식판 `1.000` 진행(T108 변경 이력 정리, T109 정식 전환: 태그 `v1.000`, Latest)** — 이후 정식판은 `1.001`…; `0.014`는 T98 숨김 핸들 경계 정중앙, T99 샘플 엑셀 데이터 구간 배경색 제거; 사용자 `해`). 릴리스 제목은 `Excel Mapper 0.014`(Windows x64 표기 뺌), 남은 릴리스는 0.012·0.013.** 이전 **릴리스 0.12.0** (`native-test-v0.12.0`, 커밋 e8be2a5): T93 취소선 숫자 셀 정렬, T94 로딩바(지연 0.1초·갱신까지 유지), T95② 파일 팝업 비교 `추가`. 이전 단계(0.5~0.11)의 상세 반영 기록은 [docs/CONTEXT_HISTORY.md](docs/CONTEXT_HISTORY.md#2026-11-03-이전-승인-작업-기록), 요청별 기록은 [docs/BACKLOG_DONE.md](docs/BACKLOG_DONE.md).

**T96 정리 완료(사용자 `해`)**: 이 문서 축소, BACKLOG 완료 항목 분리(`docs/BACKLOG_DONE.md`), 테스트 85→67초, 미사용 파일 삭제. 앱 코드 변경 없음(릴리스 0.12.0 유지).

**개선 후보 목록(제안·미승인)**: [BACKLOG 개선 후보](docs/BACKLOG.md#pending) C1~C16(진행 표시/취소, 끌어놓기·최근 파일, 사전 경고, 병합셀, 검토 저장, 내보내기, 다중 시트, 서명·설치 등). 사용자가 번호를 고르면 요청으로 전환.

**PR 상태**: #1(CLAUDE.md 전환), #2(수정·성능·리팩토링·Streamlit 제거)가 main에 병합됨. 이후 작업은 main 기준 새 변경으로 취급한다. 최신 EXE: native-test-v0.6.1(커밋 e523205).

**상시 규칙(사용자 지시 2026-11-03)**: 수정 후에는 항상 EXE까지 빌드·릴리스하고 다운로드 링크를 준다(CLAUDE.md에도 기록). 릴리스: native-test-v0.6.0(커밋 d1319a2), 다음은 v0.6.1.

## 구조·주요 파일

| 파일 | 역할 |
| --- | --- |
| `desktop/`, `desktop_entry.py`, `requirements-desktop.txt`, `.github/workflows/windows-desktop.yml` | 네이티브 Qt UI/가상 모델/가역 세션/대화상자/자체 검사·Windows 단일 EXE 빌드. 상세 NATIVE_TEST. |
| `app.py` | Streamlit 진입점. 업로드/시트·범위/키/옵션/취합·저장 조율, 상단 메뉴/설정 팝업과 파일 상태 조율. |
| `display_theme.py`, `display_theme.js`, `components/preferences/` | 공통6테마 토큰·글꼴·화면 설정, 브라우저 저장/호스트·프레임 적용·설정 줄 접힘 상태. |
| `comparison_rules.py` | 수정 값의 공백/대소문자/날짜 동일 판정·사용자 패턴. 숫자 오차 제거. 키·수식·원본값 유지. |
| `ui_chrome.py` | 메뉴/팝업 CSS·테마 동기화, NativeUI의 help→title 어댑터와 DOM 재렌더 대응. |
| `compare.py` | UI 독립 비교/추천/검증/원본 기반 파일 생성/정렬/로그. VERSION 기준. |
| `manual_edits.py` | 직접 편집 입력 검증/자료형 판정. 기존 행 정체성·내용만 변경, 서식은 저장 엔진에서 보존. |
| `excel_copy.py` | 실제 수식/상대참조/참조 시트/기본 서식 복사, 계산 캐시, 미지원 참조 차단. |
| `formats.py` | XLSX/XLSM 준비, XLS/CSV→내부 XLSX 변환. |
| `ui_helpers.py`, `matching_ui.py` | 시트/범위/열 연결/복합 키 추천, 프로필 검증, 문제 행과 예상 건수. |
| `workspace.py` | 키 정렬 행 모델·주소·단위·원본/비교 수식 캐시·gzip/base64 payload. |
| `tools/capture_theme_previews.py`, `components/preferences/previews/` | 가상 XLSX 실제 앱 캡처·6개 PNG 재생성, 사용자 데이터 미사용. |
| `components/workspace/index.html` | 지속 JS 표 UI. 3분할/합쳐보기, 가상화, 선택/필터/정렬/스크롤/배율/크기/키보드/실행 취소. |
| `collection_flow.py`, `history_state.py` | 단계별 원본/승인 체크포인트·중복 방지·이전/다음, 서버 설정 스냅샷 복원. |
| `analysis_cache.py` | 세션별 분석 LRU, 생성 결과 메타데이터 재사용. |
| `settings_store.py`, `components/profiles/index.html` | 공통 설정 JSON/네이티브 사용자 파일 어댑터, 웹 localStorage 보관 UI와 테마 동기화. |
| `samples.py`, `sample_descriptions.py`, `sample_tools.py` | 가상 샘플1~15 생성/설명/분리된 테스트 메뉴. |
| `tests/test_*.py`, `tests/browser/`, `benchmarks/` | pytest, 단독/실제 앱 Playwright, 엔진·파일 전환 측정. |

`workspace_persistent`, context/serverToken/historySession, revision/ack, rowPayload/rowsExpected/load_rows 복구 경로를 유지한다. 체크는 로컬 갱신, 저장은 승인 ID를 검증한 뒤 원본 바이트를 열어 처리. 세션 재시작 후 작업 전체 영속 복구는 보장하지 않는다.

## 중요한 결정·실제 동작

- 입력 XLSX/XLSM/XLS/CSV. XLS/CSV 결과는 XLSX. 원본 XLSM은 VBA 보존 경로. CSV UTF-8 BOM/CP949와 쉼표/세미콜론/탭. 병합된 데이터 시트, 빈/중복 제목, 빈/중복/수식 키는 차단한다.
- 순번은 파일 내 순서로 고유 키가 아니다. 키/수정 비교에서 제외, 결과에서 재생성한다. 양끝 공백 제거·숫자 문자열 통일, 문자열00123과 숫자123은 구분한다.
- 열 연결은 동일 이름 우선, 나머지 이름20%/형식20%/공통값60% 점수50 이상 일대일 추천. 전체 행 사용, 확률이 아니다. 키는 별도 suggested_keys로 단일/복합 선택 가능. 시트/범위는 선두80행 감지 후 변경 가능.
- 같은 양식은 다음 파일에도 자동 연결되며 저장 프로필도 재사용. **프로필 없이 수동 변경한 매핑 자체를 다음 파일에 보관하는 로직은 없음**을 확인했으나 별도 수정 승인 항목은 아니다.
- 기본 추가·수정ON / 삭제OFF, 셀 단위, 일반 복사, 원본 순서 유지. 행 단위 선택 가능, 원본 전용 열 보존. 보기 필터/정렬은 저장 정렬과 다르다.
- 원본/비교/수정 3분할과 합쳐보기. 추가초록/수정주황/삭제빨강·순서도 동일. 실제 셀 좌표와 ↔/없는 쪽—. 합쳐보기 수정은 원래 값 취소선+새 값 위/아래.
- 아이콘/건수 버튼은 모두 해제할 때만 회색 점선. 행/셀↔목록 연결, Ctrl+Z/Y/Shift+Z는 직전 정확한 선택·보기·설정 복원.
- 표 위 Ctrl+휠 배율60/75/85/100/115/125%(기본100). 행/모든 열(행·기준값 포함) 드래그·더블클릭 자동 맞춤·3표 동기화. 고정 열 Map 키null/false, 최소48 논리px. 표별18px 색상 레일, 목록 독립 스크롤.
- 사이드바 hover/핸들/리다이렉트 제거. 상단 메뉴와 설정 이름+값은 네이티브 st.popover, 클릭 열기/외부 클릭·Escape 닫기. 더보기는 화면 설정/프리셋/단축키/테스트 샘플 탭, 기준 키는 상단 직접 선택·변경 시 검증 후 적용, 열 연결만 별도 작은 팝업. 빠른 테마 버튼 제거·더보기 전체 테마 메뉴로 통일. 설정 접기/펼치기는 기본 펼침·현재 페이지 세션 내 유지·undo 포함. iframe Escape도 상위 팝업을 닫는다. 설정 카드는 초기화/재렌더/테마 메시지에 동기화한다.
- 화면: 라이트/그레이/웜/다크/네이비/차콜. 기본/맑은 고딕/Noto/Nanum, 미설치 맑은 고딕은 Noto 대체. Noto·Nanum TTF+OFL 동봉(약12MB, 외부 CDN 없음). 줄바꿈/열 숨김 기본OFF, 시작마지막 보기. 표시만 변경하며 설정은 localStorage excel-review.display.v1에 저장한다. 추가/삭제 있으면 전체 열, 수정만 있으면 수정 열만 표시한다. 직접 조절한 행 높이는 유지한다.
- 비교 설정: 대소문자OFF/trimON, 숫자 오차 메뉴·판정 제거(구 프리셋 tolerance 무시). 날짜는dates=ymd/mdy/dmy/custom·date_pattern=YYYY-MM-DD·ignore_date_format=False 기본. 읽는 형식 먼저, 무시 체크박스 아래. 사용자 YYYYMMDD/YY-mm-dd 등, YY=2000~2099. 시간·일련번호 추측 없음. 잘못된 초안은 마지막 유효 설정 유지. 키 식별 규칙은 그대로이며 수정 값에만 적용. 조건 변경은 선택 초기화/재비교, Ctrl+Z로 복원. 캐시/서버 이력/프리셋 comparison_rules 필드와 연동하고 구 프리셋은 기존 기본값이다.
- 하단 요약·범례·상세·화면 이력·버전, 변경 탐색 옆 건수/선택 주소는 제거. 남는 높이를 표/목록이 사용. 표 위 행 개수 제거, 검색 안내 돋보기+검색, 적용 필터 유지, 정렬은 열 제목 화살표. 파일의 변경 이력은 유지한다.
- 값만 복사 표시: 원본/비교/수정·합쳐보기·목록에 저장된 계산 캐시를 표시하고 없으면 ‘계산값 없음’. 원본/비교 수식 원문과 비교 판정은 유지한다. 표시 행은 원문/결과 복사본과 분리하여 view 캐시를 재사용한다. 일반 복사는 수식 표시로 복귀한다.
- 일반 복사는 실제 수식·목적 좌표 상대참조·기본 서식. 다른 시트는 별도 (비교) 스냅샷과 의존성 보존. 값만 복사는 저장 계산 캐시, 없으면 계산값 없음/저장 오류. 앱 자체 수식 계산 없음, Excel 재계산 요청.
- 결과는 원본 기반 별도 파일. 조건부서식/유효성/개체 전체 복제·범위 확장은 보장하지 않는다. 수식 워크북 행 삭제, 수식 시트 저장 정렬, Excel Table 행 추가·삭제·정렬 차단. 외부/3차원/이름 정의/표 구조/배열 수식 일반 복사는 미지원.
- 변경 이력 한 시트에 승인/미승인도 누적, Asia/Seoul 시간. 같은 이름 일반 시트 충돌 차단, 형식 일치 구버전 날짜 로그만 통합.
- 취합은 단계별 반영 전 원본에서 생성. 마지막도 ‘반영 후 다음’ 문구 유지/비활성, 체크는 변경 가능. **마지막 다운로드가 최신 선택을 생성·확정**하여 이후 비교 교체도 최종 누적본 사용. 같은 설정/선택만 출력 재사용하여 중복 방지.
- Ctrl+S 다운로드/Ctrl+Enter 반영 후 다음. 입력/IME/처리 중/마지막 조건 적용, 단독 Enter/Alt+방향키는 추가하지 않음. 완료 후 이전은 마지막 단계의 반영 전 검토를 다시 연다.
- 같은 취합 세션의 보기 범위/검색, 같은 열 구조의 필터/정렬/너비는 다음/이전에도 유지. 새 업로드/샘플은 collection_session으로 초기화. 원본/비교 독립 교체·다중 순차 반영/건너뛰기.

## 환경·실행

- venv `/workspace/excel-compare-env/.venv`, Python3.12 계열. 고정 실행 pandas3.1.0/openpyxl3.1.5/streamlit1.66.1/xlrd2.0.2, 개발 pytest9.2.0/xlwt1.3.0. requirements*.txt 참고.
- Playwright는 requirements-dev에 없고 이번 시스템 python에 설치됨. Chromium `/usr/bin/chromium`. 새 환경에서 존재/권한 재확인. 최신 복구 환경에 누락된 xlwt는 설치하여 XLS 검사도 보완했다.
- 세션 LRU 표4개/범위8개, 출처 바이트+시트+제목/시작 일치만 재사용, VERSION 변경 시 초기화. 시트 목록 st.cache_data24개. ExportResult1개는 context·검토/복사/정렬·승인 일치 시만 재사용. prefetch 미도입.
- Streamlit headless=true, maxUploadSize2147483647 MB, gatherUsageStats=false, primaryColor#2563eb. 실제 호스팅/메모리 한계는 존재한다.
- 웹 설정 localStorage excel-review.settings.v1, 테마 excel-mapper-theme. schema1/최대500개/이름100자/웹 JSON Import2MiB. 원본 데이터·개별 체크 저장 제외. 네이티브 어댑터 %APPDATA%/ExcelReview/settings.json(Linux XDG_DATA_HOME 또는 ~/.local/share). 웹 서버 공용 파일에는 저장하지 않는다.
- EXCEL_MAPPER_TEST_SAMPLES=0으로 샘플 비활성화. UI_APP_URL/--url로 검사 대상, UI_BASELINE_URL/--baseline-url로 전후 비교. 프로세스/승인/임시파일은 환경 종속.

```bash
cd /workspace/ai-excel-compare-project
git status --short
git fetch origin main
# 로컬 변경 유무와 브랜치를 확인한 후 최신 원격 반영
/workspace/excel-compare-env/.venv/bin/python -m pip install -r requirements-dev.txt
/workspace/excel-compare-env/.venv/bin/python -m streamlit run app.py --server.port 8524 --browser.gatherUsageStats false
/workspace/excel-compare-env/.venv/bin/python -m pytest -q
python tests/browser/release_v24.py --v34 --url http://localhost:8524
/workspace/excel-compare-env/.venv/bin/python benchmarks/collection.py
git diff --check
# 승인 구현을 검증한 뒤 기존 배포 방식:
git push origin HEAD:main
```

managed cloud 시작/복구 때 runtime 스킬과 환경 상태 확인. 네트워크 전 `/etc/codex/network-policy.json`, 프록시/CA/TLS 유지. 과거 환경 ID/준비 상태 재사용 금지. 클라우드 설정은 임의 게시하지 않는다.

## 최근 검증·실패·재개
- v35/Native0.1: Linux109/Node4·Windows native5/EXE 자체 검사·실제 한글/아이콘 캡처 통과. Windows tzdata 누락/모달 검사 대기/폰트 깨짐/로컬 업로드401·릴리스 없음 해결. 상세는 NATIVE_TEST/SAMPLE_TESTS.
- v34 pytest104/Node3·구문·diff 통과. 실제 Chromium은 sandbox setsockopt 실패→자동 승인 검토가 밖 실행 거절(denied)하여 브라우저 시나리오/깜빡임 실기/새 캡처 미완료. VM 함수 검사는 DOM 대역이며 실제 화면 통과로 해석 금지. 상세 SAMPLE_TESTS.

- v24~v33의 상세 검증/실패/복원 기록은 [이력 보관본](docs/CONTEXT_HISTORY.md)에 보존했다. 새 환경 복구 당시 원본 미커밋 파일은 없었고 대화/원격으로 재구현했으며 복원한 원문으로 주장하지 않는다.

## 미해결·다음 작업

1. Native0.5 게시 완료. 사용자 환경 전환 지연/드롭다운/다크 체크 재확인은 후속 피드백 대상. Native0.4 이력 보존. 사용자 Windows/DeX에서 새 버전의 IME·마우스/애니메이션 체감 재확인은 아직 없으며 후속 피드백 시 회귀로 확인한다. T40 사용자29건 구현·0.3 배포 완료. 사용자 Windows에서 수정 후 재확인은 아직 없으며 후속 보고 시 회귀로 확인한다. T38/T39 수정0.2 게시 완료. 사용자 Windows 화면/배율 재확인은 아직 없고, 웹 전체 동등성은 남아 있다. 복합/날짜 필터·테마 hover·복수 열 저장 정렬 UI·모든 보기 상태 undo는 아직 미이식. 정확한 전체 동등성은 미완료로 기록한다.
2. 공개 앱의 최신 자동 배포 완료는 별도 확인 대상이다.
3. 삼성 브라우저 샘플5 목록 클릭→체크 해제→휠 맨 위 이동은 Chromium 모바일/휠 회귀 통과 후에도 실기 해결 미확인. Edge 미발생은 사용자 관찰.
4. 네이티브 테스트판의 고급 필터 등 나머지 이식·사용자 Windows 고배율·대용량·복잡 서식은 후속 검증. 이 요청을 전체 동등성 완료로 기록하지 않는다.

[BACKLOG](docs/BACKLOG.md#pending)는 최신 요구조건, [README](README.md)는 사용법, [SAMPLE_TESTS](docs/SAMPLE_TESTS.md)는 근거, [상세 보관본](docs/CONTEXT_HISTORY.md)은 과거 동작/샘플 전체 조건이다. 초기 HANDOVER는 최초 요구사항으로 현재 코드보다 우선하지 않는다. 샘플5는40셀/32행, 7은의도된오류, 12는1만행, 13·14는수식/캐시, 15는빈원본+10부서×30행으로 최종300행이다.

미리보기 갱신: `python tools/capture_theme_previews.py --engine-python /workspace/excel-compare-env/.venv/bin/python --url http://localhost:8524` (Playwright/Chromium 필요). 1440×900 PNG6개, 총약650KiB, 화면/테마 변경 시 함께 재생성한다.
