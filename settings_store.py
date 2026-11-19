"""Portable settings format and per-user disk storage for the future desktop app.

The web adapter stores the same envelope in browser storage; this module never
writes to the cloud app server on behalf of a public user.
"""
from copy import deepcopy
import json
import os
import shutil
from pathlib import Path
import tempfile
from uuid import uuid4
import ui_helpers

PROFILE_FIELDS=('version','name','mapping','keys','mode','copy_mode','order','sort_columns',
                'sort_direction','sort_type','old_sheet','new_sheet','old_header','old_start',
                'new_header','new_start','old_headers','new_headers','comparison_rules')
MAX_ITEMS=500


def clean_profile(profile):
    ui_helpers.validate_profile(profile)
    if len(profile['name'].strip())>100:raise ValueError('설정 이름은 100자 이내로 입력하세요.')
    return deepcopy({key:profile[key] for key in PROFILE_FIELDS if key in profile})


def empty_library():return {'version':1,'items':[],'activeId':None}


def validate_library(value):
    if not isinstance(value,dict) or value.get('version')!=1 or not isinstance(value.get('items'),list) or len(value['items'])>MAX_ITEMS:
        raise ValueError('설정 보관함 형식을 확인하세요.')
    items=[];ids=set()
    for item in value['items']:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not item['id'] or item['id'] in ids:
            raise ValueError('설정 ID가 올바르지 않습니다.')
        ids.add(item['id']);items.append({'id':item['id'],'profile':clean_profile(item.get('profile'))})
    return {'version':1,'items':items,'activeId':value.get('activeId') if isinstance(value.get('activeId'),str) and value.get('activeId') in ids else None}


def import_settings(raw,library=None):
    try:decoded=json.loads(raw) if isinstance(raw,(str,bytes)) else raw
    except (ValueError,TypeError) as exc:raise ValueError('설정 JSON 파일을 확인하세요.') from exc
    target=validate_library(library or empty_library())
    profiles=[entry['profile'] for entry in validate_library(decoded)['items']] if isinstance(decoded,dict) and 'items' in decoded else [clean_profile(decoded)]
    if len(target['items'])+len(profiles)>MAX_ITEMS:raise ValueError('저장된 설정이 너무 많습니다.')
    names={entry['profile']['name'] for entry in target['items']}
    for profile in profiles:
        profile=deepcopy(profile);base=profile['name'];name=base;n=2
        while name in names:
            suffix=f' ({n})';name=base[:100-len(suffix)]+suffix;n+=1
        profile['name']=name;names.add(name);identity=uuid4().hex
        target['items'].append({'id':identity,'profile':profile});target['activeId']=identity
    return target


def export_settings(value):
    cleaned=validate_library(value) if isinstance(value,dict) and 'items' in value else clean_profile(value)
    return json.dumps(cleaned,ensure_ascii=False,indent=2)


def profile_conflicts(profile,old_headers,new_headers):
    missing_old=[name for name in profile['mapping'] if name not in old_headers]
    missing_new=[name for name in profile['mapping'].values() if name not in new_headers]
    return [*['원본: '+name for name in missing_old],*['비교: '+name for name in missing_new]]


def user_settings_path():
    if os.name=='nt':root=Path(os.environ.get('APPDATA',Path.home()/'AppData'/'Roaming'))
    else:root=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local'/'share'))
    return root/'ExcelMapper'/'settings.json'


def legacy_settings_path():
    """Location used while the program was still called Excel Review."""
    return user_settings_path().parent.parent/'ExcelReview'/'settings.json'


class FileSettingsStore:
    """Native desktop adapter: validate, then atomically replace a user-owned file."""
    def __init__(self,path=None):
        self.path=Path(path) if path is not None else user_settings_path()
        if path is None and not self.path.exists():
            old=legacy_settings_path()
            if old.exists():
                # Carry saved presets over from the old program name; the old file is left untouched.
                try:self.path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old,self.path)
                except OSError:pass
    def read(self):
        if not self.path.exists():return empty_library()
        try:return validate_library(json.loads(self.path.read_text(encoding='utf-8')))
        except (ValueError,TypeError) as exc:raise ValueError('저장된 설정을 읽을 수 없습니다. Import 백업 파일을 확인하세요.') from exc
    def write(self,library):
        text=export_settings(validate_library(library));self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.path.parent,delete=False) as stream:
                temporary=Path(stream.name);stream.write(text);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path)
        finally:
            if temporary is not None and temporary.exists():temporary.unlink()
