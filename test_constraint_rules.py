import unittest,constraint_rules as c
class ConstraintTests(unittest.TestCase):
 def test_user_sections_present(self):
  p=c.apply('scenes','场景要求')
  for title in ['人物锁定','姿势锁定','手指锁定','光影与质感锁定','检查要求']:self.assertIn('【'+title+'】',p)
  self.assertIn('被遮挡的手指保持遮挡，不强行补全',p);self.assertIn('场景图（图1）只提供',p)
 def test_not_duplicate_or_added_to_background(self):
  p=c.apply('scenes','test');self.assertEqual(c.apply('scenes',p),p);self.assertEqual(c.apply('background','clean'),'clean');self.assertEqual(c.apply('continue_sample','snapshot'),'snapshot')
 def test_target_pose_context(self):self.assertIn('不照搬原站姿',c.apply('poses','pose'))