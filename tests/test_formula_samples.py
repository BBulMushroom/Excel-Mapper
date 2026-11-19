"""Fixtures and explicit acceptance gaps for formula-copy samples 13 and 14."""
from io import BytesIO
from pathlib import Path
import openpyxl
from openpyxl.formula.translate import Translator
import pytest
from samples import SAMPLE_SETS, FORMULA_SAMPLE_ORDER, sample_files
from compare import table, compare_tables, apply_changes
from ui_helpers import suggested_mapping, suggested_keys, detect_layout


def sample_case(sid):
    old,new=sample_files(sid)
    a,b=detect_layout(old),detect_layout(new)
    left=table(old,a['sheet'],a['header'],a['start']);right=table(new,b['sheet'],b['header'],b['start'])
    mapping=suggested_mapping(left,right);keys=suggested_keys(left,right,mapping)
    changes,_=compare_tables(left,right,mapping,keys)
    return old,new,left,right,mapping,keys,changes


@pytest.mark.parametrize('sid',['13','14'])
def test_formula_sample_is_real_formula_with_reordered_rows_and_distinct_price_context(sid):
    old,new,left,right,mapping,keys,changes=sample_case(sid)
    assert (len(left.rows),len(right.rows))==(10,12)
    assert [r[keys[0]] for r in right.rows]==[f'ITEM-{n:03d}' for n in FORMULA_SAMPLE_ORDER]
    assert keys==(['항목코드'] if sid=='13' else ['품목코드'])
    assert [sum(c['kind']==k for c in changes) for k in ['수정','추가','삭제 후보']]==[1,2,0]   # moved rows keep equivalent formulas
    col='F' if sid=='13' else 'D'
    for data,t in [(old,left),(new,right)]:
        wb=openpyxl.load_workbook(BytesIO(data));ws=wb[t.sheet]
        try:
            for r in range(2,len(t.rows)+2):
                cell=ws[f'{col}{r}']
                assert cell.data_type=='f'
                assert cell.value==(f'=SUM(A{r}:E{r})' if sid=='13' else f'=C{r}*단가표!$B$2')
            assert wb.calculation.fullCalcOnLoad and wb.calculation.calcMode=='auto'
            assert not wb._external_links
        finally:wb.close()
    if sid=='13':
        assert [left.rows[0][c] for c in left.headers[:5]]==[1,2,3,4,5]
        assert sum(left.rows[0][c] for c in left.headers[:5])==15
        assert next(r for r in right.rows if r['항목코드']=='ITEM-003')['값1']==30
    else:
        a=openpyxl.load_workbook(BytesIO(old));b=openpyxl.load_workbook(BytesIO(new))
        try:assert a['단가표']['B2'].value==1000 and b['단가표']['B2'].value==2000
        finally:a.close();b.close()
        assert next(r for r in right.rows if r['품목코드']=='ITEM-003')['수량']==8


@pytest.mark.parametrize('sid',['13','14'])
def test_formula_samples_copy_active_formulas_and_translate_references(sid):
    old,new,left,right,mapping,keys,changes=sample_case(sid)
    col='F' if sid=='13' else 'D';field='합계' if sid=='13' else '금액'
    formula_changes=[c for c in changes if c['kind']=='수정' and c['column']==field]
    assert not formula_changes            # a formula that only moved with its row (=SUM(A2:E2) on row 2 vs A5:E5 on row 5) is not a change
    output=apply_changes(old,left,right,mapping,changes,{c['id'] for c in changes},comparison_data=new)
    wb=openpyxl.load_workbook(BytesIO(output));ws=wb[left.sheet]
    try:
        assert ws[f'{col}12'].data_type=='f'
        assert ws[f'{col}12'].value==('=SUM(A12:E12)' if sid=='13' else "=C12*'단가표 (비교)'!$B$2")
        assert ws[f'{col}13'].value==('=SUM(A13:E13)' if sid=='13' else "=C13*'단가표 (비교)'!$B$2")
        assert ws[f'{col}2'].data_type=='f'
        if sid=='14':
            assert wb['단가표']['B2'].value==1000
            assert wb['단가표 (비교)']['B2'].value==2000
    finally:wb.close()
    # Excluding formula-cell edits still preserves the original formulas, and newly added formulas are active.
    chosen={c['id'] for c in changes if c not in formula_changes}
    wb=openpyxl.load_workbook(BytesIO(apply_changes(old,left,right,mapping,changes,chosen,comparison_data=new)))
    try:
        for r in range(2,12):assert wb[left.sheet][f'{col}{r}'].data_type=='f'
        assert wb[left.sheet][f'{col}12'].data_type=='f'
    finally:wb.close()


@pytest.mark.parametrize('sid',['13','14'])
def test_formula_copy_acceptance_target_for_new_rows(sid):
    old,new,left,right,mapping,keys,changes=sample_case(sid)
    wb=openpyxl.load_workbook(BytesIO(apply_changes(old,left,right,mapping,changes,{c['id'] for c in changes},comparison_data=new)))
    try:
        col='F' if sid=='13' else 'D'
        assert wb[left.sheet][f'{col}12'].data_type=='f'
        formula=wb[left.sheet][f'{col}12'].value
        if sid=='13':assert formula=='=SUM(A12:E12)'
        else:assert formula.startswith('=C12*') and '$B$2' in formula
    finally:wb.close()




