from copy import deepcopy, copy
from io import BytesIO
import pytest
from compare import table, compare_tables, apply_changes, load
from samples import SAMPLE_SETS, sample_files
from ui_helpers import suggested_mapping

KEYS={'3':['자산코드'],'4':['품목코드','창고'],'5':['거래처코드'],'6':['자산코드'],'8':['코드'],'9':['자산코드'],'10':['품목코드'],'11':['자산코드']}
EXPECTED={'3':(82,15,5,510),'4':(50,15,5,510),'5':(40,15,5,510),'6':(82,15,5,510),'8':(12,0,0,500),'9':(0,0,0,500),'10':(19,0,5,500),'11':(0,50,500,550)}   # the 10k-row set is covered by test_fastread, test_desktop (sample 5) and benchmarks


def case(sid):
    old,new=sample_files(sid); meta=SAMPLE_SETS[sid]
    a,b=load(old),load(new)
    left=table(old,a.sheetnames[0],meta.get('old_header',1),meta.get('old_start',2))
    right=table(new,b.sheetnames[0],meta.get('new_header',1),meta.get('new_start',2))
    return old,new,left,right,suggested_mapping(left,right)


@pytest.mark.parametrize('sid',list(EXPECTED))
def test_sample_comparison_export_and_preservation(sid):
    old,new,left,right,mapping=case(sid)
    changes,unchanged=compare_tables(left,right,mapping,KEYS[sid])
    mods,adds,dels,count=EXPECTED[sid]
    assert [sum(c['kind']==kind for c in changes) for kind in ['수정','추가','삭제 후보']]==[mods,adds,dels]
    if sid=='10':
        with pytest.raises(ValueError,match='수식'): apply_changes(old,left,right,mapping,changes,{c['id'] for c in changes})
        from openpyxl import load_workbook
        cached=load_workbook(BytesIO(old),data_only=True)
        assert cached[left.sheet]['E2'].value==5984000
        for row in cached[left.sheet].iter_rows(min_row=2):assert row[4].value==row[2].value*row[3].value*11//10

    chosen={c['id'] for c in changes if sid not in ('10','11') or c['kind']!='삭제 후보'}
    output=apply_changes(old,left,right,mapping,changes,chosen)
    result=table(output,left.sheet,left.header_row,left.start_row)
    assert len(result.rows)==count
    assert '순번' not in result.headers
    wb=load(output); source=load(old)
    assert wb[left.sheet].column_dimensions['A'].width==source[left.sheet].column_dimensions['A'].width
    assert copy(wb[left.sheet]['A'+str(left.header_row)].fill)==copy(source[left.sheet]['A'+str(left.header_row)].fill)
    assert '변경 이력' in wb.sheetnames
    if sid=='5':
        assert mapping=={'거래처코드':'CustomerID','거래처명':'CompanyName','전화번호':'Tel','주소':'Address'}
        assert result.rows[0]['비고']=='기존 계약 유지'
        assert result.rows[-1]['비고'] is None
    if sid=='6': assert wb[left.sheet]['A1'].value=='자산 현황 보고서'
    if sid=='8':
        by_code={str(r['코드']).strip():r for r in result.rows}
        assert '00123' in by_code and '123' in by_code and len(by_code)==500
    if sid=='10':
        assert wb[left.sheet]['E2'].value=='=C2*D2*세율!$B$1'
        assert wb['세율']['B1'].value==1.1
        assert result.rows[0]['비고']=='원본 메모'
        with pytest.raises(ValueError,match='수식'): apply_changes(old,left,right,mapping,changes,chosen,['수량'])
    if sid=='9': assert unchanged==500


def test_compound_key_is_required_for_warehouse_sample():
    old,new,left,right,mapping=case('4')
    with pytest.raises(ValueError,match='원본 파일 · .*2행과 3행에 똑같이'): compare_tables(left,right,mapping,['품목코드'])
    assert compare_tables(left,right,mapping,['품목코드','창고'])[0]


def test_intentionally_invalid_sample_reports_both_problems():
    old,new,left,right,mapping=case('7')
    with pytest.raises(ValueError,match='원본 파일 · .*2행과 3행에 똑같이'): compare_tables(left,right,mapping,['자산코드'])
    left=deepcopy(left);left.rows[1]['자산코드']='AS00002'
    with pytest.raises(ValueError,match='비교 파일 · .*행: 기준 키 .자산코드. 칸이 비어'): compare_tables(left,right,mapping,['자산코드'])


def test_header_position_sample_requires_correct_range():
    old,new,left,right,mapping=case('6')
    with pytest.raises(ValueError,match='제목 행'): table(old,left.sheet)
    assert len(left.rows)==500 and left.header_row==4 and left.start_row==5


