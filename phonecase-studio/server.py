from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit,unquote,quote
import argparse,datetime,hashlib,json,mimetypes,os,re,secrets,subprocess,sys,threading,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import case_core as core
import image_channels as channels
ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/'config.json').read_text('utf-8-sig'))
PORT=int(CFG.get('port',8799));TOKEN=secrets.token_urlsafe(32);LOCK=threading.RLock();POOL=ThreadPoolExecutor(max_workers=1)
JOBS=ROOT/'data/jobs';OUTPUT=ROOT/'成品';JOBS.mkdir(parents=True,exist_ok=True);OUTPUT.mkdir(exist_ok=True)
APP='multi-template-phonecase-studio';MAX_BODY=120*1024*1024

def atomic(p,obj):
    temp=p.with_suffix('.writing');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,p)
def load_job(i):
    if not re.fullmatch('[a-f0-9]{32}',i):raise ValueError('任务不存在')
    p=JOBS/i/'job.json'
    if not p.exists():raise ValueError('任务不存在')
    return json.loads(p.read_text('utf-8'))
def update(i,**kw):
    with LOCK:
        j=load_job(i);j.update(kw);j['updated']=datetime.datetime.now().isoformat(timespec='seconds');atomic(JOBS/i/'job.json',j);return j

def configuration():return json.loads((ROOT/'config.json').read_text('utf-8-sig'))
def channel_state():
    cfg=configuration();result=[]
    for i in ('3','4','5'):
        try:m=channels.model(i,cfg);ep=channels.endpoint(i,cfg);configured=bool(channels.key(i) and ep);error=''
        except ValueError:m='配置不可用';configured=False;error='本机模型配置读取失败，请检查通道切换器'
        result.append({'id':i,'model':m,'configured':configured,'error':error})
    return result

def public(j):
    out={k:v for k,v in j.items() if k not in ('request_hash','request_id','endpoint','transform')}
    i=j['id'];out['assets']={k:f'/media/{i}/{k}.png' for k in ('source','template','frame','mask')}
    if j['status']=='done':out['results']={k:f'/media/{i}/{k}.png' for k in ('full','print','preview')}
    out['transform']=j.get('transform',{})
    return out

