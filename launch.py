"""Local-only launcher; supports GUI launch with pythonw on Windows."""
import argparse,json,os,sys,threading,traceback,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))

def load_env():
    file=ROOT/'.env'
    if file.exists():
        for line in file.read_text('utf-8-sig').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line:continue
            key,value=line.split('=',1)
            if key.strip() in ('CODEX_API_KEY','CHANNEL4_API_KEY'):os.environ.setdefault(key.strip(),value.strip().strip('"\''))

def main():
    p=argparse.ArgumentParser();p.add_argument('--no-browser',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args()
    load_env();(ROOT/'data').mkdir(exist_ok=True)
    import server
    if a.check:print(json.dumps(server.health(),ensure_ascii=False,indent=2));return
    url='http://127.0.0.1:'+str(server.CFG['port'])
    if not a.no_browser:threading.Timer(1.5,lambda:webbrowser.open(url)).start()
    server.main()
if __name__=='__main__':
    try:main()
    except Exception:
        (ROOT/'data').mkdir(exist_ok=True);(ROOT/'data/start-error.log').write_text(traceback.format_exc(),encoding='utf-8');raise
