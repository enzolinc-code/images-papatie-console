import unittest
import test_simple_scenes as fixture
import server as s
class FaceOrientationTests(unittest.TestCase):
 setUp=fixture.SimpleSceneTests.setUp
 tearDown=fixture.SimpleSceneTests.tearDown
 def test_front_default_is_explicit_and_overrides_head_locks(self):
  t=s.make_plan({'mode':'rebuild','source':self.p['id']})[0]
  self.assertEqual(t['face_mode'],'front');self.assertIn('不是只转动眼珠',t['prompt']);self.assertIn('明确覆盖',t['prompt']);self.assertEqual(t['refs'],[self.p['id']])
 def test_original_removes_catalog_front_suffix(self):
  t=s.make_plan({'mode':'poses','source':self.p['id'],'poses':['p01'],'face_mode':'original'})[0]
  self.assertIn('不强行转正',t['prompt']);self.assertNotIn('人物脸面朝正前方，视线直视观众',t['prompt'])
 def test_optional_identity_is_last_image_with_correct_role(self):
  t=s.make_plan({'mode':'rebuild','source':self.p['id'],'face_reference':self.a['id']})[0]
  self.assertEqual(t['refs'],[self.p['id'],self.a['id']]);self.assertIn('图2是同人物的正脸身份辅助',t['prompt'])
 def test_original_ignores_retained_face_reference(self):
  t=s.make_plan({'mode':'rebuild','source':self.p['id'],'face_mode':'original','face_reference':'missing'})[0]
  self.assertEqual(t['refs'],[self.p['id']]);self.assertIsNone(t['face_reference'])
 def test_invalid_reference_and_mode_fail(self):
  for fields in [{'face_mode':'wrong'},{'face_reference':'missing'}]:
   with self.assertRaises(ValueError):s.make_plan({'mode':'rebuild','source':self.p['id'],**fields})
 def test_cutout_and_scenes_do_not_turn_face(self):
  cut=s.make_plan({'mode':'cutout','source':self.p['id'],'face_mode':'front'})[0]
  self.assertEqual(cut['prompt'],'');self.assertNotIn('face_mode',cut)
  scene=s.make_plan({'mode':'scenes','products':[self.p['id']],'scenes':[self.a['id']],'face_mode':'front'})[0]
  self.assertNotIn('本次脸部朝向最高优先级',scene['prompt']);self.assertNotIn('face_mode',scene)
