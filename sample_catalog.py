"""User-facing sample numbers; legacy fixture identifiers remain stable for regressions."""
from pathlib import Path
import sys
from samples import sample_files,sample_collection

CATALOG={str(i):{'legacy':legacy,'label':f'{i}. {label}'} for i,legacy,label in [
 (1,'1','신규 자료만 추가'),(2,'2','전체 목록 변경 비교'),(3,'4','복합 기준 키'),(4,'5','서로 다른 열 이름·양식'),
 (5,'12','대용량 1만 행'),(6,'13','SUM 수식 복사'),(7,'14','다른 시트 참조 수식'),(8,'15','부서별 신규 예산 취합'),(9,'16','설비대장 배포 후 10명 회신 취합'),(10,'17','병합된 비품 대장(대분류·소계·결재란)')]}

def load_sample(number):
    legacy=CATALOG[str(number)]['legacy']
    if legacy=='16':
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'sample_data'/'collaboration'
        old=next(root.glob('00_*.xlsx'));incoming=sorted(p for p in root.glob('*.xlsx') if p!=old)
        return old.read_bytes(),[(p.read_bytes(),p.name) for p in incoming],old.name
    if legacy=='15':
        old,incoming=sample_collection();return old,incoming,'부서별 예산대장.xlsx'
    old,new=sample_files(legacy);return old,[(new,'비교.xlsx')],'원본.xlsx'
