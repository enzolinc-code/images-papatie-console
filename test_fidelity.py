import sys,unittest,tempfile,io,base64,json
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parent))
import server as s
import fidelity as f

class FidelityTests(unittest.TestCase):
    def setUp(self):
        (s.ROOT/"qa").mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=s.ROOT/"qa")
        self.root=Path(self.temp.name);self.old=(s.DATA,s.ASSETS,s.JOBS)
        s.DATA=self.root;s.ASSETS={};s.JOBS={}
        b=io.BytesIO();Image.new("RGB",(240,240),(30,50,80)).save(b,format="PNG")
        self.scene=s.register(b.getvalue(),"场景.png","scene")
        im=Image.new("RGBA",(80,100))
        d=ImageDraw.Draw(im);d.rectangle((10,10,69,59),fill=(210,80,40,255))
        d.rectangle((15,60,24,88),fill=(50,190,90,255));d.rectangle((42,60,51,88),fill=(50,190,90,255))
        b=io.BytesIO();im.save(b,format="PNG")
        self.product=s.register(b.getvalue(),"原始人物.png","product")
    def tearDown(self):
        s.DATA,s.ASSETS,s.JOBS=self.old;self.temp.cleanup()
    def template(self,**kw):
        return f.Store(s.DATA,s.asset_path).save({"scene":self.scene["id"],"quad":[[.2,.15],[.8,.15],[.8,.85],[.2,.85]],"aspect":60/79,"shadow":0,"rim":0,**kw})
    def test_ready_requires_clean_background_approval(self):
        self.template()
        with self.assertRaisesRegex(ValueError,"确认干净背景"):
            s.make_plan({"mode":"scenes","products":[self.product["id"]],"scenes":[self.scene["id"]]})
        self.template(use_original=True);store=f.Store(s.DATA,s.asset_path);store.approve(self.scene["id"])
        tasks=s.make_plan({"mode":"scenes","products":[self.product["id"]],"scenes":[self.scene["id"]],"channel":"4"})
        self.assertEqual(tasks[0]["kind"],"fidelity");self.assertEqual(tasks[0]["channel"],"local")
    def test_polygon_validation_rejects_crossed_quad(self):
        with self.assertRaises(ValueError):f.quad([[0,0],[1,1],[1,0],[0,1]])
    def test_local_worker_never_calls_model_and_preserves_product(self):
        self.template(use_original=True);f.Store(s.DATA,s.asset_path).approve(self.scene["id"])
        source=s.asset_path(self.product["id"]).read_bytes()
        class LocalQueue:
            def __init__(self):self.items=[]
            def put(self,item):self.items.append(item)
            def get(self):
                if not self.items:raise SystemExit
                return self.items.pop(0)
            def task_done(self):pass
        with patch.object(s,"Q",LocalQueue()),patch.object(s,"generate",side_effect=AssertionError("no image API")),patch.object(s,"channel_key",return_value=""):
            j=s.create_job({"nonce":"fidelity-local-job-1234","mode":"scenes","products":[self.product["id"]],"scenes":[self.scene["id"]],"channel":"4"})
            with self.assertRaises(SystemExit):s.worker()
        self.assertEqual(j["status"],"done")
        self.assertEqual(s.asset_path(self.product["id"]).read_bytes(),source)
        proof=json.loads((s.DATA/"jobs"/j["id"]/"1/fidelity-proof.json").read_text(encoding='utf-8'))
        self.assertEqual(proof["method"],"original_png_homography")
    def test_identity_transform_preserves_opaque_pixels_and_gaps(self):
        t={"quad":[[.25,.25],[.5,.25],[.5,.25+79/240],[.25,.25+79/240]],"aspect":60/79,"shadow":0,"rim":0}
        output=self.root/"identity.png";f.render(s.asset_path(self.scene["id"]),s.asset_path(self.product["id"]),t,output)
        im=Image.open(output)
        self.assertEqual(im.getpixel((70,70)),(210,80,40))
        self.assertEqual(im.getpixel((80,120)),(30,50,80)) # gap between the two fingers
    def test_background_cleanup_preserves_every_pixel_outside_mask(self):
        bg=s.asset_path(self.scene["id"]);generated=self.root/"generated.png";mask=self.root/"mask.png";out=self.root/"clean.png"
        Image.new("RGB",(240,240),(200,100,10)).save(generated)
        m=Image.new("L",(240,240));ImageDraw.Draw(m).rectangle((80,80,120,120),fill=255);m.save(mask)
        f.merge_cleanup(bg,generated,mask,out)
        im=Image.open(out)
        for point in [(0,0),(79,79),(121,120),(239,239)]:self.assertEqual(im.getpixel(point),(30,50,80))
        self.assertEqual(im.getpixel((100,100)),(200,100,10))
    def test_same_scene_bytes_reuse_template(self):
        self.template(use_original=True);f.Store(s.DATA,s.asset_path).approve(self.scene["id"])
        copy=s.register(s.asset_path(self.scene["id"]).read_bytes(),"改名场景.png","scene")
        self.assertTrue(f.Store(s.DATA,s.asset_path).ready(copy["id"]))
    def test_cleanup_input_does_not_contain_product(self):
        m=Image.new("RGBA",(240,240));ImageDraw.Draw(m).rectangle((10,10,40,40),fill="white")
        b=io.BytesIO();m.save(b,format="PNG")
        self.template(mask=base64.b64encode(b.getvalue()).decode())
        t=s.make_plan({"mode":"background","scene":self.scene["id"],"channel":"4"})[0]
        self.assertEqual(t["kind"],"background")
        self.assertNotIn(self.product["id"],t["refs"])
        self.assertEqual(len(t["refs"]),2)
    def test_changed_mask_invalidates_clean_approval(self):
        self.template(use_original=True);f.Store(s.DATA,s.asset_path).approve(self.scene["id"])
        m=Image.new("RGBA",(240,240));ImageDraw.Draw(m).rectangle((10,10,40,40),fill="white")
        b=io.BytesIO();m.save(b,format="PNG")
        self.template(mask=base64.b64encode(b.getvalue()).decode())
        self.assertFalse(f.Store(s.DATA,s.asset_path).ready(self.scene["id"]))

    def test_product_anchor_is_reused_across_scene_templates(self):
        self.template(product=self.product["id"],source_anchor=.87,use_original=True)
        store=f.Store(s.DATA,s.asset_path)
        self.assertEqual(store.anchors[f.digest(str(s.asset_path(self.product["id"])))],.87)
        t=store.get(self.scene["id"])
        self.assertEqual(t["product_anchors"][f.digest(str(s.asset_path(self.product["id"])))],.87)
        store.approve(self.scene["id"])
        t=store.get(self.scene["id"])
        p=self.root/"anchored.png";f.render(s.asset_path(self.scene["id"]),s.asset_path(self.product["id"]),t,p)
        self.assertEqual(f.image_size(p),(240,240))

if __name__=="__main__":unittest.main(verbosity=2)