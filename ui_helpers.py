"""Defaults and validation for the guided browser workflow."""
import re
from compare import recommend, normalized, is_sequence, column_profile


def header_key(name):
    """Comparable form of a column title: width/case/whitespace/invisible characters and edge punctuation are ignored."""
    import unicodedata
    text=unicodedata.normalize('NFKC',normalized(name)).casefold()
    text=''.join(ch for ch in text if not ch.isspace() and unicodedata.category(ch) not in ('Cf','Cc'))
    return text.strip('*:：-_·')


def _confident_pairs(left,right,sources,targets):
    """Value-based links, accepted only when they are unmistakable.

    A pair needs most of its values in common, at least three distinct values (not Y/N-like columns), a decent score, to be each other's best match and to beat every alternative clearly. Anything weaker is left unlinked for the user to choose; a wrong link costs more than a missing one.
    """
    scored=recommend(left,right,sources,targets)
    best_for_source={};best_for_target={};by_source={};by_target={}
    for item in scored:
        a,b=item['원본 열'],item['비교 열'];by_source.setdefault(a,[]).append(item);by_target.setdefault(b,[]).append(item)
    profiles_left={};profiles_right={}
    def varied(a,b):
        # Y/N-like columns share values with many unrelated columns, so at least three distinct values are required.
        if a not in profiles_left:profiles_left[a]=len(column_profile(left,a)[0])
        if b not in profiles_right:profiles_right[b]=len(column_profile(right,b)[0])
        return profiles_left[a]>=3 and profiles_right[b]>=3
    pairs=[]
    for a,items in by_source.items():
        items=sorted(items,key=lambda x:-x['추천 점수']);top=items[0];b=top['비교 열']
        rivals=sorted(by_target[b],key=lambda x:-x['추천 점수'])
        second_for_a=items[1]['추천 점수'] if len(items)>1 else 0
        second_for_b=rivals[1]['추천 점수'] if len(rivals)>1 else 0
        mutual=rivals[0]['원본 열']==a
        if mutual and top['공통값 비율']>=60 and varied(a,b) and top['추천 점수']>=55 and top['추천 점수']-second_for_a>=15 and top['추천 점수']-second_for_b>=15:
            pairs.append((a,b))
    return pairs


def suggested_mapping(left, right):
    mapping, used = {}, set()
    left_columns=[c for c in left.headers if not is_sequence(c)];right_columns=[c for c in right.headers if not is_sequence(c)]
    left_keys={c:header_key(c) for c in left_columns};right_keys={c:header_key(c) for c in right_columns}
    for source in left_columns:
        key=left_keys[source]
        if not key:continue
        # Titles must be equal after normalisation and unambiguous on both sides.
        same_left=[c for c in left_columns if left_keys[c]==key];same_right=[c for c in right_columns if right_keys[c]==key]
        if len(same_left)==1 and len(same_right)==1 and same_right[0] not in used:
            mapping[source]=same_right[0];used.add(same_right[0])
    remaining_left=[c for c in left_columns if c not in mapping];remaining_right=[c for c in right_columns if c not in used]
    for a,b in _confident_pairs(left,right,remaining_left,remaining_right):
        if a not in mapping and b not in used:mapping[a]=b;used.add(b)
    return mapping


def suggested_key(left, right, mapping):
    candidates = []
    for source, target in mapping.items():
        a, b = [normalized(r[source]) for r in left.rows], [normalized(r[target]) for r in right.rows]
        if not a or not b or '' in a or '' in b or len(set(a)) != len(a) or len(set(b)) != len(b):
            continue
        name = re.sub(r'\s+', '', source + target).lower()
        identifier = any(word in name for word in ('관리번호', '고유번호', '자산번호', '코드', 'id', 'code', 'serial'))
        unstable = any(word in name for word in ('ip', '이름', '명', 'name', '위치', 'location'))
        overlap = len(set(a) & set(b)) / max(1, min(len(a), len(b)))
        candidates.append((int(identifier) * 2 - int(unstable) + overlap, source))
    return max(candidates, key=lambda x: x[0])[1] if candidates else None


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get('version') != 1:
        raise ValueError('이 앱에서 저장한 설정 파일을 선택해 주세요.')
    if not isinstance(profile.get('name'), str) or not profile['name'].strip():
        raise ValueError('설정 이름이 없는 파일입니다.')
    if profile.get('mode','셀 단위') not in ('셀 단위','행 단위'):
        raise ValueError('적용 단위가 올바르지 않습니다.')
    if profile.get('copy_mode','일반 복사') not in ('일반 복사','값만 복사'):
        raise ValueError('복사 방식이 올바르지 않습니다.')
    for field,choices,default in [('order',('원본 순서 유지','직접 정렬'),'원본 순서 유지'),('sort_direction',('오름차순','내림차순'),'오름차순'),('sort_type',('자동','문자','숫자·IP'),'자동')]:
        if profile.get(field,default) not in choices:raise ValueError('정렬 설정이 올바르지 않습니다.')
    if not isinstance(profile.get('sort_columns',[]),list) or any(not isinstance(c,str) for c in profile.get('sort_columns',[])):
        raise ValueError('정렬할 열이 올바르지 않습니다.')
    from comparison_rules import clean
    clean(profile.get('comparison_rules'))
    mapping = profile.get('mapping')
    if not isinstance(mapping, dict) or not mapping or any(not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items()):
        raise ValueError('열 연결 정보가 올바르지 않습니다.')
    if len(set(mapping.values())) != len(mapping):
        raise ValueError('같은 열이 여러 번 연결되어 있습니다.')
    keys = profile.get('keys')
    if not isinstance(keys, list) or not keys or any(not isinstance(k, str) or k not in mapping for k in keys):
        raise ValueError('항목을 구분할 기준이 없는 설정입니다.')
    for field in ('old_headers', 'new_headers'):
        if not isinstance(profile.get(field), list) or any(not isinstance(c, str) for c in profile[field]):
            raise ValueError('엑셀 열 정보가 없는 설정입니다.')
    for field, default in [('old_header',1),('new_header',1),('old_start',2),('new_start',2)]:
        value = profile.get(field, default)
        if type(value) is not int or not 1 <= value <= 1001:
            raise ValueError('제목 또는 데이터 행 번호가 올바르지 않습니다.')
    if profile.get('old_start',2) <= profile.get('old_header',1) or profile.get('new_start',2) <= profile.get('new_header',1):
        raise ValueError('데이터 시작 행은 제목 행보다 뒤여야 합니다.')
    return profile