def child_environment(channel,cfg,endpoint):
    env=dict(os.environ)
    for k in list(env):
        if k.endswith('_API_KEY') or k in ('CODEX_API_URL','IMG4_API_URL','CHANNEL4_API_URL'):env.pop(k,None)
    key=channels.key(channel)
    if channel in ('3','4'):
        env['CODEX_API_KEY']=key;env['CODEX_API_URL']=endpoint
    if channel=='4':env['CHANNEL4_API_KEY']=key;env['CHANNEL4_API_URL']=endpoint
    if channel=='5':env['IMG4_API_KEY']=key;env['IMG4_API_URL']=endpoint
    for k in {'3':(), '4':('CHANNEL4_PROXY','CHANNEL4_RESOLUTION'),'5':('IMG4_PROXY','IMG4_RESOLUTION','IMG4_VERSION')}[channel]:
        v=channels.user_env(k)
        if v:env[k]=v
    temp=JOBS/'_runtime';temp.mkdir(exist_ok=True)
    env.update(TEMP=str(temp),TMP=str(temp),PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
    return env

def command(j,folder,cfg):
    i=j['channel'];size='x'.join(map(str,j['gen_size']));raw=folder/'raw.png';prompt=folder/'prompt.txt';refs=[folder/'guide.png',folder/'source-ref.png']
    if i=='3':
        import math
        w,h=j['gen_size'];factor=min(3840/max(w,h),math.sqrt(8294400/(w*h)))
        size=f"{max(16,int(w*factor/16)*16)}x{max(16,int(h*factor/16)*16)}"

    if i=='4' and j['model'].startswith('banana'):
        cmd=[sys.executable,'-B',str(ROOT/'tools/xingqi_bridge.py'),'--out',str(raw),'--prompt-file',str(prompt),'--size',size,'--model',j['model'],'--timeout',str(cfg['timeout'])]
    elif i=='5':
        cmd=[sys.executable,'-B',str(ROOT/'tools/apimart_bridge.py'),'--out',str(raw),'--prompt-file',str(prompt),'--size',size,'--model',j['model'],'--timeout',str(cfg['timeout'])]
    else:
        exe=ROOT/'tools/codex-image2-windows-amd64.exe'
        if not exe.is_file():raise ValueError('缺少本机生图程序，请检查工作台tools目录')
        cmd=[str(exe),'edit','--out',str(raw),'--prompt-file',str(prompt),'--size',size,'--model',j['model'],'--timeout',str(cfg['timeout']),'--max-attempts','1','--n','1']
        if j['preserve']:cmd+=['--mask',str(folder/'edit-mask.png')]
    for ref in refs:cmd+=['--image',str(ref)]
    return cmd

def execute(i):
    folder=JOBS/i
    try:
        j=load_job(i);cfg=configuration()
        if j['local']:
            update(i,status='compositing',message='素材已完整覆盖壳面，直接保真导出；本次0次生图')
            raw=None
        else:
            if not channels.key(j['channel']):raise ValueError('所选通道尚未配置本机密钥，请先在本机配置后再使用')
            if j['channel']=='5':channels.preflight('5',dict(cfg,channel5_endpoint=j['endpoint']))
            update(i,status='generating',message='已提交通道'+j['channel']+'，正在等待成图；不要重复点击',submitted=True)
            env=child_environment(j['channel'],cfg,j['endpoint']);cmd=command(j,folder,cfg)
            try:
                r=subprocess.run(cmd,capture_output=True,encoding='utf-8',errors='replace',env=env,timeout=int(cfg['timeout'])+60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            except subprocess.TimeoutExpired:raise RuntimeError('生成等待超时，原任务已保留。请核对远端任务与费用，不自动重新提交') from None
            log=r.stdout+'\n'+r.stderr
            # Logs never retain secrets or signed URLs.
            for k in ('3','4','5'):
                secret=channels.key(k)
                if secret:log=log.replace(secret,'[redacted]')
            log=re.sub(r'https?://[^\s"<>]+','[URL]',log)
            (folder/'process.log').write_text(log,encoding='utf-8')
            raw=folder/'raw.png'
            if r.returncode or not raw.is_file():
                receipt=folder/('channel'+j['channel']+'-task.json')
                if receipt.exists():
                    record=json.loads(receipt.read_text('utf-8'))
                    if record.get('phase')=='rejected':raise ValueError(record.get('error') or '所选通道拒绝请求，请检查账号与模型')
                raise RuntimeError('所选通道未取得成图，请检查任务日志及远端费用；本工作台不自动重发、不切换通道')
            update(i,status='compositing',message='正在恢复原图区域并按刀模导出三件套')
        files=core.finish(folder,OUTPUT/i,j,raw)
        update(i,status='done',message='已完成。请检查主体、凹口和补图接缝后送厂。' if raw else '已完成保真导出，本次未调用生图。',files=files,output_dir=str(OUTPUT/i),calls=0 if raw is None else 1)
    except ValueError as e:update(i,status='failed',message=str(e)[:400])
    except Exception:update(i,status='uncertain' if load_job(i).get('submitted') else 'failed',message='生成未完成，原图及任务记录已保留；请检查任务日志与远端任务，不自动重复提交。')

def create_job(body):
    channel=str(body.get('channel',''))
    if channel not in ('3','4','5'):raise ValueError('请选择通道3、4或5')
    rid=body.get('request_id','')
    if not re.fullmatch('[a-f0-9-]{32,36}',str(rid)):raise ValueError('请求标识无效，请刷新后重试')
    digest=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    with LOCK:
        for p in JOBS.glob('*/job.json'):
            j=json.loads(p.read_text('utf-8'))
            if j.get('request_id')==rid:
                if j.get('request_hash')!=digest:raise ValueError('同一请求内容已变化，请重新点击生成')
                return public(j)
            if j['status'] in ('queued','generating','compositing'):raise ValueError('已有任务正在生成，请等待完成，避免重复付费')
        i=secrets.token_hex(16);folder=JOBS/i;folder.mkdir()
        try:
            meta=core.prepare(body,folder);cfg=configuration();model=channels.model(channel,cfg);endpoint=channels.endpoint(channel,cfg)
            if not meta['local'] and not channels.key(channel):raise ValueError('所选通道未配置本机密钥；排版下载仍可使用')
            now=datetime.datetime.now().isoformat(timespec='seconds')
            j=dict(meta,id=i,status='queued',message='任务已保存，准备处理',channel=channel,model=model,endpoint=endpoint,created=now,updated=now,request_id=rid,request_hash=digest,calls=0)
            atomic(folder/'job.json',j)
        except Exception:
            # Inputs are retained for diagnosis, never start a paid request if validation failed.
            atomic(folder/'validation.json',{'status':'failed','message':'输入校验未通过，未提交生图'})
            raise
        POOL.submit(execute,i)
        return public(j)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def host_ok(self):return self.headers.get('Host') in (f'127.0.0.1:{PORT}',f'localhost:{PORT}')
    def send(self,status,obj,mime='application/json; charset=utf-8',filename=None):
        raw=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        if filename:self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(filename))
        self.end_headers()
        try:self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):
        if not self.host_ok():return self.send(403,{'error':'仅允许本机访问'})
        path=unquote(urlsplit(self.path).path)
        try:
            if path=='/api/state':return self.send(200,{'app':APP,'root':str(ROOT),'token':TOKEN,'channels':channel_state()})
            if path.startswith('/api/request/'):
                rid=path.split('/')[-1]
                if not re.fullmatch('[a-f0-9-]{32,36}',rid):raise ValueError('任务不存在')
                for f in JOBS.glob('*/job.json'):
                    j=json.loads(f.read_text('utf-8'))
                    if j.get('request_id')==rid:return self.send(200,public(j))
                raise ValueError('任务不存在')
            if path.startswith('/api/jobs/'):
                return self.send(200,public(load_job(path.split('/')[-1])))
            static={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/示例刀模.png':'示例刀模.png','/示例素材.png':'示例素材.png'}
            if path in static:
                p=ROOT/'web'/static[path];return self.send(200,p.read_bytes(),mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
            m=re.fullmatch(r'/media/([a-f0-9]{32})/(source|template|frame|mask|full|print|preview)\.png',path)
            if m:
                i,kind=m.groups();j=load_job(i);filename=None
                if kind in ('full','print','preview'):
                    if j['status']!='done':raise ValueError('成品尚未生成')
                    filename=j['files'][{'full':0,'print':1,'preview':2}[kind]];p=OUTPUT/i/filename
                else:p=JOBS/i/(kind+'.png')
                if kind=='mask':
                    alpha=core.Image.open(p).convert('L');rgba=core.Image.new('RGBA',alpha.size,'white');rgba.putalpha(alpha)
                    import io
                    buf=io.BytesIO();rgba.save(buf,format='PNG');return self.send(200,buf.getvalue(),'image/png')
                return self.send(200,p.read_bytes(),'image/png',filename if 'download=1' in self.path else None)
            return self.send(404,{'error':'页面或文件不存在'})
        except (ValueError,FileNotFoundError):return self.send(404,{'error':'任务或文件不存在'})
        except Exception:return self.send(500,{'error':'本机文件读取失败，请检查工作台目录权限'})
    def do_POST(self):
        origin=self.headers.get('Origin','')
        if not self.host_ok() or origin not in (f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}') or not secrets.compare_digest(self.headers.get('X-Local-Token',''),TOKEN):return self.send(403,{'error':'请从本机工作台页面操作'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=MAX_BODY:raise ValueError('上传内容过大，请缩小素材后再试')
            body=json.loads(self.rfile.read(n))
            if not isinstance(body,dict):raise ValueError('请求格式不正确')
            if self.path=='/api/mask':
                im=core.decode_image(body.get('image'));mask=core.template_mask(im)
                rgba=core.Image.new('RGBA',mask.size,'white');rgba.putalpha(mask)
                return self.send(200,{'mask':core.as_data(rgba),'size':list(mask.size)})
            if self.path=='/api/jobs':return self.send(200,create_job(body))
            self.send(404,{'error':'接口不存在'})
        except (ValueError,TypeError,KeyError) as e:self.send(400,{'error':str(e)[:300]})
        except Exception:self.send(500,{'error':'本机处理失败，请检查工作台目录权限；不会自动提交生图'})

if __name__=='__main__':
    for p in JOBS.glob('*/job.json'):
        j=json.loads(p.read_text('utf-8'))
        if j['status'] in ('queued','generating','compositing'):update(j['id'],status='interrupted',message='服务已重新启动，任务未自动重发；请先核对远端成图与费用')
    ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()