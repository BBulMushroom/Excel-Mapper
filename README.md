# Excel Mapper

서로 다른 양식의 엑셀을 연결·비교하고, 승인한 변경만 수정본으로 저장하는 **Windows 데스크톱 프로그램**입니다. `ExcelMapper.exe` 한 파일로 실행하며 웹 브라우저·서버·외부 AI API를 사용하지 않습니다. 현재 버전은 1.000입니다.

- EXE는 저장소의 Releases에서 받습니다.
- 사용법·범위: [docs/NATIVE_TEST.md](docs/NATIVE_TEST.md), 릴리스 이력: [docs/NATIVE_RELEASE_NOTES.md](docs/NATIVE_RELEASE_NOTES.md)
- 작업 상태·결정 사항: [CONTEXT.md](CONTEXT.md), 요청 목록: [docs/BACKLOG.md](docs/BACKLOG.md)

## 사용 방법

1. **파일**에서 원본 1개와 비교파일 1개 이상을 엽니다. 파일을 창에 끌어다 놓아도 됩니다(왼쪽 원본, 오른쪽 비교). 샘플은 **더보기 → 테스트 샘플**에서 불러옵니다.
2. **① 원본 / ② 비교 / ③ 수정**이 기준값으로 정렬되어 표시됩니다. 자동 선택된 기준 키와 열 연결을 확인하고 필요하면 바꿉니다. **합쳐보기**는 세 표를 한 표로 보여 줍니다.
3. 추가·수정·삭제 버튼과 각 행의 체크박스로 반영할 변경을 고릅니다. 삭제는 기본 선택 해제입니다. **합치기 방식**은 셀 단위/행 단위입니다.
4. 단일 비교는 **수정 다운로드**, 여러 파일 취합은 **반영 후 다음 → 최종 다운로드**를 사용합니다.

편집 켜짐 상태에서는 ③ 수정/합쳐보기 셀을 더블클릭해 값을 직접 고칠 수 있으며, 직접 입력한 값은 해당 셀의 반영 선택보다 우선합니다.

| 변경 | ① 원본 | ② 비교 | ③ 수정 |
| --- | --- | --- | --- |
| 수정 | 이전 값 셀 주황색 | 새 값 셀 주황색 | 반영한 셀 주황색 |
| 추가 | 빈자리 | 행 전체 초록색 | 반영한 행 초록색 |
| 삭제 | 행 전체 빨간색 | 빈자리 | 반영 시 빈자리 |

**열·행 숨기기(엑셀 방식):** 열 머리글을 우클릭하면 `열 숨기기`(여러 열을 선택했으면 선택한 열 전체), 숨긴 열이 이웃에 있으면 `숨기기 취소`가 나옵니다. 숨긴 자리에는 가는 이중선과 가운데 손잡이가 남고, 그 표시를 우클릭해도 `숨기기 취소`가 나옵니다. 행은 행 번호 칸을 우클릭합니다. 필터·정렬은 머리글의 ▼ 버튼으로 엽니다. 화면에서만 숨기는 기능이라 저장 파일에는 영향이 없습니다.

결과 파일에는 `변경 이력` 시트 하나에 처리 내역이 누적됩니다. 연결하지 않은 원본 열과 기본 셀 서식은 유지합니다.

## 단축키

| 키 | 동작 |
| --- | --- |
| Ctrl+F | 검색 |
| Ctrl+S | 수정 다운로드 |
| Ctrl+Enter | 반영 후 다음 |
| Ctrl+Z / Ctrl+Y | 실행 취소 / 다시 실행 |
| Ctrl+Q / Ctrl+E | 이전 / 다음 변경 |
| Space | 현재 변경 반영 전환 |
| Ctrl+C | 선택한 셀 복사 |
| Ctrl+0 / Ctrl+9 | 선택한 열 / 행 숨기기 (**숨기기** 메뉴에서 다시 표시) |
| Ctrl+휠 | 표 배율 |

