import base64,hashlib,importlib.util,io,sys,tempfile,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('upload_bridge',ROOT/'tools/xingqi_bridge.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
class UploadTests(unittest.TestCase):
 def setUp(self):
  folder=ROOT/'qa'/'upload-tests';folder.mkdir(parents=True,exist_ok=True)
  self.tmp=tempfile.TemporaryDirectory(dir=folder);self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def decode(self,p):
  value=b.reference_data_url(p);header,data=value.split(',',1);raw=base64.b64decode(data)
  self.assertLessEqual(len(raw),9_000_000)
  return header,raw
 def test_small_file_unchanged_and_actual_mime(self):
  p=self.root/'wrong.jpg';Image.new('RGBA',(30,30),(40,20,10,0)).save(p,format='PNG')
  header,raw=self.decode(p);self.assertEqual(header,'data:image/png;base64');self.assertEqual(raw,p.read_bytes())
 def noisy(self,alpha=False):
  import numpy as np
  a=np.random.default_rng(42).integers(0,256,(2100,2100,4 if alpha else 3),dtype=np.uint8)
  if alpha:a[:30,:,3]=0;a[30:60,:,3]=128
  p=self.root/'large.png';Image.fromarray(a).save(p);self.assertGreater(p.stat().st_size,10_000_000);return p
 def test_large_photo_and_original_unchanged(self):
  p=self.noisy();digest=hashlib.sha256(p.read_bytes()).digest();header,raw=self.decode(p)
  self.assertEqual(header,'data:image/jpeg;base64');self.assertEqual(hashlib.sha256(p.read_bytes()).digest(),digest)
  with Image.open(io.BytesIO(raw)) as im:self.assertEqual(im.size,(2100,2100))
 def test_large_alpha_preserved_and_deterministic(self):
  p=self.noisy(True);header,raw=self.decode(p);self.assertEqual(header,'data:image/png;base64')
  self.assertEqual(raw,self.decode(p)[1])
  with Image.open(io.BytesIO(raw)) as im:
   self.assertEqual(im.mode,'RGBA');lo,hi=im.getchannel('A').getextrema();self.assertEqual(lo,0);self.assertEqual(hi,255)
   self.assertTrue(any(0<x<255 for x in im.getchannel('A').getdata()))
 def test_corrupt_fails_locally(self):
  p=self.root/'bad.png';p.write_bytes(b'broken')
  with self.assertRaises(Exception):b.reference_data_url(p)
if __name__=='__main__':unittest.main()