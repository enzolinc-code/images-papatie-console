from __future__ import annotations
import base64,io,json,mimetypes,os,queue,re,secrets,subprocess,sys,threading,time,zipfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,unquote
from uuid import uuid4
from PIL import Image,ImageOps
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import fidelity
DATA=Path(os.environ.get("PAPAPAI_DATA",str(ROOT/"data"))).resolve(); DATA.mkdir(parents=True,exist_ok=True)
CFG={"port":8796,"endpoint":"https://agent3.shyfai.cn","model":"gpt-image-2","channel4_model":"gpt-image-2.5-cdn","timeout":600,"matting_runtime":"runtime/matting"}
if (ROOT/"config.json").exists():CFG.update(json.loads((ROOT/"config.json").read_text(encoding="utf-8")))
CFG["python"]=sys.executable
CFG["port"]=int(os.environ.get("PAPAPAI_PORT",CFG["port"]))
CFG["matting_runtime"]=str((ROOT/CFG["matting_runtime"]).resolve())

LOCK=threading.RLock(); Q=queue.Queue()
POSES=[
{"id":"chin","name":"托腮垂手","hint":"单手轻托脸颊，另一前臂搭边，手腕与五指自然垂落。"},
{"id":"both","name":"双手托腮","hint":"双肘放同一水平承托处，左右手分别轻托脸颊，头微歪，前臂呈自然V形。"},
{"id":"edge","name":"双手搭边","hint":"双肘向两侧展开，前臂横搭同一水平边沿，双手腕朝前弯曲，十指自然垂落，头抬起，不托腮。"},
{"id":"heart","name":"单手比心","hint":"一前臂横搭、手自然垂落；另一手抬至脸旁，用拇指与食指交叉比小指心，其余三指收拢。"},
{"id":"wave","name":"搭边挥手","hint":"一前臂横搭边沿，手自然垂落；另一肘部有承托，手举至脸旁轻挥，五指自然分开。"},
{"id":"cross","name":"交叠搭臂","hint":"两条前臂放低、松弛交叠横搭在同一水平边沿，双手均在低处，不靠近脸部。上身前倾。"},
{"id":"lean","name":"侧倾伏靠","hint":"上身轻前倾，头向一侧低倾，一手支撑太阳穴下方；另一前臂低位横放，手放松。"},
{"id":"pillow","name":"侧枕手臂","hint":"两条前臂并排横放在同一水平位置；头低下侧倾，脸颊真实枕在前臂上。两手均保持低位，绝不抬手托腮。"}]
POSE_MAP={p["id"]:p for p in POSES}
def atomic(path,obj):
    tmp=path.with_suffix(".writing");tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8");tmp.replace(path)
