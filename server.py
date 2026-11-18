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
import scene_outputs
import material_marks
import constraint_rules
import face_orientation
import material_trash
import image_trash
import quality_gate
import auto_scene
import image_channels
DATA=Path(os.environ.get("PAPAPAI_DATA",str(ROOT/"data"))).resolve(); DATA.mkdir(parents=True,exist_ok=True)
CFG={"port":8796,"endpoint":"","model":"gpt-image-2.6","channel4_model":"banana-pro","timeout":600,"matting_runtime":"runtime/matting"}
if (ROOT/"config.json").exists():CFG.update(json.loads((ROOT/"config.json").read_text(encoding="utf-8")))
CFG["python"]=sys.executable
CFG["port"]=int(os.environ.get("PAPAPAI_PORT",CFG["port"]))
CFG["matting_runtime"]=str((ROOT/CFG["matting_runtime"]).resolve())

LOCK=threading.RLock(); Q=queue.Queue()
LEGACY_POSES=[
{"id":"chin","name":"托腮垂手","hint":"单手轻托脸颊，另一前臂搭边，手腕与五指自然垂落。"},
{"id":"both","name":"双手托腮","hint":"双肘放同一水平承托处，左右手分别轻托脸颊，头微歪，前臂呈自然V形。"},
{"id":"edge","name":"双手搭边","hint":"双肘向两侧展开，前臂横搭同一水平边沿，双手腕朝前弯曲，十指自然垂落，头抬起，不托腮。"},
{"id":"heart","name":"单手比心","hint":"一前臂横搭、手自然垂落；另一手抬至脸旁，用拇指与食指交叉比小指心，其余三指收拢。"},
{"id":"wave","name":"搭边挥手","hint":"一前臂横搭边沿，手自然垂落；另一肘部有承托，手举至脸旁轻挥，五指自然分开。"},
{"id":"cross","name":"交叠搭臂","hint":"两条前臂放低、松弛交叠横搭在同一水平边沿，双手均在低处，不靠近脸部。上身前倾。"},
{"id":"lean","name":"侧倾伏靠","hint":"上身轻前倾，头向一侧低倾，一手支撑太阳穴下方；另一前臂低位横放，手放松。"},
{"id":"pillow","name":"侧枕手臂","hint":"两条前臂并排横放在同一水平位置；头低下侧倾，脸颊真实枕在前臂上。两手均保持低位，绝不抬手托腮。"}]
POSES=json.loads((ROOT/'prompts/poses24.json').read_text('utf-8'))
PAPATIE_POSES=json.loads((ROOT/"prompts/papatie20.json").read_text("utf-8"))
POSE_LIBRARY=PAPATIE_POSES+[dict(p,tier="原有",image_kind="ai") for p in POSES]
POSE_MAP={p["id"]:p for p in LEGACY_POSES+POSE_LIBRARY}
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
    try:scene_outputs.sync_job(ROOT,j,asset_path,DATA)
    except (OSError,ValueError) as exc:j['output_error']='成品目录保存失败：'+str(exc)
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
        try:result[aid]={"ready":store.ready(aid),"calibrated":bool(store.get(aid)),"automatic_ready":(auto_cache(aid)/"clean-background.png").is_file()}
        except (OSError,ValueError):result[aid]={"ready":False,"calibrated":False}
    return result

def snapshot():
    with LOCK:
        marks=material_marks.read(DATA);trash=material_trash.read(DATA)
        return {"assets":[dict(a,**marks.get(a["id"],{}),trashed=a["id"] in trash,deleted_at=trash.get(a["id"],{}).get("deleted_at"),purged=bool(trash.get(a["id"],{}).get("purged"))) for a in ASSETS.values()],"jobs":list(reversed(list(JOBS.values()))),"poses":POSE_LIBRARY,
                "health":health(),"master_profiles":load(DATA/"master-profiles.json",{}),"scene_templates":fidelity_status()}
def channel_key(channel):return image_channels.key(channel)

def channel_model(channel):return image_channels.model(channel,CFG)

def health():
    return {"version":"papapai-studio-1.3.0","channel4_model":channel_model("4"),"channel5_model":channel_model("5"),"channel5":bool(channel_key("5")),"channel4":bool(channel_key("4")),"key":bool(channel_key("3")),"endpoint":CFG["endpoint"],"model":CFG["model"],
            "matting":(Path(CFG["matting_runtime"])/"BiRefNet_HR-matting.onnx").is_file(),
            "imageTool":(ROOT/"tools/image_api.py").is_file(),"root":str(ROOT),"unifiedTrash":True,"materialTrash":True,"materialMarks":True,"automaticScenes":True,"faceOrientation":True,"originalPoseRebuild":True,"consistencyRules":True,"handsCorrection":True,"identityLock":True,"simpleSample":True,"maskedEditing":"unverified"}
