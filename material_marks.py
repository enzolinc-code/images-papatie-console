"""Material favorites and tags, independent from original asset records."""
import json
from pathlib import Path

def read(data):
    p=Path(data)/'material_marks.json'
    return json.loads(p.read_text('utf-8')) if p.exists() else {}

def update(data,aid,favorite,tags):
    if not isinstance(favorite,bool):raise ValueError('收藏参数无效')
    if not isinstance(tags,list) or len(tags)>8:raise ValueError('最多8个标签')
    cleaned=[]
    for tag in tags:
        if not isinstance(tag,str) or not 1<=len(tag.strip())<=20:raise ValueError('每个标签需为1至20字')
        tag=tag.strip()
        if any(ord(c)<32 for c in tag):raise ValueError('标签不能包含控制字符')
        if tag not in cleaned:cleaned.append(tag)
    marks=read(data);marks[aid]={'favorite':favorite,'tags':cleaned}
    p=Path(data)/'material_marks.json';tmp=p.with_suffix('.writing');tmp.write_text(json.dumps(marks,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)
    return marks[aid]
