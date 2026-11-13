"""Local standee compositing. No image-model call is made from this module."""
import base64,hashlib,io,json,math
from functools import lru_cache
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter,ImageChops,ImageOps

@lru_cache(maxsize=1000)
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def quad(value):
    if not isinstance(value,list) or len(value)!=4:raise ValueError("需要4个角点，按左上、右上、右下、左下排列")
    points=[]
    for pair in value:
        if not isinstance(pair,list) or len(pair)!=2:raise ValueError("角点格式无效")
        x,y=map(float,pair)
        if not all(math.isfinite(v) and 0<=v<=1 for v in (x,y)):raise ValueError("角点必须位于画布内")
        points.append([x,y])
    cross=[]
    for i in range(4):
        a,b,c=points[i],points[(i+1)%4],points[(i+2)%4]
        cross.append((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))
    if min(cross)<.0001:raise ValueError("角点不能交叉、翻转或过度压扁")
    area=sum(points[i][0]*points[(i+1)%4][1]-points[(i+1)%4][0]*points[i][1] for i in range(4))/2
    if area<.002:raise ValueError("立牌区域太小")
    return points

def image_size(path):
    with Image.open(path) as im:return im.size

def number(value,lo,hi,name):
    n=float(value)
    if not math.isfinite(n) or not lo<=n<=hi:raise ValueError(name+"超出允许范围")
    return n

def solve(a,b):
    a=[list(map(float,row))+[float(v)] for row,v in zip(a,b)]
    n=len(a)
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(a[j][i]))
        if abs(a[pivot][i])<1e-10:raise ValueError("透视角点无效")
        a[i],a[pivot]=a[pivot],a[i]
        scale=a[i][i];a[i]=[v/scale for v in a[i]]
        for j in range(n):
            if i!=j:
                scale=a[j][i];a[j]=[x-scale*y for x,y in zip(a[j],a[i])]
    return [row[-1] for row in a]

def coefficients(dst,src):
    matrix=[];b=[]
    for (x,y),(u,v) in zip(dst,src):
        matrix.append([x,y,1,0,0,0,-u*x,-u*y]);b.append(u)
        matrix.append([0,0,0,x,y,1,-v*x,-v*y]);b.append(v)
    return solve(matrix,b)

