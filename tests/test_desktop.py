"""Native integration acceptance; engine + actual Qt models, without a web server."""
import os,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt,QItemSelection,QItemSelectionModel,QSettings
from PySide6.QtWidgets import QApplication,QWidget,QFileDialog
from desktop.session import Session
from desktop.smoke import fixture
from desktop.ui import Window
from compare import table
from io import BytesIO
import openpyxl


@pytest.fixture(scope='module')
def app(tmp_path_factory):
    from desktop.style import NativeStyle
    app=QApplication.instance() or QApplication([]);app.native_style=NativeStyle();app.setStyle(app.native_style)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat);QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,str(tmp_path_factory.mktemp('native-settings')))
    return app


@pytest.fixture
def window(app):
    w=Window();w.session=Session(fixture([['a','원본',1],['b','유지',2]]),[(fixture([['a','비교',3],['c','추가',7]]),'비교.xlsx')],'원본.xlsx');w.refresh();w.show();app.processEvents()
    yield w
    w.hide();w.deleteLater();app.processEvents()


def test_native_models_edit_undo_and_approval_do_not_destroy_selection(window,app):
    w=window;s=w.session;i=next(i for i,row in enumerate(s.rows) if row['key']==['a']);visible=w.visible_rows.index(i);model=w.views[2].model();index=model.index(visible,3)
    assert not model.flags(index)&Qt.ItemFlag.ItemIsEditable
    w.toggle_edit();assert model.setData(index,'최종 입력')
    assert w.session.results[i]['내용']=='최종 입력'
    assert w.session.rows[i]['before']['내용']=='원본' and w.session.rows[i]['incoming']['내용']=='비교'
    w.undo();assert w.session.results[i]['내용']=='비교';w.redo();assert w.session.results[i]['내용']=='최종 입력'
    w.toggle_edit();assert w.session.results[i]['내용']=='최종 입력' and not model.flags(index)&Qt.ItemFlag.ItemIsEditable
    selection=QItemSelection(model.index(0,2),model.index(1,3));w.views[2].selectionModel().select(selection,QItemSelectionModel.SelectionFlag.ClearAndSelect)
    count=len(w.views[2].selectionModel().selectedIndexes());w.bulk('수정');assert len(w.views[2].selectionModel().selectedIndexes())==count
    w.undo();assert w.session.results[i]['내용']=='최종 입력'
    result=openpyxl.load_workbook(BytesIO(w.session.save().data));assert result['자료']['B2'].value=='최종 입력';assert result['자료']['B2'].font.bold and result['자료']['B2'].fill.fgColor.rgb=='00ABCDEF'
    w.toggle_combined();model=w.views[0].model();assert model.merged_html(model.index(w.visible_rows.index(i),3)) is not None


def test_native_queue_budget_sample_preserves_filter_and_checkpoint_edits():
    from samples import sample_collection,SAMPLE_SETS
    old,files=sample_collection();s=Session(old,files,SAMPLE_SETS['15']['names'][0]);s.kind='추가';s.edit(0,'사업명','직접 취합') if '사업명' in s.headers else s.edit(0,s.headers[-1],'직접 취합')
    col=s.edits[0]['column'];key=s.edits[0]['key'];s.next();assert s.kind=='추가';assert any(r[col]=='직접 취합' for r in s.left.rows)
    s.previous();assert s.edits[0]['key']==key and s.edits[0]['value']=='직접 취합';s.next()
    for _ in range(8):s.next()
    final=s.save().table;assert len(final.rows)==300
    assert len({tuple(normalized(r[k]) for k in s.keys) for r in final.rows})==300


def normalized(value):return str(value).strip()


def test_native_formula_samples_general_values_and_row_mode():
    from samples import sample_files,SAMPLE_SETS
    for sid in ['13','14']:
        old,new=sample_files(sid);s=Session(old,[(new,SAMPLE_SETS[sid]['names'][1])],SAMPLE_SETS[sid]['names'][0]);assert not s.issue
        wb=openpyxl.load_workbook(BytesIO(s.save().data));assert any(cell.data_type=='f' for sheet in wb for row in sheet for cell in row)
        s.copy_mode='값만 복사';s.prepare_results();output=s.save().data;assert output
        assert all(not str(value).startswith('=') for i,row in enumerate(s.rows) for col,value in (s.results[i] or {}).items() if col in row['incomingCalculated'] and any(c['id'] in s.selected and c['kind'] in ('추가','수정') and (c['kind']=='추가' or c['column']==col) for c in row['changes']))
    old,new=sample_files('5');s=Session(old,[(new,'비교.xlsx')],'원본.xlsx');s.selected=set();s.row_mode=True
    mod=next(c for c in s.changes if c['kind']=='수정');s.choose([mod['id']],True)
    assert all(c['id'] in s.selected for c in s.changes if c['kind']=='수정' and c['key']==mod['key'])


