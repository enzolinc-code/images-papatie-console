import unittest
from PIL import Image,ImageDraw
import acrylic
class AcrylicTests(unittest.TestCase):
 def test_clear_plate_has_thickness_and_preserves_print_input(self):
  bg=Image.new('RGBA',(160,160),(40,60,80,255));p=Image.new('RGBA',bg.size);d=ImageDraw.Draw(p);d.rectangle((40,35,120,90),fill=(180,90,60,255));d.rectangle((50,90,60,120),fill=(180,90,60,255));d.rectangle((80,90,90,120),fill=(180,90,60,255));original=p.tobytes()
  result,layers,proof=acrylic.render(bg,p)
  self.assertEqual(original,p.tobytes());self.assertTrue(proof['print_layer_unchanged']);self.assertFalse(proof['opaque_white_fill']);self.assertIn('亚克力厚度侧边',layers);self.assertIn('切边高光',layers);self.assertEqual(result.getpixel((0,0)),bg.getpixel((0,0)));self.assertLess(max(result.getpixel((70,115))[:3]),150)