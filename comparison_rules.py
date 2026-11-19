"""Comparison-only preferences; keys, formulas and workbook contents stay intact."""
from datetime import date, datetime
from functools import lru_cache
import math
import re

DEFAULTS={'ignore_case':False,'trim':True,'dates':'ymd','date_pattern':'YYYY-MM-DD','ignore_date_format':False}
DATE_MODES=('ymd','mdy','dmy','custom')


def date_pattern(pattern):
    if not isinstance(pattern,str) or not pattern or len(pattern)>80:
        raise ValueError('날짜 형식을 입력하세요. 예: YYYYMMDD, YY-MM-DD')
    return _compiled_pattern(pattern)


@lru_cache(maxsize=64)
def _compiled_pattern(pattern):
    parts=list(re.finditer(r'YYYY|YY|MM|DD|M|D',pattern,re.I));names=[];expression='';position=0
    for i,part in enumerate(parts):
        literal=pattern[position:part.start()]
        if re.search(r'[^\s./_년월일-]',literal):raise ValueError('날짜 형식은 YYYY 또는 YY, MM, DD와 구분자로 입력하세요.')
        token=part.group().upper();name='year' if token.startswith('Y') else 'month' if token.startswith('M') else 'day'
        if name in names:raise ValueError('날짜 형식에 연·월·일을 한 번씩 넣으세요.')
        names.append(name);adjacent=(i>0 and parts[i-1].end()==part.start()) or (i+1<len(parts) and parts[i+1].start()==part.end())
        width='{'+str(len(token))+'}' if name=='year' or adjacent else '{1,2}'
        expression+=re.escape(literal)+f'(?P<{name}>[0-9]{width})';position=part.end()
    tail=pattern[position:]
    if set(names)!={'year','month','day'} or re.search(r'[^\s./_년월일-]',tail):raise ValueError('날짜 형식에 연·월·일을 한 번씩 넣으세요.')
    return re.compile(expression+re.escape(tail)),len(next(p.group() for p in parts if p.group().upper().startswith('Y')))==2


def clean(value=None):
    if value is None:value={}
    if not isinstance(value,dict):raise ValueError('비교 설정 형식을 확인하세요.')
    result={**DEFAULTS,**{k:v for k,v in value.items() if k in DEFAULTS}}
    # Migrate prior off/ymd/mdy/dmy profiles; removed tolerance is never applied.
    if 'ignore_date_format' not in value:result['ignore_date_format']=value.get('dates','off')!='off'
    if result['dates']=='off':result['dates']='ymd'
    if any(type(result[k]) is not bool for k in ('ignore_case','trim','ignore_date_format')):raise ValueError('비교 설정을 확인하세요.')
    if result['dates'] not in DATE_MODES:raise ValueError('날짜 읽는 형식을 확인하세요.')
    try:date_pattern(result['date_pattern'])
    except ValueError:
        if result['dates']=='custom':raise
        result['date_pattern']=DEFAULTS['date_pattern']
    return result


def _text(value,trim):
    if value is None or isinstance(value,float) and math.isnan(value):return ''
    if isinstance(value,(int,float)) and not isinstance(value,bool):return str(int(value)) if float(value).is_integer() else str(value)
    text=str(value)
    return text.strip() if trim else text


def _date(value,text,rules):
    if isinstance(value,datetime):return value.isoformat(sep=' ')
    if isinstance(value,date):return datetime.combine(value,datetime.min.time()).isoformat(sep=' ')
    mode=rules['dates']
    # An unambiguous year-first date remains readable beside the chosen input format.
    if re.match(r'^\d{4}[-/.년]',text):
        normalized=re.sub(r'[/.년월]', '-',text).replace('일','').replace(' ','')
        try:return datetime.strptime(normalized,'%Y-%m-%d').isoformat(sep=' ')
        except ValueError:
            try:return datetime.fromisoformat(text).isoformat(sep=' ')
            except ValueError:pass
    if mode=='custom':
        regex,short_year=date_pattern(rules['date_pattern']);match=regex.fullmatch(text)
        if match:
            values={k:int(v) for k,v in match.groupdict().items()}
            if short_year:values['year']+=2000
            try:return datetime(**values).isoformat(sep=' ')
            except ValueError:return None
    if mode in ('mdy','dmy') and re.fullmatch(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{4}',text):
        try:return datetime.strptime(re.sub(r'[.-]','/',text),'%m/%d/%Y' if mode=='mdy' else '%d/%m/%Y').isoformat(sep=' ')
        except ValueError:return None
    return None


def equivalent(a,b,rules):
    left,right=_text(a,rules['trim']),_text(b,rules['trim'])
    if any(isinstance(v,str) and v.startswith('=') for v in (a,b)):return left==right
    if rules['ignore_date_format']:
        da,db=_date(a,left,rules),_date(b,right,rules)
        if da is not None and db is not None and da==db:return True
    return (left.casefold()==right.casefold()) if rules['ignore_case'] else left==right
