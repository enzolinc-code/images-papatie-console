from pathlib import Path
import base64,io,json,math,re,os
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
MAX_PIXELS=25_000_000
Image.MAX_IMAGE_PIXELS=MAX_PIXELS

def decode_image(value):
    if not isinstance(value,str) or not re.match(r'^data:image/(png|jpeg|webp);base64,',value):raise ValueError('图片格式无效，请重新上传PNG、JPG或WebP')
    try:
        raw=base64.b64decode(value.split(',',1)[1],validate=True)
        if len(raw)>40*1024*1024:raise ValueError()
        im=Image.open(io.BytesIO(raw))
        if im.width*im.height>MAX_PIXELS:raise ValueError()
        im.load();return im.convert('RGBA')
    except Exception:raise ValueError('图片无法读取或超过40MB/2500万像素限制') from None

def as_data(im):
    b=io.BytesIO();im.save(b,format='PNG');return 'data:image/png;base64,'+base64.b64encode(b.getvalue()).decode('ascii')

def template_mask(im):
    a=np.asarray(im.convert('RGBA'));red=(a[:,:,0]>150)&(a[:,:,1]<110)&(a[:,:,2]<110)&(a[:,:,3]>40)
    if red.sum()>30:
        # Each separate closed contour toggles its enclosure (outer body, camera holes).
        labels,n=ndimage.label(red);result=np.zeros(red.shape,bool);closed=0
        if n>100:raise ValueError('刀模红线噪点过多，请上传清晰的闭合轮廓')
        for i in range(1,n+1):
            line=labels==i
            filled=ndimage.binary_fill_holes(np.pad(line,2))[2:-2,2:-2]
            enclosed=filled&~line
            if enclosed.sum()<16:
                if line.sum()>40:raise ValueError('刀模存在未闭合轮廓，请检查红线或改传透明实心蒙版')
                continue
            result^=filled;closed+=1
        if not closed or result.mean()<.05:raise ValueError('未识别到有效壳面，请使用闭合红线或透明实心蒙版')
        return Image.fromarray((result*255).astype('uint8'))
    alpha=a[:,:,3]
    if (alpha<20).mean()<.01 or (alpha>220).mean()<.1:raise ValueError('刀模需为闭合红线或透明底实心蒙版；暂不支持黑白扫描图、PDF或DXF')
    return Image.fromarray(alpha.copy())

def safe_name(s):
    s=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',str(s))[:80].strip(' .')
    return s or '手机壳图案'

def generation_size(size):
    w,h=size;r=w/h
    if not 1/3<=r<=3:raise ValueError('当前AI补图支持1:3至3:1的画布比例，其他比例仍可直接排版下载')
    factor=2048/max(w,h)
    return (max(16,round(w*factor/16)*16),max(16,round(h*factor/16)*16))

