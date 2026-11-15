"""Automatic scene recognition and original-PNG layout. Models only detect the old standee."""
import argparse,json,math,hashlib,sys
from pathlib import Path
from PIL import Image,ImageFilter,ImageChops,ImageStat
VERSION=1

def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.writing');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8');tmp.replace(path)

def analyze(scene,mask,mode='auto'):
    import numpy as np,cv2
    base=Image.open(scene).convert('RGB');w,h=base.size
    a=np.asarray(Image.open(mask).convert('L').resize((w,h)));binary=(a>110).astype('uint8')
    count,labels,stats,_=cv2.connectedComponentsWithStats(binary,8)
    candidates=[]
    for i in range(1,count):
        x,y,bw,bh,area=map(int,stats[i]);fill=area/(bw*bh)
        if .008*w*h<area<.65*w*h and .08*w<bw<.95*w and .13*h<bh<.94*h and .1<fill<.88 and y>.005*h and x>.005*w and x+bw<.995*w:
            candidates.append((area,i,x,y,bw,bh))
    if not candidates:raise ValueError('自动识别未通过：未分离出完整旧立牌，已停止此场景，未调用背景生图')
    candidates.sort(reverse=True)
    if len(candidates)>1 and candidates[1][0]>.4*candidates[0][0]:raise ValueError('自动识别未通过：场景有多个明显主体，无法确定应替换的立牌')
    area,index,x,y,bw,bh=candidates[0];subject=(labels==index).astype('uint8')*255
    rows=(subject[y:y+bh,x:x+bw]>0).sum(axis=1)
    wide=np.where(rows>max(rows)*.68)[0];wide=wide[wide>.35*bh]
    support_guess=y+int(wide[-1] if len(wide) else bh*.75)
    gray=cv2.cvtColor(np.asarray(base),cv2.COLOR_RGB2GRAY);edges=cv2.Canny(gray,50,150)
    edges[cv2.dilate(subject,np.ones((7,7),np.uint8))>0]=0
    lines=cv2.HoughLinesP(edges,1,np.pi/360,threshold=max(35,int(w*.05)),minLineLength=int(w*.12),maxLineGap=int(w*.06))
    choices=[]
    if lines is not None:
        for ax,ay,bx,by in lines.reshape(-1,4):
            dx=bx-ax
            if dx==0:continue
            slope=(by-ay)/dx;cy=ay+slope*(x+bw/2-ax)
            if abs(slope)>.22 or not y+.4*bh<cy<y+.98*bh:continue
            distance=abs(cy-support_guess)/bh
            if distance>.2:continue
            length=math.hypot(dx,by-ay);score=length/w-distance*2
            choices.append((score,float(cy),float(math.atan(slope))))
    if mode=='flat':support=support_guess;angle=0.;confidence=.8
    elif choices:
        choices.sort(reverse=True);_,support,angle=choices[0];confidence=.9
    else:raise ValueError('自动识别未通过：显示器承托边不明确，已停止，未随意摆放或扣费清理')
    # Detect monitor-sized rectangular foreground, rather than accepting an entire screen as a standee.
    if area/(bw*bh)>.82 or np.mean(subject[max(y,y+bh-3):y+bh,x:x+bw]>0)>.85:
        raise ValueError('自动识别未通过：前景疑似包含整块屏幕，未清理背景')
    # Include the detached transparent acrylic contour, not only opaque printed pixels.
    region=np.zeros_like(subject);pad=round(min(w,h)*.04)
    region[max(0,y-pad):min(h,y+bh+pad),max(0,x-pad):min(w,x+bw+pad)]=1
    yy,xx=np.where((a>8)&(region>0));outer=np.zeros_like(subject)
    if len(xx)>2:cv2.fillConvexPoly(outer,cv2.convexHull(np.column_stack((xx,yy)).astype('int32')),255)
    subject=np.maximum(subject,outer)
    clean_mask=Image.fromarray(subject).filter(ImageFilter.MaxFilter(max(3,2*round(min(w,h)*.009)+1)))
    coverage=sum(clean_mask.histogram()[1:])/(w*h)
    if coverage>.72:raise ValueError('自动识别清理范围过大，已停止此场景')
    mpath=Path(mask).with_name('cleanup-mask.png');clean_mask.save(mpath)
    # Neutral highlights near the standee determine only a restrained environmental color match.
    samples=np.asarray(base.resize((100,100)),dtype=float);bright=samples[samples.min(axis=2)>110]
    mean=bright.mean(axis=0) if len(bright) else np.array([180,180,180]);gains=np.clip(mean/max(1,float(mean.mean())),.97,1.03).tolist()
    return {'version':VERSION,'mask_version':2,'bbox':[x/w,y/h,(x+bw)/w,(y+bh)/h],'support':support/h,'angle':angle,'confidence':confidence,'mask':mpath.name,'photometric':{'gain':gains},'mode':mode}

