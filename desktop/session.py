"""Reversible desktop work state built on the existing workbook engine."""
from copy import copy, deepcopy
from functools import lru_cache
import json
import hashlib
from ipaddress import ip_address
import collection_flow as collection
import comparison_rules
import manual_edits
from analysis_cache import AnalysisCache
from compare import VERSION,compare_tables,apply_changes,is_sequence,normalized,sheet_names,unsupported_objects
from formats import prepare
from ui_helpers import suggested_mapping,suggested_keys
from workspace import aligned_rows,formula_values,effective_selection


class Session:
    def __init__(self,original,comparisons,name):
        self.cache=AnalysisCache(VERSION)
        self.flow={};collection.start(self.flow,prepare(original,name),[(prepare(data,n),n) for data,n in comparisons],name)
        self.mapping={};self.keys=[];self.layout={}
        self.rules=comparison_rules.clean();self.copy_mode='일반 복사';self.row_mode=False
        self.sort_columns=[];self.descending=False;self.sort_type='자동'
        self.kind='전체 항목';self.search='';self.filters={};self.view_sort=None
        self.edits=[];self.selected=set();self.issue='';self.placements={};self.display_override=None
        self.load_stage()
        self.saved_signature=self.signature()

    def signature(self):
        return hashlib.sha256(self.old+self.new+json.dumps([self.mapping,self.keys,self.rules,self.row_mode,self.copy_mode,self.sort_columns,self.descending,sorted(self.selected,key=str),self.edits,sorted(getattr(self,'placements',{}).items())],ensure_ascii=False,sort_keys=True).encode()).hexdigest()

    def clone(self):
        other=copy(self);other.flow=deepcopy(self.flow);other.selected=set(self.selected);other.edits=deepcopy(self.edits)
        other.mapping=dict(self.mapping);other.keys=list(self.keys);other.layout=dict(self.layout);other.rules=dict(self.rules)
        other.filters=deepcopy(self.filters);other.sort_columns=list(self.sort_columns)
        return other

    DIFF_FIELDS=('row_mode','copy_mode','sort_columns','descending','sort_type','kind','search','view_sort','filters','placements','display_override')

    def diff_from(self,old):
        """What changed from `old` to this state, as a small patch; None when the rows/structure differ (needs a full snapshot)."""
        if (self.rows is not old.rows or self.layout!=old.layout or self.mapping!=old.mapping or self.keys!=old.keys or self.rules!=old.rules
                or self.issue!=old.issue or self.flow['queue_index']!=old.flow['queue_index']):return None
        diff={'selected':(frozenset(self.selected-old.selected),frozenset(old.selected-self.selected)),'fields':{}}
        for name in self.DIFF_FIELDS:
            before,after=getattr(old,name),getattr(self,name)
            if before!=after:diff['fields'][name]=(deepcopy(before),deepcopy(after))
        if self.edits!=old.edits:diff['edits']=(deepcopy(old.edits),deepcopy(self.edits))
        return diff

    def apply_diff(self,diff,forward=True):
        """Apply a patch from `diff_from` forwards (redo) or backwards (undo)."""
        added,removed=diff['selected']
        if not forward:added,removed=removed,added
        self.selected=(self.selected-removed)|added
        for name,(before,after) in diff['fields'].items():setattr(self,name,deepcopy(after if forward else before))
        if 'edits' in diff:self.edits=deepcopy(diff['edits'][1 if forward else 0])
        if 'edits' in diff or 'row_mode' in diff['fields'] or 'copy_mode' in diff['fields']:self.prepare_results()
        else:self.prepare_results({self.change_rows[i] for i in added|removed if i in self.change_rows})

    def load_stage(self):
        self.placements={};self.display_override=None
        self.old,self.new=self.flow['sources'];self.names=self.flow['names'];self.warnings=unsupported_objects(self.old)
        a,b=self.where('old',lambda:self.cache.layout(self.old),False),self.where('new',lambda:self.cache.layout(self.new),False)
        common=set(a.get('candidates',{}))&set(b.get('candidates',{}))
        if a['sheet']!=b['sheet'] and common:
            # Both files have a table on a sheet with the same name: compare those sheets with each other.
            name=max(common,key=lambda n:a['candidates'][n][0]+b['candidates'][n][0])
            a={'sheet':name,'header':a['candidates'][name][1],'start':a['candidates'][name][2]};b={'sheet':name,'header':b['candidates'][name][1],'start':b['candidates'][name][2]}
        for side,auto,data in [('old',a,self.old),('new',b,self.new)]:
            if self.layout.get(side+'_sheet') not in self.where(side,lambda:sheet_names(data),False):
                self.layout.update({side+'_sheet':auto['sheet'],side+'_header':auto['header'],side+'_start':auto['start']})
        self.read_tables()
        recommended=suggested_mapping(self.left,self.right)
        if not self.mapping or any(k not in self.left.headers or v not in self.right.headers for k,v in self.mapping.items()):self.mapping=recommended
        if not self.keys or any(k not in self.mapping for k in self.keys):self.keys=suggested_keys(self.left,self.right,self.mapping)
        self.analyze()
        restored=self.flow.get('pending_approvals')
        if restored is not None:self.selected=effective_selection(self.changes,restored,self.row_mode)
        self.edits=manual_edits.clean(self.flow.get('pending_edits',[]),self.left,self.right,self.mapping,self.keys) if not self.issue else []
        self.filters={k:v for k,v in self.filters.items() if k in self.left.headers}
        if self.view_sort and self.view_sort[1] not in [*self.left.headers,'__row__','__key__']:self.view_sort=None
        native=self.flow.get('native_edit_reviews',{}).get(self.flow['queue_index'])
        if native and native[2]==hashlib.sha256(self.old).hexdigest():self.edits=deepcopy(native[0]);self.selected=set(native[1])
        self.prepare_results()

    def label(self,side):
        names=getattr(self,'names',None) or ('','')
        return ('원본' if side=='old' else '비교')+" 파일 '"+str(names[0 if side=='old' else 1])+"'"

    def where(self,side,work,sheet=True):
        """Run a read of one file; any problem names the file (and sheet) it came from."""
        try:return work()
        except ValueError as exc:
            place=self.label(side)+(f" · 시트 '{self.layout[side+'_sheet']}'" if sheet else '')
            raise ValueError(f'{place} · {exc}') from exc
        except Exception as exc:
            raise ValueError(f'{self.label(side)}을 읽을 수 없습니다. 암호가 없는 엑셀(.xlsx·.xlsm·.xls) 또는 CSV 파일인지 확인하세요. ({type(exc).__name__}: {exc})') from exc

    def read_tables(self):
        self.left=self.where('old',lambda:self.cache.read(self.old,self.layout['old_sheet'],self.layout['old_header'],self.layout['old_start']))
        self.right=self.where('new',lambda:self.cache.read(self.new,self.layout['new_sheet'],self.layout['new_header'],self.layout['new_start']))
        self.headers=self.left.headers
        self.sequence=next((c for c in self.headers if is_sequence(c)),None)

    def analyze(self):
        self.issue='';self.changes=[];self.rows=[];self.edits=[]
        try:
            self.changes,_=compare_tables(self.left,self.right,self.mapping,self.keys,self.rules,labels=(self.label('old'),self.label('new')))
            self.rows=aligned_rows(self.left,self.right,self.mapping,self.keys,self.changes,formula_values(self.new,self.right),formula_values(self.old,self.left))
        except ValueError as exc:self.issue=str(exc)
        self.selected={c['id'] for c in self.changes if c['kind']!='삭제 후보'}
        self.change_rows={c['id']:i for i,row in enumerate(self.rows) for c in row['changes']}
        self.changed_rows=[i for i,row in enumerate(self.rows) if row['changes']]
        self.tokens={json.dumps(row['key'],ensure_ascii=False):i for i,row in enumerate(self.rows)}
        self.prepare_results()

    def configure(self,*,keys=None,mapping=None,layout=None,rules=None):
        if mapping is not None:self.mapping=dict(mapping)
        if keys is not None:self.keys=list(keys)
        if layout is not None:
            self.layout=dict(layout);self.read_tables()
            if mapping is None:self.refit_columns()
        if rules is not None:self.rules=comparison_rules.clean(rules)
        self.analyze()
        # A new sheet/row range is kept even if the comparison cannot run yet, so the links can be fixed on it.
        if self.issue and layout is None:raise ValueError(self.issue)

    def refit_columns(self):
        """After the sheet or rows change: keep links that still exist, suggest the rest, and pick keys again if needed."""
        valid={k:v for k,v in self.mapping.items() if k in self.left.headers and v in self.right.headers}
        used=set(valid.values())
        try:recommended=suggested_mapping(self.left,self.right)
        except Exception:recommended={}
        merged={**{k:v for k,v in recommended.items() if k not in valid and v not in used},**valid}
        self.mapping={h:merged[h] for h in self.left.headers if h in merged}
        self.keys=[k for k in self.keys if k in self.mapping]
        if not self.keys:
            try:self.keys=suggested_keys(self.left,self.right,self.mapping) if self.mapping else []
            except Exception:self.keys=[]
        self.filters={k:v for k,v in self.filters.items() if k in self.left.headers}
        if self.view_sort and self.view_sort[1] not in [*self.left.headers,'__row__','__key__']:self.view_sort=None

    def source(self,index,pane,calculated=True):
        row=self.rows[index];side='before' if pane==0 else 'incoming';value=row[side]
        if value is None:return None
        if not calculated or self.copy_mode!='값만 복사':return value
        return {**value,**{c:v if v is not None else '계산값 없음' for c,v in row[side+'Calculated'].items()}}

    def changed_indexes(self):
        """Rows that carry a change (original or manual); every other row has none, so loops can skip it."""
        manual=getattr(self,'review_rows',{})
        return sorted(set(self.changed_rows)|set(manual)) if manual else self.changed_rows

    def prepare_results(self,dirty=None):
        self._all_changes=None
        if dirty is None:self.results=[None]*len(self.rows);dirty=range(len(self.rows))
        else:self.results=list(self.results)
        self.review_rows={};self.edit_lookup={}
        for edit in self.edits:
            i=self.tokens.get(json.dumps(edit['key'],ensure_ascii=False))
            if i is None:continue
            self.edit_lookup[(i,edit['column'])]=edit['value']
            row=self.rows[i];changes=self.review_rows.setdefault(i,[dict(c) for c in row['changes']])
            existing=next((c for c in changes if c['column']==edit['column'] or c['kind']=='추가'),None)
            if existing is None:
                existing={'id':'manual:'+json.dumps([row['key'],edit['column']],ensure_ascii=False),'kind':'수정','column':edit['column'],'key':row['key']}
                changes.append(existing)
            existing['manual']=True
        self.change_rows={c['id']:i for i in self.changed_indexes() for c in self.review_changes(i)}
        overrides={}
        for edit in self.edits:
            i=self.tokens[json.dumps(edit['key'],ensure_ascii=False)]
            c=next(c for c in self.review_changes(i) if c['column']==edit['column'] or c['kind']=='추가')
            if c['id'] in self.selected:overrides.setdefault(tuple(edit['key']),{})[edit['column']]=edit['value']
        self.overrides=overrides
        for i in dirty:
            row=self.rows[i];base=self.source(i,0);value=dict(base) if base is not None else None
            for c in row['changes']:
                if c['id'] not in self.selected:continue
                if c['kind']=='삭제':value=None
                elif c['kind']=='추가':value=dict(self.source(i,1))
                elif value is not None:value[c['column']]=self.source(i,1)[c['column']]
            if value is not None and self.row_copied(i):
                # Row mode copies the whole comparison row: columns the comparison lacks end up blank.
                incoming=self.source(i,1) or {}
                for col in self.headers:
                    if col not in self.keys and not is_sequence(col):value[col]=incoming.get(col,'')
            if value is not None:
                for col,text in overrides.get(tuple(row['key']),{}).items():value[col]=text[1:] if text.startswith("'") else text
            self.results[i]=value
        self.ordinals={};number=0
        for i,value in enumerate(self.results):
            if value is not None and not self.rows[i].get('structure'):number+=1;self.ordinals[i]=number

    def row_blanked_columns(self):
        """Row mode: original columns left unlinked are emptied in every row whose change is applied."""
        if not any(self.row_copied(i) for i in self.changed_indexes()):return []
        return [c for c in self.headers if c not in self.mapping and c not in self.keys and not is_sequence(c)]

    def row_copied(self,index):
        """Row mode: an applied change makes the whole row come from the comparison file."""
        return self.row_mode and any(c['kind']=='수정' and c['id'] in self.selected for c in self.rows[index]['changes'])

    def choose(self,ids,on):
        dirty={self.change_rows[i] for i in ids}
        self.selected.update(ids) if on else self.selected.difference_update(ids)
        self.selected=effective_selection(self.all_changes(),self.selected,self.row_mode)
        self.prepare_results(dirty)

    def review_changes(self,index):return self.review_rows.get(index,self.rows[index]['changes']) if hasattr(self,'review_rows') else self.rows[index]['changes']

    def all_changes(self):
        # Reused until the next prepare_results; callers only read it.
        cached=getattr(self,'_all_changes',None)
        if cached is None:cached=self._all_changes=[{**c,'key':self.rows[i]['key']} for i in self.changed_indexes() for c in self.review_changes(i)]
        return cached

    def candidate(self,index,column):
        if (index,column) in self.edit_lookup:return self.edit_lookup[(index,column)]
        value=(self.source(index,1) or {}).get(column,'');return '' if value is None else str(value)

    def edit(self,index,column,text):
        row=self.rows[index]
        if self.results[index] is None or is_sequence(column) or text==str(self.raw_result(index,column)):return False
        edits=[e for e in self.edits if not (e['key']==row['key'] and e['column']==column)]
        baseline=self.raw_result(index,column,False)
        if text!=str(baseline):edits.append({'key':row['key'],'column':column,'value':text})
        self.edits=manual_edits.clean(edits,self.left,self.right,self.mapping,self.keys)
        self.prepare_results({index})
        for c in self.review_changes(index):
            if c.get('manual') and (c['column']==column or c['kind']=='추가'):self.selected.add(c['id'])
        self.selected=effective_selection(self.all_changes(),self.selected,self.row_mode)
        self.prepare_results({index});return True

    def raw_result(self,index,column,manual=True):
        row=self.rows[index];value=(row['before'] or {}).get(column,'')
        for c in row['changes']:
            if c['id'] in self.selected and (c['kind']=='추가' or c['kind']=='수정' and c['column']==column):value=(row['incoming'] or {}).get(column,'')
        if self.row_copied(index) and column not in self.keys and not is_sequence(column):value=(row['incoming'] or {}).get(column,'')
        value=self.overrides.get(tuple(row['key']),{}).get(column,value) if manual else value
        return '' if value is None else value

    def save(self):
        if self.issue:raise ValueError(self.issue)
        return apply_changes(self.old,self.left,self.right,self.mapping,self.changes,self.selected&{c['id'] for c in self.changes},self.sort_columns,self.descending,with_metadata=True,comparison_data=self.new,copy_mode=self.copy_mode,sort_type=self.sort_type,manual_edits=self.active_edits(),edit_keys=self.keys,row_mode=self.row_mode,placements={tuple(json.loads(k)):v for k,v in self.placements.items()},source_name=str(self.names[1]) if len(self.names)>1 else '')

    def engine_selected(self):return self.selected&{c['id'] for c in self.changes}

    def active_edits(self):
        return [e for e in self.edits if e['column'] in self.overrides.get(tuple(e['key']),{}) and self.results[self.tokens[json.dumps(e['key'],ensure_ascii=False)]] is not None]

    def remember(self):
        self.flow.setdefault('native_edit_reviews',{})[self.flow['queue_index']]=(deepcopy(self.edits),set(self.selected),hashlib.sha256(self.old).hexdigest())
        self.flow['manual_edits']=deepcopy(self.active_edits())
        collection.remember_review(self.flow,self.engine_selected())

    def next(self,skip=False):
        self.remember()
        output=None if skip else self.save().data
        collection.advance(self.flow,set() if skip else self.engine_selected(),output,{'old_header':self.left.header_row,'old_start':self.left.start_row})
        if not self.flow['queue_complete']:self.load_stage()

    def previous(self):
        self.remember();collection.previous(self.flow);self.load_stage()

    def value(self,i,pane,col):
        if col=='__key__':return self.rows[i]['label']
        if col=='__row__':
            row=self.rows[i];value=row['incomingRow'] if pane==1 else row['beforeRow'];return str(value) if value is not None else ''
        data=self.results[i] if pane==2 else self.source(i,pane)
        if data is None:return ''
        if pane==2 and col==self.sequence:return str(self.ordinals.get(i,''))
        value=data.get(col,'');return '' if value is None else str(value)

    @staticmethod
    @lru_cache(maxsize=262144)
    def sort_value(text):
        try:return (0,int(ip_address(text)))
        except ValueError:
            try:return (1,float(text.replace(',','')))
            except ValueError:return (2,text.casefold())

    def view_signature(self):return (self.kind,self.search,self.view_sort,json.dumps(self.filters,ensure_ascii=False,sort_keys=True,default=str))

    def set_view_sort(self,sort):
        """Sorting again re-applies the rule: a row dropped by hand while sorted stops overriding the order."""
        self.view_sort=sort;self.display_override=None

    def place(self,key,anchor,order=None):
        """Remember that an added row goes after original row `anchor`; `order` keeps the screen as dropped while sorted/filtered."""
        self.placements={**self.placements,json.dumps(key,ensure_ascii=False):anchor}
        self.display_override=(self.view_signature(),list(order)) if order is not None else None

    def apply_placements(self,result):
        """Put each placed added row right after the last shown row of the original at or above its anchor."""
        placed=[i for i in result if json.dumps(self.rows[i]['key'],ensure_ascii=False) in self.placements]
        if not placed:return result
        order=[i for i in result if i not in set(placed)]
        anchor_of={}
        for i in placed:
            anchor=self.placements[json.dumps(self.rows[i]['key'],ensure_ascii=False)];spot=0
            for n,j in enumerate(order):
                row=self.rows[j];at=row['beforeRow'] if row['beforeRow'] is not None else anchor_of.get(j)
                if at is not None and at<=anchor:spot=n+1
            order.insert(spot,i);anchor_of[i]=anchor
        return order

    def visible(self):
        override=getattr(self,'display_override',None)
        if override and override[0]==self.view_signature():
            alive=set(self._visible_rows());shown=[i for i in override[1] if i in alive]
            return shown+[i for i in alive if i not in set(shown)]
        # Without search/filters (and not sorting by the result pane) the order ignores which changes are ticked,
        # so it can be reused between checkbox toggles instead of re-sorting thousands of rows.
        plain=not self.search.strip() and not self.filters and (self.view_sort is None or self.view_sort[0]!=2)
        if plain:
            signature=(tuple(self.keys),self.kind,self.view_sort,tuple((tuple(e['key']),e['column']) for e in self.edits),tuple(sorted(self.placements.items())))
            cached=getattr(self,'_visible_cache',None)
            if cached and cached[0]==signature and cached[1] is self.rows:return list(cached[2])
        result=self._visible_rows()
        if plain:self._visible_cache=(signature,self.rows,list(result))
        return result

    def _visible_rows(self):
        result=[];kind=self.kind;query=self.search.strip().casefold()
        for i,row in enumerate(self.rows):
            if kind!='전체 항목' and not any(kind=='변경 항목' or c['kind']==kind for c in self.review_changes(i)):continue
            if query and query not in str([row['label'],row['before'],row['incoming'],self.results[i]]).casefold():continue
            keep=True
            for col,f in self.filters.items():
                value=self.value(i,f['pane'],col);needle=f.get('text','');op=f.get('op','선택값')
                if op=='선택값':ok=value in f['values']
                elif op=='포함':ok=needle.casefold() in value.casefold()
                elif op=='포함하지 않음':ok=needle.casefold() not in value.casefold()
                elif op=='같음':ok=value==needle
                elif op=='같지 않음':ok=value!=needle
                elif op=='시작 문자':ok=value.casefold().startswith(needle.casefold())
                elif op=='끝 문자':ok=value.casefold().endswith(needle.casefold())
                elif op=='빈 셀 아님':ok=bool(value)
                elif op in ('추가만','수정만','삭제만'):ok=any(c['kind']==op[:-1] and (c['kind']!='수정' or c['column']==col) for c in self.review_changes(i))
                elif op=='빈 셀':ok=not value
                else:
                    try:
                        a,b=float(value.replace(',','')),float(needle.replace(',',''))
                        ok={'보다 큼':a>b,'크거나 같음':a>=b,'보다 작음':a<b,'작거나 같음':a<=b}.get(op,False)
                    except ValueError:ok=False
                if not ok:keep=False;break
            if keep:result.append(i)
        sort=self.view_sort
        if sort:
            pane,col,descending=sort
            def sorting(i):
                row=self.rows[i]
                if col=='__key__':return tuple(self.sort_value(v) for v in row['key'])
                if col=='__row__':return (row['incomingRow'] or row['beforeRow'] or 0) if pane==1 else (row['beforeRow'] or row['incomingRow'] or 0)
                data=self.results[i] if pane==2 else self.source(i,pane)
                # A deselected added row remains reviewable at its incoming value.
                if data is None:data=self.source(i,1) or self.source(i,0) or {}
                value=data.get(col,'');return self.sort_value('' if value is None else str(value))
            result.sort(key=sorting,reverse=descending)
        elif self.keys and not self.left.structure_rows and not self.placements:
            # Sheets with section titles/subtotals (or rows placed by hand) keep the original layout so those rows stay in place.
            result.sort(key=lambda i:tuple(self.sort_value(v) for v in self.rows[i]['key']))
        if not sort and self.placements:result=self.apply_placements(result)
        return result
