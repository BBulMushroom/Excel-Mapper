"""First-impression polish: contrast, focus rings, first screen, status bar, icon and file properties."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import pytest
pytest.importorskip('PySide6.QtWidgets')
from test_desktop_v03 import app,w
from display_theme import palettes,contrast
ROOT=Path(__file__).resolve().parents[1]


def test_every_theme_has_visible_control_outlines_and_readable_helper_text():
    for name,palette in palettes().items():
        t=palette['tokens']
        for surface in ('bg','panel','input'):
            assert contrast(t['control'],t[surface])>=3.0,(name,surface)       # outlines of buttons and inputs
            assert contrast(t['muted'],t[surface])>=4.5,(name,surface)         # helper text
        assert contrast(t['ring'],t['input'])>=3.0,name                        # keyboard focus ring


def test_focus_ring_and_8px_layout_rhythm(w,app):
    style=w.styleSheet();ring=w.tokens['ring']
    for selector in ('QToolButton:focus','QLineEdit:focus','QComboBox:focus','QTableView:focus'):assert selector in style
    assert f"border:1px solid {ring}" in style and "QWidget#menuRow QToolButton {border:1px solid transparent" in style   # no layout jump on focus
    layout=w.root.layout();margins=layout.contentsMargins();assert layout.spacing()==8 and (margins.left(),margins.top())==(16,8)
    assert w.options.layout().contentsMargins().left()==16


def test_first_screen_card_status_bar_and_icon(w,app):
    from desktop.ui import Window,app_icon
    from desktop.session import Session
    from desktop.version import APP_VERSION,APP_NAME
    window=Window();window.show();app.processEvents();window.place_welcome()
    assert window.welcome.isVisible() and '불러오세요' in window.welcome.findChild(type(window.status_summary),'welcomeTitle').text()
    area=window.split.geometry();center=window.welcome.geometry().center();assert abs(center.x()-area.center().x())<=2
    assert window.statusBar().isVisible() and '파일을 열어' in window.status_summary.text()
    assert not window.windowIcon().isNull() and not app_icon().isNull() and window.windowTitle().startswith(APP_NAME)
    window.session=w.session;window.refresh();app.processEvents()
    assert not window.welcome.isVisible() and '원본.xlsx' in window.status_summary.text() and '변경' in window.status_summary.text() and '100%' in window.status_summary.text()
    window.hide();window.deleteLater()


def test_icon_file_and_windows_file_properties_match_the_program_version():
    from PIL import Image
    from desktop.version import APP_VERSION
    icon=Image.open(ROOT/'desktop'/'icons'/'app.ico');assert {(16,16),(32,32),(256,256)}<=set(icon.info['sizes'])
    text=(ROOT/'desktop'/'version_info.txt').read_text(encoding='utf-8')
    assert f"StringStruct('ProductVersion','{APP_VERSION}')" in text and "StringStruct('OriginalFilename','ExcelMapper.exe')" in text
    assert ','.join([str(int(p)) for p in APP_VERSION.split('.')]+['0','0']) in text
    workflow=(ROOT/'.github'/'workflows'/'windows-desktop.yml').read_text(encoding='utf-8')
    assert '--icon desktop/icons/app.ico' in workflow and '--version-file desktop/version_info.txt' in workflow


def test_about_box_text_uses_the_central_version():
    import inspect
    from desktop import ui
    assert 'APP_VERSION' in inspect.getsource(ui.Window.about)
