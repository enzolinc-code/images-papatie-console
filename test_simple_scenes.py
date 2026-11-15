import unittest,sys,io,tempfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent));import server as s
class SimpleSceneTests(unittest.TestCase):
 def setUp(self):
  (s.ROOT/'qa').mkdir(exist_ok=True);self.tmp=tempfile.TemporaryDirectory(dir=s.ROOT/'qa');self.old=(s.DATA,s.ASSETS,s.JOBS);s.DATA=Path(self.tmp.name);s.ASSETS={};s.JOBS={}
  b=io.BytesIO();im=Image.new('RGBA',(50,70));im.paste((50,70,90,255),(10,10,40,60));im.save(b,format='PNG');self.p=s.register(b.getvalue(),'立牌.png','product');self.a=s.register(b.getvalue(),'场景.png','scene')
 def tearDown(self):s.DATA,s.ASSETS,s.JOBS=self.old;self.tmp.cleanup()
 def test_explicit_ai_needs_no_template_and_has_locked_pose_prompt(self):
  tasks=s.make_plan({'mode':'scenes','scene_engine':'ai','products':[self.p['id']],'scenes':[self.a['id']]});self.assertEqual(len(tasks),1);t=tasks[0];self.assertEqual(t['kind'],'scene');self.assertEqual(t['refs'],[self.a['id'],self.p['id']]);self.assertIn('每根手指',t['prompt']);self.assertIn('平面印刷',t['prompt'])
 def test_redo_only_one_same_prompt_refs_and_channel(self):
  t=s.make_plan({'mode':'scenes','scene_engine':'ai','products':[self.p['id']],'scenes':[self.a['id']],'channel':'4'})[0];t['status']='done';s.JOBS['original']={'tasks':[t,t]};new=s.make_plan({'mode':'redo_scene','job':'original','index':1,'channel':'4'});self.assertEqual(len(new),1);self.assertEqual(new[0]['prompt'],t['prompt']);self.assertEqual(new[0]['refs'],t['refs']);self.assertEqual(new[0]['channel'],'4');self.assertEqual(t['status'],'done')
 def test_uncertain_and_wrong_channel_redo_rejected(self):
  t=s.make_plan({'mode':'scenes','scene_engine':'ai','products':[self.p['id']],'scenes':[self.a['id']],'channel':'4'})[0];t['status']='uncertain';s.JOBS['original']={'tasks':[t]}
  with self.assertRaises(ValueError):s.make_plan({'mode':'redo_scene','job':'original','index':0,'channel':'4'})
  t['status']='done'
  with self.assertRaises(ValueError):s.make_plan({'mode':'redo_scene','job':'original','index':0,'channel':'3'})
 def test_default_fidelity_requires_prepared_scene(self):
  with self.assertRaisesRegex(ValueError,'确认干净背景'):
   s.make_plan({'mode':'scenes','scene_engine':'fidelity','products':[self.p['id']],'scenes':[self.a['id']]})
 def test_default_fidelity_never_sends_product_to_model(self):
  import fidelity
  store=fidelity.Store(s.DATA,s.asset_path)
  store.save({'scene':self.a['id'],'quad':[[.2,.2],[.8,.2],[.8,.8],[.2,.8]],'use_original':True})
  store.approve(self.a['id'])
  t=s.make_plan({'mode':'scenes','scene_engine':'fidelity','products':[self.p['id']],'scenes':[self.a['id']]})[0]
  self.assertEqual(t['kind'],'fidelity');self.assertEqual(t['channel'],'local');self.assertIsNone(t['model']);self.assertEqual(t['prompt'],'')
 def test_current_default_is_ai(self):
  t=s.make_plan({'mode':'scenes','products':[self.p['id']],'scenes':[self.a['id']]})[0]
  self.assertEqual(t['kind'],'scene');self.assertNotIn('automatic',t)
 def test_hand_correction_provenance_and_repeated_reference(self):
  first=s.make_plan({'mode':'scenes','products':[self.p['id']],'scenes':[self.a['id']],'channel':'4'})[0]
  first.update(status='done',asset=self.a['id']);s.JOBS['first']={'tasks':[first]}
  corrected=s.make_plan({'mode':'correct_hands','job':'first','index':0,'channel':'4','extra':'修正右手'})[0]
  self.assertEqual(corrected['refs'],[self.a['id'],self.p['id'],self.a['id']]);self.assertEqual(corrected['parent_job'],'first');self.assertIn('修正右手',corrected['prompt']);self.assertIn('亚克力',corrected['prompt']);self.assertEqual(s.planned_calls([corrected]),1)
  corrected.update(status='done',asset=self.p['id']);s.JOBS['second']={'tasks':[corrected]}
  third=s.make_plan({'mode':'correct_hands','job':'second','index':0,'channel':'4'})[0]
  self.assertEqual(third['refs'],[self.p['id'],self.p['id'],self.a['id']]);self.assertEqual(third['correction_pass'],2);self.assertEqual(first['asset'],self.a['id'])
 def test_hand_correction_rejects_unknown_uncertain_and_channel_switch(self):
  t={'kind':'scene','status':'uncertain','channel':'4','refs':[self.a['id'],self.p['id']],'asset':self.a['id'],'name':'fixture'};s.JOBS['x']={'tasks':[t]}
  for index in [-1,True,2]:
   with self.assertRaises(ValueError):s.make_plan({'mode':'correct_hands','job':'x','index':index,'channel':'4'})
  with self.assertRaises(ValueError):s.make_plan({'mode':'correct_hands','job':'x','index':0,'channel':'4'})
  t['status']='done'
  with self.assertRaises(ValueError):s.make_plan({'mode':'correct_hands','job':'x','index':0,'channel':'3'})
if __name__=='__main__':unittest.main()