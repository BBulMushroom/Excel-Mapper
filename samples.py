"""Numbered sample registry. All device credentials and records are fictitious."""
from copy import copy
from functools import lru_cache
from io import BytesIO
from random import Random
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

SAMPLE_SETS = {
    '1': {
        'label': '1. CCTV 관리대장 · 메인 500 / 서브 30',
        'names': ('샘플1_메인_CCTV관리대장.xlsx', '샘플1_서브_CCTV추출자료.xlsx'),
        'summary': '메인 500행 · 서브 신규 30행 · 가상 데이터',
    },
    '2': {
        'label': '2. CCTV 변경·교체 · 메인 500 / 서브 510',
        'names': ('샘플2_메인_CCTV관리대장.xlsx', '샘플2_서브_CCTV변경자료.xlsx'),
        'summary': '메인 500행 · 서브 510행 · 수정 82셀 · 삭제 5대 · 추가 15대',
    },
}
MAIN_HEADERS = ['순번', '카메라명', 'IP', '모델명', '제조사', 'ID', 'PW', '도입년도', 'TTA여부', '카메라종류']
SUB_HEADERS = ['순번', '카메라명', 'IP', '모델명']
CAMERA_TYPES = ['돔', '불릿', '스피드돔', '포지셔닝']


@lru_cache(maxsize=1)
def device_catalog():
    from itertools import product
    locations=[f'{site} {floor}층 {spot} {direction}' for site,floor,spot,direction in product(
        ['본관','별관','주차장','외곽','연구동','물류동','정문','후문','생산동','교육관','동문','서문'],range(1,9),
        ['출입구','복도','승강기홀','계단','로비','통로','연결통로','하역장','기계실','방재실','주차구역','휴게실'],['동측','서측','남측','북측'])]
    ips=[f'172.2.{network}.{host}' for network in range(190,198) for host in range(1,255)]
    rng=Random(717209);rng.shuffle(locations);rng.shuffle(ips)
    return locations,ips


def device(number):
    rng=Random(8217+number*104729);locations,ips=device_catalog()
    maker=rng.choices(['한화비전','아이디스','AXIS','트루엔'],[45,28,12,15])[0]
    prefixes={'한화비전':'HNV','아이디스':'IDS','AXIS':'AXS','트루엔':'TRN'}
    kind=rng.choices(CAMERA_TYPES,[43,37,15,5])[0]
    model=prefixes[maker]+'-'+rng.choice(['QND','XNO','PNM','TNV','HCD'])+str(rng.choice([2080,6022,6080,7082,8080,9082]))
    return [number,locations[number-1],ips[number-1],model,maker,
            rng.choice(['admin','operator','viewer','security']),f'SampleOnly!{rng.randrange(100000,999999)}',
            rng.choices(range(2016,2027),[2,3,4,5,8,12,14,16,18,12,6])[0],
            'O' if maker!='AXIS' and rng.random()<.82 else 'X',kind]


def change_groups(ids,first_count,second_count,overlap,seed):
    rng=Random(seed);pool=list(ids);rng.shuffle(pool)
    first=set(pool[:first_count]);shared=set(rng.sample(sorted(first),overlap))
    rest=[n for n in pool if n not in first]
    return first,shared|set(rest[:second_count-overlap])


def retained_ids(count,seed):
    retired=set(Random(seed).sample(range(2,count+1),5))
    return [n for n in range(1,count+1) if n not in retired]


