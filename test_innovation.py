import unittest,json
from unittest.mock import patch
import test_workflow as fixture
import server as s
class InnovationTests(unittest.TestCase):
 setUp=fixture.WorkflowTests.setUp
 tearDown=fixture.WorkflowTests.tearDown
 def test_single_source_style_references_and_no_pose(self):
  before=set(s.ASSETS)
  t=s.make_plan({'mode':'innovate','source':self.ref['id'],'style':'semi-realistic-refined','channel':'3'})
  self.assertEqual(len(t),1);self.assertEqual(t[0]['refs'],[self.ref['id'],'__style__:semi-realistic-refined']);self.assertEqual(t[0]['kind'],'cutout');self.assertEqual(before,set(s.ASSETS));self.assertTrue(s.asset_path(t[0]['refs'][1]).is_file())
  self.assertIn('图1是唯一',t[0]['prompt']);self.assertIn('不画棋盘格',t[0]['prompt']);self.assertNotIn('严格保留图2中分黑发',t[0]['prompt'])
 def test_unknown_style_and_traversal_rejected(self):
  for style in ['../../config','missing','semi-realistic-refined/../']:
   with self.assertRaises(ValueError):s.make_plan({'mode':'innovate','source':self.ref['id'],'style':style})
 def test_innovation_ignores_global_selection(self):
  for channel in ['3','4','5']:
   t=s.make_plan({'mode':'innovate','source':self.ref['id'],'style':'semi-realistic-refined','channel':channel})[0]
   self.assertEqual(t['channel'],'3');self.assertEqual(t['model'],'gpt-image-2.6');self.assertEqual(t['generation_policy'],'innovation-image26-v1')
 def test_hidden_style_ref_cannot_be_source(self):
  with self.assertRaises(ValueError):s.make_plan({'mode':'innovate','source':'__style__:semi-realistic-refined','style':'semi-realistic-refined'})
 def test_public_catalog_has_no_private_config(self):
  cat=s.innovation.public(s.ROOT);self.assertEqual(cat[0]['id'],'semi-realistic-refined');self.assertNotIn('endpoint',json.dumps(cat));self.assertNotIn('source_skill',json.dumps(cat))
 def test_job_credentials_and_preflight_use_channel3(self):
  with patch.object(s.Q,'put'),patch.object(s,'channel_key',side_effect=lambda c:'fixture' if c=='3' else '') as key,patch.object(s.image_channels,'preflight') as pre:
   j=s.create_job({'mode':'innovate','source':self.ref['id'],'channel':'5','model':'wrong','nonce':'fixed26-test-job-1234'})
   self.assertEqual(j['tasks'][0]['channel'],'3');self.assertEqual(j['tasks'][0]['model'],'gpt-image-2.6');pre.assert_called_once_with('3',s.CFG)
 def test_other_modes_keep_selected_channel(self):
  t=s.make_plan({'mode':'poses','source':self.ref['id'],'poses':['heart'],'channel':'4'})[0]
  self.assertEqual(t['channel'],'4');self.assertEqual(t['model'],s.channel_model('4'))
 def test_no_switch_on_generation_failure(self):
  t=s.make_plan({'mode':'innovate','source':self.ref['id'],'channel':'4'})[0]
  folder=s.DATA/'fixed26';folder.mkdir()
  with patch.object(s,'run_command',return_value=1) as run:
   with self.assertRaises(RuntimeError):s.generate(t,folder)
   self.assertEqual(run.call_count,1);cmd=run.call_args.args[0];self.assertEqual(cmd[cmd.index('--model')+1],'gpt-image-2.6');self.assertEqual(run.call_args.args[3],'3')
   if 'codex3_bridge.py' in str(cmd):self.assertEqual(cmd[cmd.index('--max-attempts')+1],'1')
