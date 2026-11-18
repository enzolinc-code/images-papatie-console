import unittest,json
from unittest.mock import patch
import test_workflow as fixture
import server as s
class LayoutRepairTests(unittest.TestCase):
 setUp=fixture.WorkflowTests.setUp
 tearDown=fixture.WorkflowTests.tearDown
 def sample(self):
  with patch.object(s.Q,'put'),patch.object(s,'channel_key',return_value='fixture'):
   j=s.create_job({'mode':'scenes','products':[self.prod['id']],'scenes':[self.scenes[0]['id']],'sample_first':True,'channel':'3','nonce':'layout-source-fixture-123'})
  j['tasks'][0].update(status='done',asset=self.prod['id'],model='frozen-model')
  return j
 def test_layout_plan_keeps_original_refs_and_snapshot(self):
  j=self.sample();before=json.dumps(j,sort_keys=True)
  t=s.make_plan({'mode':'correct_layout','job':j['id'],'index':0,'channel':'3'})[0]
  self.assertEqual(t['refs'][:3],[self.prod['id'],self.prod['id'],self.scenes[0]['id']]);self.assertEqual(t['model'],'frozen-model')
  self.assertIn('自动贴合',t['name']);self.assertIn('自适应',t['prompt']);self.assertIn('禁止通过缩放整张图',t['prompt']);self.assertIn('【人物锁定】',t['prompt']);self.assertEqual(before,json.dumps(j,sort_keys=True))
 def test_does_not_change_channel(self):
  j=self.sample()
  with self.assertRaises(ValueError):s.make_plan({'mode':'correct_layout','job':j['id'],'index':0,'channel':'4'})
 def test_repeat_repair_uses_original_action_and_scene(self):
  j=self.sample()
  with patch.object(s.Q,'put'),patch.object(s,'channel_key',return_value='fixture'):
   repaired=s.create_job({'mode':'correct_layout','job':j['id'],'index':0,'channel':'3','nonce':'layout-repair-fixture-123'})
  repaired['tasks'][0].update(status='done',asset=self.scenes[1]['id'])
  t=s.make_plan({'mode':'correct_layout','job':repaired['id'],'index':0,'channel':'3'})[0]
  self.assertEqual(t['refs'][:3],[self.scenes[1]['id'],self.prod['id'],self.scenes[0]['id']]);self.assertEqual(t['correction_pass'],2)