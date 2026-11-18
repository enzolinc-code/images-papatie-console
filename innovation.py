"""Versioned style packs; source supplies identity/pose, style supplies rendering only."""
from pathlib import Path
import json,re

def styles(root):
 out=[]
 for p in sorted((root/'styles').glob('*/style.json')):
  s=json.loads(p.read_text('utf-8'))
  if s.get('enabled'):out.append(s)
 return out

def get(root,identity):
 if not isinstance(identity,str) or not re.fullmatch('[a-z0-9-]{1,60}',identity):raise ValueError('风格不存在')
 s=next((s for s in styles(root) if s['id']==identity),None)
 if not s:raise ValueError('风格不存在或已停用')
 return s

def public(root):
 return [{'id':s['id'],'name':s['name'],'version':s['version'],'preview':'/style-art/'+s['id']+'.jpg'} for s in styles(root)]

def reference(root,aid):
 if not isinstance(aid,str) or not aid.startswith('__style__:'):return None
 s=get(root,aid.split(':',1)[1]);p=root/'styles'/s['id']/'reference.png'
 if not p.is_file():raise ValueError('风格参考图不可用')
 return p

def task(root,source,style_id,path):
 s=get(root,style_id)
 from PIL import Image
 with Image.open(path) as im:r=im.width/im.height
 sizes={'1:1':1,'3:4':.75,'4:3':4/3,'2:3':2/3,'3:2':1.5,'9:16':9/16,'16:9':16/9}
 import math
 size=min(sizes,key=lambda k:abs(math.log(r/sizes[k])))
 prompt=('图1是唯一的人物身份、服装、配饰、原动作与构图参考；图2只提供绘制技法。禁止把图2的人物脸型、发型、服饰、配饰和姿势带入图1。'
 '将图1完整转绘为统一的半写实精绘数字插画，不是照片加滤镜。保持原人物辨识度、发型服装、身体比例、肩肘腕位置、左右手关系、每根可见手指和遮挡，禁止换动作、左右镜像、多指粘连或残肢。'
 +s['rules']+' 避免：'+s['avoid']+'。'
 '原人物完整入镜，四周至少留8%余量，不裁头发、发饰、衣袖、双肘与指尖；不补原图本来被裁掉的身体。'
 '输出均匀纯浅灰背景，不画棋盘格、底座、桌子、显示器、阴影、文字、水印或白色轮廓边。薄纱保留轻薄叠层；背景供后续本地抠图，不声称原始生成图透明。')
 return {'name':s['name']+' · 二次创新','kind':'cutout','refs':[source,'__style__:'+style_id],'prompt':prompt,'size':size,'style_id':style_id,'style_version':s['version'],'source_asset':source}
