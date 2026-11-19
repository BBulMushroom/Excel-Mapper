"""Command line mode: compare files and write the merged workbook without opening a window.

    ExcelMapper.exe --compare ORIGINAL COMPARISON [COMPARISON ...] [--out RESULT.xlsx] [options]

It uses the same engine and the same review rules as the window (`desktop.session.Session`), so a
result written here equals what the window would save with the same choices. Nothing in this module
imports Qt. Exit codes: 0 done, 2 bad arguments, 3 a file cannot be read, 4 the comparison/export failed.
"""
import argparse
import json
from pathlib import Path
import sys

KINDS={'add':'추가','edit':'수정','delete':'삭제'}


def attach_console():
    """A windowed Windows executable has no console; print into the one that started it, if any."""
    if sys.platform!='win32' or (sys.stdout is not None and sys.stderr is not None):return
    try:
        import ctypes
        if ctypes.windll.kernel32.AttachConsole(-1):
            sys.stdout=open('CONOUT$','w',encoding='utf-8');sys.stderr=open('CONOUT$','w',encoding='utf-8')
    except Exception:pass


def build_parser():
    parser=argparse.ArgumentParser(prog='ExcelMapper',description='엑셀 원본과 비교 파일을 비교하고 승인한 변경만 반영한 결과를 저장합니다.')
    parser.add_argument('--compare',nargs='+',metavar=('ORIGINAL','COMPARISON'),required=True,help='원본 파일 1개와 비교 파일 1개 이상(여러 개면 순서대로 취합)')
    parser.add_argument('--out',metavar='RESULT.xlsx',help='결과 파일. 없으면 분석만 하고 파일을 쓰지 않습니다.')
    parser.add_argument('--report',metavar='REPORT.json',help='분석 결과 JSON을 이 파일에 UTF-8로 저장')
    parser.add_argument('--json',action='store_true',help='사람이 읽는 요약 대신 JSON을 표준 출력으로 내보냄')
    parser.add_argument('--keys',help='기준 키 열 이름(원본 기준), 쉼표로 구분. 없으면 자동 추천')
    parser.add_argument('--map',action='append',default=[],metavar='원본열=비교열',help='열 연결 지정(여러 번 사용 가능). 없으면 자동 연결')
    parser.add_argument('--mode',choices=('cell','row'),default='cell',help='cell=셀 단위, row=행 단위(변경된 행을 비교본 한 행 전체로 복사)')
    parser.add_argument('--copy',choices=('normal','values'),default='normal',help='normal=수식·서식 복사, values=계산값만 복사')
    parser.add_argument('--apply',default='add,edit',help='반영할 종류: add,edit,delete 중 쉼표 구분, all, none. 기본 add,edit(삭제는 명시해야 반영)')
    parser.add_argument('--sheet-original');parser.add_argument('--sheet-comparison')
    parser.add_argument('--header-original',type=int);parser.add_argument('--header-comparison',type=int)
    parser.add_argument('--start-original',type=int);parser.add_argument('--start-comparison',type=int)
    parser.add_argument('--changes-limit',type=int,default=200,help='JSON에 포함할 변경 항목 수 상한(0이면 건수만, 기본 200)')
    return parser


def wanted_kinds(text):
    value=text.strip().lower()
    if value=='all':return set(KINDS.values())
    if value in ('','none'):return set()
    unknown=[part for part in value.split(',') if part.strip() not in KINDS]
    if unknown:raise ValueError('--apply에는 add, edit, delete, all, none만 쓸 수 있습니다: '+', '.join(unknown))
    return {KINDS[part.strip()] for part in value.split(',')}


def read_files(paths):
    result=[]
    for path in paths:
        file=Path(path)
        if not file.is_file():raise FileNotFoundError(f'파일을 찾을 수 없습니다: {path}')
        result.append((file.read_bytes(),file.name))
    return result


