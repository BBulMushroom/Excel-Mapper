"""Refresh the six bundled theme screenshots from synthetic workbooks, never user files.
Run with a local app: python tools/capture_theme_previews.py --engine-python /path/to/venv/bin/python
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
from playwright.sync_api import sync_playwright,expect

parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://localhost:8524');parser.add_argument('--engine-python',default=sys.executable);options=parser.parse_args()
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tests'/'browser'))
from app_helpers import open_menu,close_menus,workspace
out=root/'components'/'preferences'/'previews';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='theme-preview-') as temp:
    folder=Path(temp)
    subprocess.run([options.engine_python,'-c', '''
import sys
from pathlib import Path
from openpyxl import Workbook
folder=Path(sys.argv[1]);headers=['항목코드','부서','사업명','예산금액','담당자']
rows=[['B001','기획팀','시설 운영',1200000,'김서연'],['B002','총무팀','사무 환경',450000,'박민준'],['B003','운영팀','장비 유지',2800000,'이도윤'],['B004','재무팀','정기 점검',850000,'최지우'],['B005','지원팀','업무 지원',670000,'정하린'],['B006','시설팀','안전 관리',920000,'강서준']]
for name,values in [('원본.xlsx',rows),('비교.xlsx',[rows[0][:3]+[1500000,'김서연'],rows[2][:4]+['윤수빈'],*rows[3:],['B007','개발팀','시스템 개선',2400000,'한지호']])]:
 book=Workbook();sheet=book.active;sheet.title='예산대장';sheet.append(headers)
 for row in values:sheet.append(row)
 book.save(folder/name)
''',str(folder)],check=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1)
        page.goto(options.url,wait_until='domcontentloaded');open_menu(page,page,'menu_files')
        for side,name in [('original','원본.xlsx'),('comparison','비교.xlsx')]:page.locator('.st-key-file_'+side+' input[type=file]').set_input_files(str(folder/name))
        expect(page.locator('.st-key-status_key')).to_be_visible(timeout=30000);close_menus(page,page)
        frame=workspace(page);expect(frame.locator('#count-edit')).to_have_text('2/2',timeout=30000)
        frame.locator('#view-mode').click();page.mouse.move(1400,880)
        for theme in ['light','gray','warm','dark','navy','charcoal']:
            page.evaluate('(theme)=>window.excelApplyDisplay({theme})',theme)
            expect(frame.locator('html')).to_have_attribute('data-palette',theme)
            page.wait_for_timeout(250)
            page.screenshot(path=str(out/(theme+'.png')))
        browser.close()
print('Captured six themes from synthetic Excel workbooks:',out)
