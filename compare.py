"""Excel Mapper's UI-independent workbook mapping and update engine."""
from collections import Counter
from copy import copy
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from io import BytesIO
from functools import lru_cache
from ipaddress import ip_address
import math
import comparison_rules
import re
from zipfile import ZipFile
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.workbook.properties import CalcProperties
import excel_copy
import fastread

VERSION = '0.35.0'
LOG_SHEET = '변경 이력'
LOG_HEADERS = ['변경 유형', '키값', '대상 열', '변경 전', '변경 후', '위치', '비교 파일', '처리 일시']


def normalized(value):
    if value is None:
        return ''
    if type(value) is str:
        return value.strip()
    if isinstance(value, float) and math.isnan(value):
        return ''
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value)) if float(value).is_integer() else str(value)
    return str(value).strip()


@dataclass
class Table:
    sheet: str
    header_row: int
    start_row: int
    headers: list
    rows: list
    physical_rows: list
    formula_cells: dict = field(default_factory=dict)
    # Rows that are not data (section titles, subtotals, sign-off boxes): {physical row: {header: value}}.
    structure_rows: dict = field(default_factory=dict)
    # Cells whose value was copied from the top-left cell of a merged range: {physical row: [headers]}.
    filled_cells: dict = field(default_factory=dict)
    # Merged ranges in the data area as (first row, last row, first column, last column), for drawing them merged.
    merged_ranges: list = field(default_factory=list)


def is_sequence(column):
    return normalized(column).replace(' ', '') == '순번'


def load(data):
    try:
        with ZipFile(BytesIO(data)) as archive:
            macros='xl/vbaProject.bin' in archive.namelist() or b'macroEnabled.main+xml' in archive.read('[Content_Types].xml')
        return openpyxl.load_workbook(BytesIO(data),keep_vba=macros)
    except Exception as exc:
        raise ValueError('엑셀 파일을 읽을 수 없습니다. 암호가 없는 .xlsx 파일인지 확인하세요.') from exc


def sheet_names(data):
    """Read only workbook metadata; never materialize worksheet cells."""
    try:
        with ZipFile(BytesIO(data)) as archive:
            root=ElementTree.fromstring(archive.read('xl/workbook.xml'))
            return [node.attrib['name'] for node in root.findall('{*}sheets/{*}sheet')]
    except Exception as exc:
        raise ValueError('엑셀 파일을 읽을 수 없습니다. 암호가 없는 .xlsx 파일인지 확인하세요.') from exc


SUMMARY_LABEL=re.compile(r'(소계|합계|총계|누계|^계)$')


def table_from_sheet(ws, header_row=1, start_row=2):
    ranges=list(ws.merged_cells.ranges)
    bad=next((r for r in ranges if r.min_row<=header_row<=r.max_row and (r.min_row!=r.max_row or r.min_col!=r.max_col)),None)
    if bad:
        raise ValueError(f'제목 행({header_row}행)의 {bad.coord} 칸이 병합되어 있습니다(2단 제목). 2단 제목은 아직 지원하지 않습니다. 엑셀에서 이 병합을 해제하거나, 데이터 위치에서 제목 행 번호를 확인하세요.')
    # Iterating the rectangular dimensions creates millions of empty cells when
    # a workbook has formatting far below/beside the actual data.
    populated=[c for c in ws._cells.values() if c.value is not None]
    values={(c.row,c.column):c.value for c in populated}
    formulas={(c.row,c.column) for c in populated if c.data_type=='f'}
    data_ranges=[r for r in ranges if r.min_row>=start_row]
    if not data_ranges:return table_from_cells(ws.title,values,formulas,header_row,start_row)
    width=max((c for r,c in values if r==header_row),default=0)
    structure=set()
    rows_with_values={}
    for r,c in values:
        if r>=start_row:rows_with_values.setdefault(r,[]).append(c)
    for row,columns in rows_with_values.items():
        across=[m for m in data_ranges if m.min_row<=row<=m.max_row and m.min_col<m.max_col]
        if any(m.min_col==1 for m in across):structure.add(row);continue
        if across and all(any(m.min_col<=c<=m.max_col for m in across) for c in columns):structure.add(row);continue
        labels=[values.get((row,c)) for c in range(1,min(width,3)+1)]
        if any((row,c) in formulas for c in columns) and any(isinstance(v,str) and SUMMARY_LABEL.search(v.strip()) for v in labels):structure.add(row)
    filled={}
    for m in data_ranges:
        top=values.get((m.min_row,m.min_col))
        if top is None or (m.min_row,m.min_col) in formulas:continue
        for row in range(m.min_row,m.max_row+1):
            if row in structure:continue
            for col in range(m.min_col,m.max_col+1):
                if (row,col)==(m.min_row,m.min_col) or (m.min_col<m.max_col and col!=m.min_col):continue
                values[(row,col)]=top;filled.setdefault(row,set()).add(col)
    kept={k:v for k,v in values.items() if k[0] not in structure}
    t=table_from_cells(ws.title,kept,{p for p in formulas if p[0] not in structure},header_row,start_row)
    t.structure_rows={row:{h:values.get((row,i)) for i,h in enumerate(t.headers,1)} for row in sorted(structure)}
    t.merged_ranges=[(m.min_row,m.max_row,m.min_col,m.max_col) for m in data_ranges]
    t.filled_cells={row:[t.headers[c-1] for c in sorted(cols) if c<=len(t.headers)] for row,cols in filled.items()}
    for row in structure:
        names=[t.headers[c-1] for r,c in formulas if r==row and c<=len(t.headers)]
        if names:t.formula_cells[row]=names
    return t


