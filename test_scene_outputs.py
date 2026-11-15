import unittest,tempfile,io
from pathlib import Path
from PIL import Image
import scene_outputs as out
class OutputTests(unittest.TestCase):
 def setUp(self):
  folder=Path(__file__).resolve().parent/'qa';folder.mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=folder);self.root=Path(self.temp.name);self.img=self.root/'source.png';Image.new('RGB',(60,80),'red').save(self.img)
  self.job={'id':'testjob','created':1700000000,'tasks':[{'name':'场景/一.jpg','kind':'scene','status':'done','asset':'a','review':'pending'},{'name':'fixture-x1file.png','kind':'scene','status':'done','asset':'b','review':'rejected'},{'name':'失败','kind':'scene','status':'failed'}]}
 def tearDown(self):self.temp.cleanup()
 def test_export_is_idempotent_and_only_completed_images(self):
  p=out.sync_job(self.root,self.job,lambda aid:self.img);files=list(p.glob('*.jpg'));self.assertEqual(len(files),2);self.assertTrue(any('fixture-x1file' in f.name for f in files));stamps=[f.stat().st_mtime_ns for f in files];out.sync_job(self.root,self.job,lambda aid:self.img);self.assertEqual(stamps,[f.stat().st_mtime_ns for f in files]);self.assertTrue(all(f.resolve().is_relative_to(p.resolve()) for f in files))
 def test_delivery_excludes_rejected_and_keeps_source(self):
  result=out.handoff(self.root,self.job,lambda aid:self.img);self.assertEqual(result['count'],1);self.assertEqual(result['pending_review'],1);self.assertEqual(len(list(Path(result['folder']).glob('*.jpg'))),1);self.assertTrue(self.img.exists());self.assertEqual(len(list(Path(self.job['output_dir']).glob('*.jpg'))),2)
 def test_no_scene_output_for_failed_or_person_pose(self):
  self.job['tasks']=[{'kind':'cutout','status':'done'}];self.assertIsNone(out.sync_job(self.root,self.job,lambda aid:self.img))
if __name__=='__main__':unittest.main()