def pose_prompt(p,extra):
    return ("参考图是人物造型的唯一依据。制作写实上半身趴趴立牌可印刷图稿，保留同一人物面貌、发型、服装花纹、配饰及材质；"
            "按指定动作重构姿势。只要一个人物及完整双臂双手，不画下半身；只出现两只手，手指解剖自然。"
            "人物整体缩小居中，宽高均不超过画布70%，四周至少留15%透明余量；头发、发饰、肘部、衣袖和每个指尖全部完整入镜。"
            "输出真正透明背景PNG及alpha，不画棋盘格、白底、灰底、承托线、桌子、显示器、亚克力描边、底座、文字或投影。"
            "发丝、绒毛和指缝干净无白边、灰边及白色色块，保留自然半透明细节。动作："+p["hint"]+"\n补充："+extra)
def scene_prompt(mode,extra):
    base=("图1是需要保留的场景原照片，图2是唯一的人物透明PNG立牌图稿。只替换图1显示器上原有亚克力立牌及其印刷图案，完整移除旧人像和旧边缘。"
          "最高优先级：图2的人物五官、身体朝向、趴趴姿势、头部倾斜、肩肘腕位置、双臂交叠顺序、手掌朝向及每根手指的弯曲和间距全部保持不变。"
          "图2是已经完成的二维印刷图稿，不是需要重新摆姿势的真人。禁止重新设计动作、换手势、左右镜像、改变手指数量或弯曲结构。"
          "只允许将图2整体等比例缩放、整体平移及必要的轻微整片透视来适配原立牌位置；不能局部拉伸手指、分别旋转头部或肢体，也不能强改人物拍摄角度。"
          "人物仍保持图2原本的趴趴动作：肘部/衣袖自然搭在显示器上沿，垂手在屏幕前方。最高头饰至最低指尖完整入镜，保留完整头发、发饰、衣袖、双手和全部指尖；指缝透明显示场景。"
          "制作真实实物照片中的薄片异形透明亚克力立牌：保持平面印刷质感、窄透明切边、轻微厚度反光、与显示器接触处自然遮挡和柔和接触阴影。"
          "匹配图1机位、环境光向、色温、景深和整体颗粒，融入场景像手机拍摄的真实实物；不能变成真人、立体雕像、厚玻璃或白底贴纸。"
          "图1的显示器、屏幕内容、桌面物品和背景布局保持不变。不要旧立牌残影、重叠人物、多余肢体、异形手指、发丝白边、指缝白块、新文字或水印。")
    modes={"auto":"遵循图1原来的摆放方式；监视器上沿挂靠、车内屏幕安装或桌垫平放按原图判断，不把场景换掉。",
           "monitor":"衣袖底缘和肘部搭在显示器上沿，垂手在屏幕前方，接触有遮挡压影。",
           "car":"保留车内屏幕、挡风玻璃及车外环境，按车内自然光匹配，不添加办公桌。",
           "flat":"保留俯拍桌垫场景，立牌作为平面薄片平放其上，有贴地阴影和局部反光，不添加显示器。"}
    return base+modes[mode]+"\n补充："+extra
