"""Small OpenAI-compatible Images client. No retries or channel fallback."""
import argparse,base64,json,mimetypes,os,sys,uuid
from pathlib import Path
from urllib import request,error,parse

RATIOS={"1:1":"1024x1024","3:4":"768x1024","4:3":"1024x768","2:3":"1024x1536","3:2":"1536x1024","9:16":"864x1536","16:9":"1536x864"}

def endpoint(base,edit):
    base=base.rstrip('/')
    if not base.endswith('/v1'):base+='/v1'
    return base+('/images/edits' if edit else '/images/generations')

def multipart(fields,images):
    boundary='papapai-'+uuid.uuid4().hex;parts=[]
    for key,value in fields.items():
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode())
    for p in images:
        p=Path(p);mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
        name='image' if len(images)==1 else 'image[]'
        # Only an ASCII filename goes into the MIME header. File content is unchanged.
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="reference{p.suffix.lower()}"\r\nContent-Type: {mime}\r\n\r\n').encode()+p.read_bytes()+b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode());return b''.join(parts),'multipart/form-data; boundary='+boundary

def generate(base,key,prompt,images,out,model='gpt-image-2',size='1024x1024',quality='auto',timeout=600):
    if not key:raise ValueError('Selected channel API key is not configured')
    fields={'model':model,'prompt':prompt,'size':RATIOS.get(size,size),'n':1,'quality':quality}
    if images:body,content_type=multipart(fields,images)
    else:body=json.dumps(fields).encode();content_type='application/json'
    req=request.Request(endpoint(base,bool(images)),data=body,headers={'Authorization':'Bearer '+key,'Content-Type':content_type},method='POST')
    try:
        with request.urlopen(req,timeout=timeout) as response:result=json.load(response)
    except error.HTTPError as exc:
        message=exc.read(1200).decode('utf-8','replace').replace(key,'[redacted]')
        exc.close()
        raise RuntimeError(f'HTTP {exc.code}: {message}; request was not retried') from None
    item=result['data'][0]
    if item.get('b64_json'):raw=base64.b64decode(item['b64_json'],validate=True)
    elif item.get('url'):
        url=item['url']
        if parse.urlparse(url).scheme!='https':raise ValueError('Image download must use HTTPS')
        # Never forward the API Authorization header to the returned download host.
        with request.urlopen(url,timeout=timeout) as response:raw=response.read(60_000_001)
        if len(raw)>60_000_000:raise ValueError('Image download exceeds 60 MB')
    else:raise ValueError('Image response has neither b64_json nor url')
    from PIL import Image
    import io
    with Image.open(io.BytesIO(raw)) as im:
        im.load();Path(out).parent.mkdir(parents=True,exist_ok=True)
        with Path(out).open('xb') as stream:im.save(stream,format='PNG')
    return Path(out)

def main():
    p=argparse.ArgumentParser();p.add_argument('--prompt-file',type=Path,required=True);p.add_argument('--image',action='append',default=[])
    p.add_argument('--out',type=Path,required=True);p.add_argument('--model',default='gpt-image-2');p.add_argument('--size',default='1:1');p.add_argument('--quality',default='auto');p.add_argument('--timeout',type=int,default=600)
    p.add_argument('--n',type=int,default=1);p.add_argument('--format',default='png');p.add_argument('--tmp-dir');p.add_argument('--output-dir');p.add_argument('--dry-run',action='store_true')
    a=p.parse_args()
    if a.n!=1:p.error('Submit independent tasks instead of n > 1')
    if a.dry_run:
        print(json.dumps({'model':a.model,'size':RATIOS.get(a.size,a.size),'reference_count':len(a.image),'output':str(a.out),'network_requests':0}));return
    key=os.environ.get('CODEX_API_KEY','')
    try:print(generate(os.environ.get('CODEX_API_URL','https://agent3.shyfai.cn'),key,a.prompt_file.read_text('utf-8'),a.image,a.out,a.model,a.size,a.quality,a.timeout))
    except Exception as exc:
        print(str(exc).replace(key,'[redacted]') if key else str(exc),file=sys.stderr);raise SystemExit(1)
if __name__=='__main__':main()
