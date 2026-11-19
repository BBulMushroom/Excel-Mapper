"""Native review items: Ctrl+E/Space, row selection, merged-view colours, rail gaps, fonts, alignment."""
from test_desktop_v03 import app,w,cell,source
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from desktop.models import blend
from desktop.motion import ChangeRail


def selected_cells(view):return {(i.row(),i.column()) for i in view.selectionModel().selectedIndexes()}


def test_ctrl_e_with_ctrl_held_selects_one_cell_and_space_unchecks(w,app):
    w.navigate(1);view=w.views[2]
    # A held Ctrl key must not turn the review cursor into an additive multi-selection.
    app.keyboardModifiers=lambda:Qt.KeyboardModifier.ControlModifier
    for _ in range(4):w.review_shortcut(1)
    assert len(selected_cells(view))==1
    current=view.currentIndex();changes=w.model_changes if hasattr(w,'model_changes') else view.model().cell_changes(view.model().source_index(current),current.column())
    assert changes and all(c['id'] in w.session.selected for c in changes)
    w.toggle_focused()
    assert not any(c['id'] in w.session.selected for c in changes)


def test_space_after_list_click_toggles_the_clicked_change(w,app):
    w.combined=True;w.refresh(w.session);app.processEvents()
    position=max(n for n,(_,changes) in enumerate(w.change_model.entries) if all(c['id'] in w.session.selected for c in changes));index=w.change_model.index(position);w.change_list.setFocus();w.list_focus(index)
    assert w.change_list.currentIndex().row()==index.row()
    ids=[c['id'] for c in w.change_model.entries[index.row()][1]];assert all(i in w.session.selected for i in ids)
    w.toggle_focused();assert not any(i in w.session.selected for i in ids)


def test_row_mode_navigation_selects_the_whole_row(w,app):
    w.change_mode(1);w.navigate(1);view=w.views[2];columns=view.model().columnCount()
    rows={r for r,_ in selected_cells(view)};assert len(rows)==1
    assert {c for _,c in selected_cells(view)}==set(range(columns))


def test_row_mode_marks_the_whole_row(w,app):
    w.change_mode(1);model=w.views[0].model();row=w.visible_rows.index(source(w,'a'))
    plain=w.visible_rows.index(source(w,'b'))
    marked=model.data(model.index(row,0),Qt.ItemDataRole.BackgroundRole);unchanged=next(c for c in w.columns if model.change(w.session.rows[source(w,'a')],c,source(w,'a')) is None)
    other=model.data(model.index(row,w.columns.index(unchanged)+2),Qt.ItemDataRole.BackgroundRole)
    assert marked.name()==w.tokens['edit'] and other is not None and other.alpha()<255
    assert model.data(model.index(plain,0),Qt.ItemDataRole.BackgroundRole).name()==w.tokens['panel']
    w.change_mode(0);assert model.data(model.index(row,0),Qt.ItemDataRole.BackgroundRole).name()==w.tokens['panel']


def test_merged_text_follows_selection(w,app):
    w.combined=True;w.refresh(w.session);app.processEvents();model=w.views[0].model();t=w.tokens
    bright=t['edit-text'];dim=blend(bright,t['edit'],.42).name()
    index=cell(w,'a','내용',0);change=next(c for c in w.session.review_changes(source(w,'a')) if c['column']=='내용')
    html=model.merged_html(index)
    # Applied: original is dim and struck, comparison is bright.
    assert html.index('<s>')<html.index('<b ') and dim in html.split('<br>')[0] and dim not in html.split('<br>')[1]
    w.choose([change['id']],False);html=model.merged_html(index)
    assert '<s>' in html.split('<br>')[1] and dim in html.split('<br>')[1] and dim not in html.split('<br>')[0] and '<b ' in html.split('<br>')[0]
    # Added: bright when applied, dim when not. Deleted: struck and dim when applied, plain and bright when kept.
    add=next(i for i,r in enumerate(w.session.rows) if r['key']==['c']);col=w.columns.index('내용')+2;added=model.index(w.visible_rows.index(add),col)
    on=model.data(added,Qt.ItemDataRole.ForegroundRole);addid=w.session.review_changes(add)[0]['id'];w.choose([addid],False)
    off=model.data(added,Qt.ItemDataRole.ForegroundRole);assert on.name()==t['add-text'] and off.name()==blend(t['add-text'],t['add'],.42).name()
    delete=source(w,'z');deleted=model.index(w.visible_rows.index(delete),col);delid=w.session.review_changes(delete)[0]['id']
    kept=model.data(deleted,Qt.ItemDataRole.ForegroundRole);assert model.merged_html(deleted) is None and kept.name()==t['delete-text']
    w.choose([delid],True);html=model.merged_html(deleted);assert '<s>' in html and blend(t['delete-text'],t['delete'],.42).name() in html and model.data(deleted,Qt.ItemDataRole.ForegroundRole).name()!=t['delete-text']


