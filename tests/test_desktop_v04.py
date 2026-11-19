"""Native 0.4 interaction and IME regressions from the user review."""
from test_desktop_v03 import app,w,cell,source
from PySide6.QtCore import Qt,QTimer,QPoint
from PySide6.QtGui import QInputMethodEvent,QFont
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtTest import QTest
from desktop.dialogs import FilterDialog,MappingDialog,ScreenDialog


def test_hangul_preedit_survives_search_refresh(w,app):
    w.search.setFocus();event=QInputMethodEvent('',[]);event.setCommitString('가');QApplication.sendEvent(w.search,event)
    QApplication.sendEvent(w.search,QInputMethodEvent('나',[]));QTest.qWait(240)
    assert w.search.composing and w.search.text()=='가' and w.session.search==''
    event=QInputMethodEvent('',[]);event.setCommitString('나');QApplication.sendEvent(w.search,event);QTest.qWait(240)
    assert not w.search.composing and w.search.text()=='가나' and w.session.search=='가나'
    QTest.keyClick(w.search,Qt.Key.Key_Space);assert w.search.text().endswith(' ')


def test_cell_and_row_units_right_click_and_space(w,app):
    view=w.views[2];index=cell(w,'a','내용');other=next(c for c in w.session.review_changes(source(w,'a')) if c['column']=='금액')['id'];view.setFocus();view.setCurrentIndex(index)
    QTest.keyClick(view,Qt.Key.Key_Space);assert other in w.session.selected and not next(c for c in w.session.review_changes(source(w,'a')) if c['column']=='내용')['id'] in w.session.selected
    w.change_mode(1);index=view.model().index(w.visible_rows.index(source(w,'a')),1);QTest.mouseClick(view.viewport(),Qt.MouseButton.RightButton,pos=view.visualRect(index).center());assert not any(c['id'] in w.session.selected for c in w.session.review_changes(source(w,'a')))


def test_filter_button_only_and_compact_conditions(w,app):
    header=w.views[0].horizontalHeader();header.sectionClicked.emit(2);assert w.active_popover is None
    observations=[]
    def inspect():
        popup=QApplication.activePopupWidget();observations.append(bool(popup));popup.reject()
    QTimer.singleShot(60,inspect);QTest.mouseClick(header.viewport(),Qt.MouseButton.LeftButton,pos=header.button_rect(2).center());assert observations==[True]
    dialog=FilterDialog(w,w.session,0,'내용');dialog.show();app.processEvents();height=dialog.height();dialog.op.setCurrentText('포함');app.processEvents();assert dialog.height()<height and not dialog.all.isVisible();dialog.op.setCurrentText('선택값');app.processEvents();assert dialog.items.isVisible();dialog.reject()


def test_mapping_actual_checkstate_and_live_font(w,app):
    dialog=MappingDialog(w,w.session);row=next(r for r in range(dialog.table.rowCount()) if dialog.is_key(r));dialog.toggle_key(row);assert not dialog.is_key(row);dialog.reject()
    screen=ScreenDialog(w);font=QFont('DejaVu Sans');screen.font.setCurrentFont(font);app.processEvents();assert w.font().family()==screen.font.currentFont().family();assert w.views[0].font().family()==w.font().family();screen.reject()


def test_counter_sizes_and_catalog(w,app):
    before=[(b.width(),b.icon_label.x()) for b in w.category_buttons.values()];w.bulk('수정');app.processEvents();assert [(b.width(),b.icon_label.x()) for b in w.category_buttons.values()]==before
    from sample_catalog import CATALOG,load_sample
    assert list(CATALOG)==[str(n) for n in range(1,11)];old,files,name=load_sample('9');assert len(files)==10
    from compare import table
    assert len(table(old,'설비대장').rows)==500


def test_merged_autofit_keeps_manual_widths(w,app):
    w.toggle_edit();index=cell(w,'a','내용');index.model().setData(index,'원본보다 긴 수정 내용')
    manual=w.columns.index('금액')+2;w.views[0].setColumnWidth(manual,143)
    w.toggle_combined();app.processEvents();view=w.views[0]
    assert view.columnWidth(index.column())>=view.sizeHintForColumn(index.column())
    assert all(v.columnWidth(manual)==143 for v in w.views)
    assert view.columnWidth(0)>=view.fontMetrics().horizontalAdvance('3 ↔ —')+10


def test_view_switch_reuses_widths_and_initial_counts_fit(w,app,monkeypatch):
    calls=[]
    for v in w.views:monkeypatch.setattr(v,'resizeColumnsToContents',lambda:calls.append(1))
    w.toggle_combined();app.processEvents();w.toggle_combined();app.processEvents();assert not calls
    from desktop.ui import Window
    empty=Window();empty.show();app.processEvents()
    for b in empty.category_buttons.values():assert b.number_label.x()>=b.icon_label.x()+b.icon_label.width()
    empty.hide();empty.deleteLater()


def test_combo_opens_below_without_moving_control(w,app):
    combo=w.kind;before=combo.geometry();combo.showPopup();QTest.qWait(30)
    assert combo.geometry()==before
    assert combo.view().window().y()>=combo.mapToGlobal(combo.rect().bottomLeft()).y()
    combo.hidePopup()