def workbook(headers, rows, title):
    wb = openpyxl.Workbook()
    wb.properties.title = title
    wb.properties.description = '모든 장비·계정·비밀번호는 가상 데이터입니다.'
    ws = wb.active; ws.title = title
    ws.append(headers)
    for row in rows: ws.append(row)
    ws.freeze_panes = 'C2'
    ws.auto_filter.ref = ws.dimensions
    widths = {'순번': 8, '카메라명': 36, 'IP': 20, '모델명': 20, '제조사': 16, 'ID': 20, 'PW': 22, '도입년도': 12, 'TTA여부': 12, '카메라종류': 16}
    for index, name in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(index)].width = widths.get(name, 24)
        cell = ws.cell(1, index)
        cell.fill = PatternFill('solid', fgColor='17365D')
        cell.font = Font(name='맑은 고딕', size=11, bold=True, color='FFFFFF')
        cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28
    body_font=Font(name='맑은 고딕', size=10)
    centered=Alignment(vertical='center', horizontal='center')
    left_align=Alignment(vertical='center', horizontal='left')
    # Resolving fonts/fills through openpyxl per cell dominates 10000-row generation, so style each
    # distinct combination once and copy its style record to the other cells.
    styles={}
    for row in ws.iter_rows(min_row=2):
        ws.row_dimensions[row[0].row].height = 22
        for cell in row:
            name = headers[cell.column-1]
            key = (name in ('순번','도입년도','TTA여부','카메라종류'), name in ('IP','ID','PW'))
            if key in styles:
                cell._style = copy(styles[key]); continue
            cell.font = body_font
            cell.alignment = centered if key[0] else left_align
            if key[1]: cell.number_format = '@'
            styles[key] = copy(cell._style)
    if 'TTA여부' in headers:
        for column, options in [('I', 'O,X'), ('J', ','.join(CAMERA_TYPES))]:
            validation = DataValidation(type='list', formula1=f'"{options}"')
            validation.errorTitle = '선택값 확인'; validation.error = '목록에서 선택하세요.'; validation.showErrorMessage = True
            ws.add_data_validation(validation); validation.add(f'{column}2:{column}{len(rows)+1}')
    out = BytesIO(); wb.save(out); return out.getvalue()


@lru_cache(maxsize=16)
def sample_files(sample_id='1'):
    if sample_id not in SAMPLE_SETS: raise ValueError('지원하지 않는 샘플 세트입니다.')
    if sample_id=='15':
        old,comparisons=sample_collection();return old,comparisons[0][0]
    if sample_id=='17': return merged_sample_pair()
    if sample_id not in ('1','2'): return extra_sample(sample_id)
    main = [device(n) for n in range(1, 501)]
    if sample_id == '1':
        # Newly introduced records only; no overlap with the main inventory.
        sub = [device(n)[:4] for n in range(501, 531)]
    else:
        retained=retained_ids(500,2159)
        name_changes,model_changes=change_groups(retained,49,33,16,50022)
        sub=[]
        for n in [*retained,*range(501,516)]:
            row=device(n)[:4]
            if n in name_changes:row[1]+=' (이설)'
            if n in model_changes:row[3]=row[3].split('-')[0]+'-'+Random(n+97).choice(['XNP-6400','QNO-8080R','TNV-7011'])
            sub.append(row)
    Random(20261029).shuffle(sub)
    # Each workbook has its own display sequence, independent of identity.
    for number, row in enumerate(sub, 1):
        row[0] = number
    return workbook(MAIN_HEADERS, main, 'CCTV 관리대장'), workbook(SUB_HEADERS, sub, 'CCTV 추출자료')


# The hints describe the test case; matching keys are always chosen by the user.
for sid,title,sizes,hint in [
    ('3','순번 없는 자산대장','500 / 510','기준: 자산코드 · 순번 열 없음'),
    ('4','창고별 재고 · 복합 기준','500 / 510','기준: 품목코드 + 창고 · 품목코드 단독은 중복'),
    ('5','서로 다른 거래처 양식','500 / 510','기준: 거래처코드 · 영어 열 연결 확인'),
    ('6','제목이 4행인 보고서','500 / 510','기준: 자산코드 · 제목 4행 / 데이터 5행'),
    ('7','중복·공란 검사 [오류 확인용]','500 / 500','의도된 오류: 원본 중복 코드 / 새 파일 빈 코드'),
    ('8','앞자리 0 · 문자/숫자 혼용','500 / 500','기준: 코드 · 앞자리 0과 공백 정규화 확인'),
    ('9','행 순서만 변경','500 / 500','기준: 자산코드 · 예상 변경 0건'),
    ('10','수식 · 다른 시트 참조','500 / 495','기준: 품목코드 · 삭제 해제 후 저장 / 수식 보존 확인'),
    ('11','신규 데이터만 수신','500 / 50','기준: 자산코드 · 삭제 전체 해제 → 결과 550행'),
    ('12','대용량 자산대장','10000 / 10010','기준: 자산코드 · 검색·스크롤·행 선택·저장'),
    ('13','수식 복사 검증','10 / 12','기준: 항목코드 · SUM 수식과 행 이동 · 일반 복사 수식 검증'),
    ('15','부서별 예산 취합','0 / 30 × 10','기준: 예산항목코드 · 부서별 요청 예산 · 최종 300행'),
    ('14','다른 시트 참조 검증','10 / 12','기준: 품목코드 · 단가표 1000 / 2000 · 참조 대상과 수식 복사 확인'),
    ('17','병합된 비품 대장','19 / 21','기준: 품목코드 · 대분류·중분류 병합, 소계·총계·결재란'),
]:
    SAMPLE_SETS[sid]={'label':f'{sid}. {title} · {sizes}',
                      'names':(f'샘플{sid}_메인.xlsx',f'샘플{sid}_서브.xlsx'),
                      'summary':hint,'hint':hint}
