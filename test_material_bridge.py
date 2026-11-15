import unittest,tempfile,json,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib import request,error
import material_bridge as b
class BridgeTests(unittest.TestCase):
 def test_delete_visible_then_restore_no_source_removal(self):
  root=Path(__file__).parent/'qa';root.mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=root) as temp:
   old=b.DATA;b.DATA=Path(temp);(b.DATA/'jobs').mkdir();(b.DATA/'assets.json').write_text(json.dumps({'fixture':{'id':'fixture','transparent':True,'kind':'product'}}),'utf-8')
   http=ThreadingHTTPServer(('127.0.0.1',0),b.Handler);t=threading.Thread(target=http.serve_forever);t.start();url='http://127.0.0.1:'+str(http.server_port)+'/api/material-trash';opener=request.build_opener(request.ProxyHandler({}))
   try:
    for action,present in [('delete',True),('restore',False)]:
     req=request.Request(url,data=json.dumps({'assets':['fixture'],'action':action}).encode(),headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:8796'})
     with opener.open(req) as res:self.assertEqual(json.load(res)['count'],1);self.assertEqual(res.headers['Access-Control-Allow-Origin'],'http://127.0.0.1:8796')
     with opener.open(url) as res:self.assertEqual('fixture' in json.load(res)['trash'],present)
   finally:http.shutdown();http.server_close();t.join();b.DATA=old