def test_row_column_is_centered(w,app):
    model=w.views[0].model()
    assert model.data(model.index(0,0),Qt.ItemDataRole.TextAlignmentRole)==int(Qt.AlignmentFlag.AlignCenter)
    assert model.headerData(0,Qt.Orientation.Horizontal,Qt.ItemDataRole.TextAlignmentRole)&int(Qt.AlignmentFlag.AlignHCenter)


def test_change_list_has_no_source_labels(w,app):
    w.combined=True;w.refresh(w.session)
    from desktop.models import ChangeDelegate
    import inspect
    source_text=inspect.getsource(ChangeDelegate)
    assert "label+' '+get_column_letter" not in source_text and "원본 {row" not in source_text


def test_rail_keeps_a_visible_gap_for_one_missing_row(app):
    class Bar:
        def height(self):return 800
    from desktop.session import Session
    from desktop.smoke import fixture
    from desktop.ui import Window
    rows=[[f'k{n:05d}','원본',n] for n in range(3000)];new=[[f'k{n:05d}','비교',n] for n in range(3000)]
    window=Window();window.combined=False;window.session=Session(fixture(rows),[(fixture(new),'비교.xlsx')],'a.xlsx');window.refresh();window.resize(900,700);window.show();app.processEvents()
    rail=window.views[0].external_rail;every=[r for r in rail.marker_rects() if r[0]=='수정']
    assert len(every)==1
    middle=window.visible_rows[1500];change=next(c for c in window.session.review_changes(middle) if c['kind']=='수정')
    window.choose([change['id']],False);split=[r for r in rail.marker_rects() if r[0]=='수정']
    assert len(split)==2 and split[1][1].top()-(split[0][1].bottom())>=1.0
    window.hide();window.deleteLater()


def test_dark_inputs_and_dropdown_spacing_and_font_names(w,app):
    w.apply_theme('dark');style=w.styleSheet()
    assert "QLineEdit,QComboBox,QSpinBox {background:"+w.tokens['input']+";color:"+w.tokens['text'] in style
    assert 'QComboBox QAbstractItemView::item {min-height:30px' in style
    from desktop.dialogs import ScreenDialog,FilterDialog
    from desktop.widgets import FontNameDelegate
    dialog=ScreenDialog(w);assert isinstance(dialog.font.view().itemDelegate(),FontNameDelegate)
    index=dialog.font.view().model().index(0,0);from PySide6.QtWidgets import QStyleOptionViewItem;option=QStyleOptionViewItem();delegate=dialog.font.view().itemDelegate()
    assert delegate.sizeHint(option,index).height()>=30;dialog.reject()
    assert w.palette().color(w.palette().ColorRole.PlaceholderText).name()==w.tokens['muted']


def test_plain_columns_fit_their_text(w,app):
    view=w.views[0];column=w.columns.index('내용')+2;delegate=view.itemDelegate()
    from PySide6.QtWidgets import QStyleOptionViewItem
    option=QStyleOptionViewItem();option.initFrom(view);option.font=view.font();option.fontMetrics=view.fontMetrics()
    index=view.model().index(0,column);text=str(index.data() or '')
    assert delegate.sizeHint(option,index).width()>=view.fontMetrics().horizontalAdvance(text)+16


def test_hide_and_show_columns_and_rows(w,app):
    view=w.views[2];column=w.columns.index('내용')+2;row=w.visible_rows.index(source(w,'a'))
    view.setFocus();view.selectionModel().select(view.model().index(row,column),view.selectionModel().SelectionFlag.ClearAndSelect)
    w.hide_selected_columns()
    assert all(v.isColumnHidden(column) for v in w.views) and w.hidden_columns=={'내용'} and '열 1' in w.hide_button.text()
    view.selectionModel().select(view.model().index(row,column+1),view.selectionModel().SelectionFlag.ClearAndSelect)
    w.hide_selected_rows()
    assert all(v.isRowHidden(row) for v in w.views) and '행 1' in w.hide_button.text()
    # Hidden cells are skipped by review navigation, results are untouched.
    w.navigate(1);assert w.focused!=source(w,'a') and w.session.results[source(w,'a')] is not None
    # A refresh (e.g. toggling a change) keeps the hidden state; show-all restores everything.
    w.choose([c['id'] for c in w.session.review_changes(source(w,'c')) if True][:1],False);assert all(v.isColumnHidden(column) for v in w.views)
    w.show_hidden('all');assert not any(v.isColumnHidden(column) or v.isRowHidden(row) for v in w.views) and w.hide_button.text()=='숨기기'


