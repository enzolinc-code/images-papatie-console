import unittest,tempfile,json
from pathlib import Path
import material_marks as m
class MaterialMarkTests(unittest.TestCase):
 def setUp(self):
  p=Path(__file__).parent/'qa';p.mkdir(exist_ok=True);self.tmp=tempfile.TemporaryDirectory(dir=p);self.data=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_roundtrip_dedup_and_unicode(self):
  self.assertEqual(m.read(self.data),{});m.update(self.data,'a',True,[' 花冠 ','托腮','花冠']);m.update(self.data,'b',False,[])
  self.assertEqual(m.read(self.data),{'a':{'favorite':True,'tags':['花冠','托腮']},'b':{'favorite':False,'tags':[]}})
 def test_invalid_never_changes_file(self):
  m.update(self.data,'a',True,['旧标签']);before=(self.data/'material_marks.json').read_bytes()
  for favorite,tags in [(1,[]),(False,'tag'),(True,['a']*9),(True,['']), (True,['x'*21]),(True,['a\x00b'])]:
   with self.assertRaises(ValueError):m.update(self.data,'a',favorite,tags)
   self.assertEqual((self.data/'material_marks.json').read_bytes(),before)
 def test_clear(self):
  m.update(self.data,'a',True,['旧标签']);m.update(self.data,'a',False,[]);self.assertEqual(m.read(self.data)['a'],{'favorite':False,'tags':[]})
if __name__=='__main__':unittest.main()