def letters(columns, limit=6):
    names=[get_column_letter(c) for c in columns]
    return ', '.join(names[:limit])+(f' 외 {len(names)-limit}개' if len(names)>limit else '')


def header_problem(headers, header_row, values):
    """Name the exact columns whose title is empty or repeated."""
    parts=[]
    empty=[c for c,h in enumerate(headers,1) if not h]
    if empty:
        filled=[c for c in empty if any(col==c and row>header_row for row,col in values)]
        parts.append(f'{letters(empty)}열 이름이 비어 있습니다'+(f'(이름 없이 값이 있는 열: {letters(filled)}열)' if filled else ''))
    seen={}
    for c,h in enumerate(headers,1):
        if h:seen.setdefault(h,[]).append(c)
    parts+=[f'{letters(cols)}열 이름이 \'{h}\'(으)로 같습니다' for h,cols in seen.items() if len(cols)>1]
    return f'제목 행({header_row}행): '+' / '.join(parts)+'. 엑셀에서 열 이름을 고치거나(앞뒤 공백만 다른 이름도 같은 이름으로 봅니다), 데이터 위치에서 제목 행 번호를 확인하세요.'


def table_from_cells(title, values, formula_positions, header_row=1, start_row=2):
    """Build a Table from {(row, column): value}; shared by the openpyxl and the fast reader."""
    if start_row <= header_row:
        raise ValueError(f'데이터 시작 행({start_row}행)이 제목 행({header_row}행)보다 뒤여야 합니다. 데이터 위치에서 행 번호를 바꾸세요.')
    if not values:
        raise ValueError(f'시트 \'{title}\'에 값이 하나도 없습니다. 데이터 위치에서 다른 시트를 고르세요.')
    width=max(column for _,column in values)
    headers=[normalized(values.get((header_row,c))) for c in range(1,width+1)]
    if any(not h for h in headers) or len(set(headers))!=len(headers):
        raise ValueError(header_problem(headers,header_row,values))
    positions=sorted({row for row,_ in values if row>=start_row})
    rows=[dict(zip(headers,[values.get((pos,c)) for c in range(1,width+1)])) for pos in positions]
    formulas={}
    for row,column in sorted(formula_positions):
        if row>=start_row:formulas.setdefault(row,[]).append(headers[column-1])
    return Table(title,header_row,start_row,headers,rows,positions,formulas)


def unsupported_objects(data):
    """Excel objects the library cannot read back, so the saved file may lack them (cell values and styles are kept).

    Reads only the archive's part names and searches the sheet/drawing XML for a few markers.
    """
    try:archive=ZipFile(BytesIO(data))
    except Exception:return []
    names=archive.namelist();found=[]
    def any_name(prefix):return any(n.startswith(prefix) for n in names)
    shapes=0
    for name in names:
        if name.startswith('xl/drawings/drawing') and name.endswith('.xml'):
            shapes+=len(re.findall(rb'<(?:\w+:)?(?:sp|cxnSp|grpSp)[ >]',archive.read(name)))
    if shapes:found.append(f'도형·텍스트 상자 {shapes}개')
    if any_name('xl/slicers/') or any_name('xl/slicerCaches/') or any_name('xl/timelines/'):found.append('슬라이서·시간 표시 막대')
    if any_name('xl/ctrlProps/') or any_name('xl/activeX/'):found.append('양식 컨트롤·ActiveX')
    if any_name('xl/embeddings/'):found.append('삽입된 개체(OLE)')
    if any_name('xl/threadedComments/'):found.append('스레드 댓글(일반 메모로 남음)')
    if any_name('xl/charts/chartEx'):found.append('새 차트 형식(깔때기·폭포 등)')
    markers={b'sparklineGroup':'스파크라인(미니 차트)',b'x14:conditionalFormatting':'확장 조건부 서식',b'x14:dataValidations':'확장 데이터 유효성(다른 시트 목록 등)'}
    present=set()
    for name in names:
        if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
            xml=archive.read(name)
            for marker in markers:
                if marker in xml:present.add(marker)
    found.extend(markers[m] for m in markers if m in present)
    return found


