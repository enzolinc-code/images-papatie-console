"""Check the publishable source set. Prints paths/counts, never secret contents."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.venv','data','qa','runs','runtime','__pycache__','.pytest_cache'}

def publishable(root=ROOT):
    for p in sorted(root.rglob('*')):
        if not p.is_file() or any(part in EXCLUDED for part in p.relative_to(root).parts):continue
        if p.name=='config.json' or (p.name.startswith('.env') and p.name!='.env.example') or p.suffix.lower() in {'.zip','.pyc','.log'}:continue
        yield p

def check(root=ROOT):
    files=list(publishable(root));problems=[]
    for p in files:
        rel=p.relative_to(root).as_posix()
        if p.suffix.lower() in {'.onnx','.exe','.dll','.pyd'}:problems.append(rel+': binary/model must not be published')
        if p.suffix.lower() in {'.py','.js','.json','.md','.txt','.yaml','.yml','.vbs','.cmd','.html','.css','.example',''}:
            content=p.read_text('utf-8')
            if re.search(r'(?:sk|sess)-[A-Za-z0-9_-]{24,}',content):problems.append(rel+': possible secret')
            if re.search(r'[CD]:[/\\](?:Users|AutoTaobao|o1key_windows_portable)',content,re.I):problems.append(rel+': machine-specific path')
    expected={'chin','both','edge','heart','wave','cross','lean','pillow'}
    if {p.stem for p in (root/'web/pose-art').glob('*.png')}!=expected:problems.append('Expected eight pose PNGs')
    for name in ['README.md','launch.py','setup.py','config.example.json','.env.example','LICENSE','THIRD_PARTY.md','skills/papapai-studio/SKILL.md']:
        if not (root/name).is_file():problems.append('Missing '+name)
    if problems:
        print('\n'.join(problems));return 1
    print(json.dumps({'status':'passed','publishable_files':len(files),'pose_images':8,'excluded_runtime_directories':sorted(EXCLUDED)},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(check())