def make_plan(body):
    mode=body.get("mode");extra=str(body.get("extra","")).strip()
    if len(extra)>6000:raise ValueError("补充描述最多6000字（含默认锁定要求）")
    tasks=[]
    if mode=='continue_sample':
        sample=JOBS.get(str(body.get('sample','')),{});approved=JOBS.get(str(body.get('approved_job',body.get('sample',''))),{})
        if approved.get('id')!=sample.get('id') and approved.get('sample_root')!=sample.get('id'):raise ValueError('校正图不属于此样图')
        first=approved.get('tasks',[{}])[0]
        if first.get('status')!='done' or first.get('review')!='accepted':raise ValueError('请先检查并通过样图')
        if not sample.get('sample_remaining'):raise ValueError('样图没有待继续的场景')
        if str(body.get('channel','3'))!=first.get('channel'):raise ValueError('继续批次请沿用样图通道')
        tasks=json.loads(json.dumps(sample['sample_remaining']))
        for t in tasks:
            for aid in t['refs']:asset_path(aid)
    elif mode=="poses":
        source=body.get("source");asset_path(source)
        ids=body.get("poses",[])
        if not isinstance(ids,list) or not 1<=len(ids)<=min(60,len(POSE_MAP)) or len(set(ids))!=len(ids):raise ValueError("请选择1至"+str(min(60,len(POSE_MAP)))+"种有效姿势")
        for pid in ids:
            if pid not in POSE_MAP:raise ValueError("姿势无效")
            p=POSE_MAP[pid];tasks.append({"name":p["name"],"refs":[source],"prompt":pose_prompt(p,extra),"size":"1:1","kind":"cutout"})
    elif mode=="rebuild":
        source=body.get("source");path=asset_path(source)
        with Image.open(path) as im:ratio=im.width/im.height
        size="4:3"  # Wide canvas fits both elbows; source may be a portrait scene, not a portrait subject.
        prompt=("图1是唯一的人物与原动作参考。抠图并高清重构为独立人物透明PNG图稿。原动作复刻优先于任何美化，"
                "保留原图取景范围、脸型五官、表情、发型发际线、服装配饰及纹理。精准保留头部倾斜、肩肘腕位置、"
                "左右手朝向、每根可见手指数量和弯曲、指尖方向及全部遮挡关系；被遮挡处保持遮挡。"
                "禁止更换动作、左右镜像、增减手指、补出原图没有的肢体或改变身体比例；原本不是趴姿也不得擅自改成趴姿。"
                "移除原背景和承托物，不改变人物动作；保留服装本身白色、花瓣、饰品、指甲和绒毛，不误当背景删除。"
                "保留原有光源与材质，提升清晰度但不过度磨皮。以原参考图人物的完整外轮廓为准，不沿原场景照片边界截衣袖。人物完整缩入横向画布，主体宽高均不超过画布60%，四周至少留20%透明余量，"
                "优先缩小人物，禁止放大填满画布；左右衣袖、双肘必须完整，边缘自然闭合，禁止两侧竖直切口。已有发梢、衣袖、肘部和每个指尖不可裁断，不补全原图已裁掉的身体。"
                "输出真正带alpha的透明PNG，不画白底、棋盘格、亚克力白边、底座、桌子或屏幕。"
                "发梢鬓角保留自然半透明发丝，指缝透明，无白色毛边、灰边或白色色块。\n补充："+extra)
        tasks=[{"name":"原动作高清重构","refs":[source],"prompt":prompt,"size":size,"kind":"cutout"}]
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
    elif mode in ("correct_hands","correct_identity","correct_material"):
        job=JOBS.get(str(body.get("job","")),{});index=body.get("index")
        if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(job.get("tasks",[])):raise ValueError("原成品不存在")
        prior=job["tasks"][index]
        if prior.get("status")!="done" or prior.get("kind") not in ("scene","fidelity") or not prior.get("asset"):raise ValueError("仅可校正已完成的场景成品")
        refs=prior.get("refs",[]);product=prior.get("correction_product") or (refs[1] if len(refs)>1 else None)
        scene=prior.get("original_scene") or prior.get("scene") or (refs[0] if refs else None)
        for aid in (prior["asset"],product,scene):asset_path(aid)
        if not ASSETS[product].get("transparent"):raise ValueError("原人物透明参考图不可用")
        channel=str(body.get("channel","3"))
        if prior.get("channel") in ("3","4","5") and channel!=prior["channel"]:raise ValueError("手部校正请沿用原任务通道")
        prompt=("图1是需要二次校正的已生成亚克力立牌实拍场景；图2是人物动作、双手和手指结构的唯一标准透明图稿；图3是原始场景，仅供环境参考，不得恢复图3的旧人物。"
          "以图1为编辑底图，优先只修正立牌印刷人物中与图2不一致的双臂、手掌、手腕、手指和指缝。保持图2原始趴趴姿势、交叠顺序、左右手关系、每根手指的数量、关节弯曲和间距。不要新增手、融合手指、镜像或改变动作。"
          "保留图1的脸、发型、服饰、立牌位置大小角度、亚克力透明切边、侧面厚度、反光、接触阴影及实物摄影质感；保持显示器、屏幕内容、背景、桌面物品、机位与光照。不要把立牌变成真人或去掉亚克力材质。"
          "修复后指缝自然显示环境，不出现白块、残肢或裁断。除必要的手臂和手部衔接外，尽量不改图1其他区域。\n具体校正要求："+extra)
        identity=prior.get('identity_asset');person=prior.get('person_name','')
        if mode=='correct_identity' and not identity:identity=product
        if mode=='correct_identity':
            if not identity:raise ValueError('原任务未绑定身份母版，不能推测明星身份；请先用身份参考图重新制作')
            asset_path(identity)
            prompt='图1为当前亚克力立牌实拍成品；图2为原动作母版；图3为原场景；图4为身份母版。仅对照图4校正立牌印刷人物的身份相似度（'+person+'），保留图2手部动作、手指、衣服和图1场景、亚克力质感，不恢复旧人物。不要改手势。\n具体要求：'+extra
        if mode=='correct_material':prompt='图1为当前成品，图2为唯一人物动作母版，图3仅为原场景参考。只增强图1立牌的真实透明亚克力切边、侧面薄厚、反光、接触阴影和实物拍摄质感；保留人物面貌、原手部姿势与每根手指，不改变机位和背景，不恢复旧人物。具体要求：'+extra
        tasks=[{"name":prior["name"]+(' · 人物校正' if mode=='correct_identity' else ' · 材质修复' if mode=='correct_material' else ' · 手部校正'),"refs":[prior["asset"],product,scene],"prompt":prompt,"size":prior.get("size","1:1"),"kind":"scene","correction_product":product,"original_scene":scene,"identity_asset":identity,"person_name":person,"parent_job":str(body["job"]),"parent_index":index,"correction_pass":int(prior.get("correction_pass",0))+1}]
        if identity:
            tasks[0]["refs"].append(identity)
            tasks[0]["prompt"]+="\n图4是始终固定的身份母版，人物身份为"+person+"；只参考其面貌，不改变图2动作。"
    elif mode=="redo_scene":
        original=JOBS.get(str(body.get("job","")),{})
        index=body.get("index")
        if not isinstance(index,int) or not 0<=index<len(original.get("tasks",[])):raise ValueError("原图片不存在")
        prior=original["tasks"][index]
        if prior.get("kind")!="scene" or prior.get("status")!="done":raise ValueError("只可重做已完成的场景图；状态未明的任务请先核实")
        if str(body.get("channel"))!=prior.get("channel"):raise ValueError("重做请使用原任务通道")
        for aid in prior["refs"]:asset_path(aid)
        tasks=[{k:prior[k] for k in ("name","refs","prompt","size","kind")}]
    elif mode=="scenes":
        products=body.get("products",[]);scenes=body.get("scenes",[])
        if body.get('screening'):products,scenes=quality_gate.select(body,asset_path)
        if body.get('quick_screen'):
            valid={row['asset'] for row in quality_gate.report(products,scenes,asset_path) if row['status']!='excluded'}
            products=[x for x in products if x in valid];scenes=[x for x in scenes if x in valid]
        if not products or not scenes:raise ValueError("筛选后没有可生成的透明素材或场景，请检查排除项")
        if len(set(products))!=len(products) or len(set(scenes))!=len(scenes):raise ValueError("不能重复选择图片")
        for aid in products:
            if aid in material_trash.read(DATA):raise ValueError("该素材已移到回收站，请先恢复")
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
            engine=body.get("scene_engine","ai")
            if engine not in ("auto_fidelity","fidelity","ai"):raise ValueError("场景生成方式无效")
            if engine=="auto_fidelity":
                tasks.append({"name":item["name"],"refs":[scene,prod],"kind":"fidelity","automatic":True,"scene":scene,"scene_mode":sm,"prompt":"","size":size})
            elif engine=="fidelity":
                store=fidelity.Store(DATA,asset_path);template=store.get(scene)
                if not store.ready(scene):raise ValueError("请先标定并确认干净背景："+item["name"])
                tasks.append({"name":item["name"],"refs":[template["clean_asset"],prod],"kind":"fidelity","template":json.loads(json.dumps(template)),"scene":scene,"prompt":"","size":size})
            else:
                tasks.append({"name":item["name"],"refs":[scene,prod],"prompt":scene_prompt(sm,extra),"size":size,"kind":"scene"})
    else:raise ValueError("任务类型无效")
    if mode=='scenes':
        person=str(body.get('person_name','')).strip();identity=body.get('identity_asset')
        if len(person)>40:raise ValueError('人物名称最多40字')
        if person and not identity:raise ValueError('填写明星名称后请绑定清晰身份参考图')
        if identity:
            asset_path(identity)
            if min(ASSETS[identity]['width'],ASSETS[identity]['height'])<256:raise ValueError('身份参考图分辨率过低')
        for task in tasks:
            profile=load(DATA/'master-profiles.json',{}).get(task['refs'][1],{})
            person=str(body.get('person_name',profile.get('name',''))).strip();identity=body.get('identity_asset') or (task['refs'][1] if person else None)
            if profile.get('hint'):task['prompt']+='\n母版常用要求：'+profile['hint']
            task.update(person_name=person,identity_asset=identity,correction_product=task['refs'][1],original_scene=task.get('scene',task['refs'][0]))
            if task['kind']=='scene':
                task['prompt']+='\n动作母版为图2。场景中的旧人物只提供立牌位置，禁止参考其身份、手势或肢体。严格保持图2左右手、手掌朝向、交叠顺序、手指数量、弯曲和间距。'
                if identity:
                    task['refs'].append(identity);task['prompt']+='\n图3为固定身份母版，人物为'+person+'。面貌以图3为准，衣服与动作以图2为准，身份母版的姿势不可覆盖动作母版。'
    for task in tasks:
        if task.get('prompt'):task['prompt']=constraint_rules.apply(mode,task['prompt'])
    face_orientation.apply(tasks,body,asset_path)
    if not 1<=len(tasks)<=60:raise ValueError("每批最多60张，请减少选择")
    channel=str(body.get("channel","3"))
    if channel not in ("3","4","5"):raise ValueError("请选择通道3、4或5")
    for task in tasks:
        task["channel"]="local" if task["kind"]=="fidelity" and not task.get("automatic") else channel
        frozen=task.get("model") if mode=="continue_sample" else (prior.get("model") if mode in ("correct_hands","correct_identity","correct_material","redo_scene") else None)
        task["model"]=None if task["kind"]=="fidelity" else (frozen or channel_model(channel))
    return tasks[:1] if mode=="scenes" and body.get("sample_first") else tasks
