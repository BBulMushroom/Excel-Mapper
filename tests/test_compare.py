from io import BytesIO
from pathlib import Path
import openpyxl
from openpyxl.styles import PatternFill
import pytest
from compare import table, demo_files, compare_tables, apply_changes, normalized, recommend


def pack(rows, name='Sheet'):
    wb = openpyxl.Workbook(); ws=wb.active; ws.title=name
    for row in rows: ws.append(row)
    out=BytesIO(); wb.save(out); return out.getvalue()


def setup_demo():
    old, new = demo_files()
    left, right = table(old, 'CCTV 관리대장'), table(new, '장비추출')
    mapping={'관리번호':'DeviceID','카메라명':'DeviceName','IP 주소':'IPv4','설치위치':'Location'}
    changes, unchanged=compare_tables(left,right,mapping,['관리번호'])
    return old,new,left,right,mapping,changes,unchanged


def test_mapping_reordering_and_composite_key():
    old=pack([['ID','site','name'],[1,'A','x'],[1,'B','y']])
    new=pack([['where','code','label'],['B','1','y'],['A','1','z']])
    a,b=table(old,'Sheet'),table(new,'Sheet')
    changes, unchanged=compare_tables(a,b,{'ID':'code','site':'where','name':'label'},['ID','site'])
    assert unchanged==1 and len(changes)==1
    assert changes[0]['old']=='x' and changes[0]['new']=='z'
    assert normalized('001') != normalized(1)


def test_blank_and_duplicate_keys():
    for value in [None, '1']:
        a = table(pack([['id', 'other'], ['1', 'a'], [value, 'b']]), 'Sheet')
        with pytest.raises(ValueError,match='칸이 비어 있습니다|행에 똑같이 있습니다'): compare_tables(a,a,{'id':'id'},['id'])


def test_demo_changes_and_recommendations():
    _,_,left,right,mapping,changes,unchanged=setup_demo()
    assert [c['kind'] for c in changes]==['수정','수정','삭제 후보','추가']
    assert unchanged==1
    assert any(r['원본 열']=='관리번호' and r['비교 열']=='DeviceID' and r['추천 점수']==60 for r in recommend(left,right))


LOG_HEADERS_EXPECTED=['변경 유형','키값','대상 열','변경 전','변경 후','위치','비교 파일','처리 일시']


def test_approved_changes_styles_notes_and_history():
    old,_,left,right,mapping,changes,_=setup_demo()
    approved={c['id'] for c in changes if c['kind']!='삭제 후보'}
    output=apply_changes(old,left,right,mapping,changes,approved)
    wb=openpyxl.load_workbook(BytesIO(output)); ws=wb[left.sheet]
    assert ws['C3'].value=='10.0.0.20'
    assert ws['D3'].value=='별관'
    assert ws['E3'].value=='점검예정'
    assert ws['A4'].value=='003' and ws['A5'].value=='004'
    assert ws['E5'].value is None
    assert ws['A5'].fill.fgColor.rgb==ws['A4'].fill.fgColor.rgb
    assert ws.column_dimensions['A'].width==22
    history=wb.worksheets[-1];rows=list(history.values)
    assert list(rows[0])==LOG_HEADERS_EXPECTED and {r[0] for r in rows[1:]}<={'수정','추가'}      # only what was applied; the unapproved deletion is not logged
    assert all(r[7] and 'T' not in r[7] and '+' not in r[7] for r in rows[1:])
    original=openpyxl.load_workbook(BytesIO(old))
    assert original[left.sheet]['C3'].value=='10.0.0.3'


def test_no_approval_and_explicit_delete():
    old,_,left,right,mapping,changes,_=setup_demo()
    untouched=openpyxl.load_workbook(BytesIO(apply_changes(old,left,right,mapping,changes,set())))[left.sheet]
    assert untouched.max_row==4 and untouched['C3'].value=='10.0.0.3'
    approved={c['id'] for c in changes if c['kind']=='삭제 후보'}
    ws=openpyxl.load_workbook(BytesIO(apply_changes(old,left,right,mapping,changes,approved)))[left.sheet]
    assert ws.max_row==3 and ws['A3'].value=='002'