def load(path,default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
ASSETS=load(DATA/"assets.json",{})
JOBS={}
for folder in (DATA/"jobs").glob("*") if (DATA/"jobs").exists() else []:
    try:
        j=load(folder/"job.json",{})
        if j.get("status") in ("queued","running"):
            j["status"]="paused"
            for t in j["tasks"]:
                if t["status"]=="running":t["status"]="uncertain";t["message"]="服务中断；请核对远端任务与费用，不自动重复提交。"
            atomic(folder/"job.json",j)
        JOBS[j["id"]]=j
    except (OSError,ValueError,KeyError):pass
def save(j):
    atomic(DATA/"jobs"/j["id"]/"job.json",j)
def asset_path(aid):
    if aid not in ASSETS:raise ValueError("图片不存在，请重新选择")
    p=(DATA/ASSETS[aid]["file"]).resolve()
    if not p.is_relative_to(DATA.resolve()) or not p.is_file():raise ValueError("图片文件不可用")
    return p
def register(raw,name,kind="reference"):
    with Image.open(io.BytesIO(raw)) as src:
        if src.width*src.height>20_000_000:raise ValueError("图片超过2000万像素，请先缩小")
        im=ImageOps.exif_transpose(src).convert("RGBA");im.load()
    aid=uuid4().hex
    folder=DATA/"assets";folder.mkdir(exist_ok=True)
    im.save(folder/(aid+".png"))
    alpha=im.getchannel("A")
    obj={"id":aid,"name":str(name)[:120],"kind":kind,"width":im.width,"height":im.height,
         "transparent":alpha.getextrema()[0]<255,"file":"assets/"+aid+".png","url":"/media/"+aid,"created":time.time()}
    with LOCK:
        ASSETS[aid]=obj;atomic(DATA/"assets.json",ASSETS)
    return obj
def fidelity_status():
    store=fidelity.Store(DATA,asset_path);result={}
    for aid,a in ASSETS.items():
        if a.get("kind")!="scene":continue
        try:result[aid]={"ready":store.ready(aid),"calibrated":bool(store.get(aid))}
        except (OSError,ValueError):result[aid]={"ready":False,"calibrated":False}
    return result

def snapshot():
    with LOCK:
        return {"assets":list(ASSETS.values()),"jobs":list(reversed(list(JOBS.values()))),"poses":POSES,
                "health":health(),"scene_templates":fidelity_status()}
def channel_key(channel):
    name="CHANNEL4_API_KEY" if str(channel)=="4" else "CODEX_API_KEY"
    if os.environ.get(name):return os.environ[name]
    if str(channel)=="4":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,"Environment") as k:return winreg.QueryValueEx(k,name)[0]
        except (OSError,ImportError):pass
    return os.environ.get(name,"")

def health():
    return {"version":"papapai-studio-1.0.0","channel4":bool(channel_key("4")),"key":bool(channel_key("3")),"endpoint":CFG["endpoint"],"model":CFG["model"],
            "matting":(Path(CFG["matting_runtime"])/"BiRefNet_HR-matting.onnx").is_file(),
            "imageTool":(ROOT/"tools/image_api.py").is_file(),"root":str(ROOT)}
def pose_prompt(p,extra):
    return ("参考图是人物造型的唯一依据。制作写实上半身趴趴立牌可印刷图稿，保留同一人物面貌、发型、服装花纹、配饰及材质；"
            "按指定动作重构姿势。只要一个人物及完整双臂双手，不画下半身；只出现两只手，手指解剖自然。"
            "人物整体缩小居中，宽高均不超过画布70%，四周至少留15%透明余量；头发、发饰、肘部、衣袖和每个指尖全部完整入镜。"
            "输出真正透明背景PNG及alpha，不画棋盘格、白底、灰底、承托线、桌子、显示器、亚克力描边、底座、文字或投影。"
            "发丝、绒毛和指缝干净无白边、灰边及白色色块，保留自然半透明细节。动作："+p["hint"]+"\n补充："+extra)
def scene_prompt(mode,extra):
    base=("图1是场景底图，图2是唯一的透明人物立牌图稿。只把图1原有的亚克力立牌及其配套印刷人形、宠物图案替换为图2。"
          "严格保留图2人物五官、姿势、服饰、发型、珠宝与轮廓，不增加或复制肢体。保留图1背景、机位、透视、光向、色温及屏幕原内容。"
          "成品是薄而硬的平面异形透明亚克力印刷品，有窄而清透切边、少量局部反射折射和真实接触阴影。"
          "按场景中的原尺寸和角度安装，最高头饰至最低指尖完整入镜；指缝透明见背景。像真实手机实物拍摄，不做真人、不漂浮，"
          "不要旧人物残影、厚白边、白底贴片、新增文字或旁观人手。")
    modes={"auto":"遵循图1原来的摆放方式；监视器上沿挂靠、车内屏幕安装或桌垫平放按原图判断，不把场景换掉。",
           "monitor":"衣袖底缘和肘部搭在显示器上沿，垂手在屏幕前方，接触有遮挡压影。",
           "car":"保留车内屏幕、挡风玻璃及车外环境，按车内自然光匹配，不添加办公桌。",
           "flat":"保留俯拍桌垫场景，立牌作为平面薄片平放其上，有贴地阴影和局部反光，不添加显示器。"}
    return base+modes[mode]+"\n补充："+extra
