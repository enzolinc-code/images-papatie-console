import unittest,tempfile,io
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import server as s
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        (s.ROOT/"qa").mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=s.ROOT/"qa")
        self.old=(s.DATA,s.ASSETS,s.JOBS)
        s.DATA=Path(self.tmp.name);s.ASSETS={};s.JOBS={}
        b=io.BytesIO();Image.new("RGBA",(90,120),(200,100,80,255)).save(b,format="PNG")
        self.ref=s.register(b.getvalue(),"人物.jpg")
        b=io.BytesIO();im=Image.new("RGBA",(90,120));im.paste((200,100,80,255),(15,20,75,100));im.save(b,format="PNG")
        self.prod=s.register(b.getvalue(),"透明.png","product")
        self.scenes=[s.register(b.getvalue(),f"场景{i}","scene") for i in range(3)]
    def tearDown(self):
        s.DATA,s.ASSETS,s.JOBS=self.old;self.tmp.cleanup()
    def test_pose_tasks_have_distinct_prompts_and_full_margin(self):
        tasks=s.make_plan({"mode":"poses","source":self.ref["id"],"poses":["chin","edge","heart","cross"]})
        self.assertEqual(len(tasks),4);self.assertEqual(len(set(t["prompt"] for t in tasks)),4)
        self.assertTrue(all("15%" in t["prompt"] and "透明" in t["prompt"] for t in tasks))
    def test_scene_pairing_counts_and_reference_order(self):
        b={"mode":"scenes","scene_engine":"ai","products":[self.prod["id"],self.prod["id"]],"scenes":[a["id"] for a in self.scenes]}
        with self.assertRaises(ValueError):s.make_plan(b)
        p2=s.register(s.asset_path(self.prod["id"]).read_bytes(),"第二立牌","product")
        b["products"]=[self.prod["id"],p2["id"]]
        tasks=s.make_plan(b);self.assertEqual(len(tasks),3)
        self.assertEqual(tasks[0]["refs"],[self.scenes[0]["id"],self.prod["id"]])
        b["strategy"]="all";self.assertEqual(len(s.make_plan(b)),6)
    def test_opaque_product_rejected(self):
        with self.assertRaises(ValueError):s.make_plan({"mode":"scenes","scene_engine":"ai","products":[self.ref["id"]],"scenes":[self.scenes[0]["id"]]})
        with self.assertRaises(ValueError):s.make_plan({"mode":"poses","source":self.ref["id"],"poses":["chin","chin"]})
    def test_native_alpha_not_rematted(self):
        folder=s.DATA/"output";folder.mkdir()
        with patch.object(s,"run_command",side_effect=AssertionError("must not rematte")):
            path,edge=s.transparent(s.asset_path(self.prod["id"]),folder)
        im=Image.open(path);self.assertEqual(im.size,(218,248));self.assertEqual(im.mode,"RGBA")
        self.assertEqual(im.getpixel((84,89)),(200,100,80,255));self.assertFalse(edge)
    def test_submission_idempotency(self):
        b={"nonce":"same-request-123456","mode":"cutout","source":self.prod["id"]}
        with patch.object(s.Q,"put") as put:
            a=s.create_job(b);c=s.create_job(b)
        self.assertEqual(a["id"],c["id"]);self.assertEqual(put.call_count,1)
    def test_local_failure_keeps_raw(self):
        folder=s.DATA/"failure";folder.mkdir();raw=folder/"raw.png"
        Image.new("RGB",(80,80),"white").save(raw)
        with patch.object(s,"run_command",return_value=1):
            with self.assertRaises(ValueError):s.transparent(raw,folder)
        self.assertTrue(raw.exists())
    def test_missing_asset_rejected(self):
        with self.assertRaises(ValueError):s.asset_path("../config.json")
    def test_generate_reference_roles_and_no_duplicate_after_raw(self):
        b={"mode":"scenes","scene_engine":"ai","products":[self.prod["id"]],"scenes":[self.scenes[0]["id"]]}
        task=s.make_plan(b)[0];folder=s.DATA/"bridge-test";folder.mkdir()
        seen=[]
        def runner(cmd,folder,timeout,channel="3"):
            seen.append(cmd)
            Image.new("RGB",(128,128),"gray").save(folder/"raw.png")
            return 0
        with patch.object(s,"run_command",side_effect=runner):
            first=s.generate(task,folder);second=s.generate(task,folder)
        self.assertEqual(first,second);self.assertEqual(len(seen),1)
        refs=[seen[0][i+1] for i,arg in enumerate(seen[0][:-1]) if arg=="--image"]
        self.assertEqual(refs,[str(s.asset_path(self.scenes[0]["id"])),str(s.asset_path(self.prod["id"]))])
    def test_timeout_is_uncertain_not_automatic_retry(self):
        folder=s.DATA/"timeout";folder.mkdir()
        task=s.make_plan({"mode":"poses","source":self.ref["id"],"poses":["heart"]})[0]
        with patch.object(s,"run_command",return_value=None) as run:
            with self.assertRaises(RuntimeError):s.generate(task,folder)
        self.assertEqual(run.call_count,1)
    def test_scene_modes_match_flat_and_car(self):
        self.assertIn("桌垫",s.scene_prompt("flat",""))
        self.assertIn("挡风玻璃",s.scene_prompt("car",""))
        self.assertIn("最高头饰",s.scene_prompt("auto",""))

    def test_channel4_plan_and_model_are_fixed(self):
        task=s.make_plan({"mode":"poses","source":self.ref["id"],"poses":["heart"],"channel":"4"})[0]
        self.assertEqual(task["channel"],"4")
        self.assertEqual(task["model"],"gpt-image-2.5-cdn")
        folder=s.DATA/"ch4";folder.mkdir()
        def runner(cmd,folder,timeout,channel="3"):
            self.assertEqual(channel,"4")
            self.assertEqual(cmd[cmd.index("--model")+1],"gpt-image-2.5-cdn")
            Image.new("RGBA",(100,100),(200,100,80,0)).save(folder/"raw.png")
            return 0
        with patch.object(s,"run_command",side_effect=runner) as call:
            s.generate(task,folder)
        self.assertEqual(call.call_count,1)
    def test_channel4_uses_own_key_and_does_not_fallback(self):
        with patch.object(s,"channel_key",side_effect=lambda c:"fake-key-"+str(c)):
            self.assertEqual(s.environment("4")["CODEX_API_KEY"],"fake-key-4")
        with patch.object(s,"channel_key",side_effect=lambda c:"old-key" if str(c)=="3" else ""):
            with self.assertRaisesRegex(ValueError,"所选通道"):
                s.create_job({"nonce":"channel-4-no-key-1234","mode":"poses","source":self.ref["id"],"poses":["heart"],"channel":"4"})
    def test_invalid_channel_rejected(self):
        with self.assertRaises(ValueError):
            s.make_plan({"mode":"poses","source":self.ref["id"],"poses":["heart"],"channel":"5"})

if __name__=="__main__":unittest.main(verbosity=2)