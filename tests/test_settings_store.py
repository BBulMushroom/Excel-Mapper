import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import pytest
from settings_store import FileSettingsStore,clean_profile,empty_library,import_settings,export_settings,profile_conflicts


def profile():
    return dict(version=1,name='총무팀',mapping={'id':'id','수량':'수량'},keys=['id'],mode='행 단위',copy_mode='일반 복사',order='원본 순서 유지',old_headers=['id','수량'],new_headers=['id','수량'],old_sheet='자료',new_sheet='자료',old_header=1,new_header=1,old_start=2,new_start=2)


def test_portable_library_import_export_roundtrip_collision_and_no_workbook_data(tmp_path):
    value=profile();value['sources']='must not be saved';value['approved']=[0,1]
    library=import_settings(value)
    assert 'sources' not in library['items'][0]['profile'] and 'approved' not in library['items'][0]['profile']
    library=import_settings(export_settings(value),library)
    assert [i['profile']['name'] for i in library['items']]==['총무팀','총무팀 (2)']
    store=FileSettingsStore(tmp_path/'user'/'settings.json')
    assert store.read()==empty_library()
    store.write(library)
    assert store.read()==library
    again=import_settings(export_settings(store.read()))
    assert [item['profile'] for item in again['items']]==[item['profile'] for item in library['items']]
    assert profile_conflicts(profile(),['id'],['id','수량'])==['원본: 수량']


def test_invalid_or_failed_write_preserves_saved_library(tmp_path):
    store=FileSettingsStore(tmp_path/'settings.json');library=import_settings(profile());store.write(library)
    for invalid in ['{broken',{'version':99},dict(profile(),keys=['missing'])]:
        with pytest.raises(ValueError):import_settings(invalid,library)
    with pytest.raises(ValueError):store.write({'version':2,'items':[]})
    assert store.read()==library
    with patch('settings_store.os.replace',side_effect=OSError('disk unavailable')):
        with pytest.raises(OSError):store.write(import_settings(profile(),library))
    assert store.read()==library and list(tmp_path.iterdir())==[store.path]


