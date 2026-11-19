"""Correctness of optimized paths, without machine-dependent timing assertions."""
from io import BytesIO
from unittest.mock import patch
import json
import openpyxl
from openpyxl.styles import Font
from compare import sheet_names, table, load, apply_changes, compare_tables, recommend, mapping_score
from workspace import aligned_rows, encode_rows, decode_rows
from ui_helpers import suggested_mapping


def pack(wb):
    out=BytesIO();wb.save(out);return out.getvalue()


def test_metadata_does_not_parse_sheets_and_sparse_formatting_does_not_expand_data():
    wb=openpyxl.Workbook();ws=wb.active
    ws.append(['id','value']);ws.append(['a','original'])
    ws.cell(1_048_576,16_384).font=Font(bold=True)
    data=pack(wb)
    with patch('openpyxl.load_workbook',side_effect=AssertionError('metadata must not parse cells')):
        assert sheet_names(data)==['Sheet']
    t=table(data,'Sheet')
    assert t.headers==['id','value'] and t.rows==[{'id':'a','value':'original'}]
    assert t.physical_rows==[2]


def test_export_metadata_matches_saved_workbook_without_reopening_output():
    wb=openpyxl.Workbook();ws=wb.active
    ws.append(['순번','id','value']);ws.append([1,'a','old']);ws.append([2,'b','delete'])
    old=pack(wb)
    ws['C2']='new';ws['B3']='c';ws['C3']='add';new=pack(wb)
    a,b=table(old,'Sheet'),table(new,'Sheet');m=suggested_mapping(a,b)
    changes,_=compare_tables(a,b,m,['id'])
    with patch('compare.load',wraps=load) as loads:
        export=apply_changes(old,a,b,m,changes,{c['id'] for c in changes},['id'],True,with_metadata=True)
        assert loads.call_count==1
    assert export.table==table(export.data,'Sheet')
    # Excel serializes literal empty strings as blank cells.
    assert [tuple(None if v=='' else v for v in row) for row in export.history]==list(load(export.data)['변경 이력'].values)
    assert [r['id'] for r in export.table.rows]==['c','a']
    assert [r['순번'] for r in export.table.rows]==[1,2]


def test_compressed_transport_roundtrip_and_recommendation_equivalence():
    wb=openpyxl.Workbook();ws=wb.active
    ws.append(['코드','설명'])
    for i in range(1000):ws.append([f'{i:05d}','한글 · =문자 <script>'])
    old=pack(wb);a=table(old,'Sheet');ws['B2']='변경';b=table(pack(wb),'Sheet')
    m=suggested_mapping(a,b);c,_=compare_tables(a,b,m,['코드']);rows=aligned_rows(a,b,m,['코드'],c)
    payload=encode_rows(rows)
    assert decode_rows(payload)==rows
    assert len(payload)<len(json.dumps(rows,ensure_ascii=False).encode())/4
    expected=sorted([mapping_score(a,b,x,y) for x in a.headers for y in b.headers],key=lambda x:-x['추천 점수'])
    assert recommend(a,b)==expected
