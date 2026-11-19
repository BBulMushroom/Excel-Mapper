"""Merged cells (T103 step 1): fill merged values, keep structure rows apart, save only safe cell edits."""
from io import BytesIO
import openpyxl
import pytest
from compare import relative_formula
from sample_catalog import load_sample
from desktop.session import Session


def test_merged_sample_reads_compares_and_saves_cell_edits():
    s=Session(*load_sample('10'))
    kinds=sorted((c['kind'],c['key'][0],c['column']) for c in s.changes)
    assert [k for k,_,_ in kinds].count('수정')==5 and [k for k,_,_ in kinds].count('추가')==4 and [k for k,_,_ in kinds].count('삭제 후보')==2
    assert ('수정','E-203','중분류') in kinds and not any(c=='금액' for _,_,c in kinds)      # row shifts do not change =E8*F8
    assert sorted(s.left.structure_rows)==[4,13,14,21,22,28,29,31] and s.left.filled_cells[16]==['대분류','중분류']
    order=[s.rows[i]['beforeRow'] for i in s.visible()];assert order[:2]==[4,5] and order[-3:]==[28,29,31]
    with pytest.raises(ValueError,match='B8:B10'):s.save()                       # all changes approved: the merged-cell edit (중분류) is still refused
    edits={c['id'] for c in s.changes if c['kind']=='수정' and c['column']!='중분류'};s.selected=set(edits);s.prepare_results()
    ws=openpyxl.load_workbook(BytesIO(s.save().data))['비품대장'];assert ws['E6'].value==12 and len(ws.merged_cells.ranges)==23
    s.selected=edits|{c['id'] for c in s.changes if c['column']=='중분류'};s.prepare_results()
    with pytest.raises(ValueError,match='B8:B10'):s.save()


def test_relative_formula_ignores_row_shift_but_not_absolute_rows():
    assert relative_formula('=E8*F8',8)==relative_formula('=E7*F7',7)
    assert relative_formula('=E8*$F$2',8)!=relative_formula('=E7*$F$3',7) and relative_formula('=SUM(E5:E12)',13)==relative_formula('=SUM(E4:E11)',12)


def test_merged_ranges_are_drawn_merged_and_split_by_changes():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    from desktop.ui import Window
    w=Window();w.combined=False;w.session=Session(*load_sample('10'));w.show_unlinked=True;w.refresh(w.session)
    v=w.views[0];spans={(r,c):(v.rowSpan(r,c),v.columnSpan(r,c)) for r,c in v.model().span_starts}
    assert spans[(0,2)]==(1,9) and spans[(1,2)]==(4,1)          # section title across the row; 전자 runs until the deleted 세탁기 row
    assert (5,2) not in spans and all(r!=5 for r,_ in spans)    # the deleted row itself is never merged
    w.hide();w.deleteLater()