SAMPLE_SETS=dict(sorted(SAMPLE_SETS.items(),key=lambda item:int(item[0])))
SAMPLE_SETS['6'].update(old_header=4,old_start=5,new_header=4,new_start=5)

ASSET_HEADERS=['자산코드','자산명','분류','모델명','제조사','설치위치','담당자','도입년도','비고']
ASSET_SUB=['자산코드','자산명','모델명','설치위치']


def asset(number):
    rng=Random(20013+number*7919)
    category=rng.choices(['컴퓨터','모니터','네트워크','프린터','저장장치'],[36,28,18,10,8])[0]
    products={'컴퓨터':[('삼성전자','DB400TCA','업무용 데스크톱'),('LG전자','15Z90R','업무용 노트북'),('Dell','OptiPlex 7010','설계용 PC')],
              '모니터':[('LG전자','24MP400','사무용 모니터'),('삼성전자','S27C310','회의실 모니터')],
              '네트워크':[('Cisco','CBS350-24T','액세스 스위치'),('Aruba','AP-505','무선 AP'),('ipTIME','T5008','업무망 공유기')],
              '프린터':[('HP','M404dn','문서 프린터'),('신도리코','D450','복합기')],
              '저장장치':[('Synology','DS923+','자료 백업 장치'),('삼성전자','T7 Shield','이동식 저장장치')]}
    maker,model,name=rng.choice(products[category])
    location=rng.choice(['본사','연구소','물류센터','영업지사','별관'])+' '+rng.choice(['1층 사무실','2층 회의실','3층 운영실','지하 전산실','교육장','생산관리실'])
    return [f'AS{number:05d}',name,category,model,maker,location,
            rng.choice(['김민수','이서연','박지훈','최유진','정현우','윤수빈','한지민','오준호']),
            rng.choices(range(2017,2027),[1,2,4,7,9,15,19,20,15,8])[0],
            rng.choice(['','', '분기 점검','보증 만료 예정','예비 장비','부서 이동 이력 있음','임대 장비'])]


def projection(row, headers, all_headers):
    return [row[all_headers.index(h)] for h in headers]