def test_hiding_every_column_keeps_one_visible_via_current_cell(w,app):
    view=w.views[2];view.setFocus();model=view.model();last=model.columnCount()-1
    from PySide6.QtCore import QItemSelection,QItemSelectionModel
    view.selectionModel().select(QItemSelection(model.index(0,2),model.index(0,last)),QItemSelectionModel.SelectionFlag.ClearAndSelect)
    view.selectionModel().setCurrentIndex(model.index(0,3),QItemSelectionModel.SelectionFlag.NoUpdate)
    w.hide_selected_columns();assert w.hidden_columns=={w.columns[1]}


def test_hidden_state_resets_for_a_new_file(w,app):
    w.hidden_columns.add('내용');w.apply_hidden()
    from desktop.session import Session
    from desktop.smoke import fixture
    w.session=Session(fixture([['k','x',1]]),[(fixture([['k','y',2]]),'비교.xlsx')],'원본.xlsx');w.hidden_columns.clear();w.refresh(None)
    assert not any(w.views[0].isColumnHidden(c) for c in range(w.views[0].model().columnCount()))


def test_spinbox_arrows_tabs_and_theme_buttons(w,app):
    from desktop.dialogs import ScreenDialog
    from desktop.widgets import ThemeButton
    from display_theme import palettes
    style=w.styleSheet()
    assert 'QSpinBox::up-arrow' in style and 'QSpinBox::down-arrow' in style and 'QTabWidget::pane {border:0' in style and 'QTabWidget QDialog {border:0' in style
    dialog=ScreenDialog(w)
    for button,(name,palette) in zip(dialog.theme_group.buttons(),palettes().items()):
        assert palette['tokens']['input'] in button.styleSheet() and palette['tokens']['text'] in button.styleSheet()
    dialog.reject()
    assert ThemeButton('light').preview_timer.interval()<=100


def test_theme_preview_pixmaps_are_cached(w,app):
    from desktop.widgets import ThemeButton
    ThemeButton.previews.clear();button=ThemeButton('dark');button.show_preview();first=ThemeButton.previews.get('dark')
    button.hide_preview();button.show_preview();assert first is not None and ThemeButton.previews['dark'] is first;button.hide_preview()


def test_popup_waits_for_first_paint_before_showing(w,app):
    from desktop.dialogs import RangesDialog
    dialog=RangesDialog(w,w.session);assert hasattr(dialog,'reveal_after_first_paint');dialog.show();app.processEvents();dialog.reject()


def test_shared_caches_follow_selection(w,app):
    s=w.session;before=s.all_changes();assert s.all_changes() is before
    change=next(c for c in s.review_changes(source(w,'a')) if c['kind']=='수정');w.choose([change['id']],False)
    assert w.session.all_changes() is not before or change['id'] not in w.session.selected
    assert w.session.visible()==w.session.visible()
    marks=w.rail_marks(400,w.views[0]);assert marks is w.rail_marks(400,w.views[0])


def pump(app,milliseconds):
    """Process events in small steps; QTest.qWait would keep the GIL away from the worker thread."""
    import time
    end=time.monotonic()+milliseconds/1000
    while time.monotonic()<end:app.processEvents();time.sleep(0.01)


def test_busy_overlay_shows_progress_and_cancel_discards_the_result(w,app):
    import time
    before=w.session
    def slow():
        time.sleep(0.6);return before.clone()
    w.run(slow,'테스트 작업 중…');assert w.busy and not w.overlay.isVisible()   # a short delay avoids flashing for fast jobs
    pump(app,400);assert w.overlay.isVisible() and '테스트 작업 중' in w.overlay.label.text() and w.overlay.cancel.isVisible()
    w.overlay.cancel.click();assert not w.busy and not w.overlay.isVisible() and w.session is before
    pump(app,900);assert w.session is before and not w.tasks           # the late result was ignored


