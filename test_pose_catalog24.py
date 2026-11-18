import unittest,json,hashlib
from pathlib import Path
import test_simple_scenes as fixture
import server as s
class PoseCatalog24Tests(unittest.TestCase):
 setUp=fixture.SimpleSceneTests.setUp
 tearDown=fixture.SimpleSceneTests.tearDown
 def test_catalog_has_24_distinct_named_entries(self):
  self.assertEqual(len(s.POSES),24);self.assertEqual(len({p['id'] for p in s.POSES}),24);self.assertEqual(len({p['name'] for p in s.POSES}),24)
  self.assertTrue(all(p.get('group') and p.get('hint') for p in s.POSES))
 def test_all_catalog_choices_work_and_ui_art_is_not_model_reference(self):
  tasks=s.make_plan({'mode':'poses','source':self.p['id'],'poses':[p['id'] for p in s.POSES],'sample_first':False,'channel':'3'})
  self.assertEqual(len(tasks),24)
  self.assertTrue(all(t['refs']==[self.p['id']] for t in tasks))
  self.assertEqual(len({t['name'] for t in tasks}),24)
 def test_legacy_ids_remain_available_for_history(self):
  for pid in ['chin','both','edge','heart','wave','cross','lean','pillow']:self.assertIn(pid,s.POSE_MAP)
 def test_all_24_art_files_are_present_and_distinct(self):
  from PIL import Image
  hashes=[]
  for p in s.POSES:
   path=s.ROOT/'web/pose-art'/(p['id']+'.png');hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
   with Image.open(path) as im:self.assertGreaterEqual(im.width,768);self.assertGreaterEqual(im.height,640)
  self.assertEqual(len(set(hashes)),24)
 def test_duplicate_choices_rejected(self):
  with self.assertRaises(ValueError):s.make_plan({'mode':'poses','source':self.p['id'],'poses':['p01','p01']})