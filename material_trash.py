"""Recoverable material deletion; source bytes and historical references are retained."""
import json,time
from pathlib import Path

def read(data):
 p=Path(data)/'material-trash.json';return json.loads(p.read_text('utf-8')) if p.exists() else {}
def change(data,assets,jobs,ids,action):
 if action not in ('delete','restore'):raise ValueError('操作无效')
 if not isinstance(ids,list) or not 1<=len(ids)<=200 or len(set(ids))!=len(ids):raise ValueError('请选择1至200张不重复素材')
 for aid in ids:
  a=assets.get(aid)
  if not a or not a.get('transparent') or a.get('kind') in ('scene','result_scene'):raise ValueError('只可管理透明素材')
 if action=='delete':
  used=set()
  for j in jobs.values():
   if j.get('status') in ('queued','running'):
    for t in j.get('tasks',[])+j.get('sample_remaining',[]):
     used.update(t.get('refs',[]))
     if t.get('identity_asset'):used.add(t['identity_asset'])
  if used.intersection(ids):raise ValueError('所选素材正在生成任务中使用，请等任务结束后再删除')
 marks=read(data)
 for aid in ids:
  if action=='delete':marks[aid]={'deleted_at':time.time()}
  else:marks.pop(aid,None)
 p=Path(data)/'material-trash.json';tmp=p.with_suffix('.writing');tmp.write_text(json.dumps(marks,ensure_ascii=False,indent=2),'utf-8');tmp.replace(p)
 return {'count':len(ids),'action':action}