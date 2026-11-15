import unittest,io,json,zipfile
from pathlib import Path
from urllib import request
from PIL import Image
import test_gallery as fixture
import server as s
import image_trash,scene_outputs
class UnifiedTrashTests(unittest.TestCase):
 setUp=fixture.GalleryTests.setUp
 tearDown=fixture.GalleryTests.tearDown
 post=fixture.GalleryTests.post
 def ids(self):
  first=next(iter(s.ASSETS));ids=[first]
  for n in range(2):
   b=io.BytesIO();Image.new('RGB',(80,80),(20+n,50,80)).save(b,format='PNG');ids.append(s.register(b.getvalue(),'same-name.jpg','result_scene')['id'])
  self.job['tasks']=[{'name':'same-name.jpg','kind':'scene','status':'done','asset':aid,'review':'rejected' if i==1 else 'pending'} for i,aid in enumerate(ids)];return ids
 def trash(self,ids,action='delete'):
  previous=self.url;self.url=previous.replace('/api/gallery','/api/image-trash')
  try:return self.post({'assets':ids,'action':action})
  finally:self.url=previous
 def test_three_to_two_and_zip_filters_deleted(self):
  ids=self.ids();self.assertEqual(self.trash([ids[1]])[0],200);self.assertEqual([a['id'] for a in s.snapshot()['assets'] if a['trashed']],[ids[1]])
  with request.urlopen(self.url.replace('/api/gallery','/download/gallerytest')) as r:z=zipfile.ZipFile(io.BytesIO(r.read()));self.assertEqual(len(z.namelist()),2)
  self.assertEqual(self.job['tasks'][1]['review'],'rejected');self.assertEqual(self.trash([ids[1]],'restore')[0],200);self.assertFalse(next(a for a in s.snapshot()['assets'] if a['id']==ids[1])['trashed'])
 def test_export_removed_not_recreated_restore(self):
  ids=self.ids();s.save(self.job);p=Path(self.job['tasks'][1]['output_file']);self.assertTrue(p.exists());self.trash([ids[1]]);self.assertFalse(p.exists());s.save(self.job);self.assertFalse(p.exists());self.trash([ids[1]],'restore');self.assertTrue(p.exists())
 def test_new_handoff_copies_follow_manifest(self):
  ids=self.ids();code,r=self.post({'action':'handoff','selection':[{'job':'gallerytest','index':0}]});self.assertEqual(code,200);folder=Path(r['folder']);manifest=json.loads((folder/'image-manifest.json').read_text('utf-8'));copy=folder/manifest['images'][0]['file'];self.assertTrue(copy.exists());self.trash([ids[0]]);self.assertFalse(copy.exists());code,r=self.post({'action':'handoff','selection':[{'job':'gallerytest','index':0}]});self.assertEqual(code,400)
 def test_active_reference_can_hide_but_cannot_purge(self):
  ids=self.ids();s.JOBS['active']={'status':'running','tasks':[{'refs':[ids[0]]}]};p=s.asset_path(ids[0]);self.assertEqual(self.trash([ids[0]])[0],200);self.assertTrue(p.exists());self.assertEqual(self.trash([ids[0]],'purge')[0],400)
 def test_permanent_delete_only_in_recycle_and_not_referenced(self):
  ids=self.ids();p=s.asset_path(ids[2]);self.assertEqual(self.trash([ids[2]],'purge')[0],400);self.assertEqual(self.trash([ids[2]])[0],200);self.assertTrue(p.exists());self.assertEqual(self.trash([ids[2]],'purge')[0],200);self.assertFalse(p.exists());self.assertEqual(self.trash([ids[2]],'restore')[0],400)
 def test_invalid_batch_is_atomic_and_same_names_not_confused(self):
  ids=self.ids();self.assertEqual(self.trash([ids[0],'missing'])[0],400);self.assertEqual(image_trash.read(s.DATA),{});self.trash([ids[1]]);self.assertNotIn(ids[2],image_trash.read(s.DATA))