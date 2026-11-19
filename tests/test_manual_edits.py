"""Content edits must preserve workbook properties and survive structural comparison actions."""
from copy import copy
from io import BytesIO
import openpyxl
import pytest
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.worksheet.datavalidation import DataValidation
from compare import table,compare_tables,apply_changes


def workbook(rows):
    wb=openpyxl.Workbook();ws=wb.active;ws.title='자료'
    ws.append(['id','금액','비고'])
    for row in rows:ws.append(row)
    ws['B2'].font=Font(name='맑은 고딕',bold=True,color='123456')
    ws['B2'].fill=PatternFill('solid',fgColor='ABCDEF')
    ws['B2'].border=Border(bottom=Side(style='thin',color='654321'))
    ws['B2'].alignment=Alignment(horizontal='right');ws['B2'].number_format='#,##0.00'
    ws.row_dimensions[2].height=31;ws.column_dimensions['B'].width=22
    ws.conditional_formatting.add('B2:B20',CellIsRule(operator='greaterThan',formula=['10'],fill=PatternFill('solid',fgColor='FF0000')))
    validation=DataValidation(type='decimal',operator='greaterThan',formula1='0');ws.add_data_validation(validation);validation.add('B2:B20')
    extra=wb.create_sheet('참조');extra['A1']='=자료!B2'
    out=BytesIO();wb.save(out);return out.getvalue()


def test_content_edits_preserve_styles_rules_formulas_and_input_bytes():
    old=workbook([['a',10,'원문'],['b',20,'보존']]);new=workbook([['a',15,'원문'],['b',20,'보존']])
    a,b=table(old,'자료'),table(new,'자료');mapping={h:h for h in a.headers};changes,_=compare_tables(a,b,mapping,['id'])
    edits=[{'key':['a'],'column':'금액','value':'=SUM(1,2)'},{'key':['b'],'column':'비고','value':'  직접 편집  '}]
    output=apply_changes(old,a,b,mapping,changes,set(),comparison_data=new,manual_edits=edits,edit_keys=['id'])
    original=openpyxl.load_workbook(BytesIO(old));result=openpyxl.load_workbook(BytesIO(output));ws=result['자료']
    assert ws['B2'].value=='=SUM(1,2)' and ws['B2'].data_type=='f'
    for attribute in ('font','fill','border','alignment','number_format','protection'):
        assert copy(getattr(ws['B2'],attribute))==copy(getattr(original['자료']['B2'],attribute))
    assert ws.row_dimensions[2].height==31 and ws.column_dimensions['B'].width==22
    assert ws['C3'].value=='  직접 편집  ' and ws['B3'].value==20
    assert result['참조']['A1'].value=='=자료!B2'
    from xml.etree.ElementTree import tostring
    assert [(str(k.sqref),[tostring(rule.to_tree()) for rule in rules]) for k,rules in ws.conditional_formatting._cf_rules.items()]==[(str(k.sqref),[tostring(rule.to_tree()) for rule in rules]) for k,rules in original['자료'].conditional_formatting._cf_rules.items()]
    assert tostring(ws.data_validations.to_tree())==tostring(original['자료'].data_validations.to_tree())
    assert original['자료']['B2'].value==10
    assert [r[0] for r in result['변경 이력'].values].count('직접 수정')==2


def test_edits_follow_row_identity_through_add_delete_sort_and_validate_targets():
    # No formulas: structural deletion and saved ordering are permitted.
    def data(rows):
        wb=openpyxl.Workbook();ws=wb.active;ws.title='자료';ws.append(['id','금액','비고'])
        for r in rows:ws.append(r)
        out=BytesIO();wb.save(out);return out.getvalue()
    old=data([['a',1,'a'],['b',2,'b'],['c',3,'c']]);new=data([['a',8,'a'],['c',3,'c'],['d',4,'d']])
    a,b=table(old,'자료'),table(new,'자료');mapping={h:h for h in a.headers};changes,_=compare_tables(a,b,mapping,['id']);selected={c['id'] for c in changes}
    edits=[{'key':['a'],'column':'id','value':'z'},{'key':['c'],'column':'金額','value':'7'}]
    with pytest.raises(ValueError,match='열'):apply_changes(old,a,b,mapping,changes,selected,manual_edits=edits,edit_keys=['id'])
    edits=[{'key':['a'],'column':'id','value':'z'},{'key':['c'],'column':'금액','value':'7'},{'key':['d'],'column':'비고','value':'00123'},{'key':['b'],'column':'비고','value':'삭제된 행'}]
    export=apply_changes(old,a,b,mapping,changes,selected,['금액'],True,comparison_data=new,manual_edits=edits,edit_keys=['id'],with_metadata=True)
    output=export.data
    assert export.order==[{'key':['a'],'number':1},{'key':['c'],'number':2},{'key':['d'],'number':3}]
    assert [(r['id'],r['금액'],r['비고']) for r in table(output,'자료').rows]==[('z',8,'a'),('c',7,'c'),('d',4,'00123')]
    rejected=apply_changes(old,a,b,mapping,changes,set(),manual_edits=edits,edit_keys=['id'])
    assert [(r['id'],r['비고']) for r in table(rejected,'자료').rows]==[('z','a'),('b','삭제된 행'),('c','c')]
    with pytest.raises(ValueError,match='행'):apply_changes(old,a,b,mapping,changes,set(),manual_edits=[{'key':['x'],'column':'금액','value':'1'}],edit_keys=['id'])
