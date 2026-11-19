from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import base64
import openpyxl
from openpyxl.styles import Font,PatternFill
from openpyxl.comments import Comment
import collection_flow as flow
from analysis_cache import AnalysisCache
from compare import table,compare_tables,apply_changes


def blob(rows):
    wb=openpyxl.Workbook();ws=wb.active;ws.title='자료';ws.append(['id','값'])
    for row in rows:ws.append(row)
    out=BytesIO();wb.save(out);return out.getvalue()


def values(data):return {row['id']:row['값'] for row in table(data,'자료').rows}


def test_seeded_analysis_reuses_exact_bytes_sheet_range_and_bounds_memory():
    data=blob([['a',1]]);dataset=table(data,'자료');cache=AnalysisCache('test',table_limit=2,layout_limit=2)
    cache.seed(data,dataset)
    with patch('analysis_cache.table',side_effect=AssertionError('must reuse export analysis')),patch('analysis_cache.detect_layout',side_effect=AssertionError('must reuse layout')):
        assert cache.read(data,'자료') is dataset
        assert cache.layout(data)=={'sheet':'자료','header':1,'start':2}
    assert not cache.read(blob([['b',2]]),'자료').rows[0]['id']=='a'
    for i in range(4):cache.read(blob([[str(i),i]]),'자료')
    assert len(cache.tables)==2
    with patch('analysis_cache.table',wraps=table) as parse:
        cache.read(data,'자료',1,3)
        assert parse.call_count==1  # Never use a seed for a different range.


def test_destination_style_cache_keeps_cell_specific_comments_and_links():
    original=blob([]);wb=openpyxl.load_workbook(BytesIO(blob([['a',1],['b',2],['c',3]])));ws=wb.active
    for row in (2,3):
        ws.cell(row,2).font=Font(bold=True,color='123456')
        ws.cell(row,2).number_format='#,##0'
    ws['B2'].comment=Comment('first','tester');ws['B2'].hyperlink='https://example.com/first'
    ws['B3'].comment=Comment('second','tester');ws['B3'].hyperlink='https://example.com/second'
    ws['B4'].fill=PatternFill('solid',fgColor='ABCDEF')
    out=BytesIO();wb.save(out);incoming=out.getvalue()
    a,b=table(original,'자료'),table(incoming,'자료');mapping={'id':'id','값':'값'}
    changes,_=compare_tables(a,b,mapping,['id'])
    output=apply_changes(original,a,b,mapping,changes,{c['id'] for c in changes},comparison_data=incoming)
    result=openpyxl.load_workbook(BytesIO(output))['자료']
    assert result['B2'].font.bold and result['B3'].font.bold
    assert result['B2'].font.color.rgb==result['B3'].font.color.rgb=='00123456'
    assert result['B2'].number_format==result['B3'].number_format=='#,##0'
    assert result['B2'].comment.text=='first' and result['B3'].comment.text=='second'
    assert result['B2'].hyperlink.target.endswith('/first') and result['B3'].hyperlink.target.endswith('/second')
    assert result['B3'].hyperlink.ref=='B3' and result['B4'].fill.fgColor.rgb.endswith('ABCDEF')


