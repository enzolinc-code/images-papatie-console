"""Xingqi media adapter: JSON params for Banana, one POST with resumable polling."""
from pathlib import Path
import argparse,base64,hashlib,io,json,math,mimetypes,os,sys,time,urllib.request,urllib.error,urllib.parse,uuid
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import image_channels

def atomic(path,obj):
    tmp=path.with_suffix('.writing');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)
def ratio(value):
    a,b=map(float,value.replace('x',':').split(':'));r=a/b
    choices=['1:1','2:3','3:2','3:4','4:3','4:5','5:4','9:16','16:9','21:9']
    return min(choices,key=lambda s:abs(math.log(r/(float(s.split(':')[0])/float(s.split(':')[1])))))
def payload(args):
    resolution=os.environ.get('CHANNEL4_RESOLUTION') or '4K'
    if resolution not in ('1K','2K','4K'):raise ValueError('通道4分辨率需为1K、2K或4K')
    params={'aspectRatio':ratio(args.size),'imageSize':resolution}
    if len(args.image)>14:raise ValueError('通道4 Banana最多支持14张参考图')
    if args.image:
        params['images']=[]
        for name in args.image:
            p=Path(name)
            if p.stat().st_size>20*1024*1024:raise ValueError('参考图过大')
            params['images'].append('data:'+(mimetypes.guess_type(p.name)[0] or 'image/png')+';base64,'+base64.b64encode(p.read_bytes()).decode('ascii'))
    return {'model':args.model,'prompt':Path(args.prompt_file).read_text('utf-8'),'params':params}
def unwrap(value):return value.get('data') if isinstance(value,dict) and isinstance(value.get('data'),dict) else value

def result_url(value):
    if not isinstance(value,dict):return ''
    candidates=[value.get('result_url'),value.get('resultUrl'),value.get('url'),value.get('result')]
    data=value.get('data')
    if isinstance(data,list) and data:candidates.append(data[0])
    if isinstance(data,dict):candidates.append(data)
    if isinstance(value.get('images'),list) and value['images']:candidates.append(value['images'][0])
    for item in candidates:
        if isinstance(item,str) and urllib.parse.urlparse(item).scheme in ('https','http'):return item
        if isinstance(item,list):
            for s in item:
                if isinstance(s,str) and urllib.parse.urlparse(s).scheme in ('https','http'):return s
        if isinstance(item,dict):
            hit=result_url(item)
            if hit:return hit
    return ''
def problem(code,raw=''):
    text=str(raw).lower()
    if ('余额不足' in text or 'insufficient balance' in text):return '通道4余额或额度不足，请在接口服务商核实账户后再提交。'
    return image_channels.http_problem(code,raw)['message'].replace('通道5','通道4').replace('接口服务商','接口服务商')

def run(args,opener=None):
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():
        with Image.open(out) as im:im.verify()
        return out
    key=os.environ.get('CHANNEL4_API_KEY') or os.environ.get('CODEX_API_KEY','')
    if not key:raise ValueError('通道4未配置密钥')
    base=(os.environ.get('CHANNEL4_API_URL') or os.environ.get('CODEX_API_URL') or '').rstrip('/')
    if base.endswith('/v1'):base=base[:-3]
    if urllib.parse.urlparse(base).scheme!='https':raise ValueError('通道4接口需使用HTTPS')
    proxy=os.environ.get('CHANNEL4_PROXY','');opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({'http':proxy,'https':proxy} if proxy else {}))
    body=payload(args);digest=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    receipt=out.parent/('channel4-task.json' if out.name=='raw.png' else out.stem+'-channel4-task.json')
    record=json.loads(receipt.read_text('utf-8')) if receipt.exists() else None
    if record and record.get('request_hash')!=digest:raise ValueError('目录已有不同请求记录，不重复提交')
    if record and record.get('phase')=='rejected':raise ValueError(record.get('error') or '通道4原请求已被拒绝')
    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
    if not record:
        record={'phase':'submitting','request_hash':digest,'model':args.model,'idempotency_key':str(uuid.uuid4())};atomic(receipt,record)
        req=urllib.request.Request(base+'/v1/media/generate',data=json.dumps(body,ensure_ascii=False).encode(),headers=dict(headers,**{'Idempotency-Key':record['idempotency_key']}),method='POST')
        try:
            with opener.open(req,timeout=min(args.timeout,180)) as r:submitted=json.load(r)
        except urllib.error.HTTPError as exc:
            if exc.code in (400,401,402,403,404,413,422,429):
                message=problem(exc.code,exc.read(10000).decode('utf-8','replace'));record.update(phase='rejected',http_status=exc.code,error=message);atomic(receipt,record);raise ValueError(message) from None
            record.update(phase='submission_uncertain',http_status=exc.code);atomic(receipt,record);raise RuntimeError('通道4提交状态未确认，请核对远端任务，不重复提交') from None
        except Exception:
            record['phase']='submission_uncertain';atomic(receipt,record);raise RuntimeError('通道4提交状态未确认，请核对远端，不重复提交') from None
        data=unwrap(submitted);url=result_url(submitted)
        task=data.get('task_id') if isinstance(data,dict) else None
        if task:record.update(phase='submitted',task_id=str(task))
        elif url:record.update(phase='completed',result_url=url)
        else:raise RuntimeError('通道4未返回任务编号或成图，请核对远端，不重复提交')
        atomic(receipt,record)
    if not record.get('task_id') and not record.get('result_url'):raise RuntimeError('上次通道4提交状态未确认，不重复提交')
    deadline=time.monotonic()+args.timeout;url=record.get('result_url','')
    while not url and time.monotonic()<deadline:
        req=urllib.request.Request(base+'/v1/skills/task-status?task_id='+urllib.parse.quote(record['task_id'],safe=''),headers=headers)
        with opener.open(req,timeout=min(args.timeout,60)) as r:data=unwrap(json.load(r))
        state=str(data.get('state','')).lower()
        if data.get('is_final') is True or data.get('isFinal') is True:
            if state in ('success','succeeded','completed'):
                url=result_url(data)
                if not url:raise RuntimeError('通道4已完成但无成图地址，请核对远端任务')
                break
            record['phase']='failed';atomic(receipt,record);raise ValueError('通道4远端生成失败，请核对任务记录与费用')
        time.sleep(3)
    if not url:raise TimeoutError('通道4等待超时，任务编号已保留，只继续查询，不重复提交')
    # No Authorization header is sent to the result CDN.
    with opener.open(url,timeout=min(args.timeout,120)) as r:raw=r.read(50*1024*1024+1)
    if len(raw)>50*1024*1024:raise ValueError('成图过大')
    tmp=out.with_suffix('.downloading')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height>40_000_000:raise ValueError('成图像素过大')
            im.load();im.convert('RGBA' if im.mode=='RGBA' else 'RGB').save(tmp,format='PNG')
        os.replace(tmp,out)
    finally:
        if tmp.exists():tmp.unlink()
    record['phase']='downloaded';record.pop('result_url',None);atomic(receipt,record);return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--prompt-file',required=True);p.add_argument('--out',required=True);p.add_argument('--size',default='1:1');p.add_argument('--model',required=True);p.add_argument('--timeout',type=int,default=600);p.add_argument('--image',action='append',default=[]);args=p.parse_args()
    try:run(args);print('通道4成图已保存')
    except Exception as exc:
        print('通道4：'+(str(exc) if not isinstance(exc,(urllib.error.URLError,urllib.error.HTTPError)) else '网络或接口查询失败，请核对已保存的任务编号'));raise SystemExit(1)
if __name__=='__main__':main()
