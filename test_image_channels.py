import unittest,json,io,types,importlib.util
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import server as s
import image_channels
import test_workflow as fixture
spec=importlib.util.spec_from_file_location('apimart_test_bridge',Path(__file__).parent/'tools/apimart_bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
spec4=importlib.util.spec_from_file_location('xingqi_test_bridge',Path(__file__).parent/'tools/xingqi_bridge.py')
xingqi=importlib.util.module_from_spec(spec4);spec4.loader.exec_module(xingqi)
class ChannelTests(unittest.TestCase):
    setUp=fixture.WorkflowTests.setUp
    tearDown=fixture.WorkflowTests.tearDown
    def test_new_channel5_plans_and_bridge_route(self):
        t=s.make_plan({'mode':'poses','source':self.ref['id'],'poses':['chin'],'channel':'5'})[0]
        self.assertEqual(t['channel'],'5');self.assertEqual(t['model'],'gemini-nano-banana-2.1')
        folder=s.DATA/'bridge5';folder.mkdir();seen=[]
        def runner(cmd,folder,timeout,channel='3'):
            seen.append((cmd,channel));Image.new('RGB',(64,64),'red').save(folder/'raw.png');return 0
        with patch.object(s,'run_command',side_effect=runner):s.generate(t,folder);s.generate(t,folder)
        self.assertEqual(len(seen),1);self.assertEqual(seen[0][1],'5');self.assertTrue(any(str(x).endswith('apimart_bridge.py') for x in seen[0][0]))
    def test_repair_keeps_channel_and_model_snapshot(self):
        task=s.make_plan({'mode':'scenes','scene_engine':'ai','products':[self.prod['id']],'scenes':[self.scenes[0]['id']],'channel':'5'})[0]
        task.update(status='done',asset=self.prod['id'],model='frozen-original-model')
        s.JOBS['fixture-old']={'id':'fixture-old','tasks':[task]}
        for mode in ['correct_hands','correct_identity','correct_material','redo_scene']:
            body={'mode':mode,'job':'fixture-old','index':0,'channel':'5'}
            plan=s.make_plan(body);self.assertEqual(plan[0]['channel'],'5');self.assertEqual(plan[0]['model'],'frozen-original-model')
            with self.assertRaises(ValueError):s.make_plan(dict(body,channel='3'))
    def test_sample_continuation_keeps_model_snapshot(self):
        body={'mode':'scenes','scene_engine':'ai','products':[self.prod['id']],'scenes':[a['id'] for a in self.scenes],'sample_first':True,'channel':'5','nonce':'fixture-channel-five-sample'}
        with patch.object(s,'channel_key',return_value='fixture'),patch.object(image_channels,'preflight',return_value=None),patch.object(s.Q,'put'):
            job=s.create_job(body)
        job['tasks'][0].update(status='done',review='accepted',asset=self.prod['id'])
        for t in job['sample_remaining']:t['model']='original-queued-model'
        plan=s.make_plan({'mode':'continue_sample','sample':job['id'],'channel':'5'})
        self.assertEqual(len(plan),2);self.assertTrue(all(t['model']=='original-queued-model' for t in plan))
    def test_settings_switch_only_future_plans(self):
        cfg=s.DATA/'models.json';cfg.write_text(json.dumps({'model4':'banana-pro','model5':'gemini-nano-banana-2.1'}),encoding='utf-8')
        body={'mode':'poses','source':self.ref['id'],'poses':['chin'],'channel':'5'}
        with patch.dict(s.CFG,{'channel_settings_path':str(cfg)}):
            old=s.make_plan(body)[0];cfg.write_text(json.dumps({'model4':'banana-pro','model5':'gpt-image-2.5-ext'}),encoding='utf-8')
            new=s.make_plan(body)[0]
        self.assertEqual(old['model'],'gemini-nano-banana-2.1');self.assertEqual(new['model'],'gpt-image-2.5-ext')
    def test_channel5_key_does_not_fall_back_to_channel3(self):
        with patch.object(image_channels,'user_env',side_effect=lambda n:'fixture' if n=='CODEX_API_KEY' else ''):
            self.assertFalse(s.channel_key('5'));self.assertTrue(s.channel_key('3'));self.assertFalse(s.channel_key('unknown'))
    def args(self):
        p=s.DATA/'prompt.txt';p.write_text('test',encoding='utf-8')
        return types.SimpleNamespace(out=str(s.DATA/'result.png'),prompt_file=str(p),model='gemini-nano-banana-2.1',size='4:3',timeout=5,image=[])
    def test_channel5_uncertain_submission_cannot_repeat_post(self):
        calls=[]
        class Op:
            def open(self,req,**kwargs):calls.append(req);raise TimeoutError()
        args=self.args()
        with patch.dict(bridge.os.environ,{'IMG4_API_KEY':'fixture'}):
            with self.assertRaises(RuntimeError):bridge.run(args,Op())
            with self.assertRaises(RuntimeError):bridge.run(args,Op())
        self.assertEqual(len(calls),1)
    def test_channel5_receipt_resumes_poll_and_download_without_post(self):
        args=self.args();body=bridge.payload(args);digest=bridge.hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        bridge.atomic(s.DATA/'channel5-task.json',{'task_id':'fixture-task','request_hash':digest,'model':args.model,'phase':'submitted'})
        im=io.BytesIO();Image.new('RGBA',(32,32),(30,40,50,128)).save(im,format='PNG');raw=im.getvalue();calls=[]
        class R:
            def __init__(self,data):self.data=data
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return self.data
        class Op:
            def open(self,req,**kwargs):
                calls.append(req)
                if isinstance(req,str):return R(raw)
                if req.data:raise AssertionError('No new POST permitted')
                return R(json.dumps({'data':{'status':'completed','result':{'images':[{'url':['https://example.invalid/image.png']}]}}}).encode())
        with patch.dict(bridge.os.environ,{'IMG4_API_KEY':'fixture'}):bridge.run(args,Op())
        self.assertEqual(len(calls),2)
        with Image.open(args.out) as result:self.assertEqual(result.mode,'RGBA')
        self.assertEqual(json.loads((s.DATA/'channel5-task.json').read_text('utf-8'))['phase'],'downloaded')
    def test_nano_payload_omits_gpt_version_and_preserves_ratio(self):
        p=bridge.payload(self.args());self.assertNotIn('version',p);self.assertEqual(p['size'],'4:3');self.assertEqual(p['model'],'gemini-nano-banana-2.1')

    def test_account_rejection_prevents_queued_job(self):
        body={'mode':'poses','source':self.ref['id'],'poses':['chin'],'channel':'5','nonce':'fixture-balance-not-enqueued'}
        with patch.object(s,'channel_key',return_value='fixture'),patch.object(image_channels,'preflight',side_effect=image_channels.ChannelUnavailable('通道5余额不足')),patch.object(s.Q,'put') as queued:
            with self.assertRaisesRegex(ValueError,'余额不足'):s.create_job(body)
        self.assertFalse(s.JOBS);queued.assert_not_called()
    def test_preflight_balance_message_is_sanitized_and_get_only(self):
        import urllib.error
        calls=[]
        class Op:
            def open(self,req,**kw):
                calls.append(req)
                raise urllib.error.HTTPError(req.full_url,402,'payment',{},io.BytesIO(b'{"error":{"message":"[token_id=private] insufficient balance (current: 0.031500 USD, required: 0.050000 USD) request id private"}}'))
        with patch.object(image_channels,'key',return_value='fixture'):
            with self.assertRaisesRegex(ValueError,'0.031500') as error:image_channels.preflight('5',{},Op())
        self.assertNotIn('private',str(error.exception));self.assertEqual(calls[0].get_method(),'GET')
    def test_bridge_rejection_receipt_preserves_reason_without_repost(self):
        import urllib.error
        args=self.args();calls=[]
        class Op:
            def open(self,req,**kw):
                calls.append(req)
                raise urllib.error.HTTPError(req.full_url,402,'payment',{},io.BytesIO(b'insufficient balance (current: 0.031500 USD, required: 0.050000 USD)'))
        with patch.dict(bridge.os.environ,{'IMG4_API_KEY':'fixture'}):
            with self.assertRaisesRegex(ValueError,'余额不足'):bridge.run(args,Op())
            with self.assertRaisesRegex(ValueError,'余额不足'):bridge.run(args,Op())
        self.assertEqual(len(calls),1);record=json.loads((s.DATA/'channel5-task.json').read_text('utf-8'));self.assertEqual(record['phase'],'rejected');self.assertEqual(record['http_status'],402)


    def test_banana_channel4_uses_media_adapter(self):
        task=s.make_plan({'mode':'poses','source':self.ref['id'],'poses':['chin'],'channel':'4'})[0]
        folder=s.DATA/'route4';folder.mkdir();seen=[]
        def runner(cmd,folder,timeout,channel='3'):
            seen.append(cmd);Image.new('RGB',(64,64),'red').save(folder/'raw.png');return 0
        with patch.object(s,'run_command',side_effect=runner):s.generate(task,folder)
        self.assertTrue(any(str(x).endswith('xingqi_bridge.py') for x in seen[0]))
    def test_banana_payload_has_camel_case_params_and_data_refs(self):
        args=self.args();args.model='banana-pro';args.image=[str(s.asset_path(self.ref['id']))]
        with patch.dict(xingqi.os.environ,{'CHANNEL4_RESOLUTION':'1K'}):p=xingqi.payload(args)
        self.assertEqual(p['model'],'banana-pro');self.assertEqual(p['params']['aspectRatio'],'4:3');self.assertEqual(p['params']['imageSize'],'1K');self.assertTrue(p['params']['images'][0].startswith('data:image/png;base64,'));self.assertNotIn('quality',p);self.assertNotIn('size',p)
    def test_xingqi_async_submission_and_poll_format(self):
        args=self.args();args.model='banana-pro';calls=[];im=io.BytesIO();Image.new('RGB',(16,16),'blue').save(im,format='PNG');raw=im.getvalue()
        class R:
            def __init__(self,b):self.b=b
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return self.b
        class Op:
            def open(self,req,**kw):
                calls.append(req)
                if isinstance(req,str):return R(raw)
                if req.data:
                    self.assert_submit(req)
                    return R(json.dumps({'code':200,'data':{'task_id':123456}}).encode())
                return R(json.dumps({'task_id':123456,'is_final':True,'state':'success','result_url':'https://example.invalid/result.png'}).encode())
            def assert_submit(self,req):
                assert req.full_url.endswith('/v1/media/generate');assert json.loads(req.data)['params']['aspectRatio']=='4:3'
        with patch.dict(xingqi.os.environ,{'CHANNEL4_API_KEY':'fixture','CHANNEL4_API_URL':'https://example.invalid'}):xingqi.run(args,Op());xingqi.run(args,Op())
        self.assertEqual(len(calls),3);self.assertTrue(calls[1].full_url.endswith('/v1/skills/task-status?task_id=123456'));self.assertEqual(json.loads((s.DATA/'result-channel4-task.json').read_text('utf-8'))['phase'],'downloaded')
    def test_xingqi_sync_url_response_is_supported(self):
        self.assertEqual(xingqi.result_url({'data':[{'url':'https://example.invalid/a.png'}]}),'https://example.invalid/a.png')
    def test_xingqi_rejected_submission_is_not_repeated(self):
        import urllib.error
        args=self.args();args.model='banana-pro';calls=[]
        class Op:
            def open(self,req,**kw):calls.append(req);raise urllib.error.HTTPError(req.full_url,400,'bad request',{},io.BytesIO(b'bad params'))
        with patch.dict(xingqi.os.environ,{'CHANNEL4_API_KEY':'fixture'}):
            with self.assertRaises(ValueError):xingqi.run(args,Op())
            with self.assertRaises(ValueError):xingqi.run(args,Op())
        self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
