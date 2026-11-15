from pathlib import Path
from PIL import Image,ImageStat,ImageFilter

def inspect(path,role):
    try:
        with Image.open(path) as im:
            im.load();w,h=im.size;rgba=im.convert('RGBA');alpha=rgba.getchannel('A')
            if min(w,h)<128:return {'status':'excluded','reasons':['分辨率过低（短边不足128像素）']}
            if role=='product' and (not alpha.getbbox() or alpha.getextrema()[0]==255):return {'status':'excluded','reasons':['需要非空的真实透明人物PNG']}
            reasons=[]
            if min(w,h)<640:reasons.append('分辨率偏低，请检查脸部和手指')
            if role=='product':
                b=alpha.getbbox()
                if b and (b[0]<2 or b[1]<2 or b[2]>w-2 or b[3]>h-2):reasons.append('人物贴近画布边缘，可能裁断')
            gray=rgba.convert('L');gray.thumbnail((256,256));edge=gray.filter(ImageFilter.FIND_EDGES)
            if ImageStat.Stat(edge).stddev[0]<12:reasons.append('画面细节偏少或模糊，请检查')
            return {'status':'review' if reasons else 'usable','reasons':reasons or ['基础画质通过；角度、遮挡、多人及身份需目视判断']}
    except (OSError,ValueError):return {'status':'excluded','reasons':['图片无法解码']}

def report(products,scenes,asset_path):
    return [dict(asset=aid,role=role,**inspect(asset_path(aid),role)) for role,ids in [('product',products),('scene',scenes)] for aid in ids]

def select(body,asset_path):
    approved=set(body.get('review_approved',[]));excluded=set(body.get('excluded_assets',[]));rows=report(body.get('products',[]),body.get('scenes',[]),asset_path)
    valid={r['asset'] for r in rows if r['asset'] not in excluded and r['status']!='excluded' and (r['status']!='review' or r['asset'] in approved)}
    return [i for i in body['products'] if i in valid],[i for i in body['scenes'] if i in valid]