def test_native_sample12_model_stays_virtual(window,app):
    from samples import sample_files,SAMPLE_SETS
    old,new=sample_files('12');window.session=Session(old,[(new,SAMPLE_SETS['12']['names'][1])],SAMPLE_SETS['12']['names'][0]);window.refresh();app.processEvents()
    assert window.views[0].model().rowCount()>=10000
    count=len(window.findChildren(QWidget))
    for row in range(0,window.views[0].model().rowCount(),1000):window.views[0].scrollTo(window.views[0].model().index(row,2));app.processEvents()
    assert abs(len(window.findChildren(QWidget))-count)<10
    assert window.more_menu.actions() and window.more_menu.toolTipsVisible()
    assert window.file_button.toolTipDuration()==15000


def test_native_worker_save_keeps_input_files_and_latest_edits(window,app,tmp_path,monkeypatch):
    w=window;s=w.session;i=next(i for i,r in enumerate(s.rows) if r['key']==['a']);w.mutate(lambda state:state.edit(i,'금액','=SUM(1,2)'))
    path=tmp_path/'result.xlsx';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**kw:(str(path),'Excel'))
    w.save_dialog();deadline=time.monotonic()+20
    while w.busy and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
    assert not w.busy and path.exists(),getattr(w,'last_error','timeout');wb=openpyxl.load_workbook(BytesIO(path.read_bytes()));assert wb['자료']['C2'].value=='=SUM(1,2)';wb.close()
    assert w.session.flow['queue_complete'];assert w.session.rows[i]['before']['금액']=='1'
    w.mutate(lambda state:state.edit(i,'금액','8'));w.save_dialog();deadline=time.monotonic()+20
    while w.busy and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
    assert not getattr(w,'last_error',''),getattr(w,'last_error','')
    wb=openpyxl.load_workbook(BytesIO(path.read_bytes()));assert wb['자료']['C2'].value==8;wb.close()
    w.source_paths.add(str(path.resolve()))
    with pytest.raises(ValueError,match='덮어'):w.save_dialog()


def test_native_inline_controls_popovers_and_dpi_icons(window,app):
    """Exercise real inline controls/popovers and physical icon resolution."""
    from PySide6.QtCore import QSize,QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog,QTabWidget
    from desktop.widgets import symbol
    from desktop.dialogs import RulesDialog
    w=window
    for ratio in [1,1.5,2,3]:
        pixmap=symbol('수정','#8a3a06').pixmap(QSize(20,20),ratio)
        assert pixmap.width()==round(20*ratio) and pixmap.devicePixelRatio()==ratio
    QTest.mouseClick(w.mode.buttons[1],Qt.MouseButton.LeftButton);assert w.session.row_mode
    w.undo();assert not w.session.row_mode and w.mode.currentIndex()==0
    QTest.mouseClick(w.copy.buttons[1],Qt.MouseButton.LeftButton);assert w.session.copy_mode=='값만 복사'
    w.undo();assert w.copy.currentIndex()==0
    dialog=RulesDialog(w,w.session.rules);w.popup_anchor=w.rules_button;dialog.show();app.processEvents()
    assert dialog.windowFlags()&Qt.WindowType.Popup
    QTest.keyClick(dialog,Qt.Key.Key_Escape);assert not dialog.isVisible()
    inspected=[]
    def inspect_more():
        popup=QApplication.activePopupWidget()
        if popup:
            tabs=popup.findChild(QTabWidget);inspected.extend(tabs.tabText(i) for i in range(tabs.count()))
            tabs.setCurrentIndex(3);popup.reject()
    QTimer.singleShot(100,inspect_more);w.more_popup()
    assert inspected==['화면 설정','프리셋','단축키','테스트 샘플']
    w.set_zoom(125);assert w.scale==125 and w.zoom_combo.currentText()=='125%'
    w.zoom(-1);assert w.scale==115


def test_native_changed_list_checkbox_preserves_scroll_and_all_three_rails(window,app):
    from desktop.models import ChangeRail
    from PySide6.QtTest import QTest
    w=window;old=fixture([[f'K{i:03}',f'항목 {i}',i] for i in range(150)]);new=fixture([[f'K{i:03}',f'수정 {i}',i+1] for i in range(150)])
    w.session=Session(old,[(new,'비교.xlsx')],'원본.xlsx');w.combined=True;w.refresh();app.processEvents()
    view=w.change_list;index=w.change_model.index(50);view.scrollTo(index);app.processEvents();view.setCurrentIndex(index)
    before=view.verticalScrollBar().value();rect=view.visualRect(index);point=rect.topLeft();point.setX(18);point.setY(rect.top()+18)
    selected=set(w.session.selected);QTest.mouseClick(view.viewport(),Qt.MouseButton.LeftButton,pos=point);app.processEvents()
    assert selected!=w.session.selected and view.verticalScrollBar().value()==before
    view.verticalScrollBar().setValue(before+30);app.processEvents();assert view.verticalScrollBar().value()>=before
    assert all(isinstance(v.external_rail,ChangeRail) for v in w.views)
    assert all(v.verticalScrollBarPolicy()==Qt.ScrollBarPolicy.ScrollBarAlwaysOff for v in w.views)
    w.apply_theme('dark');assert w.tokens['bg']=='#151b25'
    w.apply_theme('light');assert '#ffedd5' in w.category_buttons['수정'].styleSheet()
