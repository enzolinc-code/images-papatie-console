import base64,io,json,threading,tempfile,unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from PIL import Image
from tools import image_api as api

class ClientTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parent/'qa';root.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=root);self.root=Path(self.tmp.name);self.calls=[];self.status=200
        b=io.BytesIO();Image.new('RGBA',(32,32),(12,34,56,100)).save(b,format='PNG');self.image=b.getvalue();self.ref=self.root/'参考.png';self.ref.write_bytes(self.image)
        case=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                data=self.rfile.read(int(self.headers['Content-Length']));case.calls.append((self.path,self.headers,data))
                self.send_response(case.status);self.send_header('Content-Type','application/json');self.end_headers()
                value={'data':[{'b64_json':base64.b64encode(case.image).decode()}]} if case.status==200 else {'error':{'message':'provider-test-key failed'}}
                self.wfile.write(json.dumps(value).encode())
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.http.server_port)
    def tearDown(self):self.http.shutdown();self.http.server_close();self.thread.join();self.tmp.cleanup()
    def test_json_generation_preserves_alpha(self):
        out=api.generate(self.base,'provider-test-key','test',[],self.root/'out.png')
        self.assertEqual(self.calls[0][0],'/v1/images/generations');self.assertEqual(json.loads(self.calls[0][2])['n'],1)
        with Image.open(out) as im:self.assertEqual(im.getchannel('A').getextrema(),(100,100))
    def test_multipart_with_real_crlf_and_reference_content(self):
        api.generate(self.base,'provider-test-key','动作',[self.ref],self.root/'out.png')
        path,headers,body=self.calls[0]
        self.assertEqual(path,'/v1/images/edits');self.assertIn(b'\r\nContent-Disposition:',body);self.assertNotIn(b'\\r\\n',body)
        self.assertIn(self.image,body);self.assertIn('multipart/form-data',headers['Content-Type'])
    def test_multiple_references_preserve_order(self):
        body,_=api.multipart({'prompt':'x'},[self.ref,self.ref]);self.assertEqual(body.count(b'name="image[]"'),2)
    def test_errors_are_redacted_and_not_retried(self):
        self.status=400
        with self.assertRaises(RuntimeError) as c:api.generate(self.base,'provider-test-key','test',[],self.root/'out.png')
        self.assertEqual(len(self.calls),1);self.assertNotIn('provider-test-key',str(c.exception));self.assertFalse((self.root/'out.png').exists())
    def test_endpoint_does_not_duplicate_v1(self):self.assertEqual(api.endpoint(self.base+'/v1/',True),self.base+'/v1/images/edits')
if __name__=='__main__':unittest.main()
