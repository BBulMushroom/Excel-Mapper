"""Repeatable add-heavy export and sequential analysis benchmark (no timing assertions)."""
from io import BytesIO
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import openpyxl
from analysis_cache import AnalysisCache
from samples import sample_collection
from compare import VERSION,table,compare_tables,apply_changes
from ui_helpers import suggested_mapping,detect_layout

original,files=sample_collection()
wb=openpyxl.load_workbook(BytesIO(files[-1][0]));ws=wb.active;seed=list(ws.values)[1:]
for i in range(30,1200):
    row=list(seed[i%30]);row[0]=f'PERF-{i}';ws.append(row)
buffer=BytesIO();wb.save(buffer);incoming=buffer.getvalue()
a,b=table(original,'예산취합대장'),table(incoming,'예산요청서');mapping=suggested_mapping(a,b)
changes,_=compare_tables(a,b,mapping,['예산항목코드']);chosen={c['id'] for c in changes}
samples=[]
for _ in range(3):
    start=perf_counter();result=apply_changes(original,a,b,mapping,changes,chosen,comparison_data=incoming,with_metadata=True);samples.append(perf_counter()-start)
assert len(result.table.rows)==1200
cache=AnalysisCache(VERSION);cache.seed(result.data,result.table)
start=perf_counter();detect_layout(result.data);table(result.data,'예산취합대장');cold=perf_counter()-start
start=perf_counter();cache.layout(result.data);reused=cache.read(result.data,'예산취합대장');warm=perf_counter()-start
assert reused is result.table
print(json.dumps({'version':VERSION,'add_1200_seconds':samples,'median':median(samples),'next_original_analysis_seconds':{'cold':cold,'reuse':warm},'rows':1200},indent=2))
