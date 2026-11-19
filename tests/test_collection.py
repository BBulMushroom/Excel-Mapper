from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import openpyxl
import collection_flow as flow
from compare import table,compare_tables,apply_changes


def data(rows):
    wb=openpyxl.Workbook();ws=wb.active;ws.title='자료'
    ws.append(['id','수량'])
    for row in rows:ws.append(row)
    out=BytesIO();wb.save(out);return out.getvalue()


def apply(state):
    old,new=state['sources'];a,b=table(old,'자료'),table(new,'자료')
    changes,_=compare_tables(a,b,{'id':'id','수량':'수량'},['id'])
    selected={c['id'] for c in changes if c['kind']!='삭제 후보'}
    return apply_changes(old,a,b,{'id':'id','수량':'수량'},changes,selected,comparison_data=new),selected


def values(blob):return {r['id']:r['수량'] for r in table(blob,'자료').rows}


def test_sequential_collection_rollback_reapply_skip_and_completion():
    state={};original=data([['a',1],['b',2]])
    flow.start(state,original,[(data([['a',3],['c',7]]),'first.xlsx'),(data([['d',9]]),'second.xlsx'),(data([['b',20]]),'third.xlsx')],'original.xlsx')
    output,selected=apply(state);flow.advance(state,selected,output)
    assert values(state['sources'][0])=={'a':3,'b':2,'c':7}
    assert state['queue_index']==1
    flow.previous(state)
    assert state['sources'][0]==original and state['pending_approvals']==sorted(selected)
    output,chosen=apply(state);flow.advance(state,chosen,output)
    assert len(values(state['sources'][0]))==3  # c is never added twice.
    flow.advance(state,set(),None)
    output,chosen=apply(state);flow.advance(state,chosen,output)
    assert state['queue_complete'] and state['queue_decisions']==['반영','건너뜀','반영']
    assert values(state['output'])=={'a':3,'b':20,'c':7}
    assert state['collection_original'][0]==original
    flow.previous(state)
    assert not state['queue_complete'] and values(state['sources'][0])=={'a':3,'b':2,'c':7}






def test_sort_modes_preserve_original_order_by_default_and_sort_numbers_and_ip():
    old=data([['a',10],['b',2],['c',1]]);a=table(old,'자료')
    mapping={'id':'id','수량':'수량'}
    unchanged=apply_changes(old,a,a,mapping,[],set())
    assert [r['id'] for r in table(unchanged,'자료').rows]==['a','b','c']
    for mode,expected in [('자동',['c','b','a']),('숫자·IP',['c','b','a']),('문자',['c','a','b'])]:
        output=apply_changes(old,a,a,mapping,[],set(),['수량'],sort_type=mode)
        assert [r['id'] for r in table(output,'자료').rows]==expected
    ip_data=data([['a','172.2.190.100'],['b','172.2.190.2']]);a=table(ip_data,'자료')
    output=apply_changes(ip_data,a,a,mapping,[],set(),['수량'],sort_type='자동')
    assert [r['id'] for r in table(output,'자료').rows]==['b','a']