def key_metrics(left,right,mapping):
    result={}
    for source,target in mapping.items():
        a=[normalized(r[source]) for r in left.rows];b=[normalized(r[target]) for r in right.rows]
        aa={v for v in a if v};bb={v for v in b if v}
        result[source]={'unique':round(100*min(len(aa)/max(1,len(a)),len(bb)/max(1,len(b)))),
                        'match':round(100*len(aa&bb)/max(1,min(len(aa),len(bb))))}
    return result


def detect_layout(data):
    """Inspect leading rows of each sheet, favouring labelled rectangular tables."""
    from io import BytesIO
    import openpyxl
    wb=openpyxl.load_workbook(BytesIO(data),read_only=True)
    best=None;candidates={}
    labels={'id','code','name','ip','순번','코드','자산코드','품목코드','거래처코드','카메라명','모델명','수량','주소','담당자','비고','설명'}
    try:
        for ws in wb:
            if ws.title=='변경 이력':continue
            ws.reset_dimensions()
            rows=list(ws.iter_rows(max_row=80,values_only=True))
            for i,row in enumerate(rows):
                values=[normalized(v) for v in row]
                while values and not values[-1]:values.pop()
                if not values or any(not v for v in values) or len(set(values))!=len(values):continue
                if not all(isinstance(v,str) for v in row[:len(values)]):continue
                following=next((j for j in range(i+1,len(rows)) if any(v is not None for v in rows[j])),None)
                if following is None:continue
                known=sum(v.lower() in labels or v.endswith(('코드','번호','이름','년도')) for v in values)
                score=len(values)+known*4
                candidate=(score,-i,ws.title,i+1,following+1)
                if best is None or candidate[:2]>best[:2]:best=candidate
                if ws.title not in candidates or candidate[:2]>candidates[ws.title][:2]:candidates[ws.title]=candidate
        # Per-sheet best tables let the caller prefer the same sheet in both files.
        if best:return {'sheet':best[2],'header':best[3],'start':best[4],'candidates':{n:(c[0],c[3],c[4]) for n,c in candidates.items()}}
        names=[s for s in wb.sheetnames if s!='변경 이력']
        return {'sheet':names[0] if names else '', 'header':1,'start':2}
    finally:wb.close()


def suggested_keys(left,right,mapping):
    from itertools import combinations
    def rank(col):
        name=col.lower()
        return 3 if any(t in name for t in ['코드','번호','code','id']) else 2 if 'ip' in name else 0
    cols=sorted(mapping,key=lambda c:-rank(c))
    def valid(columns):
        for t,fields in [(left,columns),(right,[mapping[c] for c in columns])]:
            values=[tuple(normalized(r[c]) for c in fields) for r in t.rows]
            if not values:continue
            if any('' in v or any(x.startswith('=') for x in v) for v in values) or len(set(values))!=len(values):return False
        return True
    # Stable identifiers first; if they need a companion prefer their compound key.
    stable=[c for c in cols if rank(c)>0]
    for size in range(1,min(3,len(stable))+1):
        for combo in combinations(stable,size):
            if valid(combo):return list(combo)
    for first in stable:
        for second in cols:
            if second!=first and valid([first,second]):return [first,second]
    for col in cols:
        if valid([col]):return [col]
    for combo in combinations(cols,2):
        if valid(combo):return list(combo)
    return cols[:1]
