"""Merged titles, objects that cannot be kept, and pictures that must be kept."""
from io import BytesIO
import zipfile
import openpyxl
import pytest
from compare import table,unsupported_objects,apply_changes,compare_tables


def xlsx(build):
    wb=openpyxl.Workbook();ws=wb.active;ws.title='자료';build(ws);out=BytesIO();wb.save(out);return out.getvalue()


def with_title(ws,rows=(('k1',1),('k2',2))):
    ws['A1']='재고 현황';ws.merge_cells('A1:B1')
    ws.append(['코드','수량'])
    for row in rows:ws.append(list(row))


def test_merged_title_above_the_header_is_allowed_and_kept_on_save():
    old=xlsx(with_title);new=xlsx(lambda ws:with_title(ws,(('k1',9),('k2',2))))
    left=table(old,'자료',2,3);right=table(new,'자료',2,3)
    assert left.headers==['코드','수량'] and [r['수량'] for r in left.rows]==[1,2]
    changes,_=compare_tables(left,right,{'코드':'코드','수량':'수량'},['코드'])
    result=apply_changes(old,left,right,{'코드':'코드','수량':'수량'},changes,{c['id'] for c in changes},comparison_data=new)
    saved=openpyxl.load_workbook(BytesIO(result))['자료']
    assert saved['B4'].value==9 or saved['B3'].value==9
    assert 'A1:B1' in {str(r) for r in saved.merged_cells.ranges}


def test_merges_in_data_are_read_but_header_row_merges_are_rejected_with_a_clear_message():
    in_data=xlsx(lambda ws:(ws.append(['구분','코드']),ws.append(['가','k1']),ws.append([None,'k2']),ws.merge_cells('A2:A3')))
    assert [r['구분'] for r in table(in_data,'자료',1,2).rows]==['가','가']
    in_header=xlsx(lambda ws:(ws.append(['코드','수량']),ws.append(['k1',1]),ws.merge_cells('A1:B1')))
    with pytest.raises(ValueError,match='1행'):table(in_header,'자료',1,2)


def add_parts(data,parts,sheet_marker=None):
    source=zipfile.ZipFile(BytesIO(data));out=BytesIO()
    with zipfile.ZipFile(out,'w') as target:
        for name in source.namelist():
            content=source.read(name)
            if sheet_marker and name=='xl/worksheets/sheet1.xml':content=content.replace(b'</worksheet>',sheet_marker+b'</worksheet>')
            target.writestr(name,content)
        for name,content in parts.items():target.writestr(name,content)
    return out.getvalue()


def test_objects_that_cannot_be_kept_are_listed():
    plain=xlsx(lambda ws:ws.append(['a']))
    assert unsupported_objects(plain)==[]                   # values, styles, charts, pictures, tables are kept
    drawing=b'<xdr:wsDr xmlns:xdr="x"><xdr:twoCellAnchor><xdr:sp macro=""><xdr:nvSpPr/></xdr:sp></xdr:twoCellAnchor><xdr:twoCellAnchor><xdr:sp macro=""/></xdr:twoCellAnchor></xdr:wsDr>'
    data=add_parts(plain,{'xl/drawings/drawing9.xml':drawing,'xl/slicers/slicer1.xml':b'<s/>','xl/ctrlProps/ctrlProp1.xml':b'<c/>','xl/embeddings/oleObject1.bin':b'x','xl/threadedComments/t1.xml':b'<t/>'},
                   b'<extLst><x14:conditionalFormatting/><x14:sparklineGroups/><x14:dataValidations/></extLst>')
    found='|'.join(unsupported_objects(data))
    for text in ('도형·텍스트 상자 2개','슬라이서','양식 컨트롤','삽입된 개체','스레드 댓글','스파크라인','확장 조건부 서식','확장 데이터 유효성'):assert text in found,text


def test_pictures_survive_an_edit_and_save():
    PIL=pytest.importorskip('PIL.Image')
    from openpyxl.drawing.image import Image
    image=BytesIO();PIL.new('RGB',(12,12),'red').save(image,'PNG');image.seek(0)
    def build(ws):
        ws.append(['코드','수량']);ws.append(['k1',1]);ws.add_image(Image(image),'D2')
    old=xlsx(build);new=xlsx(lambda ws:(ws.append(['코드','수량']),ws.append(['k1',5])))
    left,right=table(old,'자료'),table(new,'자료');mapping={'코드':'코드','수량':'수량'}
    changes,_=compare_tables(left,right,mapping,['코드'])
    result=apply_changes(old,left,right,mapping,changes,{c['id'] for c in changes},comparison_data=new)
    assert any(n.startswith('xl/media/') for n in zipfile.ZipFile(BytesIO(result)).namelist())


def test_the_desktop_build_ships_pillow():
    from pathlib import Path
    assert 'pillow' in (Path(__file__).resolve().parents[1]/'requirements-desktop.txt').read_text().lower()
