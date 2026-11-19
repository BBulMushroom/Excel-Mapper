import argparse
import json
import os
from pathlib import Path
import sys
import traceback


def main():
    if any(arg=='--compare' or arg.startswith('--compare=') for arg in sys.argv[1:]):
        # Command line mode: no window and no Qt import.
        root=str(Path(__file__).resolve().parents[1])
        if root not in sys.path:sys.path.insert(0,root)
        import cli
        return cli.main(sys.argv[1:])
    parser=argparse.ArgumentParser(description='Excel Mapper native desktop')
    parser.add_argument('--smoke-test',metavar='REPORT_JSON');args=parser.parse_args()
    if args.smoke_test:os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QSettings
        from PySide6.QtGui import QFont,QFontDatabase
        from .style import NativeStyle
        from .version import APP_VERSION
        app=QApplication(sys.argv[:1]);app.setOrganizationName('ExcelMapper');app.setApplicationName('ExcelMapper Native');app.native_style=NativeStyle();app.setStyle(app.native_style);app.setApplicationDisplayName('Excel Mapper');app.setApplicationVersion(APP_VERSION)
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
        font=root/'desktop'/'fonts'/'NotoSansKR-Regular.ttf'
        if not font.exists():font=root/'components'/'workspace'/'fonts'/'NotoSansKR-Regular.ttf'
        if font.exists():
            identity=QFontDatabase.addApplicationFont(str(font));families=QFontDatabase.applicationFontFamilies(identity)
            if families:
                # Use Windows' own Korean font on real desktops; retain bundled
                # glyph coverage on headless CI and non-Windows systems.
                available=QFontDatabase.families()
                family='Malgun Gothic' if sys.platform=='win32' and 'Malgun Gothic' in available else families[0]
                ui_font=QFont(family);ui_font.setPixelSize(13)
                app.setFont(ui_font)
        if args.smoke_test:
            report=Path(args.smoke_test);report.parent.mkdir(parents=True,exist_ok=True)
            QSettings.setDefaultFormat(QSettings.Format.IniFormat);QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,str(report.parent/'test-settings'))
            from .smoke import run
            run(app,report);return 0
        from .ui import Window
        window=Window();window.show();return app.exec()
    except Exception as exc:
        if args.smoke_test:Path(args.smoke_test).write_text(json.dumps({'status':'failed','error':str(exc),'traceback':traceback.format_exc()},ensure_ascii=False,indent=2),encoding='utf-8')
        else:
            log=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'ExcelMapper' / 'startup-error.log'
            log.parent.mkdir(parents=True,exist_ok=True);log.write_text(traceback.format_exc(),encoding='utf-8')
        return 1
