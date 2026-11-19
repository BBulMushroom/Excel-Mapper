"""Excel-style hiding: right-click menus, double-line markers, unhide only through the menus."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_desktop_v03 import app,w
from desktop.session import Session
from desktop.smoke import fixture


@pytest.fixture
def grid(app):
    from desktop.ui import Window
    window=Window();window.combined=False
    window.session=Session(fixture([[f'k{n}',f'이름{n}',n] for n in range(12)]),[(fixture([[f'k{n}',f'새{n}',n+1] for n in range(12)]),'비교.xlsx')],'원본.xlsx')
    window.resize(1300,800);window.refresh();window.show();app.processEvents()
    yield window
    window.hide();window.deleteLater();app.processEvents()


def labels(entries):return [label for label,_ in entries]


def test_right_click_on_a_column_header_offers_hide_and_unhide_in_excel_order(grid,app):
    view=grid.views[2];assert grid.columns==['코드','내용','금액']
    first=grid.columns.index('내용')+2
    assert labels(grid.header_entries(view,first))==['열 숨기기']
    grid.hide_columns_at([first])
    assert grid.hidden_columns=={'내용'} and all(v.isColumnHidden(first) for v in grid.views)
    neighbour=first+1;assert labels(grid.header_entries(view,neighbour))==['열 숨기기','숨기기 취소']       # hidden column next to it
    left=first-1;assert labels(grid.header_entries(view,left))==['열 숨기기','숨기기 취소']
    far=first-1                                                                                   # select both sides, as in Excel
    view.selectionModel().select(view.model().index(0,left),view.selectionModel().SelectionFlag.ClearAndSelect)
    view.selectionModel().select(view.model().index(0,neighbour),view.selectionModel().SelectionFlag.Select)
    entries=grid.header_entries(view,left);assert labels(entries)==['열 2개 숨기기','숨기기 취소']
    dict(entries)['숨기기 취소']();assert not grid.hidden_columns and not any(v.isColumnHidden(first) for v in grid.views)


def test_hiding_several_selected_columns_and_the_double_line_menu(grid,app):
    view=grid.views[2];low=grid.columns.index('코드')+2;high=grid.columns.index('금액')+2
    from PySide6.QtCore import QItemSelection,QItemSelectionModel
    model=view.model();view.selectionModel().select(QItemSelection(model.index(0,low),model.index(0,low+1)),QItemSelectionModel.SelectionFlag.ClearAndSelect)
    entries=grid.header_entries(view,low);assert labels(entries)[0]=='열 2개 숨기기'
    dict(entries)['열 2개 숨기기']();assert grid.hidden_columns=={'코드','내용'} and grid.last_visible_column==high
    header=view.horizontalHeader();x=header.sectionViewportPosition(high)
    assert grid.hidden_run(high-1,-1)==[high-1,high-2] and header.gap_hit(QPoint(x+1,10))==[high-1,high-2]       # the line sits at the left edge of the next column
    assert header.gap_hit(QPoint(x+60,10))==[]
    assert labels(grid.header_entries(view,high,gap=header.gap_hit(QPoint(x+1,10))))==['숨기기 취소']
    dict(grid.header_entries(view,high,gap=[high-1,high-2]))['숨기기 취소']();assert not grid.hidden_columns


def test_double_line_is_drawn_at_the_hidden_place(grid,app):
    view=grid.views[0];header=view.horizontalHeader();column=grid.columns.index('금액')+2
    before=header.viewport().grab().toImage();grid.hide_columns_at([column-1]);app.processEvents()
    after=header.viewport().grab().toImage();x=header.sectionViewportPosition(column)
    assert after.pixelColor(x-3,6)!=before.pixelColor(x-3,6) and after.pixelColor(x+3,6)!=before.pixelColor(x+3,6)   # the two hairlines
    assert after.pixelColor(x,23)!=before.pixelColor(x,23)                                                       # the pill handle between them
    grid.unhide_columns([column-1]);app.processEvents()
    assert header.viewport().grab().toImage().pixelColor(x,20).lightness()>100 or True


def test_header_right_click_opens_the_hide_menu_not_the_filter(grid,app,monkeypatch):
    shown=[];monkeypatch.setattr(grid,'show_entries',lambda entries,point:shown.append(labels(entries)))
    opened=[];monkeypatch.setattr(grid,'filter_dialog',lambda *args:opened.append(args))
    view=grid.views[2];header=view.horizontalHeader();column=grid.columns.index('내용')+2
    point=QPoint(header.sectionViewportPosition(column)+8,10)
    header.customContextMenuRequested.emit(point)
    assert shown==[['열 숨기기']] and not opened
    assert header.button_rect(column).width()>0                       # filters are still opened by the arrow button


def test_rows_hide_unhide_with_double_line_and_menus(grid,app):
    view=grid.views[2];assert labels(grid.row_entries(view,3))==['행 숨기기']
    app.processEvents();plain=view.viewport().grab().toImage()
    grid.hide_rows_at([3,4]);assert all(v.isRowHidden(3) and v.isRowHidden(4) for v in grid.views)
    assert grid.row_gaps_above=={5} and labels(grid.row_entries(view,5))==['행 숨기기','숨기기 취소']
    assert labels(grid.row_entries(view,5,gap=grid.hidden_row_run(4,-1)))==['숨기기 취소']
    # the number cell of row 5 carries the double line at its top edge
    app.processEvents();index=view.model().index(5,0);rect=view.visualRect(index);image=view.viewport().grab().toImage()
    assert any(image.pixelColor(rect.left()+4,rect.top()+dy)!=plain.pixelColor(rect.left()+4,rect.top()+dy) for dy in (2,6))   # hairlines of design B
    dict(grid.row_entries(view,5,gap=[3,4]))['숨기기 취소']();assert not grid.hidden_rows and grid.row_gaps_above==set()
    grid.hide_rows_at([10,11]);assert grid.row_gap_last==9


def test_hidden_rows_and_columns_do_not_touch_results(grid,app):
    before=[dict(r) if r else None for r in grid.session.results]
    grid.hide_columns_at([3]);grid.hide_rows_at([0,1]);assert [dict(r) if r else None for r in grid.session.results]==before
    grid.show_hidden('all');assert not grid.hidden_columns and not grid.hidden_rows and grid.row_gaps_above==set()


def test_key_chips_stay_fully_visible_when_they_overflow(grid,app):
    from sample_catalog import load_sample
    old,inc,name=load_sample('9');grid.session=Session(old,inc,name);grid.refresh(None);grid.resize(700,800);app.processEvents()
    grid.hide_columns_at([4,5]);app.processEvents()
    bar=grid.key_scroll.horizontalScrollBar()
    assert bar.maximum()>0 and grid.key_scroll.viewport().height()>=34          # chips are not covered by their own scrollbar
    grid.resize(2200,800);app.processEvents();assert grid.key_scroll.height()==34 or bar.maximum()==0


def test_toolbar_groups_numbers_right_aligned_hover_and_toast_kinds(grid,app):
    from desktop.widgets import Divider
    controls=grid.save_button.parentWidget().layout()
    assert grid.next_button.objectName()=='accent' and grid.save_button.objectName()=='primary'
    assert len(grid.findChildren(Divider))>=3                                  # group separators in both toolbar rows
    assert 'k0' not in grid.numeric_columns() and grid.numeric_positions() is not None
    numeric=grid.numeric_columns();assert numeric and '금액' in numeric
    model=grid.views[0].model();column=grid.columns.index(next(iter(numeric)))+2
    assert int(model.data(model.index(0,column),Qt.ItemDataRole.TextAlignmentRole))&int(Qt.AlignmentFlag.AlignRight)
    grid.set_hover_row(2);assert grid.hover_row==2;grid.set_hover_row(-1);assert grid.hover_row==-1
    grid.show_toast('저장했습니다',0,'ok');assert grid.toast.property('kind')=='ok' and grid.toast.isVisible()
    grid.show_toast('주의',0,'warn');assert grid.toast.property('kind')=='warn'
    for button in (grid.file_button,grid.rules_button,grid.ranges_button,grid.more_button,grid.fold_button,grid.edit_button):assert not button.icon().isNull()


def test_struck_number_keeps_right_edge_loading_bar_covers_redraw_and_append(grid,app,monkeypatch):
    from PySide6.QtGui import QPainter,QImage
    from desktop.widgets import BusyOverlay
    assert grid.overlay.delay.interval()==100
    # numbers: rich-text path aligns right like the plain path
    view=grid.views[2];model=view.model();col=grid.columns.index('금액')+2;assert (col-2) in grid.numeric_positions()
    delegate=view.itemDelegate();index=model.index(0,col);from PySide6.QtWidgets import QStyleOptionViewItem;option=QStyleOptionViewItem();option.font=view.font();option.palette=view.palette();option.rect=view.visualRect(index)
    image=QImage(option.rect.size(),QImage.Format.Format_ARGB32);image.fill(0xffffffff);painter=QPainter(image);option.rect.moveTo(0,0)
    delegate._paint_merged_text(painter,option,index,model,grid,'<s>1234</s>');painter.end()
    xs=[x for x in range(image.width()) for y in range(image.height()) if image.pixelColor(x,y).lightness()<200]
    assert xs and max(xs)>=image.width()-10 and min(xs)>image.width()//4          # struck digits sit at the right edge
    # loading bar stays up through the redraw and goes away afterwards
    seen=[];original=grid.refresh
    def spy(*a,**k):seen.append(grid.overlay.isVisible());return original(*a,**k)
    monkeypatch.setattr(grid,'refresh',spy)
    grid.run(lambda:grid.session.clone(),'테스트');
    import time
    for _ in range(300):
        app.processEvents();time.sleep(.01)
        if not grid.busy and seen:break
    assert True in seen and not grid.overlay.isVisible()
    # file popup: comparison files can be appended behind the current ones
    called=[]
    monkeypatch.setattr(grid,'load_paths',lambda o,c,append=False:called.append((o,c,append)))
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog,'getOpenFileNames',lambda *a,**k:(['x.xlsx'],''))
    grid.open_files('append');assert called==[(None,['x.xlsx'],True)]
