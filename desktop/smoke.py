"""Runs inside the frozen Windows executable as well as the source application."""
from io import BytesIO
from pathlib import Path
import json,platform,sys,time
import openpyxl
from openpyxl.styles import Font,PatternFill
from PySide6.QtCore import Qt
from PySide6.QtGui import QRawFont,QPixmap
from .session import Session
from .ui import Window


def fixture(rows):
    book=openpyxl.Workbook();sheet=book.active;sheet.title='자료';sheet.append(['코드','내용','금액'])
    for row in rows:sheet.append(row)
    sheet['B2'].font=Font(bold=True,color='112233');sheet['B2'].fill=PatternFill('solid',fgColor='ABCDEF');sheet.column_dimensions['B'].width=24;sheet.row_dimensions[2].height=33
    out=BytesIO();book.save(out);return out.getvalue()


def run(app,report):
    started=time.perf_counter();window=Window();window.combined=False;old=fixture([['a','원본',1],['b','유지',2]])
    first=fixture([['a','비교',3],['c','추가',7]]);second=fixture([['d','취합',9]])
    window.session=Session(old,[(first,'비교1.xlsx'),(second,'비교2.xlsx')],'원본.xlsx');window.show();window.refresh();app.processEvents()
    from .models import ChangeRail
    from PySide6.QtCore import QSize
    for ratio in [1,1.5,2,3]:
        icon=window.native_icon('추가','#176038').pixmap(QSize(20,20),ratio);assert icon.width()==round(20*ratio)
    assert all(isinstance(view.external_rail,ChangeRail) for view in window.views)
    assert len(window.mode.buttons)==len(window.copy.buttons)==2
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    assert all((root/'desktop'/'previews'/(theme+'.png')).is_file() for theme in ['light','gray','warm','dark','navy','charcoal'])
    assert not QPixmap(str(root/'desktop'/'icons'/'down-light.svg')).isNull()
    assert all(view.verticalHeader().isHidden() and not view.verticalScrollBar().isVisible() for view in window.views)
    s=window.session;assert len(s.rows)==3 and not window.edit_enabled
    raw_font=QRawFont.fromFont(window.font());assert raw_font.isValid() and raw_font.supportsCharacter(ord('A')) and raw_font.supportsCharacter(ord('가')) and raw_font.supportsCharacter(ord('∨'))
    i=next(i for i,r in enumerate(s.rows) if r['key']==['a']);col=s.headers.index('내용')+2
    model=window.views[2].model();index=model.index(window.visible_rows.index(i),col)
    assert not model.flags(index)&Qt.ItemFlag.ItemIsEditable
    window.toggle_edit();assert model.flags(index)&Qt.ItemFlag.ItemIsEditable
    assert model.setData(index,'직접 입력');assert window.session.results[i]['내용']=='직접 입력'
    before=window.session.signature();history=len(window.undo_stack);assert not model.setData(index,'직접 입력');assert window.session.signature()==before and len(window.undo_stack)==history
    window.undo();assert window.session.results[i]['내용']=='비교';window.redo();assert window.session.results[i]['내용']=='직접 입력'
    window.fold();assert window.collapsed;window.undo();assert not window.collapsed
    window.toggle_combined();app.processEvents();assert window.combined and window.change_model.rowCount()>0
    index=window.change_model.index(0);before=set(window.session.selected);window.list_toggle(index);assert window.session.selected!=before;window.undo();assert window.session.selected==before
    for theme in ['light','gray','warm','dark','navy','charcoal']:window.apply_theme(theme);app.processEvents()
    window.apply_theme('light');window.refresh();
    app.processEvents();window.grab().save(str(report.with_suffix('.png')))
    saved=window.session.save().data;result=openpyxl.load_workbook(BytesIO(saved));sheet=result['자료'];assert sheet['B2'].value=='직접 입력';assert sheet['B2'].font.bold and sheet['B2'].fill.fgColor.rgb=='00ABCDEF';assert sheet.column_dimensions['B'].width==24 and sheet.row_dimensions[2].height==33
    s=window.session.clone();s.next();assert s.flow['queue_index']==1 and s.left.rows[0]['내용']=='직접 입력';s.previous();assert s.edits[0]['value']=='직접 입력'
    # Stress the actual Qt model; the cells remain data, never per-cell QWidget objects.
    count=10000;large=fixture([[f'K{i:05}',f'항목 {i}',i] for i in range(count)])
    begin=time.perf_counter();window.session=Session(large,[(large,'비교.xlsx')],'원본.xlsx');window.refresh();app.processEvents();load_seconds=time.perf_counter()-begin
    assert window.views[0].model().rowCount()==count
    widgets_before=len(window.findChildren(__import__('PySide6.QtWidgets',fromlist=['QWidget']).QWidget))
    begin=time.perf_counter()
    for row in range(0,count,499):window.views[0].scrollTo(window.views[0].model().index(row,2));app.processEvents()
    scroll_seconds=time.perf_counter()-begin
    widgets_after=len(window.findChildren(__import__('PySide6.QtWidgets',fromlist=['QWidget']).QWidget));assert abs(widgets_after-widgets_before)<10
    assert not any(name.startswith(('streamlit','PySide6.QtWebEngine','webview')) for name in sys.modules)
    output={'status':'passed','platform':platform.platform(),'frozen':bool(getattr(sys,'frozen',False)),'rows':count,'native_widgets_before':widgets_before,'native_widgets_after':widgets_after,'load_seconds':round(load_seconds,3),'scroll_pass_seconds':round(scroll_seconds,3),'total_seconds':round(time.perf_counter()-started,3),'checks':['native-window','edit-default-off','content-only-edit','undo-redo','fold','merged-list-toggle','six-themes','xlsx-style-preservation','sequential-collection','10000-row-model','no-browser-import','bundled-korean-font','inline-selection-controls','dpi-aware-icons','three-change-rails','no-change-edit-no-history','external-rails-no-gutter','six-theme-preview-assets','svg-dropdown-resource']}
    report.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');window.hide();window.deleteLater();app.processEvents()
