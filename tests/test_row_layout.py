"""T103 step 2/4: saving added/deleted rows in merged sheets, and rows placed by dragging."""
import json
from io import BytesIO
import openpyxl
import pytest
from sample_catalog import load_sample
from desktop.session import Session
from row_layout import RowLayout


def saved(s):
    s.selected={c['id'] for c in s.changes if c['column']!='중분류'};s.prepare_results()
    return openpyxl.load_workbook(BytesIO(s.save().data))['비품대장']


def merges(ws):return {str(m) for m in ws.merged_cells.ranges}


def test_default_save_shrinks_merges_moves_top_value_and_keeps_formulas():
    ws=saved(Session(*load_sample('10')))
    assert {'A5:A11','B8:B9','A14:A18','A12:D12','F33:G33'}<=merges(ws)              # 세탁기·책상 removed, sign-off box kept
    assert ws['A14'].value=='가구' and ws['B14'].value=='사무가구'                      # the deleted first row's merged value moved down
    assert ws['E12'].value=='=SUM(E5:E11)' and ws['E31'].value=='=E12+E19+E30' and ws['C29'].value=='K-101'


def test_dragged_rows_extend_or_split_merges():
    s=Session(*load_sample('10'))
    s.place(['E-104'],7);ws=saved(s)                                                    # 스피커 after 프로젝터: same 영상 group
    assert ws['C8'].value=='E-104' and {'A5:A12','B5:B8'}<=merges(ws) and ws['E13'].value=='=SUM(E5:E12)'
    s=Session(*load_sample('10'));s.place(['F-304'],6);ws=saved(s)                       # 가구 row in the middle of 전자: the merge splits
    assert ws['C7'].value=='F-304' and ws['A7'].value=='가구' and {'A5:A6','A8:A12'}<=merges(ws) and ws['A8'].value=='전자'


def test_placed_row_is_shown_where_it_was_dropped_and_undo_order_is_kept():
    s=Session(*load_sample('10'));s.place(['E-104'],7)
    order=[s.rows[i]['key'][0] for i in s.visible() if not s.rows[i].get('structure')]
    assert order[:4]==['E-101','E-102','E-103','E-104'] and json.dumps(['E-104'],ensure_ascii=False) in s.placements


def test_single_reference_to_a_deleted_row_is_refused():
    wb=openpyxl.Workbook();ws=wb.active
    for r in range(1,5):ws.append([r])
    ws['B1']='=A3';layout=RowLayout(ws,[3],[])
    with pytest.raises(ValueError,match='3행'):layout.apply(lambda change,column:None)


def test_history_lists_only_applied_cells_with_location():
    s=Session(*load_sample('10'));s.place(['E-104'],7)
    s.selected={c['id'] for c in s.changes if c['column']!='중분류'};s.prepare_results()
    rows=list(openpyxl.load_workbook(BytesIO(s.save().data))['변경 이력'].values)
    assert rows[1][:7]==('수정','E-102','수량',10,12,'E6','비교.xlsx') and ('추가','E-104','품목명',None,'스피커','D8','비교.xlsx') in [r[:7] for r in rows]
    assert not any(r[0]=='수정' and r[2]=='중분류' for r in rows[1:]) and ('삭제','E-202','품목명','세탁기',None,'원본 9행','비교.xlsx') in [r[:7] for r in rows]