def prepare(body,folder):
    frame=decode_image(body.get('frame'));coverage=decode_image(body.get('coverage')).getchannel('A');template=decode_image(body.get('template'));source=decode_image(body.get('source'))
    if frame.size!=template.size or frame.size!=coverage.size:raise ValueError('刀模与排版尺寸不一致，请重新上传刀模')
    mask=template_mask(template);preserve=body.get('preserve') is True
    cov=np.asarray(coverage);shell=np.asarray(mask)>0
    unknown=shell&(cov<254)
    if not shell.any():raise ValueError('刀模壳面为空')
    local=preserve and not unknown.any()
    if preserve and not (shell&(cov>0)).any():raise ValueError('素材没有落在刀模壳面内，请先调整位置')
    for key,im in [('frame',frame),('coverage',coverage),('template',template),('source',source),('mask',mask)]:im.save(folder/(key+'.png'))
    guide=frame.convert('RGB');arr=np.array(guide)
    if preserve:arr[unknown]=[28,220,110]
    guide=Image.fromarray(arr)
    gen_size=generation_size(frame.size) if not local else frame.size
    crop=None
    edit=np.zeros((frame.height,frame.width,4),dtype=np.uint8);edit[:,:,:3]=255;edit[:,:,3]=np.where(unknown if preserve else shell,0,255)
    edit_image=Image.fromarray(edit)
    if not local and str(body.get('channel')) in ('4','5'):
        ratios=['1:1','2:3','3:2','3:4','4:3','4:5','5:4','9:16','16:9','21:9']
        if str(body.get('channel'))=='5':ratios+=['1:4','4:1','1:8','8:1']
        r=frame.width/frame.height
        chosen=min(ratios,key=lambda v:abs(math.log(r/(int(v.split(':')[0])/int(v.split(':')[1])))))
        a,b=map(int,chosen.split(':'));factor=2048/max(a,b)
        gen_size=(max(16,round(a*factor/16)*16),max(16,round(b*factor/16)*16))
        scale=min(gen_size[0]/frame.width,gen_size[1]/frame.height)
        rw,rh=round(frame.width*scale),round(frame.height*scale)
        ox,oy=(gen_size[0]-rw)//2,(gen_size[1]-rh)//2
        padded=Image.new('RGB',gen_size,tuple(np.asarray(frame)[0,0,:3]));padded.paste(guide.resize((rw,rh),Image.Resampling.LANCZOS),(ox,oy));guide=padded
        edit_pad=Image.new('RGBA',gen_size,'white');edit_pad.paste(edit_image.resize((rw,rh),Image.Resampling.NEAREST),(ox,oy));edit_image=edit_pad
        crop=[ox/gen_size[0],oy/gen_size[1],(ox+rw)/gen_size[0],(oy+rh)/gen_size[1]]
    else:
        guide=guide.resize(gen_size,Image.Resampling.LANCZOS);edit_image=edit_image.resize(gen_size,Image.Resampling.NEAREST)
    guide.save(folder/'guide.png')
    source.thumbnail((1600,1600),Image.Resampling.LANCZOS);source.save(folder/'source-ref.png')
    edit_image.save(folder/'edit-mask.png')
    brief=str(body.get('prompt','')).strip()
    if len(brief)>2000:raise ValueError('补图要求请控制在2000字以内')
    text=('制作手机壳平面印刷图案，不是手机实物照片，不添加边框、手机、相机、刀模线或定位标记。第一张为当前排版，第二张为原素材。'
          '保持第一张的画布构图、缩放、位置与图案只出现一次。保留原有文字且不添加文字、署名、水印。')
    if preserve:text+='只补齐第一张绿色区域的背景，绿色仅代表待补区域，成图不得残留绿色；原图区域不重画。延续临近背景颜色和纹理，不在扩展区复制眼睛、人物、文字或绷带等主体。'
    else:text+='参照第一张的位置和第二张风格，重构完整图案。主体完整，不能因扩图生成重复主体或多余肢体，避免凹口区域出现重要内容。'
    text+='无白边、无接缝。'+brief
    (folder/'prompt.txt').write_text(text,encoding='utf-8')
    return {'size':list(frame.size),'gen_size':list(gen_size),'preserve':preserve,'local':local,'name':safe_name(body.get('name','手机壳图案')),'transform':body.get('transform',{}),'prompt':brief,'missing_pixels':int(unknown.sum()),'generation_crop':crop}

def finish(folder,output,meta,raw=None):
    frame=Image.open(folder/'frame.png').convert('RGB');mask=Image.open(folder/'mask.png').convert('L');coverage=Image.open(folder/'coverage.png').convert('L')
    if raw:
        generated=Image.open(raw).convert('RGB')
        if meta.get('generation_crop'):
            box=meta['generation_crop'];generated=generated.crop(tuple(round(v*(generated.width if i%2==0 else generated.height)) for i,v in enumerate(box)))
        ratio=generated.width/generated.height;target=frame.width/frame.height
        # Some Banana adapters return a nearby ratio; contain guide position by central cover, never stretch subject.
        if abs(math.log(ratio/target))>.04:
            from PIL import ImageOps
            generated=ImageOps.fit(generated,frame.size,method=Image.Resampling.LANCZOS)
        else:generated=generated.resize(frame.size,Image.Resampling.LANCZOS)
        if meta['preserve']:
            # Original opaque pixels are restored exactly; soft alpha pixels blend once.
            final=Image.composite(frame,generated,coverage)
            outside=Image.fromarray(np.where(np.asarray(mask)>0,0,255).astype('uint8'))
            final.paste(frame,(0,0),outside)
        else:final=generated
    else:final=frame
    output.mkdir(parents=True,exist_ok=True);name=meta['name'];final.save(output/(name+'.png'))
    cut=final.convert('RGBA');cut.putalpha(mask);cut.save(output/(name+'_印刷.png'))
    preview=Image.new('RGB',final.size,'white');preview.paste(final,(0,0),mask);preview.save(output/(name+'_预览.png'))
    qa={'size':list(final.size),'alpha_outside_max':0,'preserved_opaque_pixels_equal':None,'requires_visual_check':bool(raw)}
    if meta['preserve']:
        known=(np.asarray(coverage)==255)&(np.asarray(mask)>0)
        qa['preserved_opaque_pixels_equal']=bool(np.array_equal(np.asarray(final)[known],np.asarray(frame)[known]))
        if not qa['preserved_opaque_pixels_equal']:raise ValueError('原图保真校验失败，禁止作为成品输出')
    qa['alpha_outside_max']=int(np.asarray(cut)[:,:,3][np.asarray(mask)==0].max()) if (np.asarray(mask)==0).any() else 0
    (folder/'quality.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    return [name+'.png',name+'_印刷.png',name+'_预览.png']