def close_workbook(wb):
    wb.close()
    if wb.vba_archive is not None:wb.vba_archive.close()


def table(data, sheet, header_row=1, start_row=2, fast=True):
    if fast:
        # Plain sheets (no formulas or merged cells) are read about 2.4x faster; anything else uses openpyxl below.
        try:values=fastread.read_cells(data,sheet)
        except Exception:values=None
        if values is not None:return table_from_cells(sheet,values,set(),header_row,start_row)
    wb=load(data)
    if sheet not in wb.sheetnames:
        raise ValueError(f'시트 \'{sheet}\'가 파일에 없습니다. 데이터 위치에서 시트를 다시 고르세요.')
    try:
        return table_from_sheet(wb[sheet],header_row,start_row)
    finally:
        close_workbook(wb)


@dataclass
class ExportResult:
    data: bytes
    table: Table
    history: list
    order: list | None = None


def type_name(value):
    if value is None: return 'empty'
    if isinstance(value, bool): return 'bool'
    if isinstance(value, (int, float)): return 'number'
    if isinstance(value, datetime): return 'date'
    return 'text'


def column_profile(t, column):
    values=[row[column] for row in t.rows if normalized(row[column])]
    return ({normalized(v) for v in values},Counter(map(type_name,values)),len(values))


def score_profiles(a,b,ap,bp):
    aset,at,an=ap; bset,bt,bn=bp
    overlap=len(aset & bset)/max(1,min(len(aset),len(bset)))
    name=SequenceMatcher(None,re.sub(r'\s+','',a).lower(),re.sub(r'\s+','',b).lower()).ratio()
    types=sum(min(at[t]/max(1,an),bt[t]/max(1,bn)) for t in set(at)|set(bt))
    unique=min(len(aset)/max(1,an),len(bset)/max(1,bn))
    score=round(100*(.2*name+.2*types+.6*overlap))
    return {'원본 열':a,'비교 열':b,'추천 점수':score,'공통값 비율':round(overlap*100),'고유값 비율':round(unique*100),'추천 이유':f'이름 {name:.0%} · 형식 {types:.0%} · 공통값 {overlap:.0%} (전체 데이터)'}


def mapping_score(left,right,a,b):
    return score_profiles(a,b,column_profile(left,a),column_profile(right,b))


def recommend(left,right,source_columns=None,target_columns=None):
    sources=left.headers if source_columns is None else source_columns
    targets=right.headers if target_columns is None else target_columns
    if not sources or not targets:return []
    ap={a:column_profile(left,a) for a in sources}
    bp={b:column_profile(right,b) for b in targets}
    return sorted([score_profiles(a,b,ap[a],bp[b]) for a in sources for b in targets],key=lambda x:-x['추천 점수'])


def validate_mapping(left, right, mapping, keys):
    if any(is_sequence(k) or is_sequence(mapping.get(k,'')) for k in keys): raise ValueError('순번은 비교 기준으로 사용할 수 없습니다. 다른 기준 열을 선택하세요.')
    if not mapping or not keys: raise ValueError('연결할 열과 하나 이상의 기준 키를 선택하세요.')
    if len(set(mapping.values())) != len(mapping):
        twice=sorted({b for b in mapping.values() if list(mapping.values()).count(b)>1})
        raise ValueError('비교 열 하나를 여러 원본 열에 연결할 수 없습니다: '+', '.join(f"비교 '{b}' ← 원본 "+'·'.join(f"'{a}'" for a,v in mapping.items() if v==b) for b in twice)+'. 열 연결에서 하나만 남기세요.')
    missing=[f"원본 '{a}'" for a in mapping if a not in left.headers]+[f"비교 '{b}'" for b in mapping.values() if b not in right.headers]
    if missing: raise ValueError('연결한 열을 파일에서 찾을 수 없습니다: '+', '.join(missing[:6])+'. 열 이름이 바뀌었으면 열 연결을 다시 확인하세요.')
    if any(k not in mapping for k in keys): raise ValueError('기준 키는 연결된 원본 열에서 선택하세요.')