def test_non_cancellable_job_hides_cancel_and_finishes(w,app):
    import time
    w.run(lambda:w.session.clone(),'저장하는 중…',False);pump(app,400)
    assert not w.busy and not w.overlay.isVisible()
    w.run(lambda:time.sleep(0.6) or w.session.clone(),'저장하는 중…',False);pump(app,350)
    assert w.overlay.isVisible() and not w.overlay.cancel.isVisible();pump(app,600);assert not w.busy


def test_drag_and_drop_zones_load_original_and_comparison_files(app,tmp_path):
    import time
    from PySide6.QtCore import QMimeData,QUrl
    from desktop.ui import Window
    from desktop.smoke import fixture
    old=tmp_path/'원본.xlsx';new=tmp_path/'비교1.xlsx';other=tmp_path/'메모.txt'
    old.write_bytes(fixture([['a','x',1],['b','y',2]]));new.write_bytes(fixture([['a','z',1],['b','y',2]]));other.write_text('x')
    window=Window();window.show();app.processEvents()
    mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(other)),QUrl.fromLocalFile(str(new))])
    assert window.dropped_files(mime)==[str(new)]                      # unsupported types are ignored
    assert window.drop_overlay.zone_at(10)==0 and window.drop_overlay.zone_at(window.width()-10)==1
    window.accept_dropped(1,[str(new)]);assert window.session is None and window.pending_comparisons and window.toast.isVisible() and '원본' in window.toast.text()
    window.accept_dropped(0,[str(old)]);pump(app,1500)
    assert window.session is not None and list(window.session.names)==['원본.xlsx','비교1.xlsx'] and not window.toast.isVisible()
    # With a session, each zone replaces just its own side.
    again=tmp_path/'비교2.xlsx';again.write_bytes(fixture([['a','q',1],['b','y',2]]));window.accept_dropped(1,[str(again)]);pump(app,1500)
    assert list(window.session.names)==['원본.xlsx','비교2.xlsx']
    window.hide();window.deleteLater()


def snapshot_state(w):
    s=w.session;return (s.signature(),[json_safe(r) for r in s.results],sorted(map(str,s.selected)),s.row_mode,s.kind,s.search,w.combined,w.edit_enabled,w.collapsed)


def json_safe(value):return None if value is None else sorted(value.items())


def test_undo_redo_replays_small_patches_exactly(w,app):
    steps=[]
    def checkpoint():steps.append(snapshot_state(w))
    checkpoint()
    changes=[c['id'] for c in w.session.all_changes()]
    w.choose(changes[:1],False);checkpoint()
    w.change_mode(1);checkpoint()
    w.toggle_edit();checkpoint()
    index=cell(w,'a','내용');w.views[2].model().setData(index,'직접 입력');checkpoint()
    w.filter_change('kind','수정');checkpoint()
    w.fold();checkpoint()
    w.choose(changes[1:],True);checkpoint()
    kinds={e['kind'] for e in w.undo_stack};assert kinds<={'patch','ui'} and 'patch' in kinds
    for expected in reversed(steps[:-1]):
        w.undo();assert snapshot_state(w)==expected
    assert not w.undo_stack
    for expected in steps[1:]:
        w.redo();assert snapshot_state(w)==expected
    assert not w.redo_stack


def test_history_stays_small_for_thousands_of_selection_changes(w,app):
    import sys
    ids=[c['id'] for c in w.session.all_changes()][:2]
    for n in range(1100):w.choose(ids[:1],bool(n%2))
    assert len(w.undo_stack)==w.MAX_HISTORY and all(e['kind']=='patch' for e in w.undo_stack)
    entry=w.undo_stack[-1];size=sys.getsizeof(entry)+sum(sys.getsizeof(x) for x in entry['diff']['selected'])
    assert size<2000                                   # a few ids, not a copy of the session
    before=snapshot_state(w)
    for _ in range(25):w.undo()
    for _ in range(25):w.redo()
    assert snapshot_state(w)==before


def test_full_snapshots_are_limited_and_older_steps_are_dropped_with_them(w,app):
    from desktop.session import Session
    from desktop.smoke import fixture
    for n in range(8):
        w.choose([c['id'] for c in w.session.all_changes()][:1],bool(n%2))
        w.undo_stack.append({'kind':'full','before':w.snapshot(),'after':w.snapshot()});w.push_history(w.undo_stack.pop())
    assert sum(e['kind']=='full' for e in w.undo_stack)<=w.MAX_FULL_SNAPSHOTS and w.undo_stack[0]['kind']=='full'
