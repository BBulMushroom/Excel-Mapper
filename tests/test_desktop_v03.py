"""Reported Windows 0.2 review regressions, through the actual native UI."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from io import BytesIO
from pathlib import Path
import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt,QTimer,QPoint,QPointF,QEvent,QSettings
from PySide6.QtGui import QWheelEvent,QMouseEvent,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit,QTabWidget
from desktop.ui import Window
from desktop.session import Session
from desktop.smoke import fixture
from desktop.dialogs import MappingDialog,RulesDialog,ScreenDialog
from desktop.motion import MARK_COLORS
import openpyxl

@pytest.fixture(scope='module')
def app(tmp_path_factory):
    from desktop.style import NativeStyle
    app=QApplication.instance() or QApplication([]);app.native_style=NativeStyle();app.setStyle(app.native_style)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat);QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,str(tmp_path_factory.mktemp('native-v03-settings')))
    return app

@pytest.fixture
def w(app):
    window=Window();window.combined=False;window.session=Session(fixture([['a','원본',1],['b','유지',2],['z','삭제',9]]),[(fixture([['a','비교',4],['b','유지',2],['c','추가',3]]),'비교.xlsx')],'원본.xlsx');window.refresh();window.show();app.processEvents()
    yield window
    window.hide();window.deleteLater();app.processEvents()

def source(w,key):return next(i for i,row in enumerate(w.session.rows) if row['key']==[key])
def cell(w,key,column,pane=2):return w.views[pane].model().index(w.visible_rows.index(source(w,key)),w.columns.index(column)+2)


def test_unchanged_edit_is_not_a_change_and_manual_edits_are_reviewable(w,app):
    w.toggle_edit();view=w.views[2];index=cell(w,'b','금액');history=len(w.undo_stack);signature=w.session.signature()
    QTest.mouseClick(view.viewport(),Qt.MouseButton.LeftButton,pos=view.visualRect(index).center());QTest.mouseDClick(view.viewport(),Qt.MouseButton.LeftButton,pos=view.visualRect(index).center());app.processEvents()
    editor=view.findChild(QLineEdit);assert editor and editor.text()=='2'
    QTest.keyClick(editor,Qt.Key.Key_Return);app.processEvents()
    assert not w.session.edits and w.session.signature()==signature and len(w.undo_stack)==history
    before=w.change_model.rowCount();assert index.model().setData(index,'27')
    assert w.change_model.rowCount()==before+1
    i=source(w,'b');change=w.session.review_changes(i)[0];assert change['kind']=='수정' and change['id'] in w.session.selected
    entry=next(j for j,(row,changes) in enumerate(w.change_model.entries) if row==i);assert '27' in w.change_model.data(w.change_model.index(entry))
    w.choose([change['id']],False);assert w.session.results[i]['금액']=='2'
    book=openpyxl.load_workbook(BytesIO(w.session.save().data));assert book['자료']['C3'].value==2
    w.choose([change['id']],True);assert w.session.results[i]['금액']=='27'
    book=openpyxl.load_workbook(BytesIO(w.session.save().data));assert book['자료']['C3'].value==27
    index.model().setData(index,'2');assert not w.session.edits and w.change_model.rowCount()==before
    w.undo();assert w.session.results[i]['금액']=='27';w.redo();assert not w.session.edits
    # An edited incoming change replaces that review entry instead of duplicating it.
    index=cell(w,'a','내용');before=w.change_model.rowCount();index.model().setData(index,'직접 편집');assert w.change_model.rowCount()==before
    assert any('직접 편집' in w.change_model.data(w.change_model.index(j)) for j in range(w.change_model.rowCount()))


def test_key_cells_and_mapping_cells_have_whole_cell_click_targets(w,app):
    view=w.views[0];i=source(w,'a');index=view.model().index(w.visible_rows.index(i),1);rect=view.visualRect(index)
    ids=[c['id'] for c in w.session.review_changes(i)];assert all(c in w.session.selected for c in ids)
    QTest.mouseClick(view.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(rect.right()-5,rect.center().y()));assert all(c in w.session.selected for c in ids)
    target=cell(w,'a','내용',0);point=view.visualRect(target).center();QTest.mouseClick(view.viewport(),Qt.MouseButton.RightButton,pos=point)
    selected={c['column']:c['id'] in w.session.selected for c in w.session.review_changes(i)};assert not selected['내용'] and selected['금액']
    dialog=MappingDialog(w,w.session);dialog.show();app.processEvents();row=next(r for r in range(dialog.table.rowCount()) if not dialog.is_key(dialog.table.item(r,0).row()))
    rect=dialog.table.visualRect(dialog.table.model().index(row,1));before=dialog.is_key(row)
    QTest.mouseClick(dialog.table.viewport(),Qt.MouseButton.LeftButton,pos=dialog.table.visualItemRect(dialog.table.item(row,1)).center()-QPoint(dialog.table.columnWidth(1)//2-12,0));assert dialog.is_key(row)!=before
    assert 50<=dialog.table.columnWidth(0)<=100;dialog.reject()


def test_external_rails_cover_filtered_row_intervals_and_keep_colors(w,app):
    w.session.kind='수정';w.refresh();app.processEvents();assert len(w.visible_rows)==1
    for view in w.views:
        assert view.verticalHeader().isHidden() and not view.verticalScrollBar().isVisible()
        rail=view.external_rail;assert rail.parentWidget() in w.frames and rail.x()>view.x()+view.width()-5
        marks=rail.marker_rects();assert len(marks)==1 and marks[0][0]=='수정';assert marks[0][1].height()==pytest.approx(rail.height())
        image=rail.grab().toImage();pixel=image.pixelColor(8,rail.height()//2);assert pixel.red()>pixel.green()>pixel.blue()
    view=w.views[0];index=cell(w,'a','내용',0);view.setCurrentIndex(index);app.processEvents();rect=view.visualRect(index);pixel=view.viewport().grab().toImage().pixelColor(rect.right()-8,rect.bottom()-8)
    from PySide6.QtGui import QColor
    expected=QColor(w.tokens['edit']);assert max(abs(pixel.red()-expected.red()),abs(pixel.green()-expected.green()),abs(pixel.blue()-expected.blue()))<=40   # keeps its colour under the light selection tint
    key=view.model().index(0,1);r=view.visualRect(key);assert view.viewport().grab().toImage().pixelColor(r.left()+1,r.center().y()).name()=='#f59e0b'
    w.bulk('수정');app.processEvents();assert not view.external_rail.marker_rects()
    w.apply_theme('dark');assert MARK_COLORS['수정']=='#f59e0b'
    w.toggle_combined();QTest.qWait(250);assert w.views[0].rowHeight(0)==52
    w.toggle_combined();QTest.qWait(250);assert w.views[0].rowHeight(0)==32


def test_sort_headers_navigation_and_deselected_addition_stay_in_order(w,app):
    for pane in [0,1,2]:
        for column in ['__row__','__key__','금액']:
            w.mutate(lambda s,pane=pane,column=column:setattr(s,'view_sort',(pane,column,False)))
            section=0 if column=='__row__' else 1 if column=='__key__' else w.columns.index(column)+2
            model=w.views[pane].model();assert '↑' in model.headerData(section,Qt.Orientation.Horizontal);assert model.headerData(section,Qt.Orientation.Horizontal,Qt.ItemDataRole.FontRole).bold()
    # A row outside the changed set must advance to the next visible candidate.
    w.focused=source(w,'b');order=w.visible_rows[:];pos=order.index(w.focused)
    expected=next(order[(pos+d)%len(order)] for d in range(1,len(order)+1) if any(c['id'] in w.session.selected for c in w.session.review_changes(order[(pos+d)%len(order)])))
    w.navigate(1);assert w.focused==expected
    i=source(w,'c');before=w.visible_rows[:];w.choose([c['id'] for c in w.session.review_changes(i)],False);assert w.visible_rows==before
    w.mutate(lambda s:setattr(s,'view_sort',None));assert '↑' not in w.views[2].model().headerData(4,Qt.Orientation.Horizontal)


def test_repeated_popup_trigger_closes_without_reopening(w,app):
    observations=[]
    triggers=[(w.more_popup,w.more_button),(w.rules_dialog,w.rules_button),(w.ranges_dialog,w.ranges_button),(w.mapping_dialog,w.mapping_button),(w.order_dialog,w.order.buttons[1]),(w.files_popup,w.file_button)]
    for open_popup,trigger in triggers:
        def click_trigger(trigger=trigger):
            popup=QApplication.activePopupWidget();assert popup
            QTest.mouseClick(trigger,Qt.MouseButton.LeftButton);observations.append(not popup.isVisible())
            if popup.isVisible():popup.reject()
        guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(lambda:[widget.reject() for widget in QApplication.topLevelWidgets() if hasattr(widget,'reject') and widget.isVisible()]);guard.start(700);QTimer.singleShot(60,click_trigger);open_popup();guard.stop()
    assert observations==[True]*6
    view=w.views[0];header=view.horizontalHeader();col=2;point=header.button_rect(col).center()
    def click_header():
        popup=QApplication.activePopupWidget();assert popup;QTest.mouseClick(header.viewport(),Qt.MouseButton.LeftButton,pos=point);observations.append(not popup.isVisible())
        if popup.isVisible():popup.reject()
    QTimer.singleShot(60,click_header);w.column_menu(view,point,col);assert observations==[True]*7


def wheel(view,modifiers=Qt.KeyboardModifier.NoModifier):
    point=view.viewport().rect().center();event=QWheelEvent(QPointF(point),QPointF(view.viewport().mapToGlobal(point)),QPoint(),QPoint(0,-120),Qt.MouseButton.NoButton,modifiers,Qt.ScrollPhase.NoScrollPhase,False);QApplication.sendEvent(view.viewport(),event)


def test_shift_wheel_motion_row_resize_and_view_switch(w,app):
    data=fixture([[f'K{i:03}','내용',i] for i in range(150)]);w.session=Session(data,[(data,'비교.xlsx')],'원본.xlsx');w.refresh();app.processEvents();view=w.views[0];view.setColumnWidth(2,900);app.processEvents()
    wheel(view,Qt.KeyboardModifier.ShiftModifier);QTest.qWait(150);assert view.horizontalScrollBar().value()>0 and view.verticalScrollBar().value()==0
    wheel(view);QTest.qWait(150);assert view.verticalScrollBar().value()>0
    assert len({v.verticalScrollBar().value() for v in w.views})==1
    previous=view.verticalScrollBar().value();wheel(view,Qt.KeyboardModifier.ControlModifier);assert w.scale==85 and view.verticalScrollBar().value()==previous
    view.verticalScrollBar().setValue(0);view.horizontalScrollBar().setValue(0);app.processEvents();index=view.model().index(0,0);rect=view.visualRect(index);start=QPoint(rect.center().x(),rect.bottom()-1)
    before=view.rowHeight(0);QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=start);QTest.mouseMove(view.viewport(),start+QPoint(0,18));QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=start+QPoint(0,18));assert view.rowHeight(0)>before
    height=view.rowHeight(0);w.toggle_combined();QTest.qWait(50);assert w.combined and w.split.count()==2 and w.tables.count()==3
    w.toggle_combined();QTest.qWait(250);assert not w.combined and view.rowHeight(0)==height
    rect=view.visualRect(view.model().index(0,0));edge=QPoint(rect.center().x(),rect.bottom()-1);QTest.mouseDClick(view.viewport(),Qt.MouseButton.LeftButton,pos=edge);assert view.rowHeight(0)<height


def test_settings_stable_height_font_dropdown_date_help_and_theme_preview(w,app):
    before=w.options.height();candidate=next(b for b in w.key_checks.values() if not b.isChecked());QTest.mouseClick(candidate,Qt.MouseButton.LeftButton);app.processEvents();assert w.key_apply.isVisible() and w.options.height()==before
    rules=RulesDialog(w,w.session.rules);rules.mode.setCurrentIndex(3);assert 'YY-MM-DD' in rules.example.text() and not rules.example.font().bold()
    screen=ScreenDialog(w);assert not screen.font.isEditable();screen.show();app.processEvents();button=screen.theme_group.button(0);button.show_preview();app.processEvents();assert button.preview and button.preview.isVisible();assert button.preview.pixmap().width()>200
    assert screen.theme.currentData()==w.theme;QTest.mouseClick(screen.theme_group.button(3),Qt.MouseButton.LeftButton);assert w.theme=='dark';button.hide_preview();screen.reject();rules.reject()
    for button in w.visibility:
        before=button.isChecked();QTest.mouseClick(button,Qt.MouseButton.LeftButton);assert button.isChecked()!=before;assert w.tokens['input'] in button.styleSheet();QTest.mouseClick(button,Qt.MouseButton.LeftButton);assert button.isChecked()==before


def test_manual_review_grouping_queue_restore_and_deleted_hatching(w,app):
    s=w.session.clone();i=source(w,'b');s.edit(i,'내용','직접');s.edit(i,'금액','31');s.row_mode=True
    changes=s.review_changes(i);s.choose([c['id'] for c in changes],False);assert s.results[i]['금액']=='2'
    s.choose([changes[0]['id']],True);assert all(c['id'] in s.selected for c in changes);assert s.results[i]['내용']=='직접'
    s.remember();s.load_stage();assert len(s.edits)==2 and len(s.review_changes(i))==2 and s.results[i]['금액']=='31'
    # The missing comparison side of a deleted row is visibly hatched.
    view=w.views[1];index=cell(w,'z','내용',1);rect=view.visualRect(index);image=view.viewport().grab().toImage()
    colors={image.pixelColor(x,y).name() for x in range(rect.left()+8,rect.right()-8) for y in range(rect.top()+6,rect.bottom()-6)}
    assert len(colors)>1
    # Selected deletion must not export stale direct edits into a removed row.
    i=source(w,'z');w.toggle_edit();cell(w,'z','내용').model().setData(cell(w,'z','내용'),'삭제 전 편집')
    deletion=next(c for c in w.session.review_changes(i) if c['kind']=='삭제');w.choose([deletion['id']],True)
    assert w.session.results[i] is None and not any(e['key']==['z'] for e in w.session.active_edits())
    assert w.session.save().data
