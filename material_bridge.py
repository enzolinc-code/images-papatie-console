"""Temporary compatible trash endpoint while the main worker finishes existing jobs."""
import json,threading,os
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import material_trash
ROOT=Path(__file__).resolve().parent;DATA=ROOT/'data';LOCK=threading.RLock()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send_headers(self,code):
  self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Access-Control-Allow-Origin','http://127.0.0.1:8796');self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.send_header('Cache-Control','no-store');self.end_headers()
 def reply(self,data,code=200):self.send_headers(code);self.wfile.write(json.dumps(data,ensure_ascii=False).encode())
 def do_OPTIONS(self):self.send_headers(204)
 def do_GET(self):
  if self.path!='/api/material-trash':return self.reply({'error':'不存在'},404)
  with LOCK:self.reply({'trash':material_trash.read(DATA)})
 def do_POST(self):
  if self.headers.get('Origin') not in ('http://127.0.0.1:8796',):return self.reply({'error':'来源无效'},403)
  try:
   if self.path!='/api/material-trash':raise ValueError('操作不存在')
   length=int(self.headers.get('Content-Length',0))
   if not 0<length<40000:raise ValueError('请求大小无效')
   body=json.loads(self.rfile.read(length))
   with LOCK:
    assets=json.loads((DATA/'assets.json').read_text('utf-8'));jobs={}
    for p in (DATA/'jobs').glob('*/job.json'):
     j=json.loads(p.read_text('utf-8'));jobs[j['id']]=j
    self.reply(material_trash.change(DATA,assets,jobs,body.get('assets'),body.get('action')))
  except (ValueError,TypeError,KeyError) as e:self.reply({'error':str(e)},400)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('MATERIAL_TRASH_PORT','8798'))),Handler).serve_forever()