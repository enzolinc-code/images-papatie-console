import unittest
from unittest.mock import patch
import test_workflow as fixture
import server as s
class SampleTests(unittest.TestCase):
 setUp=fixture.WorkflowTests.setUp
 tearDown=fixture.WorkflowTests.tearDown
 def body(self):return {'mode':'scenes','products':[self.prod['id']],'scenes':[a['id'] for a in self.scenes],'sample_first':True,'channel':'3','nonce':'sample-first-fixture-123'}
 def test_only_first_then_explicit_continue_and_no_duplicate(self):
  with patch.object(s.Q,'put') as put,patch.object(s,'channel_key',return_value='fixture'):
   sample=s.create_job(self.body());self.assertEqual(len(sample['tasks']),1);self.assertEqual(len(sample['sample_remaining']),2)
   b={'mode':'continue_sample','sample':sample['id'],'channel':'3','nonce':'sample-remaining-fixture-1'}
   with self.assertRaises(ValueError):s.make_plan(b)
   sample['tasks'][0].update(status='done',review='accepted',asset=self.prod['id'])
   remaining=s.create_job(b);self.assertEqual(len(remaining['tasks']),2);self.assertEqual(remaining['tasks'][0]['refs'][0],self.scenes[1]['id'])
   self.assertEqual(s.create_job(dict(b,nonce='sample-remaining-fixture-2'))['id'],remaining['id']);self.assertEqual(put.call_count,2)
 def test_repaired_sample_can_approve_without_accepting_bad_original(self):
  with patch.object(s.Q,'put'),patch.object(s,'channel_key',return_value='fixture'):
   sample=s.create_job(self.body());sample['tasks'][0].update(status='done',asset=self.prod['id'],review='rejected')
   repair=s.create_job({'mode':'correct_material','job':sample['id'],'index':0,'channel':'3','nonce':'sample-repair-fixture-1'});self.assertEqual(repair['sample_root'],sample['id']);repair['tasks'][0].update(status='done',review='accepted',asset=self.prod['id'])
   t=s.make_plan({'mode':'continue_sample','sample':sample['id'],'approved_job':repair['id'],'channel':'3'});self.assertEqual(len(t),2);self.assertEqual(sample['tasks'][0]['review'],'rejected')
 def test_quick_screen_never_deletes_files(self):
  before=set(s.ASSETS)
  with self.assertRaises(ValueError):s.make_plan(dict(self.body(),quick_screen=True))
  self.assertEqual(set(s.ASSETS),before)