def test_sort_whole_rows_by_ip():
    old,_,left,right,mapping,changes,_=setup_demo()
    data=apply_changes(old,left,right,mapping,changes,{c['id'] for c in changes if c['kind']!='삭제 후보'},['IP 주소'],ip_sort=True)
    ws=openpyxl.load_workbook(BytesIO(data))[left.sheet]
    assert [ws.cell(r,1).value for r in range(2,6)]==['001','004','003','002']
    assert ws['E5'].value=='점검예정'


def test_incoming_formula_is_text():
    old=pack([['id','value'],['a','before']])
    new=pack([['id','value'],['a','=HYPERLINK("https://example.com")']])
    a,b=table(old,'Sheet'),table(new,'Sheet')
    changes,_=compare_tables(a,b,{'id':'id','value':'value'},['id'])
    result=apply_changes(old,a,b,{'id':'id','value':'value'},changes,{0})
    wb=openpyxl.load_workbook(BytesIO(result))
    assert wb['Sheet']['B2'].data_type=='s'
    assert wb.worksheets[-1]['E2'].data_type=='s'


def test_validation_and_formula_protection():
    data=pack([['id','value'],['a','=1+1']])
    a=table(data,'Sheet')
    with pytest.raises(ValueError, match='여러 원본 열'): compare_tables(a,a,{'id':'value','value':'value'},['id'])
    with pytest.raises(ValueError,match='수식'): apply_changes(data,a,a,{'id':'id'},[],set(),['id'])
    wb=openpyxl.load_workbook(BytesIO(data)); wb.active.merge_cells('A1:B1'); out=BytesIO(); wb.save(out)
    with pytest.raises(ValueError,match='병합'): table(out.getvalue(),'Sheet')




def click(app, label):
    if label=='샘플 실행' and next(x for x in app.selectbox if x.label=='샘플 세트').value is None:
        next(x for x in app.selectbox if x.label=='샘플 세트').select('1').run()
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception


def test_recommendation_and_profile_validation():
    from ui_helpers import suggested_mapping, suggested_key, validate_profile
    _, _, left, right, mapping, _, _ = setup_demo()
    proposed = suggested_mapping(left, right)
    # Only the unmistakable links are made. 'IP 주소'↔'IPv4' share a third of their values and '설치위치' holds one
    # constant value, so with different titles they are left for the user to link.
    assert proposed == {k: v for k, v in mapping.items() if k in ('관리번호', '카메라명')}
    assert suggested_key(left, right, proposed) == '관리번호'
    profile = dict(version=1, name='업무', mapping=mapping, keys=['관리번호'], old_headers=left.headers, new_headers=right.headers)
    assert validate_profile(profile) == profile
    with pytest.raises(ValueError): validate_profile({**profile, 'keys': ['없는 열']})
    with pytest.raises(ValueError): validate_profile({**profile, 'old_start': '2'})


def test_repeated_updates_use_one_log_sheet():
    old, _, left, right, mapping, changes, _ = setup_demo()
    first = apply_changes(old, left, right, mapping, changes, {c['id'] for c in changes})
    wb = openpyxl.load_workbook(BytesIO(first))
    assert wb.sheetnames == ['CCTV 관리대장', '변경 이력']
    original_records = list(wb['변경 이력'].values)
    # A later operation adds records without replacing or duplicating log sheets.
    updated = table(first, left.sheet)
    back_changes, _ = compare_tables(updated, left, {c: c for c in mapping}, ['관리번호'])
    second = apply_changes(first, updated, left, {c: c for c in mapping}, back_changes, {c['id'] for c in back_changes})
    wb = openpyxl.load_workbook(BytesIO(second))
    assert wb.sheetnames == ['CCTV 관리대장', '변경 이력']
    records = list(wb['변경 이력'].values)
    assert records[:len(original_records)] == original_records
    assert len(records) > len(original_records)
    assert records.count(records[0]) == 1


def test_unrelated_sheets_preserved():
    old, _, left, right, mapping, changes, _ = setup_demo()
    wb = openpyxl.load_workbook(BytesIO(old))
    ordinary = wb.create_sheet('20261027_120000'); ordinary.append(['일반 자료'])
    out = BytesIO(); wb.save(out)
    result = apply_changes(out.getvalue(), left, right, mapping, changes, set())
    wb = openpyxl.load_workbook(BytesIO(result))
    assert wb['20261027_120000']['A1'].value == '일반 자료' and wb['변경 이력'].max_row == 1      # nothing approved: header only


