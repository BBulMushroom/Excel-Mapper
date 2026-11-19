"""Command line mode: same engine and rules as the window, no Qt."""
from io import BytesIO
import json
import subprocess
import sys
from pathlib import Path
import openpyxl
import pytest
import cli
from compare import table


def book(path,headers,rows):
    wb=openpyxl.Workbook();ws=wb.active;ws.title='자료';ws.append(headers)
    for row in rows:ws.append(row)
    wb.save(path);return path


@pytest.fixture
def files(tmp_path):
    original=book(tmp_path/'원본.xlsx',['코드','이름','수량','비고'],[['k1','a',1,'m1'],['k2','b',2,'m2'],['k3','c',3,'m3']])
    comparison=book(tmp_path/'비교.xlsx',['코드','이름','수량'],[['k1','a',9,],['k2','b',2],['k4','d',4]])
    return tmp_path,original,comparison


def rows(path):return {r['코드']:r for r in table(Path(path).read_bytes(),'자료').rows}


def run(capsys,*argv):
    code=cli.main(list(argv));out=capsys.readouterr();return code,out.out,out.err


def test_analysis_only_reports_counts_and_writes_nothing(files,capsys):
    tmp,old,new=files;code,out,err=run(capsys,'--compare',str(old),str(new),'--json')
    report=json.loads(out);stage=report['stages'][0]
    assert code==0 and report['output'] is None
    assert stage['counts']=={'추가':1,'수정':1,'삭제':1} and stage['keys']==['코드'] and stage['mapping']['수량']=='수량'
    assert {c['kind'] for c in stage['changes']}=={'추가','수정','삭제'} and stage['applied']=={'추가':1,'수정':1,'삭제':0}   # delete needs --apply
    assert not list(tmp.glob('결과*'))


def test_default_apply_adds_and_edits_but_keeps_deletions(files,capsys):
    tmp,old,new=files;out=tmp/'결과.xlsx';code,_,_=run(capsys,'--compare',str(old),str(new),'--out',str(out))
    result=rows(out);assert code==0 and result['k1']['수량']==9 and 'k4' in result and 'k3' in result and result['k3']['비고']=='m3'


def test_delete_and_none_policies(files,capsys):
    tmp,old,new=files
    run(capsys,'--compare',str(old),str(new),'--apply','all','--out',str(tmp/'all.xlsx'));assert 'k3' not in rows(tmp/'all.xlsx')
    run(capsys,'--compare',str(old),str(new),'--apply','none','--out',str(tmp/'none.xlsx'));result=rows(tmp/'none.xlsx');assert result['k1']['수량']==1 and 'k4' not in result


def test_row_mode_blanks_columns_missing_from_the_comparison(files,capsys):
    tmp,old,new=files;out=tmp/'행.xlsx';code,_,_=run(capsys,'--compare',str(old),str(new),'--mode','row','--out',str(out))
    result=rows(out);assert code==0 and result['k1']['수량']==9 and result['k1']['비고'] is None and result['k2']['비고']=='m2'


def test_keys_mapping_and_sheet_overrides(files,capsys):
    tmp,old,new=files;code,out,_=run(capsys,'--compare',str(old),str(new),'--keys','코드,이름','--map','수량=수량','--sheet-original','자료','--json')
    assert code==0 and json.loads(out)['stages'][0]['keys']==['코드','이름']


def test_several_comparison_files_are_merged_in_order(files,capsys):
    tmp,old,new=files;third=book(tmp/'비교2.xlsx',['코드','이름','수량'],[['k1','a',9],['k2','bb',2],['k4','d',4]])
    out=tmp/'취합.xlsx';code,text,_=run(capsys,'--compare',str(old),str(new),str(third),'--out',str(out),'--json')
    report=json.loads(text);result=rows(out);assert code==0 and len(report['stages'])==2 and result['k2']['이름']=='bb' and result['k1']['수량']==9


def test_error_exit_codes_and_input_protection(files,capsys):
    tmp,old,new=files
    assert run(capsys,'--compare',str(old),str(tmp/'없음.xlsx'))[0]==3
    assert run(capsys,'--compare',str(old),str(new),'--apply','bogus')[0]==4
    code,_,err=run(capsys,'--compare',str(old),str(new),'--out',str(new));assert code==4 and '덮어쓸 수 없습니다' in err
    assert run(capsys,'--compare',str(old),str(new),'--out',str(tmp/'x.txt'))[0]==4
    assert run(capsys,'--compare',str(old),str(new),'--mode','weird')[0]==2


def test_report_file_and_module_entry_point(files):
    tmp,old,new=files;report=tmp/'r.json'
    done=subprocess.run([sys.executable,'-I','-c','import sys;sys.path.insert(0,sys.argv[1]);import cli;raise SystemExit(cli.main(sys.argv[2:]))',str(Path(cli.__file__).parent),'--compare',str(old),str(new),'--report',str(report)],capture_output=True,text=True,encoding='utf-8')
    assert done.returncode==0 and json.loads(report.read_text(encoding='utf-8'))['ok'] and 'PySide6' not in done.stdout