def environment(channel="3"):
    env=dict(os.environ)
    env["CODEX_API_URL"]=image_channels.endpoint(channel if channel in image_channels.SUPPORTED else "3",CFG)
    if channel in ("3","4"):env["CODEX_API_KEY"]=channel_key(channel)
    if channel=="4":
        env["CHANNEL4_API_KEY"]=channel_key(channel);env["CHANNEL4_API_URL"]=image_channels.endpoint(channel,CFG)
        for name in ("CHANNEL4_PROXY","CHANNEL4_RESOLUTION"):
            value=image_channels.user_env(name)
            if value:env[name]=value
    if channel=="5":
        env["IMG4_API_KEY"]=channel_key(channel);env["IMG4_API_URL"]=image_channels.endpoint(channel,CFG)
        for name in ("IMG4_PROXY","IMG4_RESOLUTION","IMG4_VERSION"):
            value=image_channels.user_env(name)
            if value:env[name]=value
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
    channel=t.get("channel","3");model=t.get("model") or channel_model(channel)
    if channel=="4" and model.startswith("banana"):
        cmd=[CFG["python"],"-X","utf8",str(ROOT/"tools/xingqi_bridge.py"),"--prompt-file",str(prompt),"--out",str(raw),"--size",t["size"],"--model",model,"--timeout",str(CFG["timeout"])]
    elif channel=="5":
        cmd=[CFG["python"],"-X","utf8",str(ROOT/"tools/apimart_bridge.py"),"--prompt-file",str(prompt),"--out",str(raw),"--size",t["size"],"--model",model,"--timeout",str(CFG["timeout"])]
    else:
        cmd=[CFG["python"],"-X","utf8",str(ROOT/"tools/image_api.py"),"--prompt-file",str(prompt),"--out",str(raw),"--tmp-dir",str(folder),"--output-dir",str(folder),"--size",t["size"],"--n","1","--format","png","--model",model]
    for ref in t["refs"]:cmd+=["--image",str(asset_path(ref))]
    code=run_command(cmd,folder,int(CFG["timeout"]),channel)
    if code!=0 or not raw.exists():
        receipt=folder/("channel"+channel+"-task.json")
        if channel in ("4","5") and receipt.exists():
            try:diagnostic=load(receipt,{})
            except (OSError,ValueError):diagnostic={}
            if diagnostic.get("phase")=="rejected":raise image_channels.ChannelUnavailable(diagnostic.get("error") or "通道5请求被拒绝，请检查账号配置")
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
def validate_rebuild_frame(result):
    # transparent() adds 64px padding; inspect the original generated canvas instead.
    with Image.open(result) as im:
        alpha=im.convert("RGBA").getchannel("A").point(lambda a:255 if a>=24 else 0)
        box=alpha.getbbox();w,h=im.width-128,im.height-128
    if not box or w<=0 or h<=0:raise ValueError("重构画布无效，原始图已保留")
    mx,my=2,2  # Reject actual canvas contact, not intact nearby fingertips.
    if box[0]<64+mx or box[1]<64+my or box[2]>64+w-mx or box[3]>64+h-my:
        raise ValueError("人物触及生图画布边缘，疑似衣袖/发梢/指尖被裁切，未作为成品入库。原始图已保留；请缩小人物后重新重构，补透明留白不能恢复缺失部分。")

