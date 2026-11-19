"""T106: switching sheets re-fits links and keys, keeps the new sheet even when the comparison cannot run, and prefers same-name sheets."""
from io import BytesIO
import openpyxl
from desktop.session import Session


def book(sheets):
    wb=openpyxl.Workbook();wb.remove(wb.active)
    for name,rows in sheets:
        ws=wb.create_sheet(name)
        for r in rows:ws.append(r)
    out=BytesIO();wb.save(out);return out.getvalue()


def test_switching_sheet_refits_links_and_keeps_new_sheet_on_problems():
    old=book([('요약',[['구분','합계','비고','담당','메모'],['a',1,'x','y','z']]),('자산',[['자산코드','자산명'],['A1','PC'],['A2','TV']]),('중복',[['코드','값'],['k',1],['k',1]])])
    new=book([('요약',[['구분','합계','비고','담당','메모'],['a',2,'x','y','z']]),('자산',[['자산코드','자산명'],['A1','PC2'],['A3','폰']]),('중복',[['코드','값'],['k',1],['k',1]])])
    s=Session(old,[(new,'b.xlsx')],'a.xlsx');layout=dict(s.layout,old_sheet='자산',new_sheet='자산')
    s.configure(layout=layout);assert s.keys==['자산코드'] and set(s.mapping)=={'자산코드','자산명'} and not s.issue and len(s.changes)==3
    s.configure(layout=dict(layout,old_sheet='중복',new_sheet='중복'))                     # no key can be found: no error, new sheet kept
    assert s.layout['old_sheet']=='중복' and s.left.headers==['코드','값'] and s.issue


def test_same_name_sheet_is_preferred_when_files_differ():
    old=book([('자산',[['자산코드','자산명'],['A1','PC']]),('메모',[['x']])])
    new=book([('기타',[['코드','이름','값','설명','비고','추가'],['k','n',1,'d','b','c']]),('자산',[['자산코드','자산명'],['A1','PC2']])])
    s=Session(old,[(new,'b.xlsx')],'a.xlsx');assert (s.layout['old_sheet'],s.layout['new_sheet'])==('자산','자산')