def indexed(t, columns):
    found = {}
    for i, row in enumerate(t.rows):
        values = tuple(normalized(row[c]) for c in columns)
        line=t.physical_rows[i]
        empty=[c for c,v in zip(columns,values) if not v]
        if empty: raise ValueError(f"시트 '{t.sheet}' {line}행: 기준 키 '"+"', '".join(empty)+"' 칸이 비어 있습니다. 값을 채우거나 비교 설정에서 다른 기준 키를 고르세요.")
        formula=next((c for c in columns if isinstance(row[c], str) and row[c].startswith('=')),None)
        if formula: raise ValueError(f"시트 '{t.sheet}' {line}행: 기준 키 '{formula}' 열에 수식이 있어 키로 쓸 수 없습니다. 비교 설정에서 다른 열을 기준 키로 고르세요.")
        if values in found:
            label=' + '.join(f"{c} '{v}'" for c,v in zip(columns,values))
            raise ValueError(f"시트 '{t.sheet}': 기준 키 {label} 값이 {t.physical_rows[found[values][0]]}행과 {line}행에 똑같이 있습니다. 비교 설정에서 기준 키에 열을 더하거나(복합 키), 엑셀에서 중복을 정리하세요.")
        found[values] = (i, row)
    return found


CELL_REF=re.compile(r"(?<![A-Za-z_\d])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\d(])")


def relative_formula(text, row):
    """`=E8*F8` on row 8 and `=E7*F7` on row 7 are the same formula: relative row references become offsets."""
    return CELL_REF.sub(lambda m:m.group(1)+m.group(2)+m.group(3)+(m.group(4) if m.group(3) else f'R[{int(m.group(4))-row}]'),text)


def same_cell(a, b, a_row, b_row, rules):
    if isinstance(a,str) and isinstance(b,str) and a.startswith('=') and b.startswith('='):
        return relative_formula(a,a_row)==relative_formula(b,b_row)
    return comparison_rules.equivalent(a,b,rules)


def compare_tables(left, right, mapping, keys, rules=None, labels=('원본 파일','비교 파일')):
    rules=comparison_rules.clean(rules)
    validate_mapping(left, right, mapping, keys)
    try:li=indexed(left, keys)
    except ValueError as exc:raise ValueError(f'{labels[0]} · {exc}') from exc
    try:ri=indexed(right, [mapping[k] for k in keys])
    except ValueError as exc:raise ValueError(f'{labels[1]} · {exc}') from exc
    changes, unchanged = [], 0
    def add(kind, key, a=None, b=None, column='', old=None, new=None):
        changes.append({'id': len(changes), 'kind': kind, 'key': list(key), 'left': a, 'right': b, 'column': column, 'old': old, 'new': new})
    for key, (i, row) in li.items():
        if key not in ri:
            add('삭제 후보', key, a=i)
            continue
        j, other = ri[key]
        count = len(changes)
        for a, b in mapping.items():
            if a not in keys and not is_sequence(a) and not is_sequence(b) and not same_cell(row[a],other[b],left.physical_rows[i],right.physical_rows[j],rules):
                add('수정', key, i, j, a, row[a], other[b])
        if count == len(changes): unchanged += 1
    for key, (j, row) in ri.items():
        if key not in li: add('추가', key, b=j)
    return changes, unchanged


def write_literal(cell, value):
    cell.value = value
    # Incoming strings cannot become executable spreadsheet formulas.
    if isinstance(value, str): cell.data_type = 's'


def apply_changes(data,*args,comparison_data=None,copy_mode='일반 복사',manual_edits=None,edit_keys=None,**kwargs):
    wb=load(data)
    right=args[1] if len(args)>1 else kwargs['right']
    copier=excel_copy.ExcelCopy(wb,comparison_data,right.sheet,copy_mode)
    try:
        return _apply_changes(wb,data,*args,copier=copier,manual_edits=manual_edits,edit_keys=edit_keys,**kwargs)
    finally:
        copier.close()
        close_workbook(wb)


