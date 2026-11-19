# Native test 0.4 — 승인 작업 T41~T69

2026-11-03. 사용자 최신 `해`로 승인. DeX에서 Windows EXE를 보는 방법은 사용자가 해결했으므로 원격 환경을 만들지 않았다. 기존 웹 앱을 감싼 프로그램이 아닌 PySide6 네이티브 EXE를 계속 사용한다. 엔진 v0.35.0 유지, 네이티브 UI 테스트판 버전0.4.0.

## 완료 구현

- 스크롤: GridModel의 표시 상태/role 캐시, 행 인덱스 직접 조회, 단순 텍스트 셀 빠른 그리기, DPR을 보존한 인디케이터 이미지 캐시. 휠 입력은 짧은 연속 보간으로 처리하고 방향 전환/직접 드래그는 즉시 반응한다. Ctrl+휠 배율과 Shift+휠 가로 이동 유지.
- 선택: 체크박스 유지. 셀 단위 수정은 해당 변경 셀만, 행 단위는 해당 행 묶음. 추가/삭제는 행 단위. 본문 좌클릭 확인/강조, 우클릭 또는 Space 반영 전환, 더블클릭은 편집. 변경 목록도 우클릭/Space로 전환한다. 체크박스 직접 좌클릭은 계속 동작한다.
- 탐색: Ctrl+Q 이전 변경/Ctrl+E 다음 변경. 현재 표시 정렬 순서·선택 단위대로 이동하며 해제된 변경은 제외한다. 입력창의 문자/공백과 IME 조합은 보존한다.
- 편집: 첫 클릭 선택, 더블클릭 전체 선택 편집, 선택된 셀을 느리게 재클릭하면 그 문자 위치로 커서. 편집기 글꼴·배율·높이·여백 일치. 편집은 기본 꺼짐이며 수정/합쳐보기의 수정 가능한 셀만 허용한다.
- 검색: 한글 preedit 동안 검색 타이머를 멈추고 commit 후 적용한다. refresh에서 입력 중인 검색 텍스트를 덮어쓰지 않는다. 검색 아이콘 위치 보완.
- 글꼴 선택 즉시 QApplication/기존 자식 위젯/그리드에 적용, 표시 캐시와 자동 폭 갱신. 폰트 뒤 샘플 글자 숨김은 별도 확정되지 않아 변경하지 않았다.
- 자동 폭: 행/기준값에 과도한 일괄 최소65px/+8px 제거. 제목 팝업 버튼·주소·체크 폭을 포함하고 합쳐보기 rich text의 실제 크기를 사용한다. 줄바꿈 OFF면 rich text도 강제 줄바꿈하지 않는다. 기준값은 체크 여부와 관계없이 텍스트 시작 위치를 맞춘다.
- 보기 전환: 보이는 셀의 pixmap을 한 화면 캡처에서 분리하고 대응 셀로 이동시킨다. 변경된 원본/비교 셀은 합쳐보기의 위/아래로 합쳐지고 오른쪽 수정 셀은 변경 카드로 이동한다. 글자를 가로로 늘리지 않는다.360ms 전환·최종 화면 교차 표시, DPR 유지. 새 파일은 맨 위, 보기 전환은 첫 표시 행과 행 안 offset 보존.
- 상단: 데이터 위치 명칭, 파일/더보기 꺾쇠 제거, 기준 키 바로 옆 고정 높이 적용 버튼(초안 변경 시 강조), 설정 접기/편집 우측, 꺼진 표 표시 버튼 점선. 추가/수정/삭제 숫자 버튼은 전체 건수로 폭 예약해 아이콘이 움직이지 않는다. 실행 취소/다시 실행 아이콘 중앙/크기 보완.
- 필터: 제목 본문은 열 선택, 오른쪽 작은 ▼ 버튼만 팝업 열기/▲·재클릭 닫기. 정렬 ↑/↓·굵기 유지. 선택값 외 조건에서는 체크 목록/전체 선택을 숨기고 높이를 내용에 맞춘다. 열 연결 체크의 int2/enum 비교 오류 수정·셀 전체 클릭, 드롭다운과 표 행 높이 정렬. 드롭다운/상단 팝업은 둥근 모서리와130ms 펼침.
- 행 단위 변경 카드: 행 주소·기준값·수정 개수, 항목/원본/비교 열로 세부 변경을 표시한다. 셀 단위는 기존 셀 주소 카드 유지.
- 프리셋 클릭 시 기준 키/합치기/복사/비교 조건/결과 순서 요약, 상세 보기에서 열 연결·원본/비교 범위. 클릭만으로 적용하지 않고 불러오기를 누른다.

## 샘플 정리

네이티브 메뉴는 새1~9번으로 정리했다. `sample_catalog.py`가 사용자 번호와 기존 fixture를 분리한다. 기존 웹 샘플과 회귀 검사의 내부 번호는 바꾸지 않았다.

|새 번호|기존 번호|목적|
|---|---|---|
|1|1|신규 자료만 추가|
|2|2|전체 목록 수정/추가/삭제|
|3|4|복합 기준 키|
|4|5|다른 열 이름/양식|
|5|12|1만 행|
|6|13|SUM 수식|
|7|14|다른 시트 참조|
|8|15|빈 원본+10부서 신규 예산 취합|
|9|16|설비대장 원본500행을10명에게 배포하고 회신 취합|

