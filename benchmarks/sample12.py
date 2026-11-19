"""Run with the project Python: python benchmarks/sample12.py (no timing assertions)."""
import json
from pathlib import Path
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compare import VERSION, sheet_names, table, compare_tables, apply_changes
from samples import sample_files
from ui_helpers import suggested_mapping
from workspace import aligned_rows, encode_rows

timings={}
def timed(name,fn):
    started=perf_counter();value=fn();timings[name]=round(perf_counter()-started,4);return value

old,new=timed('generate_sample',lambda:sample_files('12'))
timed('sheet_metadata',lambda:(sheet_names(old),sheet_names(new)))
a,b=timed('read_tables',lambda:(table(old,'자산대장'),table(new,'수집자료')))
m=timed('mapping',lambda:suggested_mapping(a,b))
changes,_=timed('compare',lambda:compare_tables(a,b,m,['자산코드']))
rows=timed('aligned_rows',lambda:aligned_rows(a,b,m,['자산코드'],changes))
payload=timed('compress_view',lambda:encode_rows(rows))
export=timed('export_with_metadata',lambda:apply_changes(old,a,b,m,changes,{c['id'] for c in changes},with_metadata=True))
assert len(export.table.rows)==10010
print(json.dumps({'version':VERSION,'seconds':timings,'view_json_bytes':len(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()),'view_payload_bytes':len(payload)},ensure_ascii=False,indent=2))
