"""Row mode copies the whole comparison row, including blanks for columns the comparison lacks."""
from io import BytesIO
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import openpyxl
import pytest
from compare import table
from workspace import effective_selection


def workbook(headers,rows):
    wb=openpyxl.Workbook();ws=wb.active;ws.title='자료';ws.append(headers)
    for row in rows:ws.append(row)
    out=BytesIO();wb.save(out);return out.getvalue()


ORIGINAL=workbook(['코드','A','B','C','D','E'],[['k1','a1','b1','c1','d1','e1'],['k2','a2','b2','c2','d2','e2'],['k3','a3','b3','c3','d3','e3']])
# k1: A changed and E missing; k2: untouched; k3: only the blank-able columns differ nowhere (no change at all).
COMPARISON=workbook(['코드','A','B','C'],[['k1','NEW','b1','c1'],['k2','a2','b2','c2'],['k3','a3','b3','c3']])


def result_rows(data):return {r['코드']:r for r in table(data,'자료').rows}


def session(row_mode):
    pytest.importorskip('PySide6.QtWidgets')
    from desktop.session import Session
    s=Session(ORIGINAL,[(COMPARISON,'비교.xlsx')],'원본.xlsx');s.row_mode=row_mode
    s.selected=effective_selection(s.all_changes(),s.selected,row_mode);s.prepare_results();return s


def test_row_mode_blanks_columns_missing_from_the_comparison_in_the_saved_file():
    s=session(True);rows=result_rows(s.save().data)
    assert rows['k1']['A']=='NEW' and rows['k1']['B']=='b1'
    assert rows['k1']['D'] is None and rows['k1']['E'] is None       # D/E do not exist in the comparison
    assert rows['k2']['D']=='d2' and rows['k3']['E']=='e3'           # rows without an applied change are untouched


def test_cell_mode_keeps_original_values_in_unmapped_columns():
    s=session(False);rows=result_rows(s.save().data)
    assert rows['k1']['A']=='NEW' and rows['k1']['D']=='d1' and rows['k1']['E']=='e1'


def test_screen_result_matches_the_saved_file_in_row_mode():
    s=session(True);i=next(n for n,r in enumerate(s.rows) if r['key']==['k1'])
    assert s.results[i]['A']=='NEW' and s.results[i]['D']=='' and s.results[i]['E']==''
    assert s.raw_result(i,'D')=='' and s.row_copied(i)
    saved=result_rows(s.save().data)['k1']
    for column in ('코드','A','B','C','D','E'):assert (s.results[i][column] or None)==saved[column]


def test_unticking_the_row_restores_the_original_row():
    s=session(True);i=next(n for n,r in enumerate(s.rows) if r['key']==['k1'])
    s.choose([c['id'] for c in s.rows[i]['changes']],False)
    assert not s.row_copied(i) and s.results[i]['D']=='d1' and s.results[i]['E']=='e1'


def test_history_sheet_records_emptied_cells():
    s=session(True);wb=openpyxl.load_workbook(BytesIO(s.save().data));history=[[c.value for c in row] for row in wb['변경 이력'].iter_rows(min_row=2)]
    assert any(row[0]=='행 단위 비움' and row[2]=='D' and row[3]=='d1' for row in history)