## 명령줄 사용 (자동화·AI 연동)

창을 열지 않고 같은 엔진으로 비교·저장합니다. 결과는 창에서 같은 선택으로 저장한 것과 같습니다.

```bash
# 분석만 (JSON): 건수, 기준 키, 열 연결, 변경 목록
ExcelMapper.exe --compare 원본.xlsx 비교.xlsx --json

# 추가·수정만 반영해 저장 (삭제는 --apply delete 또는 all 로 명시해야 반영)
ExcelMapper.exe --compare 원본.xlsx 비교.xlsx --out 결과.xlsx

# 행 단위(변경된 행을 비교본 한 행 전체로 복사), 키·열 연결 지정, 여러 비교 파일 순서대로 취합
ExcelMapper.exe --compare 원본.xlsx 비교1.xlsx 비교2.xlsx --mode row --keys 코드 --map "수량=Qty" --out 결과.xlsx --report 분석.json
```

- 옵션: `--apply add,edit,delete|all|none`, `--copy normal|values`, `--sheet-original/--sheet-comparison`, `--header-*`, `--start-*`, `--changes-limit N`
- 종료 코드: 0 성공, 2 인자 오류, 3 파일 오류, 4 비교·저장 실패. 입력 파일은 덮어쓰지 않습니다.
- Windows에서 EXE는 콘솔 창 없는 프로그램이라 출력이 안 보일 수 있습니다. 터미널에서 실행하면 그 터미널에 출력하고, `--report 파일.json`은 항상 파일로 저장합니다. `python cli.py ...`도 같습니다.

## 개발·검증

Python 3.12 기준입니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt -r requirements-desktop.txt
QT_QPA_PLATFORM=offscreen python -m pytest -q
python desktop_entry.py
```

- 비교 엔진: `compare.py`, `excel_copy.py`, `comparison_rules.py`, `collection_flow.py` (UI와 분리)
- 데스크톱 UI: `desktop/`, 진입점 `desktop_entry.py`
- 샘플: `samples.py`, `sample_catalog.py`, `sample_data/`
- 성능 측정: `benchmarks/`, EXE 패키징: `tools/package_native.py` 및 `.github/workflows/windows-desktop.yml`

## 지원 범위와 제한

- XLSX·XLSM·XLS·CSV를 지원합니다. 병합셀은 읽기와 행 추가·삭제를 지원하지만 병합된 칸의 값 수정 저장은 지원하지 않습니다. 빈·중복 열 제목은 지원하지 않습니다.
- 앞뒤 공백을 제외하고 숫자 1과 문자 "1"을 같게 비교합니다. 문자 "001"은 별개로 보존됩니다.
- 앱은 수식을 계산하지 않습니다. 일반 복사는 실제 수식을 유지하고 상대참조를 이동합니다. 값만 복사는 비교파일에 저장된 계산값을 사용하며 계산값이 없으면 저장을 차단합니다.
- 수식이 있는 파일의 행 삭제, 수식이 있는 시트의 정렬, Excel 표(Table)가 있는 시트의 행 추가·삭제·정렬은 차단합니다. openpyxl이 임의의 수식 참조를 안전하게 다시 쓰지 못하기 때문입니다.
- 새 행은 마지막 행 뒤에 추가하고 직전 행의 셀 서식을 복사합니다. 원본 전용 열은 새 행에서 빈 값입니다.
- openpyxl이 지원하지 않는 Excel 고급 개체, 외부 참조, 조건부 서식의 완전한 보존은 보장하지 않습니다. 원본은 항상 따로 백업하고 결과를 확인하세요.
- 기본 정렬은 없음입니다. IP 정렬은 IP 열을 선택할 때 사용합니다. 비교는 선택한 시트에만 적용됩니다.
- 모든 샘플의 장비·계정·비밀번호는 가상 데이터입니다.
