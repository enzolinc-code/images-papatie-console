"""Transparent acrylic plate, thickness and highlights, separate from the original print."""
from PIL import Image,ImageDraw,ImageFilter,ImageChops
VERSION='clear-acrylic-v2'

def shift(mask,dx,dy):
    result=Image.new('L',mask.size);result.paste(mask,(dx,dy));return result

def layer(mask,color):
    result=Image.new('RGBA',mask.size,color);result.putalpha(mask);return result

def render(base,printed,shadow=.15,rim=.12):
    base=base.copy().convert('RGBA');alpha=printed.getchannel('A');bbox=alpha.getbbox()
    if not bbox:raise ValueError('人物印刷层为空')
    width=bbox[2]-bbox[0];height=bbox[3]-bbox[1]
    border=max(3,min(12,round(width*.012)));depth=max(1,min(4,round(width*.004)))
    seed=alpha.point(lambda a:255 if a>35 else 0)
    plate=seed.filter(ImageFilter.MaxFilter(border*2+1)).filter(ImageFilter.GaussianBlur(max(.6,border*.16))).point(lambda a:255 if a>115 else 0)
    parts={}
    # A small real separation from the photographed support, rather than a whole-person halo.
    if shadow:
        m=shift(plate,depth+1,depth*2+1).filter(ImageFilter.GaussianBlur(max(1.1,width*.004)))
        m=m.point(lambda a:round(a*min(.32,shadow*1.6)));parts['接触阴影']=layer(m,(25,30,33));base.alpha_composite(parts['接触阴影'])
    # Clear substrate refracts the photographed background subtly, without opaque white fill.
    clear=ImageChops.subtract(plate,alpha)
    blurred=base.filter(ImageFilter.GaussianBlur(.55));refraction=Image.composite(blurred,base,clear.point(lambda a:round(a*.25)))
    base=refraction
    if rim:
        side=ImageChops.subtract(shift(plate,depth,depth),plate)
        side=side.point(lambda a:round(a*.5));parts['亚克力厚度侧边']=layer(side,(91,111,118));base.alpha_composite(parts['亚克力厚度侧边'])
        # The clear cut edge has directional glints and a darker opposite edge, not a white sticker border.
        edge=ImageChops.subtract(plate,plate.filter(ImageFilter.MinFilter(3)))
        up=ImageChops.subtract(plate,shift(plate,1,1));down=ImageChops.subtract(plate,shift(plate,-1,-1))
        strength=min(1,max(.55,rim*5))
        soft=clear.point(lambda a:round(a*.035));parts['透明板薄层']=layer(soft,(211,231,237));base.alpha_composite(parts['透明板薄层'])
        glint=ImageChops.lighter(edge.point(lambda a:round(a*.16*strength)),up.point(lambda a:round(a*.83*strength)))
        parts['切边高光']=layer(glint,(247,253,255));base.alpha_composite(parts['切边高光'])
        low=down.point(lambda a:round(a*.30*strength));parts['切边暗线']=layer(low,(71,93,104));base.alpha_composite(parts['切边暗线'])
    # The print layer itself is unchanged; fingers and face are never synthesized or locally warped.
    base.alpha_composite(printed)
    if rim:
        gloss=Image.new('L',base.size);d=ImageDraw.Draw(gloss);x0,y0,x1,y1=bbox
        d.polygon([(x0+width*.08,y0),(x0+width*.19,y0),(x0+width*.69,y1),(x0+width*.58,y1)],fill=13)
        gloss=ImageChops.multiply(gloss.filter(ImageFilter.GaussianBlur(max(1,width*.015))),plate)
        parts['表面弱反射']=layer(gloss,(248,253,255));base.alpha_composite(parts['表面弱反射'])
    return base,parts,{'version':VERSION,'clear_border_px':border,'thickness_px':depth,'opaque_white_fill':False,'print_layer_unchanged':True}