def test_log_name_conflict_is_not_overwritten():
    old, _, left, right, mapping, changes, _ = setup_demo()
    wb = openpyxl.load_workbook(BytesIO(old))
    wb.create_sheet('변경 이력').append(['사용자 자료'])
    out = BytesIO(); wb.save(out)
    with pytest.raises(ValueError, match='형식이 다른'):
        apply_changes(out.getvalue(), left, right, mapping, changes, set())


def test_sample_one_schema_networks_counts_and_changes():
    from ipaddress import IPv4Address
    from samples import SAMPLE_SETS, sample_files, MAIN_HEADERS, SUB_HEADERS, CAMERA_TYPES
    assert list(SAMPLE_SETS) == [*(str(n) for n in range(1,16)),'17']
    main_data, sub_data = sample_files('1')
    main, sub = table(main_data, 'CCTV 관리대장'), table(sub_data, 'CCTV 추출자료')
    assert main.headers == MAIN_HEADERS and sub.headers == SUB_HEADERS
    assert len(main.rows) == 500 and len(sub.rows) == 30
    assert [r['순번'] for r in main.rows] == list(range(1,501))
    assert [r['순번'] for r in sub.rows] == list(range(1,31))
    assert not ({r['IP'] for r in main.rows} & {r['IP'] for r in sub.rows})
    for dataset in (main, sub):
        ips = [r['IP'] for r in dataset.rows]
        assert len(set(ips)) == len(ips)
        assert {int(ip.split('.')[2]) for ip in ips} == set(range(190,198))
        assert all(str(IPv4Address(ip)).startswith('172.2.') and 1 <= int(ip.split('.')[-1]) <= 254 for ip in ips)
    assert {r['TTA여부'] for r in main.rows} == {'O','X'}
    assert {r['카메라종류'] for r in main.rows} == set(CAMERA_TYPES)
    assert all(r['ID'] in ('admin','operator','viewer','security') and r['PW'].startswith('SampleOnly!') for r in main.rows)
    mapping = {column: column for column in SUB_HEADERS if column!='순번'}
    changes, unchanged = compare_tables(main, sub, mapping, ['IP'])
    assert unchanged == 0
    assert {kind:sum(c['kind']==kind for c in changes) for kind in ['수정','추가','삭제 후보']} == {'수정':0,'추가':30,'삭제 후보':500}
    assert sorted(c['column'] for c in changes if c['kind']=='수정') == []
    assert sample_files('1') == (main_data, sub_data)


def test_sample_two_full_update_and_multiple_changed_fields():
    from samples import sample_files, SUB_HEADERS
    main_data, sub_data = sample_files('2')
    main, sub = table(main_data, 'CCTV 관리대장'), table(sub_data, 'CCTV 추출자료')
    assert len(main.rows)==500 and len(sub.rows)==510
    assert [r['순번'] for r in sub.rows]==list(range(1,511))
    mapping={c:c for c in SUB_HEADERS if c!='순번'}
    changes, unchanged=compare_tables(main,sub,mapping,['IP'])
    assert unchanged==429
    assert {kind:sum(c['kind']==kind for c in changes) for kind in ['수정','추가','삭제 후보']}=={'수정':82,'추가':15,'삭제 후보':5}
    assert {c['column'] for c in changes if c['kind']=='수정'}=={'카메라명','모델명'}
    output=apply_changes(main_data,main,sub,mapping,changes,{c['id'] for c in changes})
    result=table(output,main.sheet)
    assert len(result.rows)==510
    assert [r['순번'] for r in result.rows]==list(range(1,511))
    assert {r['IP'] for r in result.rows}=={r['IP'] for r in sub.rows}
    originals={r['IP']:r for r in main.rows}
    assert all(r['PW']==originals[r['IP']]['PW'] for r in result.rows if r['IP'] in originals)
    assert result.rows[-1]['PW'] is None


def test_same_headers_map_even_when_every_record_is_new():
    from ui_helpers import suggested_mapping
    from samples import sample_files, SUB_HEADERS
    a,b=sample_files('1')
    mapping=suggested_mapping(table(a,'CCTV 관리대장'),table(b,'CCTV 추출자료'))
    assert mapping == {column:column for column in SUB_HEADERS if column!='순번'}


