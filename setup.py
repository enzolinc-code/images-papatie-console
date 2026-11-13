"""Create an isolated local installation. Never calls a paid image API."""
import argparse,json,os,subprocess,sys,venv
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--matting',action='store_true',help='also install optional BiRefNet/PyMatting packages');a=p.parse_args()
    if sys.version_info<(3,10):raise SystemExit('Python 3.10+ is required')
    (ROOT/'data').mkdir(exist_ok=True);os.environ['TMP']=os.environ['TEMP']=str(ROOT/'data')
    env=ROOT/'.venv'
    if not env.exists():venv.EnvBuilder(with_pip=True).create(env)
    python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    requirements='requirements-matting.txt' if a.matting else 'requirements.txt'
    subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/requirements)],check=True)
    cfg=ROOT/'config.json'
    if not cfg.exists():cfg.write_text((ROOT/'config.example.json').read_text('utf-8'),encoding='utf-8')
    subprocess.run([str(python),str(ROOT/'launch.py'),'--check'],check=True)
    print('Installed. Open the desktop launcher, or run .venv Python with launch.py.')
if __name__=='__main__':main()
