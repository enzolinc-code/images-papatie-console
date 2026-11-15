import unittest,tempfile,json
from pathlib import Path
import material_trash as m
class TrashTests(unittest.TestCase):
 def setUp(self):
  r=Path(__file__).parent/'qa';r.mkdir(exist_ok=True);self.tmp=tempfile.TemporaryDirectory(dir=r);self.data=Path(self.tmp.name);self.assets={k:{'id':k,'kind':'product','transparent':True} for k in ['a','b']}
 def tearDown(self):self.tmp.cleanup()
 def test_delete_restore_preserves_records(self):
  original=json.dumps(self.assets);m.change(self.data,self.assets,{},['a','b'],'delete');self.assertEqual(set(m.read(self.data)),{'a','b'});self.assertEqual(json.dumps(self.assets),original);m.change(self.data,self.assets,{},['a'],'restore');self.assertEqual(set(m.read(self.data)),{'b'})
 def test_active_reference_atomic_rejection(self):
  jobs={'j':{'status':'running','tasks':[{'refs':['b']}]}}
  with self.assertRaises(ValueError):m.change(self.data,self.assets,jobs,['a','b'],'delete')
  self.assertEqual(m.read(self.data),{})
 def test_history_reference_kept_and_restorable(self):
  jobs={'j':{'status':'done','tasks':[{'refs':['b'],'asset':'a'}]}};m.change(self.data,self.assets,jobs,['a'],'delete');self.assertEqual(jobs['j']['tasks'][0]['asset'],'a');self.assertIn('a',self.assets)
 def test_invalid_ids_no_partial_delete(self):
  for ids in [['a','missing'],['a','a'],[]]:
   with self.assertRaises(ValueError):m.change(self.data,self.assets,{},ids,'delete')
  self.assertEqual(m.read(self.data),{})