def _copy_whole_rows(ws, left, right, mapping, changes, approved, row_copies, cols, incoming_cols, overrides, keys, copier, merged_at=None):
    """Row mode: a row with an applied change becomes the comparison row, blanks included.

    Columns the comparison does not have (unmapped) are emptied; changed columns were already written.
    Key and sequence columns stay as they are. Returns (key, column, old value) of every emptied cell.
    """
    written = {(c['left'], c['column']) for c in changes if c['kind'] == '수정' and c['id'] in approved}
    emptied = []
    for left_index, right_index in row_copies.items():
        key = tuple(normalized(left.rows[left_index][k]) for k in keys) if keys else ()
        physical = left.physical_rows[left_index]
        for header in left.headers:
            if is_sequence(header) or header in keys or (key, header) in overrides or (left_index, header) in written or (physical, cols[header]) in (merged_at or {}):
                continue
            cell = ws.cell(physical, cols[header])
            if header in mapping and mapping[header] in incoming_cols:
                copier.write(cell, right.physical_rows[right_index], incoming_cols[mapping[header]], right.rows[right_index][mapping[header]])
            else:
                old = cell.value
                if old is not None:
                    emptied.append((key, header, old))
                cell.value = None
    return emptied


def _sort_result_rows(ws, left, cols, positions, sort_columns, descending, ip_sort, sort_type):
    """Sort the data rows of the result sheet in place and keep `positions` pointing at the moved rows."""
    first=next((c.coordinate for c in ws._cells.values() if c.data_type == 'f'),None)
    if first:
        raise ValueError(f'수식이 있는 시트({first} 칸 등)는 저장할 때 정렬할 수 없습니다. 결과 순서를 원본 유지로 바꾸세요.')
    identity_positions=positions
    row_identity={pos:key for key,pos in identity_positions.items()}
    sort_positions = list(range(left.start_row, ws.max_row + 1))
    records = []
    for pos in sort_positions:
        cells = [copy(ws.cell(pos, c)) for c in range(1, ws.max_column + 1)]
        records.append((cells, copy(ws.row_dimensions[pos]),row_identity.get(pos)))
    auto_kinds={}
    if sort_type=='자동' and not ip_sort:
        for column in sort_columns:
            texts=[normalized(record[0][cols[column]-1].value) for record in records]
            texts=[t for t in texts if t]
            if not texts:continue
            try:
                for text in texts:ip_address(text)
                auto_kinds[column]='ip'
            except ValueError:
                try:
                    if all(math.isfinite(float(text.replace(',',''))) for text in texts):auto_kinds[column]='number'
                except ValueError:pass
    def sort_key(record):
        values = []
        for column in sort_columns:
            value = record[0][cols[column]-1].value
            text = normalized(value)
            if sort_type=='문자':
                values.append((1,text.casefold()))
            elif ip_sort or sort_type=='숫자·IP' or auto_kinds.get(column)=='ip':
                try: values.append((0, int(ip_address(text))))
                except ValueError:
                    try: values.append((0,float(text.replace(',',''))))
                    except ValueError:values.append((1,text.casefold()))
            elif auto_kinds.get(column)=='number':values.append((0,float(text.replace(',',''))) if text else (1,''))
            elif isinstance(value, (int, float)): values.append((0, value))
            else: values.append((1, text.casefold()))
        return tuple(values)
    records.sort(key=sort_key, reverse=descending)
    for position, (cells, dimensions, identity) in zip(sort_positions, records):
        if identity is not None:identity_positions[identity]=position
        ws.row_dimensions[position].height = dimensions.height
        ws.row_dimensions[position].hidden = dimensions.hidden
        for col, old in enumerate(cells, 1):
            cell = ws.cell(position, col)
            cell.value, cell.data_type = old.value, old.data_type
            cell._style, cell.comment, cell.hyperlink = copy(old._style), copy(old.comment), copy(old.hyperlink)

def _restructure_rows(ws, left, right, mapping, cols, incoming_cols, deletions, appended, positions, overrides, placements, copier, edits):
    """Delete and insert rows with RowLayout (merges, formula ranges and formats follow). Returns (positions, structure rows).

    A new row goes after its placement (a row of the original chosen by dragging) or, by default, after the last data row."""
    from row_layout import RowLayout
    data_rows=sorted(left.physical_rows)
    default=data_rows[-1] if data_rows else left.start_row-1
    if not left.structure_rows and not ws.merged_cells.ranges:default=max(default,ws.max_row)   # plain sheet: unplaced rows still go to the end
    insertions=[(placements.get(tuple(c['key']),default),c) for c in appended]
    layout=RowLayout(ws,deletions,insertions)
    left_cols={i:h for h,i in cols.items()}
    def value_of(change,column):
        header=left_cols.get(column);source=mapping.get(header) if header else None
        return right.rows[change['right']].get(source) if source else None
    finish=layout.apply(value_of)
    width=max(ws.max_column,len(left.headers))
    survivors=[r for r in data_rows if r not in set(deletions)]
    for (anchor,change),target in zip(insertions,layout.positions):
        above=[r for r in survivors if r<=anchor] or survivors or [None]
        template=layout.shift(above[-1]) if above[-1] is not None else None
        if template is not None:
            for col in range(1,width+1):ws.cell(target,col)._style=copy(ws.cell(template,col)._style)
            ws.row_dimensions[target].height=ws.row_dimensions[template].height
        for a,b in mapping.items():
            if not is_sequence(a) and not is_sequence(b) and (tuple(change['key']),a) not in overrides:
                copier.write(ws.cell(target,cols[a]),right.physical_rows[change['right']],incoming_cols[b],right.rows[change['right']][b])
    deleted=set(deletions)
    positions={key:layout.shift(pos) for key,pos in positions.items() if pos not in deleted}
    for (anchor,change),target in zip(insertions,layout.positions):positions[tuple(change['key'])]=target
    finish()
    return positions,{layout.shift(r) for r in left.structure_rows if layout.shift(r) is not None}