def auto_cache(scene):
    return DATA/'auto-scenes'/fidelity.digest(str(asset_path(scene)))

def planned_calls(tasks):
    calls=0;seen=set()
    for task in tasks:
        if task.get('automatic'):
            scene=task['scene'];key=auto_cache(scene).name
            if key not in seen and not (auto_cache(scene)/'clean-background.png').is_file():calls+=1
            seen.add(key)
        elif task['kind'] not in ('local','fidelity'):calls+=1
    return calls

def automatic_scene(task,folder,phase):
    cache=auto_cache(task['scene']);cache.mkdir(parents=True,exist_ok=True)
    scene=asset_path(task['scene']);product=asset_path(task['refs'][1]);recognized=cache/'recognition.json'
    if not recognized.is_file():
        if (cache/'recognition-error.json').is_file():raise ValueError(json.loads((cache/'recognition-error.json').read_text('utf-8'))['error'])
        phase('自动识别旧立牌与承托边')
        detect_folder=cache/'detection';detect_folder.mkdir(exist_ok=True)
        cmd=[CFG['python'],'-X','utf8',str(ROOT/'auto_scene.py'),'--scene',str(scene),'--folder',str(cache),'--runtime',CFG['matting_runtime'],'--mode',task.get('scene_mode','auto')]
        code=run_command(cmd,detect_folder,1200,task.get('channel','3'))
        if code!=0 or not recognized.is_file():
            log=detect_folder/'process.log';detail=log.read_text('utf-8').strip().splitlines()[-1] if log.exists() and log.stat().st_size else '本地识别未取得结果'
            message='自动识别未通过，未调用背景生图：'+detail[:160]
            atomic(cache/'recognition-error.json',{'error':message})
            raise ValueError(message)
    recognition=json.loads(recognized.read_text('utf-8'))
    if recognition.get('version')!=auto_scene.VERSION:raise ValueError('识别缓存版本不兼容，请重新识别场景')
    if recognition.get('mask_version',1)<2 and (cache/'detected-alpha.png').is_file():
        recognition=auto_scene.analyze(scene,cache/'detected-alpha.png',task.get('scene_mode','auto'));auto_scene.write(recognized,recognition)
        if (cache/'cleanup/raw.png').is_file():auto_scene.merge_background(scene,cache/'cleanup/raw.png',cache/'cleanup-mask.png',cache/'clean-background.png')
    mask=cache/'cleanup-mask.png'
    if not mask.is_file():raise ValueError('自动清理蒙版缺失，已停止此场景')
    clean=cache/'clean-background.png'
    if not clean.is_file():
        phase('自动清理旧立牌背景 · 仅处理背景')
        cleanup=cache/'cleanup';cleanup.mkdir(exist_ok=True)
        meta=cleanup/'task.json'
        if meta.is_file():background=json.loads(meta.read_text('utf-8'))
        else:
            guide=cache/'cleanup-guide.png';auto_scene.guide(scene,mask,guide)
            with LOCK:a=register(guide.read_bytes(),'自动清理区域参考.png','mask_guide')
            channel=task.get('channel','3')
            background={'refs':[task['scene'],a['id']],'channel':channel,'model':task.get('model') or channel_model(channel),'size':task['size'],
              'prompt':'图1是实物拍摄场景原图，图2红色区域是系统识别出的旧亚克力立牌。完整移除红色范围内旧人物、旧立牌透明白边和旧接触阴影，补全后面的显示器、墙面、桌面。只恢复干净背景，不添加任何新人物或新立牌，不改变机位、屏幕边框、屏幕内容和红色范围之外的物品。保持原始光照、照片颗粒和透视。不要红色蒙版残留。'}
            atomic(meta,background)
        if background.get('channel')!=task.get('channel','3'):raise ValueError('此场景已有其他通道清理记录，请先核实该次结果，不自动换通道重试')
        # generate() reuses raw.png. An uncertain remote request is never retried by the worker.
        attempt=cleanup/'attempt.json'
        if attempt.is_file() and not (cleanup/'raw.png').is_file():raise RuntimeError('该场景背景已提交且结果待核实，后续人物不会再次扣费提交')
        atomic(attempt,{'submitted':True,'channel':background['channel']})
        raw=generate(background,cleanup)
        temp=cache/'clean-background.writing.png';auto_scene.merge_background(scene,raw,mask,temp);temp.replace(clean)
        auto_scene.write(cache/'background-proof.json',{'scene_hash':fidelity.digest(str(scene)),'channel':background['channel'],'product_sent_to_model':False,'outside_mask_preserved':True,'blending':'poisson'})
    proof_path=cache/'background-proof.json'
    if (cache/'cleanup/raw.png').is_file() and (not proof_path.is_file() or json.loads(proof_path.read_text('utf-8')).get('blending')!='poisson'):
        auto_scene.merge_background(scene,cache/'cleanup/raw.png',mask,clean)
        auto_scene.write(proof_path,{'blending':'poisson','product_sent_to_model':False,'outside_mask_preserved':True})
    phase('自动摆放与实物光影合成 · 保留人物手指')
    with Image.open(scene) as im:size=im.size
    template=auto_scene.layout(recognition,product,size)
    result=folder/'result.png';proof=fidelity.render(clean,product,template,result,folder/'layers')
    proof.update(automatic=True,recognition=recognition,background_cache=str(clean),product_sent_to_model=False)
    atomic(folder/'fidelity-proof.json',proof)
    return result
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
                    if t.get("automatic"):
                        def phase(message):
                            with LOCK:
                                if j["stop"]:raise ValueError("已停止后续自动处理；已提交的背景结果保留")
                                t["phase"]=message;save(j)
                        raw=automatic_scene(t,folder,phase)
                    elif t["kind"]=="fidelity":
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
                        if j.get("mode")=="rebuild":validate_rebuild_frame(result)
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
                        t.update(status="uncertain" if uncertain else "failed",message=str(exc)[:250])
                        if getattr(exc,"stop_batch",False):
                            for remaining in j["tasks"][idx+1:]:
                                if remaining["status"]=="pending":remaining.update(status="cancelled",message="同批通道请求被拒绝，未继续提交")
                        save(j)
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
        if body.get('mode')=='continue_sample':
            for existing in JOBS.values():
                if existing.get('sample_parent')==body.get('sample'):return existing
        tasks=make_plan(body)
        remaining=make_plan(dict(body,sample_first=False))[1:] if body.get('mode')=='scenes' and body.get('sample_first') else []
        if planned_calls(tasks)>0 and not channel_key(str(body.get("channel","3"))):raise ValueError("所选通道未配置密钥，请检查对应环境变量")
        if planned_calls(tasks)>0:image_channels.preflight(str(body.get("channel","3")),CFG)
        jid=uuid4().hex
        folder=DATA/"jobs"/jid;folder.mkdir(parents=True)
        j={"id":jid,"nonce":nonce,"mode":body["mode"],"created":time.time(),"status":"queued","stop":False,
           "tasks":[dict(t,status="pending") for t in tasks]}
        if body.get('mode') in ('correct_hands','correct_identity','correct_material'):
            source_job=JOBS.get(str(body.get('job','')),{})
            root=source_job.get('id') if source_job.get('sample_remaining') else source_job.get('sample_root')
            if root:j['sample_root']=root
        if remaining:j.update(sample_remaining=remaining,sample_total=len(remaining)+1)
        if body.get('mode')=='continue_sample':j['sample_parent']=body['sample']
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
                    items=[t for t in JOBS[jid]["tasks"] if t["status"]=="done" and t.get("asset") not in image_trash.read(DATA)]
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
            if path not in ("/","/app.js","/poses.js","/fidelity.js","/gallery.js","/studio.js","/library.js","/style.css"):return self.send({"error":"不存在"},code=404)
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
            if path=="/api/master-profile":
                with LOCK:
                    aid=b.get('asset');asset_path(aid);name=str(b.get('name','')).strip();hint=str(b.get('hint','')).strip()
                    if len(name)>40 or len(hint)>1000:raise ValueError('母版常用要求过长')
                    profiles=load(DATA/'master-profiles.json',{});profiles[aid]={'name':name,'hint':hint};atomic(DATA/'master-profiles.json',profiles);return self.send(profiles[aid])
            if path=="/api/preflight":
                return self.send({"items":quality_gate.report(b.get("products",[]),b.get("scenes",[]),asset_path)})
            if path=="/api/image-trash":
                with LOCK:return self.send(image_trash.change(ROOT,DATA,ASSETS,JOBS,b.get("assets"),b.get("action")))
            if path=="/api/material-trash":
                with LOCK:return self.send(image_trash.change(ROOT,DATA,ASSETS,JOBS,b.get("assets"),b.get("action")))
            if path=="/api/material-marks":
                with LOCK:
                    aid=b.get("asset");asset_path(aid)
                    value=material_marks.update(DATA,aid,b.get("favorite"),b.get("tags",[]))
                    return self.send(value)
            if path=="/api/gallery":
                with LOCK:
                    action=b.get("action")
                    if action=="rename":
                        j=JOBS.get(b.get("job"));title=str(b.get("title","")).strip()
                        if not j:raise ValueError("任务不存在")
                        if not 1<=len(title)<=60:raise ValueError("作品名称需为1至60字")
                        j["title"]=title;save(j);return self.send({"ok":True,"title":title})
                    if action=="archive":
                        j=JOBS.get(b.get("job"))
                        if not j:raise ValueError("任务不存在")
                        if j["status"] in ("running","queued"):raise ValueError("进行中的批次不能归档")
                        if not isinstance(b.get("archived"),bool):raise ValueError("归档参数无效")
                        j["archived"]=b["archived"];save(j);return self.send({"ok":True})
                    rows=b.get("selection",[])
                    if not isinstance(rows,list) or not 1<=len(rows)<=200:raise ValueError("请选择1至200张成品")
                    selected=[];seen=set()
                    for row in rows:
                        j=JOBS.get(row.get("job"));i=row.get("index")
                        if not j or not isinstance(i,int) or not 0<=i<len(j["tasks"]):raise ValueError("图片记录不存在")
                        t=j["tasks"][i]
                        if t["status"]!="done" or not t.get("asset"):raise ValueError("只能选择已完成成品")
                        if (j["id"],i) in seen:raise ValueError("不能重复选择图片")
                        asset_path(t["asset"]);seen.add((j["id"],i));selected.append((j,t))
                    if action=="review":
                        if b.get("review") not in ("pending","accepted","rejected"):raise ValueError("验收值无效")
                        for j,t in selected:t["review"]=b["review"]
                        for jid in {j["id"] for j,t in selected}:save(JOBS[jid])
                        return self.send({"count":len(selected)})
                    if action=="handoff":
                        from urllib.parse import urlencode
                        from datetime import datetime
                        selected=[(j,t) for j,t in selected if t.get("review")!="rejected" and t.get("asset") not in image_trash.read(DATA)]
                        if not selected:raise ValueError("选中图片均为需要修正，未发送")
                        folder=ROOT/"成品"/"分发批次"/("选图-"+datetime.now().strftime("%Y%m%d-%H%M%S")+"-"+uuid4().hex[:8]);folder.mkdir(parents=True)
                        manifest=[]
                        for i,(j,t) in enumerate(selected,1):
                            with Image.open(asset_path(t["asset"])) as im:
                                transparent=im.mode=="RGBA" and im.getchannel("A").getextrema()[0]<255
                                im=im.convert("RGBA" if transparent else "RGB")
                                im.save(folder/(f"{i:03d}.png" if transparent else f"{i:03d}.jpg"),format="PNG" if transparent else "JPEG",**({} if transparent else {"quality":95,"subsampling":0}))
                            manifest.append({"asset":t["asset"],"file":f"{i:03d}.png" if transparent else f"{i:03d}.jpg"})
                        image_trash.write(folder/"image-manifest.json",{"images":manifest})
                        return self.send({"count":len(selected),"folder":str(folder),"url":"http://127.0.0.1:8766/?"+urlencode({"from":"papapai","folder":str(folder)})+"#batch"})
                    raise ValueError("成品操作无效")
            if path=="/api/output":
                from urllib.parse import urlencode
                with LOCK:
                    j=JOBS.get(str(b.get("job","")))
                    if not j:raise ValueError("任务不存在")
                    folder=scene_outputs.sync_job(ROOT,j,asset_path,DATA)
                    if not folder:raise ValueError("这批尚无已完成的场景图")
                    action=b.get("action","prepare")
                    if action=="handoff":
                        result=scene_outputs.handoff(ROOT,j,asset_path,DATA);save(j)
                        result["url"]="http://127.0.0.1:8766/?"+urlencode({"from":"papapai","folder":result["folder"]})+"#batch"
                        return self.send(result)
                    if action not in ("prepare","open"):raise ValueError("目录操作无效")
                    save(j)
                    if action=="open":
                        if os.name!="nt":raise ValueError("请复制目录路径，在文件管理器打开")
                        os.startfile(str(folder))
                    return self.send({"folder":str(folder),"count":sum(t.get("status")=="done" and t.get("kind") in ("scene","fidelity") and t.get("asset") not in image_trash.read(DATA) for t in j["tasks"])})
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
                rows=quality_gate.report(b.get('products',[]),b.get('scenes',[]),asset_path) if b.get('quick_screen') else []
                return self.send({"count":len(tasks),"calls":planned_calls(tasks),"names":[t["name"] for t in tasks],"skipped":[ASSETS[x['asset']]['name'] for x in rows if x['status']=='excluded'],"warnings":[ASSETS[x['asset']]['name'] for x in rows if x['status']=='review']})
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