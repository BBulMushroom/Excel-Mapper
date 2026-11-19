"""The fast reader must return exactly what openpyxl returns, or step aside."""
from datetime import date,datetime,time,timedelta
from io import BytesIO
import zipfile
import openpyxl
import pytest
import compare
import fastread
from sample_catalog import CATALOG,load_sample


def same(data,sheet,header=1,start=2):
    fast=compare.table(data,sheet,header,start,fast=True);slow=compare.table(data,sheet,header,start,fast=False)
    assert (fast.sheet,fast.header_row,fast.start_row,fast.headers,fast.rows,fast.physical_rows,fast.formula_cells)==(slow.sheet,slow.header_row,slow.start_row,slow.headers,slow.rows,slow.physical_rows,slow.formula_cells)
    assert [[type(v) for v in r.values()] for r in fast.rows]==[[type(v) for v in r.values()] for r in slow.rows]
    return fast


def book(build,title='자료'):
    wb=openpyxl.Workbook();ws=wb.active;ws.title=title;build(ws);out=BytesIO();wb.save(out);return out.getvalue()


@pytest.mark.parametrize('sid',[k for k in CATALOG if k!='5'])          # the 10k-row sample is compared in the speed test below
def test_every_sample_file_reads_identically(sid):
    old,incoming,_=load_sample(sid)
    for data in [old,*[d for d,_ in incoming]]:
        for name in compare.sheet_names(data):
            if name=='변경 이력':continue
            try:slow=compare.table(data,name,fast=False)
            except ValueError:continue                      # sheets the engine rejects anyway
            same(data,name,slow.header_row,slow.start_row)


def test_value_types_dates_and_odd_cells_read_identically():
    def build(ws):
        ws.append(['코드','수량','단가','날짜','일시','시간','여부','메모','빈칸'])
        ws.append(['a',1,1.5,date(2026,11,3),datetime(2026,11,3,14,30,5),time(9,15),True,'한글 텍스트\n줄바꿈',None])
        ws.append(['b',10**12,1e-7,datetime(1999,1,1),datetime(2000,2,29,0,0),time(0,0,1),False,'  앞뒤 공백  ',''])
        ws.append(['c',-3,0.1+0.2,date(1900,3,1),datetime(2100,1,1,23,59,59),time(23,59,59),None,'x'*300,None])
        ws['E5']=timedelta(hours=30,minutes=5);ws['E5'].number_format='[h]:mm:ss'
        ws['I3']='끝 열'
    same(book(build),'자료')


def test_header_and_start_rows_and_trailing_columns():
    def build(ws):
        ws['A1']='보고서 제목';ws['E1']='우측 메모'
        ws.append([]);ws.append(['코드','이름']);ws.append(['k1','a']);ws.append(['k2','b']);ws['G8']=1
    for header,start in ((3,4),):
        try:same(book(build),'자료',header,start)
        except ValueError:pass                                        # both readers reject the same layout alike
    with pytest.raises(ValueError,match='제목 행'):compare.table(book(build),'자료',3,4,fast=True)
    with pytest.raises(ValueError,match='제목 행'):compare.table(book(build),'자료',3,4,fast=False)


def test_second_sheet_and_missing_sheet():
    wb=openpyxl.Workbook();wb.active.title='첫째';wb.active.append(['x']);two=wb.create_sheet('둘째');two.append(['코드','값']);two.append(['k',1]);out=BytesIO();wb.save(out)
    assert same(out.getvalue(),'둘째').rows==[{'코드':'k','값':1}]
    for fast in (True,False):
        with pytest.raises(ValueError,match="시트 '없음'가 파일에 없습니다"):compare.table(out.getvalue(),'없음',fast=fast)


def test_formulas_and_merged_cells_use_the_openpyxl_reader():
    with_formula=book(lambda ws:(ws.append(['코드','수량']),ws.append(['k',1]),ws.append(['j','=B2*2'])))
    with pytest.raises(fastread.Unsupported):fastread.read_cells(with_formula,'자료')
    assert same(with_formula,'자료').formula_cells=={3:['수량']}
    merged=book(lambda ws:(ws.__setitem__('A1','제목'),ws.merge_cells('A1:B1'),ws.append([]),ws.append(['코드','수량']),ws.append(['k',1])))
    with pytest.raises(fastread.Unsupported):fastread.read_cells(merged,'자료')
    assert compare.table(merged,'자료',3,4).rows==[{'코드':'k','수량':1}]


def test_inline_strings_error_cells_and_1904_calendar():
    data=book(lambda ws:(ws.append(['코드','값']),ws.append(['k',datetime(2026,1,2)]),ws.append(['e','#N/A'])))
    source=zipfile.ZipFile(BytesIO(data));out=BytesIO()
    with zipfile.ZipFile(out,'w') as target:
        for name in source.namelist():
            content=source.read(name)
            if name=='xl/workbook.xml':content=content.replace(b'<workbookPr',b'<workbookPr date1904="1"',1) if b'<workbookPr' in content else content
            if name=='xl/worksheets/sheet1.xml':content=content.replace(b'<c r="A2" t="s"><v>2</v></c>','<c r="A2" t="inlineStr"><is><t>인라인</t></is></c>'.encode('utf-8'))
            target.writestr(name,content)
    same(out.getvalue(),'자료')


def test_unknown_corrupt_or_foreign_files_fall_back_cleanly():
    with pytest.raises(ValueError):compare.table(b'not a workbook','자료')
    assert fastread.cast_number('12')==12 and fastread.cast_number('1e3')==1000.0


def test_fast_reader_is_faster_on_the_ten_thousand_row_sample():
    import time
    old,_,_=load_sample('5');name=compare.sheet_names(old)[0]
    t0=time.perf_counter();slow_table=compare.table(old,name,fast=False);slow=time.perf_counter()-t0
    t0=time.perf_counter();fast_table=compare.table(old,name,fast=True);fast=time.perf_counter()-t0
    assert fast<slow and fast_table.headers==slow_table.headers and fast_table.rows==slow_table.rows


def test_shared_strings_rich_text_phonetic_and_escapes_match_openpyxl():
    from openpyxl.reader.strings import read_string_table
    xml=('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
         '<si><t>plain</t></si><si><r><t>rich </t></r><r><rPr><b/></rPr><t>text</t></r></si>'
         '<si><t>가나다</t><rPh sb="0" eb="1"><t>ガ</t></rPh></si><si><t/></si><si><t xml:space="preserve">  a  </t></si><si><t>x005F_y</t></si></sst>').encode('utf-8')
    assert fastread.shared_strings(xml)==read_string_table(BytesIO(xml))==['plain','rich text','가나다','','  a  ','y']


def test_column_row_parsing_matches_openpyxl():
    from openpyxl.utils.cell import coordinate_to_tuple
    for coordinate in ('A1','Z9','AA10','AB12','XFD1048576','c3'):
        assert fastread.column_row(coordinate)==coordinate_to_tuple(coordinate.upper())


def test_inline_rich_text_matches_openpyxl():
    from openpyxl.cell.text import Text
    from xml.etree import ElementTree as ET
    node=ET.fromstring('<is xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><r><t>굵게 </t></r><r><rPr><b/></rPr><t>와 보통</t></r><rPh sb="0" eb="1"><t>ホ</t></rPh></is>')
    assert fastread.text_of(node)==Text.from_tree(node).content=='굵게 와 보통'
