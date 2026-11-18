"""接口服务商 async image bridge. One submission; subsequent calls resume the same task."""
from pathlib import Path
import argparse,base64,hashlib,io,json,math,mimetypes,os,time,urllib.request,urllib.error,urllib.parse,uuid
from PIL import Image
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import image_channels

def atomic(path,value):
    tmp=path.with_suffix('.writing');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)
def ratio(size):
    ratios=['1:1','2:3','3:2','3:4','4:3','4:5','5:4','9:16','16:9','21:9','1:4','4:1','1:8','8:1']
    text=size.replace('x',':')
    a,b=map(float,text.split(':'));value=a/b
    return min(ratios,key=lambda r:abs(math.log(value/(float(r.split(':')[0])/float(r.split(':')[1])))))
def payload(args):
    body={'model':args.model,'prompt':Path(args.prompt_file).read_text('utf-8'),'size':ratio(args.size),'resolution':os.environ.get('IMG4_RESOLUTION') or '2K','n':1}
    if args.model.startswith('gpt-image-2.5'):body['version']=os.environ.get('IMG4_VERSION') or 'flare'
    if args.image:
        body['image_urls']=[]
        for name in args.image:
            p=Path(name)
            if p.stat().st_size>20*1024*1024:raise ValueError('参考图过大，请缩小后提交')
            mime=mimetypes.guess_type(p.name)[0] or 'image/png'
            body['image_urls'].append('data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode('ascii'))
    return body

def run(args,opener=None):
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():
        with Image.open(out) as im:im.verify()
        return out
    key=os.environ.get('IMG4_API_KEY','')
    if not key:raise ValueError('通道5未配置本机密钥')
    base=(os.environ.get('IMG4_API_URL') or '').rstrip('/')
    if urllib.parse.urlparse(base).scheme!='https':raise ValueError('通道5接口必须使用HTTPS')
    proxy=os.environ.get('IMG4_PROXY') or ''
    opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({'http':proxy,'https':proxy}))
    body=payload(args);digest=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    receipt=out.parent/'channel5-task.json'
    record=json.loads(receipt.read_text('utf-8')) if receipt.exists() else None
    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','X-Provider-Response-Version':'2026-07-27'}
    if record and record.get('request_hash')!=digest:raise ValueError('此目录已有不同请求记录，保留原任务，禁止重复提交')
    if record and record.get('phase')=='rejected':raise ValueError(record.get('error') or '通道5上次请求已被拒绝，请新建任务，不自动重发')
    if not record:
        record={'phase':'submitting','model':args.model,'request_hash':digest,'idempotency_key':str(uuid.uuid4())};atomic(receipt,record)
        req=urllib.request.Request(base+'/images/generations',data=json.dumps(body,ensure_ascii=False).encode(),headers=dict(headers,**{'Idempotency-Key':record['idempotency_key']}),method='POST')
        try:
            with opener.open(req,timeout=min(args.timeout,180)) as r:submitted=json.load(r)
        except urllib.error.HTTPError as exc:
            if exc.code in (400,401,402,403,404,413,422,429):
                problem=image_channels.http_problem(exc.code,exc.read(10000).decode('utf-8','replace'))
                record.update(phase='rejected',http_status=exc.code,error_category=problem['category'],error=problem['message']);atomic(receipt,record)
                raise ValueError(problem['message']) from None
            record.update(phase='submission_uncertain',http_status=exc.code);atomic(receipt,record)
            raise RuntimeError('通道5提交状态未确认（HTTP '+str(exc.code)+'），请核对远端，不自动重复提交') from None
        except Exception as exc:
            record['phase']='submission_uncertain';atomic(receipt,record)
            raise RuntimeError('通道5提交状态未确认；已保存提交记录，请先核对远端，不自动重复提交') from exc
        data=submitted.get('data')
        task=str((data[0] or {}).get('task_id','')) if isinstance(data,list) and data else str(data.get('id') or data.get('task_id') or '') if isinstance(data,dict) else ''
        if not task:raise RuntimeError('通道5未返回任务编号，请核对远端记录，不重复提交')
        record.update(phase='submitted',task_id=task);atomic(receipt,record)
    if not record.get('task_id'):raise RuntimeError('上次提交状态未确认，请先核对远端记录，不重复提交')
    deadline=time.monotonic()+args.timeout;result=None
    while time.monotonic()<deadline:
        req=urllib.request.Request(base+'/tasks/'+urllib.parse.quote(record['task_id'],safe='')+'?language=zh',headers=headers)
        with opener.open(req,timeout=min(args.timeout,60)) as r:data=json.load(r).get('data',{})
        status=str(data.get('status','')).lower()
        if status in ('completed','succeeded','success'):result=data.get('result') or {};break
        if status in ('failed','error','cancelled','canceled'):
            record['phase']='failed';atomic(receipt,record);raise RuntimeError('通道5远端任务失败，请在远端核对原因与费用')
        time.sleep(3)
    if result is None:raise TimeoutError('通道5等待超时，任务编号已保存；可继续查询，不会重复提交')
    urls=[]
    for item in result.get('images',[]):
        value=item.get('url') if isinstance(item,dict) else item
        if isinstance(value,list):urls.extend(value)
        elif value:urls.append(value)
    if not urls:raise RuntimeError('通道5任务已完成，但未返回成图地址')
    url=str(urls[0])
    if urllib.parse.urlparse(url).scheme not in ('https','http'):raise ValueError('成图地址无效')
    # Download does not carry the API authorization header.
    with opener.open(url,timeout=min(args.timeout,120)) as r:raw=r.read(50*1024*1024+1)
    if len(raw)>50*1024*1024:raise ValueError('成图过大，请核对远端结果')
    tmp=out.with_suffix('.downloading')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height>40_000_000:raise ValueError('成图像素过大')
            im.load();im.convert('RGBA' if im.mode=='RGBA' else 'RGB').save(tmp,format='PNG')
        os.replace(tmp,out)
    finally:
        if tmp.exists():tmp.unlink()
    record['phase']='downloaded';atomic(receipt,record)
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--prompt-file',required=True);p.add_argument('--out',required=True);p.add_argument('--size',default='1:1');p.add_argument('--model',required=True);p.add_argument('--image',action='append',default=[]);p.add_argument('--timeout',type=int,default=600)
    args=p.parse_args()
    try:run(args);print('通道5成图已保存')
    except Exception as exc:
        # Never include HTTP response bodies, credentials, or signed download URLs.
        print('通道5：'+(str(exc) if not isinstance(exc,(urllib.error.URLError,urllib.error.HTTPError)) else '网络或接口请求失败；请核对已保存的远端任务编号'));raise SystemExit(1)
if __name__=='__main__':main()
