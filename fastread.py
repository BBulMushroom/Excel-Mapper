"""Quick value reader for plain .xlsx sheets (no formulas, no merged cells).

openpyxl builds a full object for every cell and its style, which takes about 1.4 s per 10,000 rows.
This reads only values with the standard XML parser and the same conversion rules (shared strings,
number casting, date detection, booleans), about 2.4x faster. Anything unusual raises `Unsupported`
and the caller falls back to openpyxl, so the result never differs: `tests/test_fastread.py` compares both.
"""
from io import BytesIO
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from openpyxl.styles.numbers import builtin_format_code,is_date_format,is_timedelta_format
from openpyxl.utils.datetime import from_excel,from_ISO8601,WINDOWS_EPOCH,MAC_EPOCH

MAIN='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL='http://schemas.openxmlformats.org/package/2006/relationships'
CELL,ROW,VALUE,FORMULA,INLINE='{%s}c'%MAIN,'{%s}row'%MAIN,'{%s}v'%MAIN,'{%s}f'%MAIN,'{%s}is'%MAIN
SI,TEXT,RUN='{%s}si'%MAIN,'{%s}t'%MAIN,'{%s}r'%MAIN


class Unsupported(Exception):
    """The sheet needs openpyxl's full reader."""


def cast_number(value):
    return float(value) if ('.' in value or 'E' in value or 'e' in value) else int(value)


def text_of(node):
    """Plain text then rich-text runs, never phonetic hints: what openpyxl's `Text.content` returns, without building its objects."""
    parts=[]
    plain=node.find(TEXT)
    if plain is not None and plain.text is not None:parts.append(plain.text)
    for run in node.findall(RUN):
        piece=run.find(TEXT)
        if piece is not None and piece.text is not None:parts.append(piece.text)
    return ''.join(parts)


def shared_strings(raw):
    """Same list as openpyxl's `read_string_table`."""
    strings=[]
    for _,node in ET.iterparse(BytesIO(raw)):
        if node.tag!=SI:continue
        strings.append(text_of(node).replace('x005F_',''));node.clear()
    return strings


def column_row(coordinate):
    """('AB12') -> (12, 28), the order openpyxl's coordinate_to_tuple uses."""
    column=0;index=0
    for index,char in enumerate(coordinate):
        if 'A'<=char<='Z':column=column*26+ord(char)-64
        elif 'a'<=char<='z':column=column*26+ord(char)-96
        else:break
    return int(coordinate[index:]),column


def sheet_part(archive,sheet):
    workbook=ET.fromstring(archive.read('xl/workbook.xml'))
    if workbook.tag!='{%s}workbook'%MAIN:raise Unsupported('strict or unknown workbook namespace')
    properties=workbook.find('{%s}workbookPr'%MAIN);epoch=MAC_EPOCH if properties is not None and properties.get('date1904') in ('1','true') else WINDOWS_EPOCH
    target=None
    for node in workbook.iter('{%s}sheet'%MAIN):
        if node.get('name')==sheet:target=node.get('{%s}id'%REL)
    if target is None:raise Unsupported('sheet not found')
    for relation in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels')).iter('{%s}Relationship'%PKG_REL):
        if relation.get('Id')==target:
            path=relation.get('Target');return (path.lstrip('/') if path.startswith('/') else 'xl/'+path),epoch
    raise Unsupported('relationship not found')


def style_flags(archive):
    """Which cell styles show dates / durations, decided exactly as openpyxl's stylesheet does."""
    if 'xl/styles.xml' not in archive.namelist():return set(),set()
    root=ET.fromstring(archive.read('xl/styles.xml'))
    custom={int(n.get('numFmtId')):n.get('formatCode') for n in root.iter('{%s}numFmt'%MAIN)}
    styles=root.find('{%s}cellXfs'%MAIN);dates=set();durations=set()
    if styles is None:return dates,durations
    for index,xf in enumerate(styles.findall('{%s}xf'%MAIN)):
        number=int(xf.get('numFmtId',0));code=custom[number] if number in custom else builtin_format_code(number)
        if is_date_format(code):dates.add(index)
        if is_timedelta_format(code):durations.add(index)
    return dates,durations


def read_cells(data,sheet):
    """{(row, column): value} for every cell holding a value, like openpyxl's loaded sheet."""
    archive=ZipFile(BytesIO(data));part,epoch=sheet_part(archive,sheet)
    sheet_xml=archive.read(part)
    if re.search(rb'<(?:\w+:)?(?:mergeCell|f)[ >/]',sheet_xml):
        raise Unsupported('merged cells or formulas')
    strings=shared_strings(archive.read('xl/sharedStrings.xml')) if 'xl/sharedStrings.xml' in archive.namelist() else []
    dates,durations=style_flags(archive);values={}
    for _,row in ET.iterparse(BytesIO(sheet_xml)):
        if row.tag!=ROW:continue
        number=row.get('r')
        if number is None:raise Unsupported('row without number')
        number=int(number)
        for element in row:
            if element.tag!=CELL:continue
            coordinate=element.get('r')
            if not coordinate:raise Unsupported('cell without address')
            kind=element.get('t','n');raw=None;inline=None
            for child in element:
                tag=child.tag
                if tag==VALUE:raw=child.text or None
                elif tag==FORMULA:raise Unsupported('formula')      # namespace-aware second look
                elif tag==INLINE:inline=child
            value=None
            if kind=='inlineStr':
                if inline is not None:value=text_of(inline)
            elif raw is not None:
                if kind=='n':
                    value=cast_number(raw)
                    style=element.get('s')
                    if style and int(style) in dates:
                        try:value=from_excel(value,epoch,timedelta=int(style) in durations)
                        except (OverflowError,ValueError):raise Unsupported('date outside limits')
                elif kind=='s':value=strings[int(raw)]
                elif kind=='b':value=bool(int(raw))
                elif kind in ('str','e'):value=raw
                elif kind=='d':value=from_ISO8601(raw)
                else:raise Unsupported('cell type '+kind)
            if value is not None:
                at,column=column_row(coordinate)
                if at!=number:raise Unsupported('cell outside its row')
                values[(at,column)]=value
        row.clear()
    return values
