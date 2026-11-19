"""Data-impacting comparison preferences preserve identity and output values."""
from datetime import date
import pytest
from comparison_rules import clean, equivalent
from compare import Table, compare_tables


def test_rules_cover_text_dates_custom_patterns_and_removed_tolerance():
    rules=clean({'ignore_case':True,'tolerance':.01,'dates':'mdy'})
    for a,b in [(' AbC ','abc'),('2027-03-04','03/04/2027'),(date(2027,3,4),'2027/03/04')]:assert equivalent(a,b,rules)
    for a,b in [('00123','123'),('=SUM(A1:A2)','=sum(A1:A2)'),(100,100.001),('2027-03-04','04/03/2027')]:assert not equivalent(a,b,rules)
    assert 'tolerance' not in rules
    assert not equivalent(' abc ','abc',clean({'trim':False}))
    assert not equivalent('ABC','abc',clean())
    assert equivalent('04/03/2027','2027-03-04',clean({'dates':'dmy'}))
    for pattern,source,target in [('YYYYMMDD','20261102','2026-11-02'),('YY-mm-dd','26-11-02','2026/11/02'),('DD.MM.YYYY','29.02.2028','2028-02-29'),('YY/MM/DD','99/01/02','2099-01-02')]:
        rule=clean({'dates':'custom','date_pattern':pattern,'ignore_date_format':True})
        assert equivalent(source,target,rule)
        assert not equivalent(source,target,{**rule,'ignore_date_format':False})
        assert not equivalent(source,'46328',rule)
    assert not equivalent('20260230','2026-03-02',clean({'dates':'custom','date_pattern':'YYYYMMDD','ignore_date_format':True}))
    for pattern in ['', 'YYYY-MM','YYYY-DD-DD','%Y-%m-%d','YYYY-MM-DD HH:mm',[],{}]:
        with pytest.raises(ValueError):clean({'dates':'custom','date_pattern':pattern})
    assert clean({'dates':'off'})==clean()
    assert not clean({'dates':'ymd','ignore_date_format':False})['ignore_date_format']


def test_rules_never_normalize_keys_or_mutate_input_and_keep_default_compatibility():
    left=Table('원본',1,2,['id','value'],[{'id':'A','value':' AbC '},{'id':'B','value':'x'}],[2,3])
    right=Table('비교',1,2,['id','value'],[{'id':'A','value':'abc'},{'id':'b','value':'x'}],[2,3])
    changes,_=compare_tables(left,right,{'id':'id','value':'value'},['id'])
    assert [c['kind'] for c in changes]==['수정','삭제 후보','추가']
    changes,_=compare_tables(left,right,{'id':'id','value':'value'},['id'],{'ignore_case':True})
    assert [c['kind'] for c in changes]==['삭제 후보','추가']
    assert left.rows[0]['value']==' AbC ' and right.rows[0]['value']=='abc'


