"""Column-link dialog (T105): bulk link/unlink of visible columns, moved targets, hidden unlinked columns, row-mode blanks."""
import pytest
from PySide6.QtWidgets import QApplication
from sample_catalog import load_sample
from desktop.session import Session


@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])


def test_search_bulk_links_and_hidden_unlinked_columns(app):
    from desktop.ui import Window
    from desktop.dialogs import MappingDialog
    w=Window();w.session=Session(*load_sample('10'));w.refresh(w.session)
    d=MappingDialog(w,w.session)
    d.link_rows(d.visible_rows(),False);keys,mapping=d.values();assert keys==['품목코드'] and mapping=={'품목코드':'품목코드'}   # key stays linked
    d.search.setText('분류');d.link_rows(d.visible_rows(),True);assert set(d.values()[1])=={'품목코드','대분류','중분류'}
    row=next(r for r in range(d.table.rowCount()) if d.name(r)=='품목명');d.choose(row,'중분류')        # a used comparison column moves
    assert d.values()[1].get('품목명')=='중분류' and '중분류' not in d.values()[1]
    d.reject()
    w.session.configure(keys=['품목코드'],mapping={'품목코드':'품목코드','수량':'수량'});w.refresh(w.session)
    assert w.columns==['품목코드','수량'];w.toggle_unlinked(True);assert len(w.columns)==9;w.toggle_unlinked(False)
    s=w.session;s.row_mode=True;s.selected={c['id'] for c in s.changes if c['kind']=='수정'};s.prepare_results()
    assert '대분류' in s.row_blanked_columns() and '수량' not in s.row_blanked_columns()
    w.hide();w.deleteLater()
