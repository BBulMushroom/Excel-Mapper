"""Content-only overrides addressed by the original comparison identity."""
import math
import re


def clean(edits, left, right, mapping, keys):
    from compare import indexed, is_sequence
    if edits is None:return []
    if not isinstance(edits,list):raise ValueError('직접 편집 내용을 읽을 수 없습니다.')
    if not edits:return []
    valid=set(indexed(left,keys))|set(indexed(right,[mapping[k] for k in keys]))
    result={}
    for edit in edits:
        if not isinstance(edit,dict):raise ValueError('직접 편집 내용을 확인하세요.')
        key,column,value=edit.get('key'),edit.get('column'),edit.get('value')
        if not isinstance(key,list) or not all(isinstance(k,str) for k in key) or tuple(key) not in valid:
            raise ValueError(f"직접 편집한 행(기준 키 {' + '.join(map(str,key)) if isinstance(key,list) else key})을 찾을 수 없습니다. 파일이나 기준 키가 바뀌었으면 그 편집을 다시 입력하세요.")
        if not isinstance(column,str) or column not in left.headers or is_sequence(column):
            raise ValueError(f"직접 편집한 열 '{column}'을 원본에서 찾을 수 없거나 순번 열입니다. 순번은 자동으로 매겨지므로 편집할 수 없습니다.")
        if not isinstance(value,str) or len(value)>32767 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',value):
            raise ValueError(f"'{column}' 칸 내용은 제어 문자 없이 32,767자까지 입력할 수 있습니다(지금 {len(value) if isinstance(value,str) else 0:,}자).")
        result[(tuple(key),column)]={'key':key,'column':column,'value':value}
    return list(result.values())


def content(text):
    """Predictable Excel-like constants; do not guess dates or strip text spaces."""
    if text=='':return None,'n'
    if text.startswith("'"):return text[1:],'s'
    if text.startswith('=') and len(text)>1:return text,'f'
    if text in ('TRUE','FALSE'):return text=='TRUE','b'
    if re.fullmatch(r'[+-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?',text):
        number=float(text)
        # Excel stores only 15 significant digits. Keep long identifiers literal.
        digits=re.sub(r'[^0-9]','',text.split('e')[0].split('E')[0]).lstrip('0')
        if math.isfinite(number) and len(digits)<=15:
            return (int(text) if re.fullmatch(r'[+-]?\d+',text) else number),'n'
    return text,'s'
