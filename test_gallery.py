import unittest,tempfile,io,json,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib import request,error
from PIL import Image
import server as s
class GalleryTests(unittest.TestCase):
 def setUp(self):
  (s.ROOT/'qa').mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=s.ROOT/'qa');self.old=(s.ROOT,s.DATA,s.ASSETS,s.JOBS);s.ROOT=Path(self.temp.name);s.DATA=s.ROOT/'data';s.DATA.mkdir();s.ASSETS={};s.JOBS={}
  b=io.BytesIO();im=Image.new('RGBA',(30,40));im.paste((60,80,100,255),(5,5,25,35));im.save(b,format='PNG');a=s.register(b.getvalue(),'fixture.png','result_cutout');self.job={'id':'gallerytest','created':1700000000,'status':'done','tasks':[{'name':'一','kind':'local','status':'done','asset':a['id'],'review':'pending'},{'name':'二','kind':'local','status':'done','asset':a['id'],'review':'rejected'}]};s.JOBS[self.job['id']]=self.job;(s.DATA/'jobs'/self.job['id']).mkdir(parents=True)
  self.http=ThreadingHTTPServer(('127.0.0.1',0),s.Handler);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.http.server_port)+'/api/gallery'
 def tearDown(self):self.http.shutdown();self.http.server_close();self.thread.join();s.ROOT,s.DATA,s.ASSETS,s.JOBS=self.old;self.temp.cleanup()
 def post(self,b):
  req=request.Request(self.url,data=json.dumps(b).encode(),headers={'Content-Type':'application/json'})
  try:
   with request.urlopen(req) as r:return r.status,json.load(r)
  except error.HTTPError as e:
   with e:return e.code,json.load(e)
 def test_archive_roundtrip_and_running_rejected(self):
  self.assertEqual(self.post({'action':'archive','job':'gallerytest','archived':True})[0],200);self.assertTrue(self.job['archived']);self.post({'action':'archive','job':'gallerytest','archived':False});self.assertFalse(self.job['archived']);self.job['status']='running';self.assertEqual(self.post({'action':'archive','job':'gallerytest','archived':True})[0],400)
 def test_invalid_bulk_review_has_no_partial_mutation(self):
  code,_=self.post({'action':'review','review':'accepted','selection':[{'job':'gallerytest','index':0},{'job':'gallerytest','index':9}]});self.assertEqual(code,400);self.assertEqual(self.job['tasks'][0]['review'],'pending')
 def test_bulk_review_and_selected_delivery_preserve_alpha(self):
  self.assertEqual(self.post({'action':'review','review':'accepted','selection':[{'job':'gallerytest','index':0}]})[0],200)
  code,r=self.post({'action':'handoff','selection':[{'job':'gallerytest','index':0},{'job':'gallerytest','index':1}]});self.assertEqual(code,200);self.assertEqual(r['count'],1);files=[p for p in Path(r['folder']).iterdir() if p.suffix.lower() in ('.png','.jpg')];self.assertEqual(len(files),1)
  with Image.open(files[0]) as im:self.assertEqual(im.getchannel('A').getextrema(),(0,255))
 def test_rename_validates_and_preserves_records(self):
  self.assertEqual(self.post({'action':'rename','job':'gallerytest','title':'  花冠场景作品  '})[0],200);self.assertEqual(self.job['title'],'花冠场景作品');self.assertEqual(len(self.job['tasks']),2)
  self.assertEqual(self.post({'action':'rename','job':'gallerytest','title':' '})[0],400);self.assertEqual(self.job['title'],'花冠场景作品')
 def test_material_marks_endpoint_and_snapshot(self):
  self.url=self.url.replace('/api/gallery','/api/material-marks');aid=next(iter(s.ASSETS));original=dict(s.ASSETS[aid])
  code,value=self.post({'asset':aid,'favorite':True,'tags':[' 常用 ','花冠','常用']})
  self.assertEqual(code,200);self.assertEqual(value,{'favorite':True,'tags':['常用','花冠']});self.assertEqual(s.ASSETS[aid],original)
  self.assertTrue(next(a for a in s.snapshot()['assets'] if a['id']==aid)['favorite'])
 def test_material_marks_reject_unknown_asset_and_invalid_tags(self):
  self.url=self.url.replace('/api/gallery','/api/material-marks');aid=next(iter(s.ASSETS))
  self.assertEqual(self.post({'asset':aid,'favorite':True,'tags':['x'*21]})[0],400)
  self.assertEqual(self.post({'asset':'unknown','favorite':True,'tags':[]})[0],400)
  self.assertFalse((s.DATA/'material_marks.json').exists())
if __name__=='__main__':unittest.main()