새9번은 `sample_data/collaboration/`에 가상 XLSX11개를 동봉한다. 실제 사용자 자료가 아니다. 각 회신의 담당자/여러 수정·일부 목록/추가를 확인할 수 있다. **3자 병합·충돌 자동 해결 기능을 추가한 것은 아니다.** 동일 원본에서 나온 회신을 순차 반영하면 앞서 반영한 값이 다음 회신의 과거 값으로 돌아갈 수 있으며, 샘플 선택 설명에도 이를 명시했다.

## 검증과 한계

로컬 전체 pytest124개/Node4개 통과 후 자동 폭 회귀를 추가해 최종 Qt21개 통과. `tests/test_desktop_v04.py`에 IME commit/preedit, Space·우클릭 선택 단위, 필터 버튼/높이, 열 연결 체크·즉시 폰트, 건수 버튼·샘플 목록 회귀를 추가했다. Qt 캡처는 `tools/capture_native_preview.py`로 같은 가상 예산대장의6테마/2보기를 생성한다. 테마 hover용 동봉 PNG6개도 같은 화면으로 갱신한다. Windows EXE 최종 빌드/실제 frozen 자체 검사 결과는 아래 기록한다.

스크롤 동일조건 전후 측정은 [PERFORMANCE](PERFORMANCE.md) 참고. Linux/offscreen 처리 시간으로 Windows FPS/실제 마우스 체감을 보장하지 않는다. Windows 실제 한글 IME·사용자 파일·고배율 장시간 체감은 사용자 재확인 대상이다. 웹 전체 고급 기능 동등성 완료판은 아니다. 수식 계산 엔진·고급3자 충돌 병합은 추가하지 않았다.

## 실패한 시도·해결

- 건수 버튼을 직접 paintEvent/QIcon으로 그리는 두 방법은 Qt 프로세스 segfault가 발생해 폐기했다. 기본 QToolButton 위에 마우스 이벤트를 전달하는 QLabel2개를 배치해 해결했고 이후 Qt/전체 검사 통과.
- 새 rich text sizeHint의 잘못된 변수 참조·invalid index 접근을 수정했다. 기본 테이블 edit 가상함수 재정의는 제거하고 delegate 초기 커서 설정만 사용한다.
- 첫 Windows 빌드41532756062/fe08fc1의 자체 검사 캡처에서 합쳐보기 전환 후 수정값·행 주소가 잘리는 것을 확인해 게시하지 않았다. 보기 모드/글꼴 변경 시 자동 폭 재계산을 추가하고, 사용자가 직접 조절한 열은 이름으로 추적해 유지한다. 새 회귀에서 자동 폭 복원 중 원본 view만 수동 폭이 유지되지 않는 것을 발견해 동기화 대상에 source도 포함해 해결했다.
- 헤더 기본 paintSection이 painter 상태를 바꿔 작은 필터 버튼이 보이지 않던 문제는 기본 호출 전후 save/restore로 해결했다.
- 이전 검사의 기준값 좌클릭 일괄 토글 기대는 최신 셀 단위/우클릭 요구와 충돌하여 새 요구에 맞게 수정했다. 샘플 검사의 sheet 인수 누락도 보완했다.

## 실행/재검증

```bash
/workspace/excel-compare-env/.venv/bin/python -m pytest -q
node tests/js_review_controls.cjs
/workspace/excel-compare-env/.venv/bin/python desktop_entry.py --smoke-test /tmp/native04-smoke/report.json
/workspace/excel-compare-env/.venv/bin/python tools/capture_native_preview.py --output /tmp/native04-preview
```

Windows는 `.github/workflows/windows-desktop.yml`에서 Qt21개→PyInstaller 단일 EXE→frozen 자체 검사/PNG/해시 순서다. 가상 샘플/6테마 PNG/아이콘/정적 한글 폰트/tzdata를 동봉하며 Streamlit·QtWebEngine을 제외한다. 검증된 run의 정확한 source SHA로 `publish-native.yml`을 실행한다. 토큰 값은 기록하지 않는다.

## 최종 Windows 실행 검사

소스 `1cb4c8fd84fd602c6d89f76084902330218fa3ba`, [빌드41533737720](https://github.com/BBulMushroom/ai-excel-compare-project/actions/runs/41533737720). Windows Server2025/Python3.12 x64 네이티브21개·패키지 EXE 자체 검사19항목 통과. 실제 EXE를 실행한 PNG/JSON/해시를 내려받아 PE64·한글/아이콘·주소·수정값 표시를 확인했다. [Windows 화면](images/native-v04-windows.png), [같은 예제 Linux 나눠보기](images/native-v04-split.png)/[합쳐보기](images/native-v04-merged.png)와 구분한다.

EXE45,277,088bytes(43.2MiB), SHA256 `53cdb7434fb9ed010716ba1d17beb4f0e6eb58c3b62154d49d3ca1873dfad0e0`. 합성3열1만행 위젯181→181, CI1회 로드2.126초/스크롤순회0.018초. 이 자체 검사의 순회는 앞 PERFORMANCE의 실제 샘플 휠 측정과 조건이 다르므로 서로 개선율로 비교하지 않는다. Windows 실제 IME/마우스 장시간 체감은 자동 검사와 구분한다.

[0.4 릴리스](https://github.com/BBulMushroom/ai-excel-compare-project/releases/tag/native-test-v0.4.0) 게시 작업41534223179 성공. GitHub API에서 target1cb4c8f/draft=false/prerelease=true·EXE45,277,088bytes·4첨부를 확인했다. 기존0.3/0.2/0.1은 보존한다. 이후 main 문서 갱신은 EXE 재빌드 대상이 아니다.