def asset_pair(count=500, incoming=None, changes=True, header_offset=False):
    main=[asset(n) for n in range(1,count+1)]
    ids=incoming if incoming is not None else [*retained_ids(count,818+count),*range(count+1,count+16)]
    sub=[projection(asset(n),ASSET_SUB,ASSET_HEADERS) for n in ids]
    if changes:
        kept=[n for n in ids if n<=count]
        models,locations=change_groups(kept,(count-5)//10,(count-5)//15,(count-5)//30,113+count)
        for number,row in zip(ids,sub):
            if number in models:row[2]=Random(number).choice(['ProDesk 400 G9','Latitude 5440','ThinkCentre M70q'])
            if number in locations:row[3]=row[3]+' (이전)'
    Random(38).shuffle(sub)
    old=workbook(ASSET_HEADERS,main,'자산대장')
    new=workbook(ASSET_SUB,sub,'수집자료')
    if header_offset:
        def offset(data):
            wb=openpyxl.load_workbook(BytesIO(data)); ws=wb.active
            ws.insert_rows(1,3); ws['A1']='자산 현황 보고서'; ws['A2']='기준일: 2026-10-29'
            ws.freeze_panes='B5'; ws.auto_filter.ref=f'A4:{get_column_letter(ws.max_column)}{ws.max_row}'
            out=BytesIO(); wb.save(out); return out.getvalue()
        old,new=offset(old),offset(new)
    return old,new


# Kept deliberately small so the original, comparison and exported formulas can be inspected.
FORMULA_SAMPLE_ORDER=(4,1,11,3,7,2,12,5,10,6,9,8)


def formula_sample_pair(sid):
    from openpyxl.workbook.properties import CalcProperties
    def build(comparison):
        ids=FORMULA_SAMPLE_ORDER if comparison else range(1,11)
        if sid=='13':
            headers=['값1','값2','값3','값4','값5','합계','항목코드']
            rows=[]
            for n in ids:
                values=[n,2,3,4,5] if n in (1,3,11,12) else [Random(13+n*101+k).randint(1,90) for k in range(5)]
                if comparison and n==3:values[0]=30
                rows.append([*values,None,f'ITEM-{n:03d}'])
            name='합계자료' if comparison else '합계대장'
            formula_column=6
        else:
            headers=['품목코드','품목명','수량','금액','비고']
            rows=[[f'ITEM-{n:03d}',Random(14+n).choice(['복사용지 A4','서류 보관함','랜 케이블','바인더','라벨 용지','멀티탭','회의용 필기구']),8 if comparison and n==3 else n if n in (3,11,12) else Random(430+n).randint(1,24),None,Random(n).choice(['정기 발주','긴급 구매','월말 취합','부서 요청'])] for n in ids]
            name='발주자료' if comparison else '발주대장'
            formula_column=4
        wb=openpyxl.load_workbook(BytesIO(workbook(headers,rows,name)))
        try:
            wb.properties.description=f'샘플 {sid}: 실제 수식이 포함된 복사 검증 자료. 일반 복사와 값만 복사 동작을 확인합니다.'
            wb.calculation=CalcProperties(calcId=0,calcMode='auto',fullCalcOnLoad=True,forceFullCalc=True)
            ws=wb.active
            for r in range(2,len(rows)+2):
                cell=ws.cell(r,formula_column)
                cell.value=f'=SUM(A{r}:E{r})' if sid=='13' else f'=C{r}*단가표!$B$2'
                cell.number_format='0' if sid=='13' else '#,##0'
            if sid=='14':
                price=wb.create_sheet('단가표')
                price.append(['구분','단가']);price.append(['기준 단가',2000 if comparison else 1000])
                price.column_dimensions['A'].width=24;price.column_dimensions['B'].width=18
                price['B2'].number_format='#,##0'
                for cell in price[1]:
                    cell.fill=PatternFill('solid',fgColor='17365D');cell.font=Font(bold=True,color='FFFFFF')
            out=BytesIO();wb.save(out)
            caches={f'{get_column_letter(formula_column)}{i+2}':sum(row[:5]) if sid=='13' else row[2]*(2000 if comparison else 1000) for i,row in enumerate(rows)}
            return with_formula_cache(out.getvalue(),caches)
        finally:wb.close()
    return build(False),build(True)


def extra_sample(sid):
    if sid in ('13','14'):return formula_sample_pair(sid)
    if sid in ('3','6','9','11','12'):
        if sid=='9': return asset_pair(incoming=list(range(1,501)),changes=False)
        if sid=='11': return asset_pair(incoming=list(range(501,551)),changes=False)
        return asset_pair(count=10000 if sid=='12' else 500,header_offset=sid=='6')
    if sid=='4':
        headers=['품목코드','품목명','창고','보관위치','수량','단가','담당자','비고']
        shared=headers[:5]
        def item(n):
            rng=Random(4000+n)
            return [f'ITEM{(n-1)//2+1:04d}',Random((n-1)//2+1).choice(['니트릴 장갑','케이블 타이','보호 필름','포장 테이프','토너','복사용지','보안 봉투']), '서울창고' if n%2 else '부산창고',f'{rng.choice("ABCDE")}-{rng.randint(1,48):02d}',rng.randint(0,450),rng.choice([1200,3500,7200,18500,24000,67000]),rng.choice(['김정민','이수현','박도윤','최은지']),rng.choice(['','안전재고 확인','정기 발주','검수 대기'])]
        main=[item(n) for n in range(1,501)]
        kept=retained_ids(500,404);ids=[*kept,*range(501,516)]
        qty,locations=change_groups(kept,29,21,1,4042)
        sub=[item(n)[:5] for n in ids]
        for n,row in zip(ids,sub):
            if n in qty:row[4]+=Random(n).randint(1,35)
            if n in locations:row[3]='검수장-'+str(Random(n).randint(1,8))
        Random(4).shuffle(sub)
        return workbook(headers,main,'재고대장'),workbook(shared,sub,'창고재고')
    if sid=='5':
        headers=['거래처코드','거래처명','전화번호','주소','담당자','결제조건','비고']
        def company(n):
            rng=Random(5001+n*131)
            prefix=['한빛','서진','대영','유진','동원','우성','성진','다온','세림','정우','신영','태성','아람','현대','한결','미래','새한','성우','제일','나래']
            suffix=['산업','테크','상사','솔루션','물산','시스템','유통','기술','정밀','이엔지','로지스','전자','화학','정보통신','무역','디자인','기공','소재','개발','파트너스','인더스트리','서비스','네트웍스','엔지니어링','컴퍼니','글로벌']
            # A shuffled pool gives unique, plausible business names without ID suffixes.
            names=[a+b for a in prefix for b in suffix];Random(50051).shuffle(names)
            return [f'CO{n:05d}',names[n-1],f'{rng.choice(["02","031","032","042","051"])}-{rng.randint(210,998)}-{rng.randint(1000,9999)}',rng.choice(['서울특별시 금천구 가산디지털로','경기도 성남시 판교로','인천광역시 연수구 송도과학로','부산광역시 강서구 녹산산단로','대전광역시 유성구 테크노로'])+' '+str(rng.randint(12,390)),rng.choice(['김서준','이하윤','박민재','최지우','정예린']),rng.choice(['월말 정산','익월 10일','검수 후 30일','선입금']),'기존 계약 유지' if n==1 else rng.choice(['','정기 계약','견적 갱신 예정','담당자 확인','배송지 별도'])]
        main=[company(n) for n in range(1,501)];sub=[]
        kept=retained_ids(500,505)
        phones,addresses=change_groups(kept,24,16,8,5052)
        for n in [*kept,*range(501,516)]:
            code,name,phone,address,*_=company(n)
            if n in phones:phone=f'070-{Random(n).randint(2000,8999)}-{Random(91+n).randint(1000,9999)}'
            if n in addresses:address+=' (이전 사업장)'
            sub.append([address,code,phone,name])
        Random(5).shuffle(sub)
        return workbook(headers,main,'거래처 관리'),workbook(['Address','CustomerID','Tel','CompanyName'],sub,'CRM Export')
    if sid=='7':
        main=[asset(n) for n in range(1,501)]
        sub=[projection(asset(n),ASSET_SUB,ASSET_HEADERS) for n in range(1,501)]
        main[1][0]=main[0][0]; sub[9][0]=None
        return workbook(ASSET_HEADERS,main,'자산대장'),workbook(ASSET_SUB,sub,'수집자료')
    if sid=='8':
        codes=[f'{n:05d}' for n in range(1,251)]+list(range(1001,1250))+[123]
        main=[[code,Random(i).choice(['보관 상자','서류철','랜 케이블','회수용 봉투','라벨지','전원 어댑터']),Random(i+87).randint(1,240),'원본 메모'] for i,code in enumerate(codes,1)]
        changed=set(Random(808).sample(range(1,501),12))
        sub=[[(' '+str(row[0])+' ') if i%2 else str(row[0]),row[1],row[2]+(Random(i).randint(1,20) if i in changed else 0)] for i,row in enumerate(main,1)]
        Random(8).shuffle(sub)
        return workbook(['코드','품목명','수량','비고'],main,'품목대장'),workbook(['코드','품목명','수량'],sub,'수집자료')
    if sid=='10':
        main=[[f'P{n:05d}',Random(n).choice(['사무용 의자','회의용 테이블','문서 세단기','모니터 거치대','캐비닛','공기청정기']),Random(n+50).randint(1,30),Random(n+500).choice([12000,45000,98000,175000,320000,680000]),f'=C{n+1}*D{n+1}*세율!$B$1','원본 메모'] for n in range(1,501)]
        kept=retained_ids(500,1010);changed=set(Random(1011).sample(kept,19))
        sub=[[main[n-1][0],main[n-1][1],main[n-1][2]+(Random(n).randint(1,12) if n in changed else 0)] for n in kept]
        Random(10).shuffle(sub)
        old=workbook(['품목코드','품목명','수량','단가','금액','비고'],main,'견적대장')
        wb=openpyxl.load_workbook(BytesIO(old)); tax=wb.create_sheet('세율'); tax.append(['세율',1.1])
        out=BytesIO(); wb.save(out)
        cached={f'E{i+2}':row[2]*row[3]*11//10 for i,row in enumerate(main)}
        return with_formula_cache(out.getvalue(),cached),workbook(['품목코드','품목명','수량'],sub,'수집자료')
    raise ValueError('샘플 생성기가 없습니다.')


def with_formula_cache(data, values):
    """Fixture-only known results; preserve active formulas and store Excel's cached <v>."""
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    output=BytesIO()
    with ZipFile(BytesIO(data)) as source,ZipFile(output,'w') as target:
        for item in source.infolist():
            raw=source.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                root=ET.fromstring(raw)
                for cell in root.findall('.//{*}c'):
                    if cell.attrib.get('r') in values and cell.find('{*}f') is not None:
                        cached=cell.find('{*}v')
                        if cached is None:cached=ET.SubElement(cell,'{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                        cached.text=str(values[cell.attrib['r']])
                raw=ET.tostring(root)
            target.writestr(item,raw)
    return output.getvalue()


BUDGET_HEADERS=['예산항목코드','부서','사업명','예산과목','세부내역','요청금액','집행예정월','담당자','비고']
BUDGET_DEPARTMENTS=['기획팀','총무팀','인사팀','재무팀','정보지원팀','시설관리팀','영업팀','고객지원팀','연구개발팀','품질관리팀']


@lru_cache(maxsize=1)
def sample_collection():
    original=budget_workbook([],'예산취합대장')
    comparisons=[]
    for index,department in enumerate(BUDGET_DEPARTMENTS):
        rng=Random(15000+index)
        themes={
            '기획팀':[('경영계획 수립','용역비','중장기 운영계획 수립'),('성과관리 운영','운영비','성과지표 운영 및 보고서 제작')],
            '총무팀':[('공용 비품 교체','자산취득비','노후 사무 비품 교체'),('업무환경 개선','운영비','공용 공간 운영 및 환경 개선')],
            '인사팀':[('직무역량 교육','교육훈련비','직무별 외부 교육과정'),('신규 입사자 교육','교육훈련비','입문 교육 운영')],
            '재무팀':[('회계업무 개선','용역비','회계 프로세스 점검'),('결산 지원','운영비','결산 자료 검증 및 업무 지원')],
            '정보지원팀':[('업무시스템 개선','용역비','내부 시스템 기능 개선'),('보안 장비 교체','자산취득비','노후 보안 장비 교체')],
            '시설관리팀':[('청사 시설 보수','수선유지비','노후 시설 점검 및 보수'),('냉난방 설비 관리','수선유지비','설비 정기 점검')],
            '영업팀':[('고객사 설명회','행사비','지역별 고객사 설명회'),('영업자료 제작','홍보비','제품 안내자료 제작')],
            '고객지원팀':[('상담 품질 개선','교육훈련비','상담 응대 교육'),('고객 지원 운영','운영비','고객 문의 지원체계 운영')],
            '연구개발팀':[('시험 환경 구축','자산취득비','연구용 시험 환경 확충'),('개발 검증 지원','용역비','시제품 성능 검증')],
            '품질관리팀':[('정기 품질 검사','검사수수료','외부 시험기관 품질 검사'),('품질관리 개선','교육훈련비','품질 기준 및 검사 교육')],
        }
        rows=[]
        for item in range(1,31):
            project,account,detail=rng.choice(themes[department])
            scale=1.8 if department in ('정보지원팀','시설관리팀','연구개발팀') else 1
            amount=int(rng.triangular(300000,45000000*scale,5500000*scale)/10000)*10000
            month=rng.choices(range(1,13),[1,2,4,3,3,4,3,2,4,3,3,1])[0]
            rows.append([f'BUD-2027-{index+1:02d}-{item:03d}',department,project,account,
                         detail+' · '+rng.choice(['본사','별관','지역사무소','공용시설','내부 운영']),amount,f'2027-{month:02d}',
                         rng.choice(['김민수','이서연','박지훈','최유진','정현우','윤수빈','한지민','오준호']),
                         rng.choice(['','', '견적 확인 중','정기 사업','전년도 이월 없음','신규 요청','일정 협의 필요'])])
        rng.shuffle(rows)
        comparisons.append((budget_workbook(rows,'예산요청서'),f'샘플15_{index+1:02d}_{department}_예산요청.xlsx'))
    return original,comparisons


def budget_workbook(rows,title):
    wb=openpyxl.load_workbook(BytesIO(workbook(BUDGET_HEADERS,rows,title)))
    try:
        ws=wb.active
        for i,header in enumerate(BUDGET_HEADERS,1):ws.column_dimensions[get_column_letter(i)].width=42 if header=='세부내역' else 25 if header in ('사업명','예산항목코드') else 16
        for row in ws.iter_rows(min_row=2):row[5].number_format='#,##0"원"'
        output=BytesIO();wb.save(output);return output.getvalue()
    finally:wb.close()


def collection_zip(comparisons):
    from zipfile import ZipFile,ZIP_DEFLATED
    output=BytesIO()
    with ZipFile(output,'w',compression=ZIP_DEFLATED) as archive:
        for data,name in comparisons:archive.writestr(name,data)
    return output.getvalue()


MERGED_HEADERS=['대분류','중분류','품목코드','품목명','수량','단가','금액','비고','담당']
# (대분류, [(중분류, [(코드, 품목명, 수량, 단가, 비고, 담당)])])
MERGED_BLOCKS=[
    ('전자',[('영상',[('E-101','TV',4,1200000,'','김민수'),('E-102','모니터',10,250000,'','김민수'),('E-103','프로젝터',2,800000,'','이서연')]),
             ('생활',[('E-201','냉장고',2,900000,'','이서연'),('E-202','세탁기',3,700000,'','박지훈'),('E-203','에어컨',5,1100000,'','박지훈')]),
             ('사무',[('E-301','복합기',2,1500000,'','최유진')]),('사무',[('E-302','노트북',12,1300000,'','최유진')])]),
    ('가구',[('사무가구',[('F-101','책상',20,180000,'','정하늘'),('F-102','의자',20,120000,'2개 교체 예정','정하늘')]),
             ('수납',[('F-201','책장',6,150000,'','한도윤')]),
             ('생활가구',[('F-301','침대',2,450000,'','한도윤'),('F-302','소파',3,600000,'','오세아'),('F-303','옷장',2,380000,'','오세아')])]),
    ('사무용품',[('필기',[('S-101','볼펜',200,500,'','윤지아'),('S-102','형광펜',80,900,'','윤지아'),('S-103','연필',150,300,'','윤지아')]),
               ('용지',[('S-201','A4용지',40,25000,'','장태오'),('S-202','포스트잇',60,1500,'','장태오')])]),
]


def merged_inventory(blocks, comparison=False):
    """Office inventory with merged category cells, section titles, subtotals and a sign-off box (sample 10)."""
    wb=openpyxl.Workbook();ws=wb.active;ws.title='비품대장'
    title=Font(name='맑은 고딕',size=14,bold=True);bold=Font(name='맑은 고딕',bold=True);center=Alignment(horizontal='center',vertical='center')
    header_fill=PatternFill('solid',fgColor='17365D');section_fill=PatternFill('solid',fgColor='DDEBF7');total_fill=PatternFill('solid',fgColor='F2F2F2')
    ws['A1']='2026년 비품 현황';ws['A1'].font=title;ws.merge_cells('A1:I1')
    ws['A2']='기준일: 2026-11-01'+(' (회신본)' if comparison else '');ws.merge_cells('A2:I2')
    for col,name in enumerate(MERGED_HEADERS,1):
        cell=ws.cell(3,col,name);cell.fill=header_fill;cell.font=Font(name='맑은 고딕',bold=True,color='FFFFFF');cell.alignment=center
    row=4;cache={};subtotals=[]
    for number,(major,groups) in enumerate(blocks,1):
        ws.cell(row,1,f'{number}. {major}').font=bold;ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=9)
        for col in range(1,10):ws.cell(row,col).fill=section_fill
        row+=1;first=row
        for minor,items in groups:
            top=row
            for code,name,qty,price,note,owner in items:
                ws.cell(row,1,major);ws.cell(row,2,minor)
                for col,value in zip(range(3,7),(code,name,qty,price)):ws.cell(row,col,value)
                ws.cell(row,7,f'=E{row}*F{row}');cache[f'G{row}']=qty*price
                if note:ws.cell(row,8,note)
                if owner:ws.cell(row,9,owner)
                if code=='F-102':ws.merge_cells(start_row=row,start_column=8,end_row=row,end_column=9)
                row+=1
            if not comparison or minor=='영상':
                if row-top>1:ws.merge_cells(start_row=top,start_column=2,end_row=row-1,end_column=2)
        last=row-1
        if not comparison and last>first:ws.merge_cells(start_row=first,start_column=1,end_row=last,end_column=1)
        for r in range(first,last+1):
            for col in (1,2):ws.cell(r,col).alignment=center
        ws.cell(row,1,f'{major} 소계').font=bold;ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=4)
        ws.cell(row,5,f'=SUM(E{first}:E{last})');ws.cell(row,7,f'=SUM(G{first}:G{last})')
        cache[f'E{row}']=sum(ws.cell(r,5).value for r in range(first,last+1));cache[f'G{row}']=sum(cache[f'G{r}'] for r in range(first,last+1))
        for col in range(1,10):ws.cell(row,col).fill=total_fill
        subtotals.append(row);row+=1
    ws.cell(row,1,'총계').font=bold;ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=4)
    ws.cell(row,5,'='+'+'.join(f'E{r}' for r in subtotals));ws.cell(row,7,'='+'+'.join(f'G{r}' for r in subtotals))
    cache[f'E{row}']=sum(cache[f'E{r}'] for r in subtotals);cache[f'G{row}']=sum(cache[f'G{r}'] for r in subtotals)
    row+=2
    ws.cell(row,6,'담당');ws.merge_cells(start_row=row,start_column=6,end_row=row,end_column=7)
    ws.cell(row,8,'팀장');ws.merge_cells(start_row=row,start_column=8,end_row=row,end_column=9)
    ws.merge_cells(start_row=row+1,start_column=6,end_row=row+2,end_column=7);ws.merge_cells(start_row=row+1,start_column=8,end_row=row+2,end_column=9)
    for col,width in zip('ABCDEFGHI',(10,10,10,12,8,12,14,16,10)):ws.column_dimensions[col].width=width
    out=BytesIO();wb.save(out);return with_formula_cache(out.getvalue(),cache)


def merged_sample_pair():
    from copy import deepcopy
    blocks=deepcopy(MERGED_BLOCKS)
    def items(major,minor):return next(i for m,g in blocks if m==major for n,i in g if n==minor)
    def edit(code,**changes):
        for major,groups in blocks:
            for minor,rows in groups:
                for n,item in enumerate(rows):
                    if item[0]==code:rows[n]=(code,item[1],changes.get('qty',item[2]),item[3],changes.get('note',item[4]),item[5])
    edit('E-102',qty=12);edit('E-301',qty=3);edit('F-102',qty=18);edit('S-201',note='대량 구매')
    # 중분류 변경: 에어컨이 생활에서 사무로 (행은 옮기지 않는다)
    life=items('전자','생활');aircon=life.pop();blocks[0][1][2]=('사무',[aircon]+blocks[0][1][2][1])
    life[:]=[i for i in life if i[0]!='E-202']                                   # 삭제: 블록 가운데
    office=items('가구','사무가구');office[:]=[i for i in office if i[0]!='F-101'] # 삭제: 병합 첫 행
    items('전자','영상').append(('E-104','스피커',6,150000,'','김민수'))          # 추가: 전자 블록 안
    items('가구','생활가구').append(('F-304','수납장',2,220000,'','오세아'))
    items('사무용품','용지').append(('S-203','클립',100,800,'','장태오'))          # 추가: 마지막 블록 끝
    blocks.append(('주방',[('주방',[('K-101','전기포트',3,40000,'','이서연')])]))  # 추가: 새 대분류
    return merged_inventory(MERGED_BLOCKS),merged_inventory(blocks,comparison=True)
