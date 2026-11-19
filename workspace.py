"""Aligned comparison rows for the three-pane UI, independent of Streamlit."""
from collections import defaultdict
from compare import indexed, normalized, is_sequence


def aligned_rows(left, right, mapping, keys, changes, calculated=None, before_calculated=None):
    before=indexed(left,keys)
    incoming=indexed(right,[mapping[k] for k in keys])
    by_key=defaultdict(list)
    for change in changes: by_key[tuple(change['key'])].append(change)
    rows=[]
    calculated=calculated or {}
    before_calculated=before_calculated or {}
    for key in dict.fromkeys([*before,*incoming]):
        old=before[key][1] if key in before else None
        new=incoming[key][1] if key in incoming else None
        rows.append({'key':list(key),'label':' / '.join(key),
                     'beforeRow':left.physical_rows[before[key][0]] if key in before else None,
                     'incomingRow':right.physical_rows[incoming[key][0]] if key in incoming else None,
                     'before':{c:normalized(old[c]) for c in left.headers} if old is not None else None,
                     'incoming':{c:normalized(new[next((h for h in right.headers if is_sequence(h)), c)]) if is_sequence(c) and any(is_sequence(h) for h in right.headers) else normalized(new[mapping[c]]) if c in mapping else '' for c in left.headers} if new is not None else None,
                     'beforeCalculated':{a:before_calculated.get(left.physical_rows[before[key][0]],{}).get(a) for a in left.formula_cells.get(left.physical_rows[before[key][0]],[]) } if key in before else {},
                     'incomingCalculated':{a:calculated.get(right.physical_rows[incoming[key][0]],{}).get(b) for a,b in mapping.items() if key in incoming and b in right.formula_cells.get(right.physical_rows[incoming[key][0]],[])},
                     'changes':[{'id':c['id'],'kind':'삭제' if c['kind']=='삭제 후보' else c['kind'],'column':c['column']} for c in by_key[key]]})
        if left.filled_cells and key in before:rows[-1]['beforeFilled']=left.filled_cells.get(rows[-1]['beforeRow'],[])
        if right.filled_cells and key in incoming:rows[-1]['incomingFilled']=[a for a,b in mapping.items() if b in right.filled_cells.get(rows[-1]['incomingRow'],[])]
    return with_structure_rows(rows,left,before_calculated) if left.structure_rows else rows


def with_structure_rows(rows, left, before_calculated):
    """Show section titles, subtotals and sign-off rows of the original at their place; they never carry changes.

    Rows only in the comparison go after the last data row and before the structure rows that end the table."""
    pending=[{'key':['§',str(r)],'label':'','structure':True,'beforeRow':r,'incomingRow':None,
              'before':{c:normalized(v) for c,v in values.items()},'incoming':None,
              'beforeCalculated':{a:before_calculated.get(r,{}).get(a) for a in left.formula_cells.get(r,[])},'incomingCalculated':{},'changes':[]}
             for r,values in sorted(left.structure_rows.items())]
    result=[];added=[]
    for row in rows:
        if row['beforeRow'] is None:added.append(row);continue
        while pending and pending[0]['beforeRow']<row['beforeRow']:result.append(pending.pop(0))
        result.append(row)
    return result+added+pending


def effective_selection(changes, selected, row_mode=False):
    valid={c['id'] for c in changes}
    selected=set(selected)&valid
    if row_mode:
        keys={tuple(c['key']) for c in changes if c['kind']=='수정' and c['id'] in selected}
        selected|={c['id'] for c in changes if c['kind']=='수정' and tuple(c['key']) in keys}
    return selected


def encode_rows(rows):
    """Compress the immutable view once; avoid multi-MB repeated component args."""
    import base64
    import gzip
    import json
    return base64.b64encode(gzip.compress(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode(),compresslevel=1,mtime=0)).decode('ascii')


def decode_rows(payload):
    import base64
    import gzip
    import json
    return json.loads(gzip.decompress(base64.b64decode(payload)))


def source_columns(left, right, mapping):
    """Physical Excel column letters; incoming columns can be reordered or renamed."""
    from openpyxl.utils import get_column_letter
    old={c:get_column_letter(i) for i,c in enumerate(left.headers,1)}
    new={c:get_column_letter(i) for i,c in enumerate(right.headers,1)}
    sequence=next((c for c in right.headers if is_sequence(c)),None)
    return {c:{'before':old[c],'incoming':new.get(mapping.get(c,sequence if is_sequence(c) else None))} for c in left.headers}


def formula_values(data, dataset):
    """Only read calculation caches when the selected sheet actually has formulas."""
    if not dataset.formula_cells:return {}
    import excel_copy
    copier=excel_copy.ExcelCopy(None,data,dataset.sheet,'값만 복사')
    columns={name:i+1 for i,name in enumerate(dataset.headers)}
    try:
        values={}
        for row,names in dataset.formula_cells.items():
            values[row]={}
            for name in names:
                exists,value,_=copier.calculated_value(row,columns[name])
                values[row][name]=normalized(value) if exists else None
        return values
    finally:copier.close()
