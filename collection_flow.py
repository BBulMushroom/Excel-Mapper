"""Reversible, sequential collection; checkpoints prevent double application."""
from copy import deepcopy
import hashlib
from uuid import uuid4

FIELDS=('comparison_queue','queue_index','queue_versions','queue_decisions','queue_reviews',
        'queue_complete','collection_original','collection_session','pending_approvals')


def start(state, original, comparisons, original_name, layout=None):
    if not comparisons:
        raise ValueError('비교파일을 하나 이상 선택하세요.')
    state['comparison_queue']=list(comparisons)
    state['collection_session']=uuid4().hex
    state['queue_index']=0
    state['queue_versions']=[(original,original_name,deepcopy(layout or {}))]
    state['collection_original']=(original,original_name)
    state['queue_decisions']=[]
    state['queue_reviews']={}
    state['queue_complete']=False
    activate(state)


def activate(state):
    index=state['queue_index']
    data,name,layout=state['queue_versions'][index]
    comparison,comparison_name=state['comparison_queue'][index]
    state['sources']=(data,comparison)
    state['names']=(name,comparison_name)
    state['source_layout']=deepcopy(layout)
    state['source_generation']=state.get('source_generation',0)+1
    state['edit_original']=state['edit_comparison']=False
    for key in ('work_signature','saved_snapshot','output','result_order','history_values','payload_context','workspace_context'):
        state.pop(key,None)
    review=state['queue_reviews'].get(index,{})
    state['pending_approvals']=review.get('selected') if review.get('base')==hashlib.sha256(data).hexdigest() else None
    state['pending_edits']=deepcopy(review.get('edits',[])) if state['pending_approvals'] is not None else []
    state['manual_edits']=[]


def remember_review(state, selected, edits=None):
    index=state['queue_index']
    data=state['queue_versions'][index][0]
    state['queue_reviews']={**state.get('queue_reviews',{}),index:{'base':hashlib.sha256(data).hexdigest(),'selected':sorted(selected),'edits':deepcopy(edits if edits is not None else state.get('manual_edits',[]))}}


def advance(state, selected, output=None, layout=None):
    if state.get('queue_complete') and state['queue_index']!=len(state['comparison_queue'])-1:
        raise ValueError('이미 취합을 완료했습니다.')
    index=state['queue_index']
    remember_review(state,selected)
    version=state['queue_versions'][index]
    if output is not None:
        version=(output,version[1],deepcopy(layout or version[2]))
    state['queue_versions']=[*state['queue_versions'][:index+1],version]
    state['queue_decisions']=[*state['queue_decisions'][:index],'반영' if output is not None else '건너뜀']
    if index+1<len(state['comparison_queue']):
        state['queue_index']=index+1
        activate(state)
    else:
        state['queue_complete']=True
        state['output']=version[0]


def previous(state):
    if state.get('queue_complete'):
        state['queue_complete']=False
        state['queue_versions']=state['queue_versions'][:state['queue_index']+1]
        state['queue_decisions']=state['queue_decisions'][:state['queue_index']]
        activate(state)
    elif state.get('queue_index',0)>0:
        state['queue_index']-=1
        state['queue_versions']=state['queue_versions'][:state['queue_index']+1]
        state['queue_decisions']=state['queue_decisions'][:state['queue_index']]
        activate(state)


def summary(state):
    files=state.get('comparison_queue',[])
    return {'index':state.get('queue_index',0),'count':len(files),
            'complete':state.get('queue_complete',False),
            'session':state.get('collection_session',''),
            'applied':state.get('queue_reviews',{}).get(state.get('queue_index',0),{}).get('selected',[]) if state.get('queue_complete') else None,
            'names':[name for _,name in files]}