def _renumber_sequence_columns(ws, left, cols, skip=()):
    for column, position in cols.items():
        if is_sequence(column):
            number = 0
            for row in range(left.start_row, ws.max_row + 1):
                if row not in skip and any(ws.cell(row, c).value is not None for c in range(1, ws.max_column+1) if c != position):
                    number += 1
                    ws.cell(row, position).value = number


def _write_history(wb, left, right, mapping, changes, approved, manual_history, row_copy_history=(), positions=None, cols=None, source_name=''):
    """Append what this save actually changed to the change-history sheet (one row per cell) and return it.

    Rows that were not approved are not written. Added/deleted rows are written column by column, like edits."""
    stamp = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    positions = positions or {}
    cols = cols or {h: i + 1 for i, h in enumerate(left.headers)}
    if left.sheet == LOG_SHEET:
        raise ValueError('변경 이력 시트는 비교 대상으로 사용할 수 없습니다.')
    if LOG_SHEET in wb.sheetnames:
        history = wb[LOG_SHEET]
        if [history.cell(1, c).value for c in range(1, len(LOG_HEADERS) + 1)] != LOG_HEADERS:
            raise ValueError('이 파일에는 형식이 다른 “변경 이력” 시트(예전 버전에서 만든 이력 등)가 있습니다. 엑셀에서 그 시트 이름을 바꾸거나 지운 뒤 다시 저장하세요.')
    else:
        history = wb.create_sheet(LOG_SHEET)
        history.append(LOG_HEADERS)
    colors = {'추가': 'DCFCE7', '삭제': 'FEE2E2', '수정': 'FFEDD5', '직접 수정': 'FFEDD5', '행 단위 비움': 'F1F5F9'}
    fills = {kind: PatternFill('solid', fgColor=color) for kind, color in colors.items()}
    def label(key): return ' / '.join(str(k) for k in key)
    def shown(value): return not (value is None or (isinstance(value, str) and (not value.strip() or value.startswith('='))))
    def where(key, column=None):
        row = positions.get(tuple(key))
        if row is None: return ''
        return f'{get_column_letter(cols[column])}{row}' if column in cols else f'{row}행'
    entries = []   # (sort row, column order, values)
    order = {h: i for i, h in enumerate(left.headers)}
    deleted = sorted(left.physical_rows[c['left']] for c in changes if c['kind'] == '삭제 후보' and c['id'] in approved)
    for change in changes:
        if change['id'] not in approved:
            continue
        key = change['key']
        if change['kind'] == '수정':
            row = positions.get(tuple(key), 0)
            entries.append((row, order.get(change['column'], 0), ['수정', label(key), change['column'], change['old'], change['new'], where(key, change['column']), source_name]))
        elif change['kind'] == '추가':
            row = positions.get(tuple(key), 0); incoming = right.rows[change['right']]
            for a, b in mapping.items():
                if not is_sequence(a) and shown(incoming.get(b)):
                    entries.append((row, order.get(a, 0), ['추가', label(key), a, None, incoming.get(b), where(key, a) if row else '', source_name]))
        elif change['kind'] == '삭제 후보':
            original = left.physical_rows[change['left']]; old = left.rows[change['left']]
            sort_row = original - sum(r < original for r in deleted) - 0.5
            for header in left.headers:
                if not is_sequence(header) and shown(old.get(header)):
                    entries.append((sort_row, order.get(header, 0), ['삭제', label(key), header, old.get(header), None, f'원본 {original}행', source_name]))
    for key, column, old in row_copy_history:
        entries.append((positions.get(tuple(key), 0), order.get(column, 0), ['행 단위 비움', label(key), column, old, None, where(key, column), source_name]))
    for edit, old, new in manual_history:
        entries.append((positions.get(tuple(edit['key']), 0), order.get(edit['column'], 0), ['직접 수정', label(edit['key']), edit['column'], old, new, where(edit['key'], edit['column']), '']))
    for _, _, values in sorted(entries, key=lambda e: (e[0], e[1])):
        target = history.max_row + 1
        for col, value in enumerate(values + [stamp], 1):
            cell = history.cell(target, col); write_literal(cell, value); cell.fill = fills[values[0]]
            if col in (4, 5): cell.alignment = Alignment(wrap_text=True, vertical='top')
    history.freeze_panes = 'A2'
    history.auto_filter.ref = history.dimensions
    for cell in history[1]: cell.font = Font(bold=True)
    for col, header in enumerate(LOG_HEADERS, 1):
        longest = max((len(str(c.value)) for c in history[get_column_letter(col)] if c.value is not None), default=len(header))
        history.column_dimensions[get_column_letter(col)].width = min(50, max(10, longest * 1.3 + 2))
    return history


