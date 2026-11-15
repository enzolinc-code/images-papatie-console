import unittest,tempfile,io,json,hashlib
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
import server as s
import auto_scene as a
class AutoSceneTests(unittest.TestCase):
 def setUp(self):
  (s.ROOT/'qa').mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=s.ROOT/'qa');self.old=(s.DATA,s.ASSETS,s.JOBS);s.DATA=Path(self.temp.name);s.ASSETS={};s.JOBS={}
  bg=Image.new('RGB',(700,500),(180,175,165));ImageDraw.Draw(bg).rectangle((0,300,700,500),fill=(35,65,80));b=io.BytesIO();bg.save(b,format='PNG');self.scene=s.register(b.getvalue(),'scene.png','scene')
  fg=Image.new('RGBA',(100,140));d=ImageDraw.Draw(fg);d.ellipse((30,5,70,45),fill=(40,20,20,255));d.rectangle((5,50,95,90),fill=(190,100,70,255));d.rectangle((70,90,78,130),fill=(190,100,70,255));d.rectangle((85,90,93,130),fill=(190,100,70,255));b=io.BytesIO();fg.save(b,format='PNG');self.product=s.register(b.getvalue(),'person.png','product');self.product2=s.register(b.getvalue(),'person2.png','product')
 def tearDown(self):s.DATA,s.ASSETS,s.JOBS=self.old;self.temp.cleanup()
 def task(self):return s.make_plan({'mode':'scenes','scene_engine':'auto_fidelity','products':[self.product['id']],'scenes':[self.scene['id']],'channel':'3'})[0]
 def seed(self):
  cache=s.auto_cache(self.scene['id']);cache.mkdir(parents=True);r={'version':a.VERSION,'bbox':[.2,.15,.8,.83],'support':.6,'angle':.04,'photometric':{'gain':[1.02,1,.98]}}
  a.write(cache/'recognition.json',r);mask=Image.new('L',(700,500));ImageDraw.Draw(mask).rectangle((140,75,560,415),fill=255);mask.save(cache/'cleanup-mask.png');return cache
 def test_default_automatic_and_scene_cost_dedup(self):
  tasks=s.make_plan({'mode':'scenes','scene_engine':'auto_fidelity','products':[self.product['id'],self.product2['id']],'scenes':[self.scene['id']],'strategy':'all'})
  self.assertEqual(len(tasks),2);self.assertTrue(all(t['automatic'] for t in tasks));self.assertEqual(s.planned_calls(tasks),1);self.assertEqual(tasks[0]['channel'],'3')
  copy=s.register(s.asset_path(self.scene['id']).read_bytes(),'copy.png','scene');tasks=s.make_plan({'mode':'scenes','scene_engine':'auto_fidelity','products':[self.product['id']],'scenes':[self.scene['id'],copy['id']]});self.assertEqual(s.planned_calls(tasks),1)
 def test_cleanup_sent_only_scene_and_reused_for_next_product(self):
  self.seed();source=s.asset_path(self.product['id']).read_bytes();seen=[]
  def generate(task,folder):
   seen.append(task);self.assertNotIn(self.product['id'],task['refs']);self.assertNotIn(self.product2['id'],task['refs']);out=folder/'raw.png';Image.new('RGB',(700,500),(100,120,130)).save(out);return out
  with patch.object(s,'generate',side_effect=generate),patch.object(s,'run_command',side_effect=AssertionError('cached recognition')):
   for i,p in enumerate([self.product['id'],self.product2['id']]):
    t=self.task();t['refs'][1]=p;folder=s.DATA/('out'+str(i));folder.mkdir();out=s.automatic_scene(t,folder,lambda _:None);self.assertTrue(out.is_file());self.assertTrue(json.loads((folder/'fidelity-proof.json').read_text())['automatic'])
  self.assertEqual(len(seen),1);self.assertEqual(s.asset_path(self.product['id']).read_bytes(),source);self.assertEqual(s.planned_calls([self.task()]),0)
 def test_uncertain_cleanup_never_submitted_twice(self):
  self.seed();folder=s.DATA/'out';folder.mkdir()
  with patch.object(s,'generate',side_effect=RuntimeError('unknown remote result')) as call:
   for _ in range(2):
    with self.assertRaises(RuntimeError):s.automatic_scene(self.task(),folder,lambda _:None)
   self.assertEqual(call.call_count,1)
 def test_failed_recognition_never_calls_image_model(self):
  folder=s.DATA/'out';folder.mkdir()
  with patch.object(s,'run_command',return_value=1) as local,patch.object(s,'generate',side_effect=AssertionError('no paid call')):
   for _ in range(2):
    with self.assertRaises(ValueError):s.automatic_scene(self.task(),folder,lambda _:None)
   self.assertEqual(local.call_count,1)
 def test_layout_preserves_aspect_and_full_canvas(self):
  r={'bbox':[.2,.1,.8,.85],'support':.6,'angle':.1};t=a.layout(r,s.asset_path(self.product['id']),(700,500));self.assertTrue(all(.015<=v<=.985 for p in t['quad'] for v in p));self.assertEqual(t['aspect'],91/126);self.assertLess(t['rim'],.1)
 def test_mask_requires_subject_and_monitor_support(self):
  mask=s.DATA/'mask.png';im=Image.new('L',(700,500));d=ImageDraw.Draw(im);d.ellipse((290,80,410,200),fill=255);d.rectangle((220,190,480,298),fill=255);d.rectangle((300,298,320,370),fill=255);im.save(mask)
  r=a.analyze(s.asset_path(self.scene['id']),mask);self.assertAlmostEqual(r['support'],.6,delta=.03);self.assertTrue((s.DATA/'cleanup-mask.png').exists())
  blank=s.DATA/'blank.png';Image.new('L',(700,500)).save(blank)
  with self.assertRaises(ValueError):a.analyze(s.asset_path(self.scene['id']),blank)
 def test_flat_scene_uses_subject_without_monitor(self):
  mask=s.DATA/'mask.png';im=Image.new('L',(700,500));d=ImageDraw.Draw(im);d.ellipse((290,80,410,200),fill=255);d.rectangle((220,190,480,298),fill=255);d.rectangle((300,298,320,370),fill=255);im.save(mask)
  bg=s.DATA/'flat.png';Image.new('RGB',(700,500),(80,90,100)).save(bg)
  with self.assertRaises(ValueError):a.analyze(bg,mask,'monitor')
  self.assertEqual(a.analyze(bg,mask,'flat')['mode'],'flat')
 def test_harmonized_background_preserves_outside_mask(self):
  mask=s.DATA/'mask.png';m=Image.new('L',(700,500));ImageDraw.Draw(m).rectangle((200,100,450,350),fill=255);m.save(mask)
  made=s.DATA/'made.png';Image.new('RGB',(700,500),(230,220,200)).save(made);out=s.DATA/'blended.png'
  a.merge_background(s.asset_path(self.scene['id']),made,mask,out)
  source=Image.open(s.asset_path(self.scene['id'])).convert('RGB');result=Image.open(out)
  for p in [(0,0),(199,100),(451,350),(699,499)]:self.assertEqual(source.getpixel(p),result.getpixel(p))
 def test_worker_runs_automatic_scene_as_scene_output(self):
  class Queue:
   def __init__(self):self.items=[]
   def put(self,item):self.items.append(item)
   def get(self):
    if not self.items:raise SystemExit
    return self.items.pop(0)
   def task_done(self):pass
  def automatic(task,folder,phase):
   phase('自动识别验收');out=folder/'result.png';Image.new('RGB',(700,500),(100,120,130)).save(out);return out
  with patch.object(s,'Q',Queue()),patch.object(s,'automatic_scene',side_effect=automatic),patch.object(s,'generate',side_effect=AssertionError('unexpected image call')),patch.object(s,'channel_key',return_value='fixture'),patch.object(s.scene_outputs,'sync_job',return_value=None):
   job=s.create_job({'nonce':'auto-worker-fixture-1234','mode':'scenes','scene_engine':'auto_fidelity','products':[self.product['id']],'scenes':[self.scene['id']]})
   with self.assertRaises(SystemExit):s.worker()
  self.assertEqual(job['status'],'done');self.assertTrue(job['tasks'][0]['automatic']);self.assertEqual(s.ASSETS[job['tasks'][0]['asset']]['kind'],'result_scene')
if __name__=='__main__':unittest.main()