import unittest,json
from pathlib import Path
import server as s
import test_workflow as fixture
class Papatie20Tests(unittest.TestCase):
    setUp=fixture.WorkflowTests.setUp
    tearDown=fixture.WorkflowTests.tearDown
    def test_twenty_new_poses_are_grouped_with_stable_nonlegacy_ids(self):
        poses=s.PAPATIE_POSES
        self.assertEqual(len(poses),20);self.assertEqual(len({p['id'] for p in poses}),20)
        self.assertEqual(sum(p['tier']=='常用' for p in poses),14);self.assertEqual(sum(p['tier']=='进阶' for p in poses),6)
        self.assertTrue(all(p['id'].startswith('pp_') and p.get('action') and p.get('adaptation') for p in poses))
        self.assertEqual(len(s.POSE_LIBRARY),len(s.POSES)+20)
    def test_all_new_poses_create_individual_tasks_without_sending_ui_photo(self):
        tasks=s.make_plan({'mode':'poses','source':self.ref['id'],'poses':[p['id'] for p in s.PAPATIE_POSES],'channel':'3'})
        self.assertEqual(len(tasks),20)
        self.assertTrue(all(t['refs']==[self.ref['id']] for t in tasks))
        self.assertTrue(all('动作简化' in t['prompt'] for t in tasks))
    def test_reference_photos_are_not_mislabeled_ai_generated(self):
        from PIL import Image
        for p in s.PAPATIE_POSES:
            self.assertEqual(p['image_kind'],'reference');self.assertTrue(p['source_file'].startswith('SKU_'))
            with Image.open(s.ROOT/'web/pose-art'/(p['id']+'.png')) as im:self.assertEqual(im.size,(800,800))
    def test_old_pose_ids_remain_valid(self):
        for p in s.POSES:self.assertIn(p['id'],s.POSE_MAP)
        for key in ['chin','both','edge','heart','wave','cross','lean','pillow']:self.assertIn(key,s.POSE_MAP)
    def test_duplicate_new_ids_rejected(self):
        with self.assertRaises(ValueError):s.make_plan({'mode':'poses','source':self.ref['id'],'poses':['pp_A01','pp_A01'],'channel':'3'})
if __name__=='__main__':unittest.main()
