from io import BytesIO
import pytest
from formats import prepare
from compare import table, load, sheet_names

@pytest.mark.parametrize('encoding',['utf-8-sig','cp949'])
def test_csv_text_codes_and_literal_formulas(encoding):
    data='코드,설명\n00123,"주소, 상세"\n00124,=1+1\n'.encode(encoding)
    wb=prepare(data,'sample.csv');t=table(wb,'데이터')
    assert t.rows[0]=={'코드':'00123','설명':'주소, 상세'}
    assert load(wb)['데이터']['B3'].data_type=='s'

def test_real_xls_import():
    xlwt=pytest.importorskip('xlwt')
    wb=xlwt.Workbook();ws=wb.add_sheet('업무');ws.write(0,0,'코드');ws.write(1,0,'00123')
    buf=BytesIO();wb.save(buf)
    data=prepare(buf.getvalue(),'test.xls')
    assert sheet_names(data)==['업무']
    assert table(data,'업무').rows==[{'코드':'00123'}]


def test_macro_archive_is_preserved_in_export():
    import openpyxl
    from zipfile import ZipFile, ZIP_DEFLATED
    from compare import compare_tables,apply_changes
    wb=openpyxl.Workbook();ws=wb.active;ws.append(['id','v']);ws.append(['a','old'])
    out=BytesIO();wb.save(out);source=BytesIO()
    with ZipFile(BytesIO(out.getvalue())) as original,ZipFile(source,'w',ZIP_DEFLATED) as target:
        for entry in original.infolist():target.writestr(entry,original.read(entry.filename))
        target.writestr('xl/vbaProject.bin',b'opaque macro archive bytes')
    data=source.getvalue();a=table(data,'Sheet')
    wb.active['B2']='new';out=BytesIO();wb.save(out);b=table(out.getvalue(),'Sheet')
    changes,_=compare_tables(a,b,{'id':'id','v':'v'},['id'])
    output=apply_changes(data,a,b,{'id':'id','v':'v'},changes,{0})
    with ZipFile(BytesIO(output)) as archive:
        assert archive.read('xl/vbaProject.bin')==b'opaque macro archive bytes'
    assert table(output,'Sheet').rows[0]['v']=='new'
