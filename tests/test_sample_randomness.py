"""Sample realism changes must not sacrifice identity or the intended change counts."""
from samples import sample_files,device,asset
from compare import table,compare_tables
from ui_helpers import suggested_mapping


def test_camera_records_are_unique_and_not_periodically_allocated():
    rows=[device(i) for i in range(1,531)]
    assert len({r[1] for r in rows})==530 and len({r[2] for r in rows})==530
    assert all(r==device(i) for i,r in enumerate(rows,1))
    networks=[int(r[2].split('.')[2]) for r in rows]
    assert any(networks[i]!=networks[i+8] for i in range(30))
    old,new=sample_files('2');a,b=table(old,'CCTV 관리대장'),table(new,'CCTV 추출자료')
    changes,_=compare_tables(a,b,suggested_mapping(a,b),['IP'])
    changed=[c['left']+1 for c in changes if c['kind']=='수정']
    assert len(changed)==82 and len({n%10 for n in changed})>=8
    deleted=[c['left'] for c in changes if c['kind']=='삭제 후보']
    assert max(deleted)-min(deleted)>100


def test_assets_have_realistic_names_models_and_mixed_assignments():
    rows=[asset(i) for i in range(1,501)]
    assert len({r[5] for r in rows})>15 and len({r[6] for r in rows})>5
    assert not any('업무용 자산 ' in r[1] or 'MODEL-' in r[3] for r in rows)
    assert any(rows[i][2]!=rows[i+3][2] for i in range(40))
    old,new=sample_files('5');a,b=table(old,'거래처 관리'),table(new,'CRM Export')
    changes,_=compare_tables(a,b,suggested_mapping(a,b),['거래처코드'])
    mods=[c for c in changes if c['kind']=='수정']
    assert len(mods)==40 and len({tuple(c['key']) for c in mods})==32
    assert len({r['거래처명'] for r in a.rows})==500
