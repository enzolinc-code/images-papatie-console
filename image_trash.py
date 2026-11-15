"""One recoverable image state shared by all galleries, downloads and exports."""
import json,time,hashlib
from pathlib import Path

def read(data):
 p=Path(data)/'material-trash.json';return json.loads(p.read_text('utf-8')) if p.exists() else {}
def write(p,value):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.writing');t.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf-8');t.replace(p)
def active_ids(jobs):
 used=set()
 for j in jobs.values():
  for t in j.get('tasks',[])+j.get('sample_remaining',[]):
   used.update(t.get('refs',[]))
   for k in ['identity_asset','correction_product','original_scene']:
    if t.get(k):used.add(t[k])
 return used

def reconcile(root,data,assets,jobs):
 root=Path(root).resolve();data=Path(data);trash=read(data);ledger= data/'trash-exports/ledger.json';records=json.loads(ledger.read_text('utf-8')) if ledger.exists() else {}
 candidates=[]
 for j in jobs.values():
  for t in j.get('tasks',[]):
   if t.get('asset') and t.get('output_file'):candidates.append((t['asset'],Path(t['output_file'])))
 for manifest in (root/'成品/分发批次').glob('*/image-manifest.json'):
  for item in json.loads(manifest.read_text('utf-8')).get('images',[]):candidates.append((item['asset'],manifest.parent/item['file']))
 for aid,path in candidates:
  path=path.resolve()
  if not path.is_relative_to((root/'成品').resolve()):continue
  key=hashlib.sha256(str(path).encode()).hexdigest();backup=data/'trash-exports'/aid/(key+path.suffix)
  if aid in trash and path.is_file():
   backup.parent.mkdir(parents=True,exist_ok=True)
   if not backup.exists():path.replace(backup)
   else:path.unlink()
   records[key]={'asset':aid,'original':str(path),'backup':str(backup)}
 for key,item in list(records.items()):
  if item['asset'] in trash:continue
  src=Path(item['backup']).resolve();dst=Path(item['original']).resolve()
  if src.is_relative_to((data/'trash-exports').resolve()) and dst.is_relative_to((root/'成品').resolve()) and src.exists():
   if not dst.exists():dst.parent.mkdir(parents=True,exist_ok=True);src.replace(dst)
   records.pop(key,None)
 write(ledger,records)

def change(root,data,assets,jobs,ids,action):
 if action not in ('delete','restore','purge'):raise ValueError('删除操作无效')
 if not isinstance(ids,list) or not 1<=len(ids)<=200 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise ValueError('请选择1至200张不同图片')
 if any(i not in assets for i in ids):raise ValueError('图片记录不存在')
 trash=read(data)
 if action=='purge':
  if len(ids)!=1:raise ValueError('彻底删除请逐张确认')
  aid=ids[0]
  if aid not in trash:raise ValueError('请先移到回收站')
  if aid in active_ids(jobs):raise ValueError('仍有任务引用这张图片，可保留在回收站，暂不能彻底删除')
  template=Path(data)/'fidelity/templates.json'
  if template.exists() and '"'+aid+'"' in template.read_text('utf-8'):raise ValueError('仍有场景模板引用，暂不能彻底删除')
  p=(Path(data)/assets[aid]['file']).resolve()
  if not p.is_relative_to((Path(data)/'assets').resolve()):raise ValueError('图片路径不在内部素材目录')
  if p.exists():p.unlink()
  for j in jobs.values():
   for i,t in enumerate(j.get('tasks',[]),1):
    if t.get('asset')==aid:
     folder=Path(data)/'jobs'/j['id']/str(i)
     for name in ['raw.png','result.png','result.jpg','matting.png']:
      f=(folder/name).resolve()
      if f.is_relative_to((Path(data)/'jobs').resolve()) and f.is_file():f.unlink()
  ledger=Path(data)/'trash-exports/ledger.json'
  records=json.loads(ledger.read_text('utf-8')) if ledger.exists() else {}
  for key,item in list(records.items()):
   if item['asset']==aid:
    f=Path(item['backup']).resolve()
    if f.is_relative_to((Path(data)/'trash-exports').resolve()) and f.is_file():f.unlink()
    records.pop(key,None)
  write(ledger,records)
  trash[aid]['purged']=True;trash[aid]['purged_at']=time.time()
 else:
  for aid in ids:
   if action=='delete':trash.setdefault(aid,{'deleted_at':time.time()})
   elif trash.get(aid,{}).get('purged'):raise ValueError('图片已经彻底删除，无法恢复')
   else:trash.pop(aid,None)
 write(Path(data)/'material-trash.json',trash);reconcile(root,data,assets,jobs)
 return {'count':len(ids),'action':action}