def _apply_changes(wb, data, left, right, mapping, changes, approved, sort_columns=None, descending=False, ip_sort=False, *, with_metadata=False, copier=None, sort_type='자동', manual_edits=None, edit_keys=None, row_mode=False, placements=None, source_name=''):
    import manual_edits as direct
    edits=direct.clean(manual_edits,left,right,mapping,edit_keys or []) if manual_edits else []
    overrides={(tuple(e['key']),e['column']):e['value'] for e in edits}
    base=indexed(left,edit_keys) if edit_keys else {}
    positions={key:left.physical_rows[i] for key,(i,_) in base.items()}
    ws = wb[left.sheet]
    if ws.tables and (sort_columns or any(c['id'] in approved and c['kind'] != '수정' for c in changes)):
        raise ValueError(f"시트 '{ws.title}'에 엑셀 표(Table) '"+"', '".join(ws.tables)+"'가 있어 셀 수정만 저장할 수 있습니다. 승인된 추가·삭제를 해제하거나, 엑셀에서 표를 일반 범위로 변환한 뒤 다시 저장하세요.")
    first=next((c.coordinate for c in ws._cells.values() if c.data_type == 'f'),None) if sort_columns else None
    if first:
        raise ValueError(f'수식이 있는 시트({first} 칸 등)는 저장할 때 정렬할 수 없습니다. 결과 순서를 원본 유지로 바꾸세요.')
    merged_at={}
    for m in ws.merged_cells.ranges:
        if m.max_row<left.start_row or (m.min_row==m.max_row and m.min_col==m.max_col):continue
        for r in range(m.min_row,m.max_row+1):
            for c in range(m.min_col,m.max_col+1):merged_at[(r,c)]=m
    structured=bool(merged_at or left.structure_rows)
    if structured and sort_columns:
        raise ValueError(f"시트 '{ws.title}'에 병합된 칸이나 소계·구역 제목 같은 구조 행이 있어 저장할 때 정렬할 수 없습니다. 결과 순서를 원본 유지로 바꾼 뒤 다시 저장하세요.")
    def writable(row,col,value):
        m=merged_at.get((row,col))
        if m is None:return True
        if normalized(ws.cell(m.min_row,m.min_col).value if col==m.min_col else None)==normalized(value):return False
        raise ValueError(f"{row}행 {get_column_letter(col)}열은 병합된 칸({m.coord}) 안에 있어 '{normalized(value)}'(으)로 바꾸는 수정을 아직 저장할 수 없습니다. 이 항목의 승인을 해제한 뒤 다시 저장하세요.")
    cols = {h: i + 1 for i, h in enumerate(left.headers)}
    incoming_cols = {h: i + 1 for i, h in enumerate(right.headers)}
    deletions = []
    appended = []
    row_copies = {}
    for change in changes:
        if change['id'] not in approved: continue
        if change['kind'] == '수정':
            if row_mode: row_copies[change['left']] = change['right']
            if (tuple(change['key']),change['column']) not in overrides and writable(left.physical_rows[change['left']],cols[change['column']],change['new']):
                copier.write(ws.cell(left.physical_rows[change['left']], cols[change['column']]), right.physical_rows[change['right']], incoming_cols[mapping[change['column']]], change['new'])
        elif change['kind'] == '삭제 후보':
            deletions.append(left.physical_rows[change['left']])
        else: appended.append(change)
    row_copy_history = _copy_whole_rows(ws, left, right, mapping, changes, approved, row_copies, cols, incoming_cols, overrides, list(edit_keys or []), copier, merged_at) if row_copies else []
    placements=placements or {}
    if structured or any(tuple(c['key']) in placements for c in appended):
        positions,structure_rows=_restructure_rows(ws,left,right,mapping,cols,incoming_cols,deletions,appended,positions,overrides,placements,copier,edits)
    else:
        structure_rows=set()
        if deletions:
            # openpyxl cannot reliably update arbitrary dependencies on deleted rows.
            first=next((f'{sheet.title}!{c.coordinate}' for sheet in wb for c in sheet._cells.values() if c.data_type == 'f'),None)
            if first:
                raise ValueError(f'수식이 있는 파일({first} 칸 등)은 행을 삭제해 저장할 수 없습니다. 승인된 삭제 {len(deletions)}건의 승인을 해제한 뒤 다시 저장하세요.')
            for row in sorted(deletions, reverse=True): ws.delete_rows(row)
        from bisect import bisect_left
        deleted_rows=sorted(deletions)
        positions={key:pos-bisect_left(deleted_rows,pos) for key,pos in positions.items() if pos not in deletions}
        # max_row/max_column scan populated cells: compute once, not for every add.
        target, width = ws.max_row, ws.max_column
        for change in appended:
            target += 1
            positions[tuple(change['key'])]=target
            source = max(left.start_row, target - 1)
            for col in range(1, width + 1):
                previous, cell = ws.cell(source, col), ws.cell(target, col)
                cell._style = copy(previous._style)
                # _style already contains number format, alignment and protection.
            ws.row_dimensions[target].height = ws.row_dimensions[source].height
            for a, b in mapping.items():
                if not is_sequence(a) and not is_sequence(b) and (tuple(change['key']),a) not in overrides: copier.write(ws.cell(target, cols[a]), right.physical_rows[change['right']], incoming_cols[b], right.rows[change['right']][b])
    manual_history=[]
    for edit in edits:
        pos=positions.get(tuple(edit['key']))
        if pos is None:continue  # Rejected additions / approved deletions have no result cell.
        if not writable(pos,cols[edit['column']],edit['value']):continue
        cell=ws.cell(pos,cols[edit['column']]);old=cell.value
        cell.value,cell.data_type=direct.content(edit['value'])
        manual_history.append((edit,old,cell.value))
    if sort_columns:
        _sort_result_rows(ws, left, cols, positions, sort_columns, descending, ip_sort, sort_type)
    _renumber_sequence_columns(ws, left, cols, structure_rows)
    history = _write_history(wb, left, right, mapping, changes, approved, manual_history, row_copy_history, positions, cols, source_name)
    wb.calculation=CalcProperties(calcMode='auto',fullCalcOnLoad=True,forceFullCalc=True)
    output = BytesIO()
    wb.save(output)
    if with_metadata:
        final=table_from_sheet(ws,left.header_row,left.start_row)
        numbering={pos:i for i,pos in enumerate(final.physical_rows,1)}
        order=[{'key':list(key),'number':numbering[pos]} for key,pos in positions.items() if pos in numbering] if edits else None
        return ExportResult(output.getvalue(),final,list(history.values),order)
    return output.getvalue()


