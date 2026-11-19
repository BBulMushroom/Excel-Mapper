from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import openpyxl
import pytest
from openpyxl.styles import PatternFill, Font
from compare import apply_changes, table, compare_tables


def book(rows, title='자료', extras=None):
    wb=openpyxl.Workbook();ws=wb.active;ws.title=title
    for row in rows:ws.append(row)
    for name,values in (extras or {}).items():
        sheet=wb.create_sheet(name)
        for row in values:sheet.append(row)
    out=BytesIO();wb.save(out);return out.getvalue()


def cached(data, address, value):
    out=BytesIO()
    with ZipFile(BytesIO(data)) as source, ZipFile(out,'w') as dest:
        for item in source.infolist():
            raw=source.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                root=ET.fromstring(raw);cell=root.find(f'.//{{*}}c[@r="{address}"]')
                v=cell.find('{*}v');v.text=str(value)
                raw=ET.tostring(root)
            dest.writestr(item,raw)
    return out.getvalue()


def export(old,new,mode='일반 복사',mapping=None,approved=None,sort=None):
    left,right=table(old,'자료'),table(new,'자료')
    mapping=mapping or {h:h for h in left.headers}
    changes,_=compare_tables(left,right,mapping,['id'])
    chosen={c['id'] for c in changes} if approved is None else approved
    data=apply_changes(old,left,right,mapping,changes,chosen,sort,comparison_data=new,copy_mode=mode)
    return openpyxl.load_workbook(BytesIO(data))


def test_normal_formula_translation_mixed_absolute_and_column_shift_with_styles():
    old=book([['id','result','n'],['a','before',2]])
    new=book([['id','n','result'],['a',3,'=B2+$B$2+B$2+$B2'],['b',4,'=B3+$B$2']])
    wb=openpyxl.load_workbook(BytesIO(new));ws=wb.active
    ws['C2'].fill=PatternFill('solid',fgColor='123456');ws['C2'].font=Font(bold=True,color='ABCDEF')
    ws['C2'].number_format='#,##0.00';out=BytesIO();wb.save(out)
    result=export(old,out.getvalue())
    assert result['자료']['B2'].value=='=A2+$B$2+A$2+$B2'
    assert result['자료']['B3'].value=='=A3+$B$2'
    assert result['자료']['B2'].data_type=='f'
    assert result['자료']['B2'].fill.fgColor.rgb=='00123456'
    assert result['자료']['B2'].font.bold
    assert result['자료']['B2'].number_format=='#,##0.00'
    assert result.calculation.fullCalcOnLoad and result.calculation.forceFullCalc
    assert result['변경 이력']['E2'].data_type=='s'


def test_values_only_uses_cached_zero_and_keeps_original_style():
    old=book([['id','result'],['a',10]])
    new=cached(book([['id','result'],['a','=1-1']]),'B2',0)
    result=export(old,new,'값만 복사')
    assert result['자료']['B2'].value==0 and result['자료']['B2'].data_type=='n'
    assert not result['자료']['B2'].has_style


def test_values_only_missing_cache_errors_only_for_selected_formula():
    old=book([['id','result'],['a',10]])
    new=book([['id','result'],['a','=1+1']])
    with pytest.raises(ValueError,match='B2.*계산값'):export(old,new,'값만 복사')
    assert export(old,new,'값만 복사',approved=set())['자료']['B2'].value==10


def test_literal_equals_strings_remain_strings_even_in_normal_copy():
    old=book([['id','result'],['a','old']]);wb=openpyxl.load_workbook(BytesIO(old))
    wb.active['B2']='=not a formula';wb.active['B2'].data_type='s';out=BytesIO();wb.save(out)
    assert export(old,out.getvalue())['자료']['B2'].data_type=='s'


def test_other_sheet_snapshot_preserves_comparison_price_and_rewrites_dependencies():
    old=book([['id','result'],['a',1]],extras={'단가 표':[['가격'],[1000]]})
    new=book([['id','result'],['b',"='단가 표'!$A$2*2"]],extras={'단가 표':[['가격'],['=보조!$A$1']], '보조':[[2000]]})
    result=export(old,new,approved={1}) # deletion excluded, addition selected
    assert result['자료']['B3'].value=="='단가 표 (비교)'!$A$2*2"
    assert result['단가 표']['A2'].value==1000
    assert result['단가 표 (비교)']['A2'].value=="='보조 (비교)'!$A$1"
    assert result['보조 (비교)']['A1'].value==2000
    assert not result._external_links


@pytest.mark.parametrize('formula',["='[other.xlsx]Sheet'!A1",'=NamedPrice*2','=SUM(Table1[Price])'])
def test_unsupported_reference_fails_instead_of_silently_retargeting(formula):
    old=book([['id','result'],['a',1]]);new=book([['id','result'],['a',formula]])
    with pytest.raises(ValueError,match='지원하지 않습니다'):export(old,new)


def test_imported_formula_prevents_sort_even_when_original_has_none():
    old=book([['id','result'],['a',1]]);new=book([['id','result'],['a','=1+1']])
    with pytest.raises(ValueError,match='수식.*정렬'):export(old,new,sort=['id'])


def test_values_only_explicit_empty_string_cache_is_not_missing_result():
    old=book([['id','result'],['a',10]])
    data=book([['id','result'],['a','=""']]);out=BytesIO()
    with ZipFile(BytesIO(data)) as source, ZipFile(out,'w') as dest:
        for item in source.infolist():
            raw=source.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                root=ET.fromstring(raw);cell=root.find('.//{*}c[@r="B2"]');cell.set('t','str');raw=ET.tostring(root)
            dest.writestr(item,raw)
    assert export(old,out.getvalue(),'값만 복사')['자료']['B2'].value is None


