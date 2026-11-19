"""Import tabular formats into the workbook engine; XLS/CSV export as XLSX."""
from io import BytesIO, StringIO
from pathlib import Path
import csv
import openpyxl


def prepare(data,name):
    try:return _prepare(data,name)
    except ValueError as exc:raise ValueError(f"파일 '{name}': {exc}") from exc


def _prepare(data,name):
    ext=Path(name).suffix.lower()
    if ext in ('.xlsx','.xlsm'): return data
    wb=openpyxl.Workbook();wb.remove(wb.active)
    if ext=='.csv':
        for encoding in ('utf-8-sig','cp949'):
            try: text=data.decode(encoding);break
            except UnicodeDecodeError: pass
        else: raise ValueError('CSV 인코딩을 확인하세요. UTF-8 또는 CP949를 지원합니다.')
        try: dialect=csv.Sniffer().sniff(text[:65536],delimiters=',;\t')
        except csv.Error: dialect=csv.excel
        ws=wb.create_sheet('데이터')
        for index,row in enumerate(csv.reader(StringIO(text,newline=''),dialect),1):
            for col,value in enumerate(row,1):
                if len(value)>32767:raise ValueError(f'CSV {index}행의 값이 엑셀 셀 길이 한도(32,767자)를 초과합니다.')
                cell=ws.cell(index,col,value);cell.data_type='s'
    elif ext=='.xls':
        import xlrd
        try: book=xlrd.open_workbook(file_contents=data)
        except Exception as exc: raise ValueError('XLS 파일을 읽을 수 없습니다. 암호와 파일 형식을 확인하세요.') from exc
        for sheet in book.sheets():
            ws=wb.create_sheet(sheet.name)
            for index,row in enumerate(sheet.get_rows(),1):
                values=[]
                for cell in row:
                    value=cell.value
                    if cell.ctype==xlrd.XL_CELL_DATE: value=xlrd.xldate_as_datetime(value,book.datemode)
                    elif cell.ctype==xlrd.XL_CELL_BOOLEAN: value=bool(value)
                    elif cell.ctype in (xlrd.XL_CELL_EMPTY,xlrd.XL_CELL_BLANK): value=None
                    values.append(value)
                for col,value in enumerate(values,1):
                    cell=ws.cell(index,col,value)
                    if isinstance(value,str):cell.data_type='s'
        book.release_resources()
    else: raise ValueError('XLSX, XLSM, XLS, CSV 파일을 선택하세요.')
    if not wb.worksheets:raise ValueError('데이터 시트가 없습니다.')
    out=BytesIO();wb.save(out);return out.getvalue()