def render(scene,product,template,target,layers=None):
    base=Image.open(scene).convert("RGBA")
    fg=Image.open(product).convert("RGBA")
    alpha=fg.getchannel("A");bbox=alpha.getbbox()
    if bbox is None or alpha.getextrema()[0]==255:raise ValueError("请选择真实透明PNG立牌")
    fg=fg.crop(bbox)
    aspect=number(template.get("aspect",fg.width/fg.height),.15,5,"立牌平面比例")
    width=min(2048,fg.width);height=max(1,round(width/aspect))
    if height>4096:height=4096;width=max(1,round(height*aspect))
    plane=Image.new("RGBA",(width,height))
    anchor=max(.01,min(.99,float(template.get("anchor",.72))))
    source_anchor=max(.01,min(.99,float(template.get("product_anchors",{}).get(digest(str(product)),anchor))))
    fit_height=max(1,min(height,width*fg.height/fg.width,anchor*height/source_anchor,(1-anchor)*height/(1-source_anchor)))
    fit_width=max(1,round(fit_height*fg.width/fg.height))
    fit=fg.resize((fit_width,max(1,round(fit_height))),Image.Resampling.LANCZOS)
    plane.alpha_composite(fit,((width-fit.width)//2,round(anchor*height-source_anchor*fit.height)))
    q=quad(template["quad"])
    dst=[(x*base.width,y*base.height) for x,y in q]
    src=[(0,0),(width,0),(width,height),(0,height)]
    coeff=coefficients(dst,src)
    # Interpolate premultiplied alpha so transparent RGB cannot cause colored/white fringes.
    warped=plane.convert("RGBa").transform(base.size,Image.Transform.PERSPECTIVE,coeff,Image.Resampling.BICUBIC).convert("RGBA")
    a=warped.getchannel("A")
    contact=number(template.get("shadow",.15),0,.5,"阴影")
    rim=number(template.get("rim",.12),0,.4,"透明切边")
    separate={}
    if contact:
        shadow=Image.new("L",base.size)
        shadow.paste(a,(max(1,round(base.width*.003)),max(1,round(base.height*.004))))
        shadow=shadow.filter(ImageFilter.GaussianBlur(max(1,base.width*.002))).point(lambda x:round(x*contact))
        layer=Image.new("RGBA",base.size,(0,0,0));layer.putalpha(shadow);base.alpha_composite(layer);separate["shadow"]=layer
    if rim:
        edge=ImageChops.subtract(a.filter(ImageFilter.MaxFilter(3)),a).point(lambda x:round(x*rim))
        layer=Image.new("RGBA",base.size,(235,243,247));layer.putalpha(edge);base.alpha_composite(layer);separate["rim"]=layer
    base.alpha_composite(warped)
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    base.convert("RGB").save(target,format="PNG")
    if layers:
        folder=Path(layers);folder.mkdir(parents=True,exist_ok=True)
        warped.save(folder/"人物原图透视层.png")
        for name,im in separate.items():im.save(folder/(name+".png"))
    return {"size":base.size,"method":"original_png_homography","source_hash":digest(str(product)),
            "template":q,"note":"只做整体透视和透明合成，未重绘人物；换算含插值，不保证逐像素相同"}

def merge_cleanup(original,generated,mask,target):
    base=Image.open(original).convert("RGB")
    made=Image.open(generated).convert("RGB").resize(base.size,Image.Resampling.LANCZOS)
    m=Image.open(mask).convert("L")
    if m.size!=base.size:raise ValueError("清理蒙版尺寸不一致")
    # Fade only inside the selected area; pixels outside the mask are never replaced.
    feather=ImageChops.multiply(m,m.filter(ImageFilter.GaussianBlur(1)))
    Image.composite(made,base,feather).save(target,format="PNG")

class Store:
    def __init__(self,data,asset_path):
        self.data=Path(data);self.asset_path=asset_path
        self.folder=self.data/"fidelity";self.folder.mkdir(exist_ok=True)
        self.anchor_file=self.folder/"product-anchors.json"
        self.anchors=json.loads(self.anchor_file.read_text(encoding="utf-8")) if self.anchor_file.exists() else {}
        self.file=self.folder/"templates.json"
        self.templates=json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else {}
    def write(self):
        p=self.file.with_suffix(".writing");p.write_text(json.dumps(self.templates,ensure_ascii=False,indent=2),encoding="utf-8");p.replace(self.file)
    def get(self,scene):
        h=digest(str(self.asset_path(scene)))
        t=self.templates.get(h)
        if t:t["product_anchors"]=dict(self.anchors)
        return t
    def save(self,body):
        scene=body["scene"];source=self.asset_path(scene);h=digest(str(source))
        old=self.templates.get(h,{})
        q=quad(body["quad"])
        t={**old,"id":h,"scene":scene,"quad":q,
           "aspect":number(body.get("aspect",1),.15,5,"立牌平面比例"),
           "anchor":number(body.get("anchor",.72),0,1,"人物承托线"),
           "support":number(body.get("support",.45),0,1,"场景承托线"),
           "shadow":number(body.get("shadow",.15),0,.5,"阴影"),
           "rim":number(body.get("rim",.12),0,.4,"切边")}
        if body.get("clear_mask"):
            t.pop("mask_hash",None);t.pop("clean_asset",None);t["approved"]=False
        if body.get("mask"):
            raw=base64.b64decode(body["mask"],validate=True)
            with Image.open(io.BytesIO(raw)) as im:
                mask=im.getchannel("A") if im.mode=="RGBA" else im.convert("L")
                if mask.size!=image_size(source):raise ValueError("清理蒙版尺寸不一致")
                if not mask.getbbox():raise ValueError("清理区域为空")
                if sum(mask.histogram()[1:])>mask.width*mask.height*.8:raise ValueError("清理区域超过画面80%，请缩小范围")
                mask.save(self.folder/(h+"-mask.png"))
            mh=hashlib.sha256(mask.tobytes()).hexdigest()
            if mh!=t.get("mask_hash"):
                t["mask_hash"]=mh;t["approved"]=False;t.pop("clean_asset",None)
        if body.get("clean_asset"):
            clean=self.asset_path(body["clean_asset"])
            if image_size(clean)!=image_size(source):raise ValueError("干净背景必须与场景原图尺寸相同")
            t.update(clean_asset=body["clean_asset"],approved=False)
        if body.get("use_original"):
            t.update(clean_asset=scene,approved=False)
        if body.get("product"):
            key=digest(str(self.asset_path(body["product"])))
            self.anchors[key]=number(body.get("source_anchor",.86),.01,.99,"人物承托点")
            tmp=self.anchor_file.with_suffix(".writing");tmp.write_text(json.dumps(self.anchors),encoding="utf-8");tmp.replace(self.anchor_file)
        t["product_anchors"]=dict(self.anchors)
        self.templates[h]=t;self.write();return t
    def approve(self,scene):
        t=self.get(scene)
        if not t or not t.get("clean_asset"):raise ValueError("请先清理旧立牌或提供干净场景")
        self.asset_path(t["clean_asset"]);t["approved"]=True;self.write();return t
    def ready(self,scene):
        t=self.get(scene)
        return bool(t and t.get("approved") and t.get("clean_asset"))