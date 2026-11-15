import unittest
import test_simple_scenes as fixtures
import server as s
class OriginalPoseTests(unittest.TestCase):
 setUp=fixtures.SimpleSceneTests.setUp
 tearDown=fixtures.SimpleSceneTests.tearDown
 def test_rebuild_without_pose_selection(self):
  tasks=s.make_plan({'mode':'rebuild','source':self.p['id'],'channel':'4','poses':['invalid']})
  self.assertEqual(len(tasks),1)
  t=tasks[0];self.assertEqual(t['refs'],[self.p['id']]);self.assertEqual(t['kind'],'cutout');self.assertEqual(t['channel'],'4');self.assertEqual(t['size'],'4:3')
  self.assertIn('每根可见手指',t['prompt']);self.assertIn('不使用姿势库',t['prompt']);self.assertIn('【检查要求】',t['prompt']);self.assertNotIn('所选目标趴趴动作',t['prompt'])
 def test_original_pixels_remain_available(self):
  tasks=s.make_plan({'mode':'cutout','source':self.p['id']})
  self.assertEqual(tasks[0]['kind'],'local');self.assertEqual(tasks[0]['prompt'],'')
 def test_missing_source_rejected(self):
  with self.assertRaises((ValueError,KeyError,TypeError)):s.make_plan({'mode':'rebuild','source':'missing'})
 def test_canvas_ratio_and_extra(self):
  from PIL import Image
  path=s.asset_path(self.p['id']);Image.new('RGBA',(100,100),(10,20,30,255)).save(path)
  t=s.make_plan({'mode':'rebuild','source':self.p['id'],'extra':'保留戒指'})[0]
  self.assertEqual(t['size'],'4:3');self.assertIn('保留戒指',t['prompt'])
  Image.new('RGBA',(140,70),(10,20,30,255)).save(path)
  self.assertEqual(s.make_plan({'mode':'rebuild','source':self.p['id']})[0]['size'],'4:3')

 def test_edge_guard_ignores_added_transparent_padding(self):
  from PIL import Image
  path=s.DATA/'guard.png';im=Image.new('RGBA',(528,428));im.paste((0,0,0,255),(64,100,300,300));im.save(path)
  with self.assertRaisesRegex(ValueError,'疑似'):s.validate_rebuild_frame(path)
  im=Image.new('RGBA',(528,428));im.paste((0,0,0,255),(150,130,380,290));im.save(path)
  s.validate_rebuild_frame(path)
 def test_prompt_requires_complete_sleeves(self):
  t=s.make_plan({'mode':'rebuild','source':self.p['id']})[0]
  self.assertIn('20%',t['prompt']);self.assertIn('禁止两侧竖直切口',t['prompt'])

 def test_complete_near_edge_fingertip_is_not_clipping(self):
  from PIL import Image
  path=s.DATA/'intact.png';im=Image.new('RGBA',(528,428));im.paste((0,0,0,255),(100,100,400,359));im.save(path);s.validate_rebuild_frame(path)
