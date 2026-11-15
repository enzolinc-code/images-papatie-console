"""Scene image output folders and explicit distribution handoff; no publishing."""
import json,re,time,secrets
import image_trash
from pathlib import Path
from datetime import datetime
from PIL import Image

def sync_job(root,job,asset_path,data=None):
    data=Path(data) if data is not None else Path(root)/'data';trash=image_trash.read(data)
    image_trash.reconcile(root,data,{}, {job['id']:job})
    items=[(i,t) for i,t in enumerate(job.get("tasks",[]),1) if t.get("kind") in ("scene","fidelity") and t.get("status")=="done" and t.get("asset") not in trash]
    if not items:return None
    jid=job["id"]
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}",jid):raise ValueError("任务标识无效")
    folder=Path(root)/"成品"/datetime.fromtimestamp(job["created"]).strftime("%Y-%m-%d")/jid
    folder.mkdir(parents=True,exist_ok=True)
    for i,t in items:
        forbidden=set('<>:'+chr(34)+chr(47)+chr(92)+'|?*')
        name="".join("_" if ord(c)<32 or c in forbidden else c for c in str(t["name"]))
        name=Path(name).stem[:60].strip('. ') or '场景'
        target=folder/(f"{i:03d}-"+name+".jpg")
        previous=Path(t.get('output_file',str(target)))
        if not target.is_file() or t.get("export_asset")!=t["asset"]:
            temp=target.with_suffix('.writing')
            with Image.open(asset_path(t["asset"])) as im:im.convert('RGB').save(temp,format='JPEG',quality=95,subsampling=0)
            temp.replace(target)
        if previous!=target and previous.parent.resolve()==folder.resolve() and previous.is_file():previous.unlink()
        t['output_file']=str(target);t['export_asset']=t['asset']
    job['output_dir']=str(folder);job.pop('output_error',None)
    return folder

def handoff(root,job,asset_path,data=None):
    data=Path(data) if data is not None else Path(root)/"data"
    sync_job(root,job,asset_path,data)
    items=[t for t in job.get('tasks',[]) if t.get('kind') in ('scene','fidelity') and t.get('status')=='done' and t.get('review')!='rejected' and t.get('asset') not in image_trash.read(data)]
    if not items:raise ValueError('没有可分发的图片，已排除需要修正的图片')
    folder=Path(root)/'成品'/'分发批次'/(job['id']+'-'+datetime.now().strftime('%H%M%S')+'-'+secrets.token_hex(3));folder.mkdir(parents=True)
    manifest=[]
    for t in items:
        src=Path(t['output_file']);(folder/src.name).write_bytes(src.read_bytes())
        manifest.append({'asset':t['asset'],'file':src.name})
    image_trash.write(folder/'image-manifest.json',{'images':manifest})
    return {'folder':str(folder),'count':len(items),'pending_review':sum(t.get('review','pending')!='accepted' for t in items)}
