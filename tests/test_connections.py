from pathlib import Path
from compare import Table






def test_physical_addresses_after_sparse_rows_and_reordered_renamed_columns():
    from workspace import aligned_rows, source_columns
    from compare import compare_tables
    a=Table('old',4,5,['id','value'],[{'id':'a','value':'old'},{'id':'b','value':'delete'}],[5,12])
    b=Table('new',7,8,['Value','Code'],[{'Value':'add','Code':'c'},{'Value':'new','Code':'a'}],[8,21])
    mapping={'id':'Code','value':'Value'}
    changes,_=compare_tables(a,b,mapping,['id'])
    rows=aligned_rows(a,b,mapping,['id'],changes)
    assert [(r['beforeRow'],r['incomingRow']) for r in rows]==[(5,21),(12,None),(None,8)]
    assert source_columns(a,b,mapping)=={'id':{'before':'A','incoming':'B'},'value':{'before':'B','incoming':'A'}}