def make_plan(body):
    mode=body.get("mode");extra=str(body.get("extra","")).strip()
    if len(extra)>3000:raise ValueError("补充描述最多3000字")
    tasks=[]
    if mode=="poses":
        source=body.get("source");asset_path(source)
        ids=body.get("poses",[])
        if not isinstance(ids,list) or not 1<=len(ids)<=8 or len(set(ids))!=len(ids):raise ValueError("请选择1至8种姿势")
        for pid in ids:
            if pid not in POSE_MAP:raise ValueError("姿势无效")
            p=POSE_MAP[pid];tasks.append({"name":p["name"],"refs":[source],"prompt":pose_prompt(p,extra),"size":"1:1","kind":"cutout"})
    elif mode=="cutout":
        source=body.get("source");asset_path(source)
        tasks=[{"name":"透明抠图","refs":[source],"prompt":"","size":"1:1","kind":"local"}]
    elif mode=="background":
        scene=body.get("scene");asset_path(scene)
        store=fidelity.Store(DATA,asset_path);template=store.get(scene)
        if not template or not template.get("mask_hash"):raise ValueError("请先涂抹原立牌区域并保存")
        if store.ready(scene):raise ValueError("此背景已确认，可直接复用，无需重复清理")
        mask=store.folder/(template["id"]+"-mask.png")
        base=Image.open(asset_path(scene)).convert("RGB");m=Image.open(mask).convert("L")
        guide=Image.composite(Image.blend(base,Image.new("RGB",base.size,"red"),.5),base,m)
        buf=io.BytesIO();guide.save(buf,format="PNG");a=register(buf.getvalue(),"清理区域参考.png","mask_guide")
        prompt="图1是场景原图，图2红色覆盖区域为需要清理的旧立牌。移除该区域内原人物亚克力立牌及其配套印刷图案、接触阴影，合理补全被遮挡的显示器、墙面或桌垫背景。不要新人物、不要新立牌、不要文字，不改变红色范围之外的场景。只恢复干净背景。"
        ratio=base.width/base.height
        tasks=[{"name":"清理旧立牌背景","refs":[scene,a["id"]],"prompt":prompt,"size":"1:1" if .88<ratio<1.14 else ("3:4" if ratio<1 else "4:3"),"kind":"background","scene":scene,"template_id":template["id"],"mask_hash":template["mask_hash"]}]
    elif mode=="scenes":
        products=body.get("products",[]);scenes=body.get("scenes",[])
        if not products or not scenes:raise ValueError("请选择透明立牌和场景")
        if len(set(products))!=len(products) or len(set(scenes))!=len(scenes):raise ValueError("不能重复选择图片")
        for aid in products:
            asset_path(aid)
            if not ASSETS[aid]["transparent"]:raise ValueError("场景替换请先选择有透明通道的PNG立牌")
        for aid in scenes:asset_path(aid)
        sm=body.get("scene_mode","auto")
        if sm not in ("auto","monitor","car","flat"):raise ValueError("场景模式无效")
        strategy=body.get("strategy","rotate")
        if strategy not in ("rotate","all"):raise ValueError("批量方式无效")
        pairs=[(p,s) for p in products for s in scenes] if strategy=="all" else [(products[i%len(products)],s) for i,s in enumerate(scenes)]
        for prod,scene in pairs:
            item=ASSETS[scene];ratio=item["width"]/item["height"]
            size="1:1" if .88<ratio<1.14 else ("3:4" if ratio<1 else "4:3")
            engine=body.get("scene_engine","fidelity")
            if engine not in ("fidelity","ai"):raise ValueError("场景生成方式无效")
            if engine=="fidelity":
                store=fidelity.Store(DATA,asset_path);template=store.get(scene)
                if not store.ready(scene):raise ValueError("请先标定并确认干净背景："+item["name"])
                tasks.append({"name":item["name"],"refs":[template["clean_asset"],prod],"kind":"fidelity","template":json.loads(json.dumps(template)),"scene":scene,"prompt":"","size":size})
            else:
                tasks.append({"name":item["name"],"refs":[scene,prod],"prompt":scene_prompt(sm,extra),"size":size,"kind":"scene"})
    else:raise ValueError("任务类型无效")
    if not 1<=len(tasks)<=60:raise ValueError("每批最多60张，请减少选择")
    channel=str(body.get("channel","3"))
    if channel not in ("3","4"):raise ValueError("请选择通道3或4")
    for task in tasks:
        task["channel"]="local" if task["kind"]=="fidelity" else channel
        task["model"]=None if task["kind"]=="fidelity" else (CFG["channel4_model"] if channel=="4" else CFG["model"])
    return tasks
