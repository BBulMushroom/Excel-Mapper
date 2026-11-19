"""The program is now Excel Mapper; settings saved under the old Excel Review name must survive."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
import pytest


def test_preset_file_is_copied_from_the_old_folder(tmp_path,monkeypatch):
    import settings_store
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path));monkeypatch.setattr(settings_store.os,'name','posix')
    old=tmp_path/'ExcelReview'/'settings.json';old.parent.mkdir();library=settings_store.empty_library();old.write_text(settings_store.export_settings(library),encoding='utf-8')
    store=settings_store.FileSettingsStore()
    assert store.path==tmp_path/'ExcelMapper'/'settings.json' and store.path.exists() and old.exists()
    assert json.loads(store.path.read_text(encoding='utf-8'))==json.loads(old.read_text(encoding='utf-8'))


def test_new_install_has_no_leftover_file(tmp_path,monkeypatch):
    import settings_store
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path));monkeypatch.setattr(settings_store.os,'name','posix')
    store=settings_store.FileSettingsStore();assert not store.path.exists() and store.read()==settings_store.empty_library()


def test_screen_settings_move_to_the_new_name_and_titles_are_renamed(tmp_path_factory):
    pytest.importorskip('PySide6.QtWidgets')
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat);QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,str(tmp_path_factory.mktemp('rename-settings')))
    old=QSettings(QSettings.defaultFormat(),QSettings.Scope.UserScope,'ExcelReview','Native');old.setValue('theme','navy');old.sync()
    from desktop.ui import Window
    window=Window()
    assert window.preferences.value('theme')=='navy' and window.theme=='navy'
    assert window.windowTitle().startswith('Excel Mapper')
    window.deleteLater()
