import unittest,io
from PIL import Image
import test_simple_scenes as fixtures
import server as s
class IdentityTests(unittest.TestCase):
 setUp=fixtures.SimpleSceneTests.setUp
 tearDown=fixtures.SimpleSceneTests.tearDown
 def test_identity_reference_persists_in_correction(self):
  b=io.BytesIO();Image.new('RGB',(500,500),(170,140,120)).save(b,format='PNG');identity=s.register(b.getvalue(),'identity.png','identity')
  t=s.make_plan({'mode':'scenes','products':[self.p['id']],'scenes':[self.a['id']],'person_name':'刘亦菲','identity_asset':identity['id'],'channel':'3'})[0]
  self.assertEqual(t['refs'],[self.a['id'],self.p['id'],identity['id']]);self.assertIn('刘亦菲',t['prompt']);t.update(status='done',asset=self.a['id']);s.JOBS['x']={'tasks':[t]}
  for mode in ['correct_hands','correct_identity']:
   c=s.make_plan({'mode':mode,'job':'x','index':0,'channel':'3'})[0];self.assertEqual(c['refs'][-1],identity['id']);self.assertEqual(c['person_name'],'刘亦菲');self.assertEqual(c['correction_product'],self.p['id'])
 def test_screening_excludes_without_deleting(self):
  before=set(s.ASSETS)
  with self.assertRaises(ValueError):s.make_plan({'mode':'scenes','products':[self.p['id']],'scenes':[self.a['id']],'screening':True,'review_approved':[self.p['id'],self.a['id']]})
  self.assertEqual(set(s.ASSETS),before)
 def test_named_person_requires_identity(self):
  with self.assertRaises(ValueError):s.make_plan({'mode':'scenes','products':[self.p['id']],'scenes':[self.a['id']],'person_name':'刘亦菲'})
