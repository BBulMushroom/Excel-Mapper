from io import BytesIO
from zipfile import ZipFile
from pathlib import Path
import openpyxl
import pytest
from samples import sample_files,sample_collection,collection_zip,BUDGET_HEADERS,BUDGET_DEPARTMENTS
from ui_helpers import detect_layout,suggested_keys,suggested_mapping
from compare import table,compare_tables,apply_changes
from workspace import aligned_rows,formula_values
import collection_flow as flow


@pytest.mark.parametrize('sid,column,cache',[('13','합계',25),('14','금액',22000)])
def test_formula_samples_have_calculation_results_for_values_copy(sid,column,cache):
    old,new=sample_files(sid);a,b=detect_layout(old),detect_layout(new)
    left=table(old,a['sheet']);right=table(new,b['sheet']);mapping=suggested_mapping(left,right);keys=suggested_keys(left,right,mapping)
    changes,_=compare_tables(left,right,mapping,keys);calculated=formula_values(new,right)
    rows=aligned_rows(left,right,mapping,keys,changes,calculated,formula_values(old,left))
    key='항목코드' if sid=='13' else '품목코드';field='합계' if sid=='13' else '금액'
    row=next(row for row in rows if row['key']==['ITEM-011'])
    assert row['incoming'][field].startswith('=') and row['incomingCalculated'][field]==str(cache)
    original_row=next(r for r in rows if r['beforeRow']==2)
    assert original_row['beforeCalculated'][field]==formula_values(old,left)[2][field]
    assert original_row['before'][field].startswith('=')
    result=apply_changes(old,left,right,mapping,changes,{c['id'] for c in changes},comparison_data=new,copy_mode='값만 복사')
    wb=openpyxl.load_workbook(BytesIO(result));target='F12' if sid=='13' else 'D12'
    assert wb[left.sheet][target].value==cache and wb[left.sheet][target].data_type=='n'
    if sid=='13':
        original=openpyxl.load_workbook(BytesIO(old),data_only=True)
        assert original[left.sheet]['F2'].value==15


def test_missing_cache_and_literal_equals_strings_are_distinguished():
    wb=openpyxl.Workbook();ws=wb.active;ws.append(['id','v']);ws.append(['a','=1+1']);ws.append(['b','=literal']);ws['B3'].data_type='s'
    data=BytesIO();wb.save(data);dataset=table(data.getvalue(),ws.title)
    assert dataset.formula_cells=={2:['v']}
    assert formula_values(data.getvalue(),dataset)=={2:{'v':None}}
    rows=aligned_rows(dataset,dataset,{'id':'id'},['id'],[],{},formula_values(data.getvalue(),dataset))
    assert rows[0]['beforeCalculated']=={'v':None} and rows[1]['beforeCalculated']=={}
    assert rows[0]['before']['v']=='=1+1'


def test_sample15_ten_files_accumulate_without_duplicates_and_can_skip():
    original,comparisons=sample_collection();assert len(comparisons)==10
    assert not table(original,'예산취합대장').rows
    assert table(original,'예산취합대장').headers==BUDGET_HEADERS
    assert '수량' not in BUDGET_HEADERS and '단가' not in BUDGET_HEADERS
    for i,(data,filename) in enumerate(comparisons):
        entries=table(data,'예산요청서').rows
        assert {row['부서'] for row in entries}=={BUDGET_DEPARTMENTS[i]}
        assert all(isinstance(row['요청금액'],int) and row['요청금액']>0 for row in entries)
        assert BUDGET_DEPARTMENTS[i] in filename
    assert all(len(table(data,'예산요청서').rows)==30 for data,_ in comparisons)
    with ZipFile(BytesIO(collection_zip(comparisons))) as archive:assert len(archive.namelist())==10
    for skipped in (None,4):
        state={};flow.start(state,original,comparisons,'원본.xlsx')
        for index in range(10):
            old,new=state['sources'];left=table(old,'예산취합대장');right=table(new,'예산요청서');mapping=suggested_mapping(left,right);keys=suggested_keys(left,right,mapping)
            assert keys==['예산항목코드']
            changes,_=compare_tables(left,right,mapping,keys);chosen={c['id'] for c in changes if c['kind']!='삭제 후보'}
            assert sum(c['kind']=='추가' for c in changes)==30
            result=None if index==skipped else apply_changes(old,left,right,mapping,changes,chosen,comparison_data=new)
            flow.advance(state,chosen,result)
        rows=table(state['output'],'예산취합대장').rows
        assert len(rows)==(300 if skipped is None else 270)
        assert len({row['예산항목코드'] for row in rows})==len(rows)
        expected=sum(row['요청금액'] for i,(blob,_) in enumerate(comparisons) if i!=skipped for row in table(blob,'예산요청서').rows)
        assert sum(row['요청금액'] for row in rows)==expected