def test_mapping_analysis_includes_values_after_first_thousand_rows():
    from compare import mapping_score
    rows=[['value']]+[[i] for i in range(1001)]
    a=table(pack(rows),'Sheet')
    b=table(pack([['value'],[1000]]),'Sheet')
    assert mapping_score(a,b,'value','value')['공통값 비율']==100


def test_aligned_workspace_rows_and_change_locations():
    from workspace import aligned_rows
    _,_,left,right,mapping,changes,_=setup_demo()
    rows=aligned_rows(left,right,mapping,['관리번호'],changes)
    assert [r['label'] for r in rows]==['001','002','003','004']
    modified=rows[1]
    assert modified['before']['IP 주소']=='10.0.0.3'
    assert modified['incoming']['IP 주소']=='10.0.0.20'
    assert {c['column'] for c in modified['changes']}=={'IP 주소','설치위치'}
    assert rows[2]['before'] is not None and rows[2]['incoming'] is None
    assert rows[2]['changes'][0]['kind']=='삭제'
    assert rows[3]['before'] is None and rows[3]['incoming']['관리번호']=='004'
    assert rows[3]['incoming']['담당자 메모']==''


def test_selection_validation_and_row_mode():
    from workspace import effective_selection
    *_,changes,_=setup_demo()
    assert effective_selection(changes,[0,999])=={0}
    assert effective_selection(changes,[0],row_mode=True)=={0,1}
    assert effective_selection(changes,[],row_mode=True)==set()






def test_sequence_never_identifies_or_changes_data_and_is_renumbered_after_sort():
    a=table(pack([['순번','id','v'],[1,'a','A'],[2,'b','B']]),'Sheet')
    data=pack([['순번','id','v'],[1,'b','B'],[2,'a','A'],[3,'c','C']])
    b=table(data,'Sheet'); mapping={'순번':'순번','id':'id','v':'v'}
    changes,unchanged=compare_tables(a,b,mapping,['id'])
    assert unchanged==2 and len(changes)==1 and changes[0]['kind']=='추가'
    with pytest.raises(ValueError,match='순번'): compare_tables(a,b,mapping,['순번'])
    result=apply_changes(pack([['순번','id','v'],[1,'a','A'],[2,'b','B']]),a,b,mapping,changes,{0},['id'],True)
    rows=table(result,'Sheet').rows
    assert [r['id'] for r in rows]==['c','b','a']
    assert [r['순번'] for r in rows]==[1,2,3]


def test_sample_names_have_no_number_suffix_and_sequence_is_local():
    import re
    from samples import sample_files
    for sid,count in [('1',30),('2',510)]:
        main,new=sample_files(sid)
        for data,name in [(main,'CCTV 관리대장'),(new,'CCTV 추출자료')]:
            t=table(data,name)
            assert not any(re.search(r'-\d+',r['카메라명']) for r in t.rows)
            assert [r['순번'] for r in t.rows]==list(range(1,len(t.rows)+1))




def test_sample_names_are_unique_and_can_be_used_as_keys():
    from samples import sample_files
    from ui_helpers import suggested_mapping
    for sid in ['1','2']:
        old,new=sample_files(sid)
        left,right=table(old,'CCTV 관리대장'),table(new,'CCTV 추출자료')
        for dataset in [left,right]:
            names=[r['카메라명'] for r in dataset.rows]
            assert len(names)==len(set(names))
            assert all(any(direction in name for direction in ['동측','서측','남측','북측']) for name in names)
        changes,_=compare_tables(left,right,suggested_mapping(left,right),['카메라명'])
        assert changes
    # Distinct locations across former repetition boundaries, without synthetic numeric suffixes.
    from samples import device
    assert len({device(i)[1] for i in range(1,531)})==530




def test_header_problem_names_the_columns():
    from compare import table_from_cells
    values={(1,1):'코드',(1,2):'분류',(1,3):'분류 ',(2,1):'a',(2,4):'메모'}
    with pytest.raises(ValueError,match=r"제목 행\(1행\): D열 이름이 비어 있습니다.*B, C열 이름이 '분류'"):table_from_cells('자료',values,set())