def environment(channel="3"):
    env=dict(os.environ)
    env["CODEX_API_URL"]=CFG.get("channel4_endpoint",CFG["endpoint"]) if channel=="4" else CFG["endpoint"]
    env["CODEX_API_KEY"]=channel_key(channel)
    env["TMP"]=str(DATA);env["TEMP"]=str(DATA)
    env["PYTHONDONTWRITEBYTECODE"]="1";env["PYTHONIOENCODING"]="utf-8"
    return env
def run_command(cmd,folder,timeout,channel="3"):
    try:
        r=subprocess.run(cmd,capture_output=True,encoding="utf-8",errors="replace",env=environment(channel),timeout=timeout,
                         creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        log=r.stdout+"\n"+r.stderr
        key=channel_key(channel)
        if key:log=log.replace(key,"[redacted]")
        (folder/"process.log").write_text(log,encoding="utf-8")
        return r.returncode
    except subprocess.TimeoutExpired:
        return None
def generate(t,folder):
    raw=folder/"raw.png"
    if raw.exists():return raw
    prompt=folder/"prompt.txt";prompt.write_text(t["prompt"],encoding="utf-8")
    cmd=[CFG["python"],"-X","utf8",str(ROOT/"tools/image_api.py"),"--prompt-file",str(prompt),
         "--out",str(raw),"--tmp-dir",str(folder),"--output-dir",str(folder),"--size",t["size"],"--n","1","--format","png","--model",t.get("model",(CFG["channel4_model"] if t.get("channel")=="4" else CFG["model"]))]
    for ref in t["refs"]:cmd+=["--image",str(asset_path(ref))]
    code=run_command(cmd,folder,int(CFG["timeout"]),t.get("channel","3"))
    if code!=0 or not raw.exists():
        raise RuntimeError("所选通道未取得成图，状态需核实；请先核对远端任务与费用，不自动重试。")
    return raw
def transparent(raw,folder):
    with Image.open(raw) as src:
        im=src.convert("RGBA");im.load()
    if im.getchannel("A").getextrema()[0]==255:
        target=folder/"matting.png"
        if not target.exists():
            cmd=[CFG["python"],"-X","utf8",str(ROOT/"tools/cutout.py"),str(raw),str(target),"--runtime",CFG["matting_runtime"]]
            code=run_command(cmd,folder,1200)
            if code!=0 or not target.exists():raise ValueError("本地抠图失败；原始生图已保留，可单独续做抠图。")
        im=Image.open(target).convert("RGBA")
    alpha=im.getchannel("A").point(lambda x:0 if x<4 else x)
    im.putalpha(alpha)
    if alpha.getbbox() is None:raise ValueError("透明结果为空，需人工检查")
    bbox=alpha.getbbox()
    # Native canvas may put the subject at an edge: disclose; padding never restores missing pixels.
    edge=bbox[0]<=1 or bbox[1]<=1 or bbox[2]>=im.width-1 or bbox[3]>=im.height-1
    result=Image.new("RGBA",(im.width+128,im.height+128));result.alpha_composite(im,(64,64))
    p=folder/"result.png";result.save(p)
    with Image.open(p) as checked:
        checked.load()
        if checked.mode!="RGBA" or checked.getchannel("A").getextrema()[0]!=0:raise ValueError("透明PNG校验失败")
    return p,edge
def worker():
    while True:
        jid=Q.get()
        try:
            j=JOBS[jid]
            with LOCK:
                if j["status"]!="queued":continue
                j["status"]="running";save(j)
            for idx,t in enumerate(j["tasks"]):
                with LOCK:
                    if j["stop"]:
                        for remaining in j["tasks"]:
                            if remaining["status"]=="pending":remaining["status"]="cancelled"
                        break
                    if t["status"]!="pending":continue
                    t["status"]="running";t["phase"]="本地保真合成" if t["kind"]=="fidelity" else ("抠图" if t["kind"]=="local" else "生成");save(j)
                folder=DATA/"jobs"/jid/str(idx+1);folder.mkdir(exist_ok=True)
                try:
                    if t["kind"]=="fidelity":
                        raw=folder/"result.png"
                        proof=fidelity.render(asset_path(t["refs"][0]),asset_path(t["refs"][1]),t["template"],raw,folder/"layers")
                        atomic(folder/"fidelity-proof.json",proof)
                    elif t["kind"]=="local":
                        raw=asset_path(t["refs"][0])
                    else:
                        if not (folder/"raw.png").exists() and not channel_key(t.get("channel","3")):raise ValueError("所选通道未配置密钥")
                        raw=generate(t,folder)
                    if t["kind"]=="background":
                        result=folder/"clean-background.png"
                        store=fidelity.Store(DATA,asset_path)
                        mask=store.folder/(t["template_id"]+"-mask.png")
                        current=store.get(t["scene"])
                        if not current or current.get("mask_hash")!=t["mask_hash"]:raise ValueError("清理期间蒙版已修改，原生成保留，请重新核对")
                        fidelity.merge_cleanup(asset_path(t["scene"]),raw,mask,result)
                        edge=False
                    elif t["kind"]=="fidelity":
                        result=raw;edge=False
                    elif t["kind"]=="scene":
                        result=folder/"result.jpg"
                        with Image.open(raw) as im:im.convert("RGB").save(result,quality=96,subsampling=0)
                        edge=False
                    else:
                        with LOCK:t["phase"]="透明边缘处理";save(j)
                        result,edge=transparent(raw,folder)
                    a=register(result.read_bytes(),t["name"]+result.suffix,"result_scene" if t["kind"] in ("scene","fidelity","background") else "result_cutout")
                    with LOCK:
                        if t["kind"]=="background":
                            store=fidelity.Store(DATA,asset_path);current=store.get(t["scene"])
                            if current and current.get("mask_hash")==t["mask_hash"]:
                                current.update(clean_asset=a["id"],approved=False);store.write()
                        t.update(status="done",asset=a["id"],review="pending",
                                 message="已生成，待目视验收"+("；原始人物接近画布边缘，请特别检查裁切" if edge else ""))
                        save(j)
                except Exception as exc:
                    with LOCK:
                        uncertain=isinstance(exc,RuntimeError)
                        t.update(status="uncertain" if uncertain else "failed",message=str(exc)[:250]);save(j)
            with LOCK:
                statuses=[t["status"] for t in j["tasks"]]
                j["status"]="done" if all(s=="done" for s in statuses) else "partial"
                save(j)
        finally:Q.task_done()
def create_job(body):
    nonce=body.get("nonce")
    if not isinstance(nonce,str) or not re.fullmatch(r"[a-zA-Z0-9-]{12,100}",nonce):raise ValueError("提交标识无效，请刷新")
    with LOCK:
        for j in JOBS.values():
            if j.get("nonce")==nonce:return j
        tasks=make_plan(body)
        if any(t["kind"] not in ("local","fidelity") for t in tasks) and not channel_key(str(body.get("channel","3"))):raise ValueError("所选通道未配置密钥，请检查对应环境变量")
        jid=uuid4().hex
        folder=DATA/"jobs"/jid;folder.mkdir(parents=True)
        j={"id":jid,"nonce":nonce,"mode":body["mode"],"created":time.time(),"status":"queued","stop":False,
           "tasks":[dict(t,status="pending") for t in tasks]}
        JOBS[jid]=j;save(j);Q.put(jid);return j
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,data,mime="application/json; charset=utf-8",code=200):
        if isinstance(data,(dict,list)):data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code);self.send_header("Content-Type",mime)
        self.send_header("X-Content-Type-Options","nosniff");self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        try:
            path=unquote(urlparse(self.path).path)
            if path=="/api/state":return self.send(snapshot())
            if path.startswith("/media/"):
                aid=path.split("/")[-1];p=asset_path(aid)
                return self.send(p.read_bytes(),mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            if path.startswith("/download/"):
                jid=path.split("/")[-1]
                if jid not in JOBS:raise ValueError("任务不存在")
                dest=DATA/"jobs"/jid/"results.zip"
                with LOCK:
                    items=[t for t in JOBS[jid]["tasks"] if t["status"]=="done"]
                    if not items:raise ValueError("没有已完成的图片")
                    with zipfile.ZipFile(dest,"w",zipfile.ZIP_DEFLATED) as z:
                        for n,t in enumerate(items,1):
                            p=asset_path(t["asset"]);name=re.sub(r'[<>:"/\\|?*]',"_",t["name"])[:60]
                            z.write(p,f"{n:02d}-{name}.png" if t["kind"]!="scene" else f"{n:02d}-{name}.png")
                return self.send(dest.read_bytes(),"application/zip")
            if path.startswith("/pose-art/"):
                name=path.rsplit("/",1)[-1]
                if name not in {key+".png" for key in POSE_MAP}:return self.send({"error":"不存在"},code=404)
                file=ROOT/"web/pose-art"/name
                if not file.exists():return self.send({"error":"图例待补"},code=404)
                return self.send(file.read_bytes(),"image/png")
            if path not in ("/","/app.js","/poses.js","/fidelity.js","/style.css"):return self.send({"error":"不存在"},code=404)
            p=ROOT/"web"/("index.html" if path=="/" else path[1:])
            return self.send(p.read_bytes(),{".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8"}[p.suffix])
        except (ValueError,OSError) as exc:self.send({"error":str(exc)},code=400)
    def do_POST(self):
        try:
            expected=f"http://{self.headers.get('Host','')}"
            if self.headers.get("Origin") not in (None,expected):raise ValueError("拒绝外部页面请求")
            if self.headers.get("Content-Type","").split(";")[0]!="application/json":raise ValueError("请求格式无效")
            length=int(self.headers.get("Content-Length",0))
            if not 0<length<=30_000_000:raise ValueError("请求过大或为空")
            b=json.loads(self.rfile.read(length))
            path=urlparse(self.path).path
            if path.startswith("/api/fidelity/"):
                with LOCK:
                    store=fidelity.Store(DATA,asset_path)
                    if path=="/api/fidelity/get":
                        t=store.get(b["scene"])
                        mask_data=None
                        if t and t.get("mask_hash"):
                            mp=store.folder/(t["id"]+"-mask.png")
                            if mp.exists():
                                m=Image.open(mp).convert("L");rgba=Image.new("RGBA",m.size,"white");rgba.putalpha(m)
                                buf=io.BytesIO();rgba.save(buf,format="PNG");mask_data=base64.b64encode(buf.getvalue()).decode()
                        return self.send({"template":t,"ready":store.ready(b["scene"]),"mask":mask_data,"source_anchor":store.anchors.get(fidelity.digest(str(asset_path(b["product"])))) if b.get("product") else None})
                    if path=="/api/fidelity/save":return self.send(store.save(b))
                    if path=="/api/fidelity/approve":return self.send(store.approve(b["scene"]))
                    if path=="/api/fidelity/preview":
                        t=store.get(b["scene"])
                        if not t:raise ValueError("请先保存场景标定")
                        product=b["product"];asset_path(product)
                        temp=store.folder/(uuid4().hex+".png")
                        fidelity.render(asset_path(t.get("clean_asset",b["scene"])),asset_path(product),t,temp)
                        a=register(temp.read_bytes(),"保真合成预览.png","fidelity_preview")
                        return self.send(a)
                raise ValueError("保真接口不存在")
            if path=="/api/upload":
                raw=base64.b64decode(b["data"],validate=True)
                return self.send(register(raw,b.get("name","上传图片"),b.get("kind","reference")))
            if path=="/api/import":
                p=Path(str(b.get("path","")).strip().strip('"')).expanduser()
                if not p.is_file() or p.suffix.lower() not in (".png",".jpg",".jpeg",".webp"):raise ValueError("请选择有效图片路径")
                return self.send(register(p.read_bytes(),p.name,b.get("kind","reference")))
            if path=="/api/scan":
                p=Path(str(b.get("path","")).strip().strip('"'))
                if not p.is_dir():raise ValueError("场景目录不存在")
                files=sorted(p.rglob("*") if b.get("recursive") else p.iterdir(), key=lambda x:[(0,int(v)) if v.isdigit() else (1,v.lower()) for v in re.split(r"(\d+)",str(x))])
                images=[x for x in files if x.is_file() and x.suffix.lower() in (".png",".jpg",".jpeg",".webp")]
                if len(images)>200:raise ValueError("目录超过200张图片，请选择更小的目录")
                items=[];errors=[]
                for x in images:
                    try:items.append(register(x.read_bytes(),str(x.relative_to(p)),"scene"))
                    except (ValueError,OSError):errors.append(x.name)
                return self.send({"assets":items,"skipped":errors})
            if path=="/api/plan":
                tasks=make_plan(b)
                return self.send({"count":len(tasks),"calls":sum(t["kind"] not in ("local","fidelity") for t in tasks),"names":[t["name"] for t in tasks]})
            if path=="/api/jobs":return self.send(create_job(b))
            if path in ("/api/cancel","/api/resume","/api/review"):
                with LOCK:
                    j=JOBS.get(b.get("job"))
                    if not j:raise ValueError("任务不存在")
                    if path=="/api/cancel":
                        j["stop"]=True
                        if j["status"]!="running":
                            for t in j["tasks"]:
                                if t["status"]=="pending":t["status"]="cancelled"
                            j["status"]="partial"
                    elif path=="/api/resume":
                        if j["status"] in ("running","queued"):raise ValueError("任务仍在运行")
                        resumed=0
                        for i,t in enumerate(j["tasks"],1):
                            # Only unsubmitted tasks or local postprocessing with an existing raw.
                            if t["status"] in ("pending","cancelled") or (t["status"]=="failed" and (t["kind"]=="local" or (DATA/"jobs"/j["id"]/str(i)/"raw.png").exists())):
                                t["status"]="pending";resumed+=1
                        if not resumed:raise ValueError("没有可安全续做的任务；状态未明的生图需要先核对远端")
                        j["stop"]=False;j["status"]="queued";Q.put(j["id"])
                    else:
                        idx=int(b["index"])
                        if not 0<=idx<len(j["tasks"]):raise ValueError("图片序号无效")
                        t=j["tasks"][idx]
                        if t["status"]!="done":raise ValueError("尚无图片可验收")
                        if b["review"] not in ("accepted","rejected","pending"):raise ValueError("验收值无效")
                        t["review"]=b["review"]
                    save(j)
                    return self.send(j)
            raise ValueError("接口不存在")
        except (ValueError,OSError,KeyError,IndexError,TypeError) as exc:
            self.send({"error":str(exc)[:250]},code=400)
        except Exception:
            self.send({"error":"本地处理异常，请检查图片和工作台日志"},code=500)
def main():
    threading.Thread(target=worker,daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1",int(CFG["port"])),Handler).serve_forever()
if __name__=="__main__":main()