def stage_report(session,kinds,limit):
    """Counts and (limited) change list of the current comparison, and what the chosen policy applies."""
    details={c['id']:c for c in session.changes}
    changes=session.all_changes()
    counts={kind:sum(c['kind']==kind for c in changes) for kind in KINDS.values()}
    selected={kind:sum(c['kind']==kind and c['id'] in session.selected for c in changes) for kind in KINDS.values()}
    items=[]
    for change in changes[:max(0,limit)]:
        detail=details.get(change['id'],{})
        items.append({'id':change['id'],'kind':change['kind'],'key':list(change['key']),'column':change.get('column') or None,
                      'old':detail.get('old'),'new':detail.get('new'),'applied':change['id'] in session.selected})
    return {'original':session.names[0],'comparison':session.names[1],'sheet_original':session.layout['old_sheet'],'sheet_comparison':session.layout['new_sheet'],
            'keys':list(session.keys),'mapping':dict(session.mapping),'counts':counts,'applied':selected,'changes':items,'changes_total':len(changes),'issue':session.issue or ''}


def run(args):
    from desktop.session import Session
    from workspace import effective_selection
    kinds=wanted_kinds(args.apply)
    files=read_files(args.compare)
    if len(files)<2:raise ValueError('--compare에는 원본 파일과 비교 파일이 모두 필요합니다.')
    session=Session(files[0][0],files[1:],files[0][1])
    layout=dict(session.layout)
    for field,value in (('old_sheet',args.sheet_original),('new_sheet',args.sheet_comparison),('old_header',args.header_original),('new_header',args.header_comparison),('old_start',args.start_original),('new_start',args.start_comparison)):
        if value is not None:layout[field]=value
    mapping=dict(session.mapping)
    for item in args.map:
        if '=' not in item:raise ValueError('--map은 원본열=비교열 형식입니다: '+item)
        left,right=[part.strip() for part in item.split('=',1)];mapping[left]=right
    keys=[k.strip() for k in args.keys.split(',') if k.strip()] if args.keys else None
    if layout!=session.layout or args.map or keys:
        session.configure(layout=layout if layout!=session.layout else None,keys=keys,mapping=mapping if args.map else None)
    stages=[];last=len(session.flow['comparison_queue'])-1
    while True:
        if session.issue:raise ValueError(session.issue)
        session.row_mode=args.mode=='row';session.copy_mode='값만 복사' if args.copy=='values' else '일반 복사'
        session.selected={c['id'] for c in session.all_changes() if c['kind'] in kinds}
        session.selected=effective_selection(session.all_changes(),session.selected,session.row_mode);session.prepare_results()
        stages.append(stage_report(session,kinds,args.changes_limit))
        if session.flow['queue_index']>=last:break
        session.next(False)
    output=None
    if args.out:
        out=Path(args.out)
        if out.suffix.lower() not in ('.xlsx','.xlsm'):raise ValueError('결과 파일은 .xlsx 또는 .xlsm이어야 합니다.')
        if out.resolve() in {Path(p).resolve() for p in args.compare}:raise ValueError('입력 파일을 덮어쓸 수 없습니다. 다른 이름으로 저장하세요.')
        out.write_bytes(session.save().data);output=str(out)
    return {'ok':True,'stages':stages,'output':output}


def summary_text(report):
    lines=[]
    for stage in report['stages']:
        c=stage['counts'];a=stage['applied']
        lines.append(f"{stage['original']} ← {stage['comparison']}  키: {', '.join(stage['keys'])}")
        lines.append(f"  추가 {c['추가']}(반영 {a['추가']}) · 수정 {c['수정']}(반영 {a['수정']}) · 삭제 {c['삭제']}(반영 {a['삭제']})")
    lines.append('저장: '+report['output'] if report['output'] else '분석만 했습니다. 저장하려면 --out을 지정하세요.')
    return '\n'.join(lines)


def main(argv=None):
    attach_console()
    try:args=build_parser().parse_args(argv)
    except SystemExit as exc:return int(exc.code or 0)
    try:report=run(args)
    except FileNotFoundError as exc:return fail(exc,3,args)
    except (ValueError,OSError) as exc:return fail(exc,4 if not isinstance(exc,OSError) else 3,args)
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if args.report:Path(args.report).write_text(text,encoding='utf-8')
    print(text if args.json else summary_text(report))
    return 0


def fail(exc,code,args):
    message={'ok':False,'error':str(exc)}
    if args.report:Path(args.report).write_text(json.dumps(message,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(message,ensure_ascii=False) if args.json else '오류: '+str(exc),file=sys.stderr if not args.json else sys.stdout)
    return code


if __name__=='__main__':raise SystemExit(main())