def detect(scene,folder,runtime,mode='auto'):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(Path(runtime)/'packages'))
    import numpy as np,onnxruntime as ort
    from scipy.special import expit
    model=Path(runtime)/'BiRefNet_HR-matting.onnx'
    if not model.is_file():raise ValueError('自动识别需要本地BiRefNet HR模型，请配置抠图运行环境')
    opt=ort.SessionOptions();opt.intra_op_num_threads=2;opt.enable_cpu_mem_arena=False
    session=ort.InferenceSession(str(model),sess_options=opt,providers=['CPUExecutionProvider']);entry=session.get_inputs()[0]
    h,w=[v if isinstance(v,int) and v>0 else 2048 for v in entry.shape[-2:]]
    source=Image.open(scene).convert('RGB');a=np.asarray(source.resize((w,h),Image.Resampling.BICUBIC),np.float32)/255
    a=(a-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
    raw=np.squeeze(session.run(None,{entry.name:np.ascontiguousarray(a.transpose(2,0,1)[None])})[-1])
    if raw.ndim!=2:raise ValueError('自动识别模型输出格式无效')
    if raw.min()<0 or raw.max()>1:raw=expit(raw)
    mask=folder/'detected-alpha.png';Image.fromarray((np.clip(raw,0,1)*255).astype('uint8')).resize(source.size,Image.Resampling.BILINEAR).save(mask)
    result=analyze(scene,mask,mode);write(folder/'recognition.json',result);return result

def layout(recognition,product,size):
    w,h=size;fg=Image.open(product).convert('RGBA');alpha=fg.getchannel('A');box=alpha.getbbox()
    if not box or alpha.getextrema()[0]==255:raise ValueError('需要完整透明PNG立牌')
    cropped=alpha.crop(box);fw,fh=cropped.size
    # Bottom of the broad sleeve/forearm band is the support anchor. Dangling fingers are narrower.
    widths=[]
    for row in range(fh):
        b=cropped.crop((0,row,fw,row+1)).point(lambda p:255 if p>80 else 0).getbbox();widths.append(b[2]-b[0] if b else 0)
    broad=[i for i,n in enumerate(widths) if fh*.4<i<fh*.95 and n>max(widths)*.67]
    anchor=min(.94,max(.45,(max(broad)+1)/fh if broad else .75))
    x0,y0,x1,y1=recognition['bbox'];cx=(x0+x1)/2;support=recognition['support'];angle=recognition['angle'];scale=min(x1-x0,.86,max(.02,(support-y0)*h/w*(fw/fh)/anchor),max(.02,(y1-support)*h/w*(fw/fh)/(1-anchor)))
    def points(s):
        height=s*w/h/(fw/fh)
        return [[cx+dx*math.cos(angle)-dy*h/w*math.sin(angle),support+dx*w/h*math.sin(angle)+dy*math.cos(angle)] for dx,dy in [(-s/2,-height*anchor),(s/2,-height*anchor),(s/2,height*(1-anchor)),(-s/2,height*(1-anchor))]]
    for _ in range(50):
        q=points(scale)
        if all(.015<=v<=.985 for p in q for v in p):break
        scale*=.96
    else:raise ValueError('自动摆放无法保证人物完整入镜，已停止此场景')
    if scale<.12:raise ValueError('自动摆放区域过小，已停止此场景')
    digest=hashlib.sha256(Path(product).read_bytes()).hexdigest()
    return {'quad':q,'aspect':fw/fh,'anchor':anchor,'product_anchors':{digest:anchor},'shadow':.13,'rim':.08,'photometric':recognition.get('photometric',{}),'automatic':True}

def guide(scene,mask,target):
    base=Image.open(scene).convert('RGB');m=Image.open(mask).convert('L');tint=Image.blend(base,Image.new('RGB',base.size,'red'),.55);Image.composite(tint,base,m).save(target)


def merge_background(scene,generated,mask,target):
    """Gradient-domain blend removes the silhouette-shaped color seam; outside mask stays exact."""
    import numpy as np,cv2
    base=Image.open(scene).convert('RGB');made=Image.open(generated).convert('RGB').resize(base.size,Image.Resampling.LANCZOS);m=Image.open(mask).convert('L')
    if m.size!=base.size or not m.getbbox():raise ValueError('自动清理蒙版无效')
    box=m.getbbox();center=((box[0]+box[2])//2,(box[1]+box[3])//2)
    result=cv2.seamlessClone(np.asarray(made)[...,::-1].copy(),np.asarray(base)[...,::-1].copy(),np.asarray(m),center,cv2.NORMAL_CLONE)[...,::-1]
    Image.composite(Image.fromarray(result),base,m.point(lambda x:255 if x else 0)).save(target,format='PNG')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',required=True);p.add_argument('--folder',required=True);p.add_argument('--runtime',required=True);p.add_argument('--mode',default='auto');a=p.parse_args()
    try:detect(a.scene,a.folder,a.runtime,a.mode);print('自动识别完成',flush=True)
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)