@lru_cache(maxsize=1)
def demo_files():
    out = []
    for new in [False, True]:
        wb = openpyxl.Workbook(); ws = wb.active
        ws.title = '장비추출' if new else 'CCTV 관리대장'
        rows = ([['DeviceID', 'DeviceName', 'IPv4', 'Location'], ['001', '정문', '10.0.0.2', '본관'], ['002', '후문', '10.0.0.20', '별관'], ['004', '주차장', '10.0.0.4', '옥외']] if new else [['관리번호', '카메라명', 'IP 주소', '설치위치', '담당자 메모'], ['001', '정문', '10.0.0.2', '본관', '유지'], ['002', '후문', '10.0.0.3', '본관', '점검예정'], ['003', '로비', '10.0.0.10', '본관', '보관']])
        for row in rows: ws.append(row)
        for cell in ws[1]: cell.fill = PatternFill('solid', fgColor='1E3A5F'); cell.font = Font(color='FFFFFF', bold=True)
        for col in 'ABCDE': ws.column_dimensions[col].width = 22
        for row in ws.iter_rows(min_row=2):
            for cell in row: cell.fill = PatternFill('solid', fgColor='EFF6FF')
        ws.freeze_panes = 'A2'
        data = BytesIO(); wb.save(data); out.append(data.getvalue())
    return out
