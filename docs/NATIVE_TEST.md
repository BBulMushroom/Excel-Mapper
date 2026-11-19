# 네이티브 테스트판 0.5.0

[EXE 다운로드](https://github.com/BBulMushroom/ai-excel-compare-project/releases/download/native-test-v0.5.0/ExcelReview.exe) · [변경/계측/실패 기록](NATIVE_V05.md) · [Windows 화면](images/native-v05-windows.png). 이전0.4~0.1 기록은 아래 보존한다.

- T70~T77/용량 축소 승인 구현. 전환 준비 중3표 재측정 제거·행/카드 조회 개선, 드롭다운/체크 대비·아이콘/건수/화살표 보완.
- 소스bb1e570, Windows41537209208 Qt23개·패키지19항목 통과, PE64·해시·PNG 확인. EXE35,807,070bytes(34.1MiB), 이전 대비20.9% 감소. 한글/샘플 유지. SHA256 `e82c52274e5215e1b41980a81f9ff58facbce28950da3ed745b291aa3086169f`.
- 동일 Linux/offscreen 1회 측정에서1만행 합치기 준비2451.2→328.3ms/나누기2119.2→289.5ms. Windows FPS/사용자 체감 보장은 아니다.

---

# 네이티브 테스트판 0.4.0

2026-11-03 T41~T69 승인 구현. DeX 실행은 사용자 해결로 별도 원격 환경을 만들지 않았다. [상세 변경·결정·실패·검증](NATIVE_V04.md). 아래0.3~0.1 기록은 보존한다.

- [EXE 다운로드](https://github.com/BBulMushroom/ai-excel-compare-project/releases/download/native-test-v0.4.0/ExcelReview.exe). 단일 EXE43.2MiB, 기존 사용자 설정/프리셋은 사용자 영역에 유지한다.
- 최종 소스 `1cb4c8fd84fd602c6d89f76084902330218fa3ba`, [Windows41533737720](https://github.com/BBulMushroom/ai-excel-compare-project/actions/runs/41533737720): Qt21개·실제 frozen EXE19항목 통과. 로컬 전체124개/Node4개 통과 후 자동 폭 보완과 신규 회귀를 포함한 Qt21개 재검증.
- EXE45,277,088bytes, SHA256 `53cdb7434fb9ed010716ba1d17beb4f0e6eb58c3b62154d49d3ca1873dfad0e0`. [실제 Windows 화면](images/native-v04-windows.png). 첫 fe08fc1 빌드는 검사 통과 후 캡처에서 합쳐보기 자동 폭 잔류를 발견해 미게시했으며 최종 소스로 보완했다.
- 주요 변경: 스크롤 렌더/연속 보간, 셀 결합 전환, IME 검색·즉시 글꼴·엑셀식 편집, 셀/행 개별 승인·우클릭/Space·Ctrl+Q/E, 자동 폭·수동 폭 보존, ▼ 필터/높이/열 연결, 프리셋 요약·행 카드·샘플1~9.
- [0.4 릴리스](https://github.com/BBulMushroom/ai-excel-compare-project/releases/tag/native-test-v0.4.0) 게시41534223179 성공, draft=false/target1cb4c8f/4첨부 확인. 이전 릴리스 보존.
- 동일 원본 배포 회신의3자 충돌 자동 병합은 추가하지 않았다. 새9번 설명에 순차 반영이 앞사람 값을 되돌릴 수 있음을 명시했다. 고급 웹 기능 전체 동등성이나 사용자 Windows 전체 환경 검증 완료판은 아니다.

---

# 네이티브 테스트판 0.3.0

2026-11-02 사용자 확인29건 반영. 상세 변경·결정·회귀는 docs/CONTEXT_HISTORY.md, [요청 원문](BACKLOG.md#pending). 아래0.2/0.1 기록은 이력으로 보존한다.

- 최종 소스 `16b0d5de0332b385cb588afc7069375c16b20eb0`, [Windows 빌드41445649807](https://github.com/BBulMushroom/ai-excel-compare-project/actions/runs/41445649807): 네이티브15개·패키지 자체 검사19항목 통과. Windows Server2025/Python3.12 x64에서 실제 EXE를 실행했다.
- EXE44,843,021bytes(42.8MiB), PE64, SHA256 `ee8d16634bffd92ddc6ba8ea04254525966caa582d002214d82586062b534566`. 해시/PNG/JSON/바이너리를 내려받아 확인했다.1만행 위젯175→175, 관측 로드3.225초/스크롤순회0.581초(CI1회·합성3열, 전후 성능 개선율이나 업무 파일 성능 보장 아님).
- [실제 Windows EXE 화면](images/native-v03-windows.png). 동일 예제 [나눠보기](images/native-v03-split.png)/[합쳐보기](images/native-v03-merged.png)는 Linux Qt 캡처이며 Windows 화면과 구분한다.
- 로컬 전체pytest119/Node4 통과. 이후 전환/수명 보완은 관련 Qt 회귀8·최종 Windows15 및 EXE 검사로 재확인. `python -m pytest -q tests/test_desktop.py tests/test_desktop_v03.py`, `python desktop_entry.py --smoke-test /tmp/native-smoke/report.json`.
- 빌드 첫 통과 후 실제 전환 캡처에서 행 높이 잔류와 QSplitter의 전환 위젯 자동 삽입을 발견해 보완했다. 중간 빌드는 릴리스하지 않았으며 최종16b0d5d만 게시한다.
- [0.3 릴리스](https://github.com/BBulMushroom/ai-excel-compare-project/releases/tag/native-test-v0.3.0) 게시 완료(작업41446547424 성공). GitHub API에서 대상16b0d5d/draft=false/prerelease=true와 EXE44,843,021bytes·총4첨부를 확인했다. 기존0.2/0.1은 보존한다. 실행 파일을 교체해도 사용자 설정과 프리셋은 사용자 영역에 유지된다.

---

# 네이티브 테스트판 0.2.0

2026-11-02 T38/T39 사용자 `해` 승인 후 수정. 기존0.1 이력은 아래 보존한다.

- 웹판 저장 캡처와 같은 가상 예산 예제1440×900로 나눠보기/합쳐보기·라이트/다크를 대조했다. `python tools/capture_native_preview.py --output /tmp/native-parity`, `QT_SCALE_FACTOR=2`로 실제2배 캡처도 생성했다. 새 브라우저 캡처 실행은 이전 자동 승인 검토에서 거절되어 재시도/우회하지 않았다. 저장된 웹 기준과 최신 웹 소스를 사용했으며, 최신 실제 브라우저와 픽셀 일치 검증을 했다는 뜻은 아니다.
- 메뉴/설정 줄/선택 pills/검색/배율/3표/목록 간격을 웹 기준으로 수정. 파일·비교 설정·시트/범위·열 연결은 앵커 팝업, 더보기는 화면 설정/프리셋/단축키/테스트 샘플 탭. 기존 엔진/입력/수식/편집/취합 유지.
- Windows 맑은 고딕 우선, 없으면 `desktop/fonts/NotoSansKR-Regular.ttf`. Qt6.8에서 기존 가변 폰트가 `QFontDatabase.styles == ['Thin']`으로만 나오는 사실을 확인. 원본 가변 TTF에서 fontTools4.61.1로 wght400 정적 인스턴스를 만들고 Desktop Regular 이름으로 저장했다(OFL 유지). fontTools는 런타임 의존성이 아니다. 기존 폰트 교체만으로 실제 PC의 모든 선명도 원인이 해소되었다고 단정하지 않는다.
- 아이콘은 QIconEngine/QPainter로 요청 DPR에 맞춰 그림.20논리px의1/1.5/2/3배 결과20/30/40/60px 확인. 표별18px 스크롤 레일·5px 변경 위치 표시, 변경 목록 주소/취소선/새 값·선택 상태. 시작 화면·6테마·표 배율60/75/85/100/115/125.
- 열 제목 옆 정렬/필터 팝업. 선택값/포함/미포함/같음/다름/시작/끝/빈 셀/비어있지 않음/숫자 대소/추가·수정·삭제 조건. 웹 복합 AND/OR·날짜·상위N 조건과 완전 동등하지 않다.
- 로컬 전체pytest111/Node4 통과, 네이티브7개 포함. 팝업 Escape/더보기 탭/인라인 선택 undo/DPR/목록 체크 후 스크롤 유지/3레일·테마 재전환을 실제 Qt로 검사한다. 테스트 QSettings 경로 지정이 명시 organization 생성자에 적용되지 않던 문제도 defaultFormat 명시로 수정해 검사 중 실제 사용자 설정을 건드리지 않는다.
- **남은 동등성**: 웹 고급 필터 전체, 테마 hover 이미지, 복수 열 저장 정렬 UI, 너비/배율/테마/표 숨김 등 보기 상태 전체 undo. OS 파일 선택기는 Windows 기본. 현재 완전 동일 최종판이라고 안내하지 않는다.
- Windows 첫0.2 캡처에서 아래 화살표U+2304가 누락된 사실을 발견. 동봉 글꼴이 지원하는U+2228로 바꾸고 자체 검사에 해당 글리프 검사를 추가했다. 이 첫 빌드 파일은 최종 배포하지 않는다.
- 최종 소스 `4fd2f95ed9059d42a2d870d00f7fbbff72fd8b3d`, [Windows run41434407918](https://github.com/BBulMushroom/ai-excel-compare-project/actions/runs/41434407918): 네이티브7개·실제 EXE 자체 검사 통과. PE64/44,236,660bytes(42.2MiB), SHA256 `3d0e055b9dc7212fba355d9dbbecbda626533e8a401f2e22966b55546417e723`.1만행 위젯171→171, 합성3열 로드1.992초/스크롤 순회0.322초(CI1회 관측).
- [실제 Windows EXE 화면](images/native-v02-windows.png), 같은 예제 [나눠보기](images/native-v02-split.png)/[합쳐보기](images/native-v02-merged.png)(Linux Qt1440×900). 두 종류의 캡처를 구분한다. 사용자의 Windows PC에서 모든 배율/폰트가 같다고 검증한 것은 아니다.
- [0.2 릴리스](https://github.com/BBulMushroom/ai-excel-compare-project/releases/tag/native-test-v0.2.0) 게시 완료(작업41434752870 성공). GitHub API에서 draft=false/prerelease=true와 EXE44,236,660bytes·총4첨부를 확인했다. 이전0.1 릴리스는 보존한다.

---

# 네이티브 테스트판 0.1.0

Windows 10/11 x64용 첫 테스트판이다. PySide6/Qt의 일반 데스크톱 창·QTableView 모델을 사용한다. Streamlit, WebView, HTML 창, HTTP 서버를 실행하지 않는다. 기존 `compare.py`/`excel_copy.py` 저장 엔진을 재사용한다.

## 실행·파일

- 배포 목표: `ExcelReview.exe` 한 파일. Python·Excel 별도 설치 없이 실행. 자체 압축은 실행할 때 임시 폴더로 해제되므로 파일 하나가 모든 런타임 파일을 메모리에서 직접 실행한다는 뜻은 아니다.
- 일반 설정은 사용자 QSettings(Windows 사용자 영역), 프리셋은 `%APPDATA%/ExcelReview/settings.json`에 보관한다. 배포에 INI 동봉은 필요하지 않다. 더보기→프리셋에서 Import/Export.
- 개발 실행: `python -m pip install -r requirements-desktop.txt`, `python desktop_entry.py`.
- Qt 필수 모듈만 사용한다. 브라우저/Streamlit/pandas는 네이티브 의존성에서 제외했다. Qt/LGPL와 기타 의존성 고지는 프로그램 정보·라이선스 메뉴 및 `desktop/licenses/`에 있다.
- 처음 여는 파일은 원본1개+비교1개 이상. 입력 파일을 덮어쓰지 않고 다른 파일로 저장한다. 원본/비교 교체, 순차 취합, 이전/건너뛰기/마지막 파일 선택 재검토를 지원한다.

## 포함된 테스트 기능

- 원본/비교/수정3표, 합쳐보기와 오른쪽 변경 목록, 추가/수정/삭제 색 구분.
- 기본 삭제OFF, 셀/행 선택, 변경 종류 일괄 전환·개별 체크·목록 더블클릭, 선택 상태 되돌리기/다시 실행.
- 기본 편집OFF, 수정본/합쳐보기 더블클릭 내용 편집, 실제 수식/값만 복사·저장 엔진, 상대참조/서식 보존의 기존 엔진 제약 유지.
- 기준 키 추천/복합 키/열 연결, 시트·제목/시작 행, 비교 규칙/사용자 날짜 형식, 기본 설정 줄 접기.
- 검색·종류 필터, 열 머리글의 보기 정렬/값·텍스트·숫자 기본 필터, 저장 순서, Ctrl+S/Ctrl+Enter/Ctrl+Z/Y/C/Ctrl+휠.
- 기본 Qt 툴팁은 hover 대기350ms/표시 기간15초로 설정한다. 디자인은 Qt 기본을 유지한다. 메뉴는 QAction/QMenu로 미리 구성하며 대화상자는 요청할 때만 만든다. 웹의 title 표시 시간을 강제로 변경하는 기능은 아니다.
- 6개 테마·설치된 글꼴·줄바꿈·변경 없는 열 숨기기, 프리셋 사용자 보관·Import/Export, 테스트 샘플1~15.
- Qt 모델은 화면에 보이는 셀만 그린다. 데이터 전체 행을 숨기거나 표시 행 수를 자르지 않는다.

## 첫 테스트판의 범위

웹판 전체 화면과 완전히 같은 기능·모양으로 검증 완료한 제품은 아니다. 네이티브 필터는 기본 조건부터 제공하며 웹판의 모든 복합 조건·날짜 조건·상위N·가상 값 목록 UI와 같지 않다. 테마 이미지 hover 미리보기, 스크롤바 색상 인디케이터, 상세 보기 상태 전체의 undo(검색·필터는 세션 undo, 너비·배율·테마 등은 아직 아님), 복수 열 저장 정렬 UI 등은 추가 이식/검증 대상이다. 현재 저장 정렬 UI는 한 열을 선택하며 엔진/프리셋의 복수 열 기능은 유지한다.

Qt/EXE의 동작 검증과 사용자의 실제 Windows/보안 정책에서 실행 검증을 구분한다. EXE는 현재 코드서명 인증서로 서명하지 않는다. 폐쇄망의 실행 파일 반입/실행 정책에 따라 별도 허용이 필요할 수 있다. 인터넷 연결 없이 사용할 구조이지만 운영체제 파일 선택기·보안 프로그램의 동작까지 앱이 제어하지는 않는다.

## 검증·빌드

- `python -m pytest -q tests/test_desktop.py`: 네이티브5종(실제 Qt 모델/편집/undo/선택 유지,15번10부서300행 취합,13·14번 수식/값/행 단위,12번1만행 가상 모델,작업 스레드 저장/입력 파일 보호).
- `python desktop_entry.py --smoke-test artifacts/native-smoke.json`: 오프스크린 Qt 창·화면PNG·실제 XLSX·취합·1만행을 검증한다. 웹 브라우저 검사가 아니다.
- `.github/workflows/windows-desktop.yml`: Windows runner/Python3.12 x64, 고정 네이티브 의존성, PyInstaller6.12.0 `--onefile --windowed`, 네이티브 검사 후 실제 EXE를 `--smoke-test`로 다시 실행. 성공한 EXE·Windows 검사 JSON·PNG·SHA256을 아티팩트에 저장한다.
- Linux에서 확장자만 바꿔 EXE로 제공하지 않는다. Windows CI 성공 여부/파일 해시/릴리스 링크는 실제 산출 후 기록한다.

## 확인된 결과와 남은 확인

2026-11-02 Linux: 전체 pytest109개, 네이티브5개 포함 통과. 자체 검사에서도1만행·Qt 위젯167→167 유지, 합성3열1만행 로드 약1.39초/여러 위치 스크롤 약0.17초(이 환경 한 번의 관측, Windows/실파일 보장 아님). 원본 스타일·실제 수식·기본 편집OFF·직접 편집·undo/redo·합쳐보기 체크·6테마·취합 확인. Windows 빌드/EXE 검증 완료: 소스8ff26dd, [성공한 실행](https://github.com/BBulMushroom/ai-excel-compare-project/actions/runs/41418899756), [빌드 파일](https://github.com/BBulMushroom/ai-excel-compare-project/actions/runs/41418899756/artifacts/13128752264). 실제 Windows2025Server에서 만들어진 EXE를 실행해 검사했다. 크기46,529,404bytes(44.4MiB), SHA256 `90fff415148a525ef4a42e8e304979b8f9d3a034ac130d940da7d478abae6b93`. 네이티브5개 및 패키지 자체 검사 통과.1만행 위젯168→168, 관측 로드0.760초·스크롤순회0.065초(합성3열·해당 CI1회, 실제 업무 성능 보장 아님). [실제 화면](images/native-v01.png)에서 한글·기본 아이콘을 확인했다.

웹판 T35/T36: tooltip title을 같은 값으로 반복 설정하지 않게 하고 DOM 변경마다 모든 iframe에 테마 메시지를 보내지 않도록 보완했다. 새 iframe이 추가된 경우만 그 동기화를 수행한다. Node에서 동일 title 반복50회 시1번만 실제 쓰기 확인. 기본 title 툴팁의 표시 시간은 브라우저가 정하므로 강제 조절했다고 주장하지 않는다. 기존 Chromium 실행 거절로 웹 실기 재현은 아직 미완료다.

덱스: Android에서는 Windows EXE를 직접 실행할 수 없다. 기존 Streamlit은 공통 엔진 기능 확인용으로 유지 가능하나 네이티브 화면과 같지 않다. 네이티브 UI를 덱스 브라우저에서 보려면 클라우드 Linux/Windows 데스크톱+인증된 웹 원격접속(noVNC/Guacamole 등)이 별도로 필요하다. 현재 환경에는 Xvfb/x11vnc/noVNC와 외부 접속 경로가 준비되어 있지 않다. 이 문서는 원격 접속이 제공됐다는 의미가 아니다.

Windows 초기 검사에서 Asia/Seoul 시간대 데이터 누락으로 저장이 실패했다. tzdata2025.2와 해당 리소스를 EXE에 포함하도록 수정했다. 자동 검사 오류 대화상자가 대기를 만들지 않도록 offscreen에서는 오류를 결과로 반환하며 일반 실행의 오류 안내는 유지한다. Windows 테스트에서 읽은 파일은 BytesIO로 열어 대상 파일 핸들이 저장 교체를 방해하지 않도록 했다.

초기 EXE 기능 검사는 통과했지만 Windows offscreen 캡처에서 한글이 사각형으로 나타나 추가 검증했다. Noto Sans KR(TTF+OFL)을 포함하고 A/가 글리프 지원을 자체 검사에 넣어 해결했다. 글꼴에 없던 일부 도구 아이콘은 QStyle 기본/Qt 직접 그리기로 바꿨다. 검사 통과와 실제 화면 읽기 가능 여부를 구분해서 확인했다.

배포 업로드는 로컬 gh release create의 uploads.github.com 인증이401로 실패했고, 실패한 릴리스가 남아있지 않아 첨부 전용 첫 작업도 release not found로 실패했다. `.github/workflows/publish-native.yml`에서 검증된 소스8ff/성공 run/PE64/해시/검사 결과를 확인한 후 저장소 GITHUB_TOKEN으로 릴리스를 생성 또는 첨부하도록 보완했다. 검증된 EXE를 다시 빌드하는 작업이 아니다. 토큰 값을 읽거나 문서에 남기지 않았다.

사용자는 DeX에서 웹 테스트를 계속하면서 네이티브 추가/수정이 매번 한 시간 걸릴지 우려했다. 최초 이식·Windows 빌드 구성·플랫폼 문제 해결의 비용과 반복 수정 비용을 구분해 설명했다. 공통 엔진은 공유하지만 두 UI를 모두 유지하면 작업이 두 벌이 된다. 이번 네이티브 테스트판은 마무리하되 향후 주력 UI/배포 주기는 다시 판단할 항목이며 작은 변경마다 EXE를 만들기로 확정하지 않았다. 별도 원격 데스크톱 환경은 만들지 않았다.

최종 테스트 릴리스 게시 완료: https://github.com/BBulMushroom/ai-excel-compare-project/releases/tag/native-test-v0.1.0 . EXE 직접 링크는 releases/download/native-test-v0.1.0/ExcelReview.exe이며, 검사JSON/화면PNG/SHA256도 첨부했다. GitHub API에서 draft=false/prerelease=true와 EXE 크기46,529,404bytes 및4개 첨부를 확인했다. 릴리스의 바이너리는 검증 소스8ff26dd에서 만들었으며 이후 main의 배포/인수인계 문서 변경으로 다시 빌드하지 않았다.
