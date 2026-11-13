/* Original-PNG scene compositor. The product is never sent to the cleanup model. */
const fidelityPanel=document.createElement('div');fidelityPanel.className='card';fidelityPanel.style.marginBottom='20px';
fidelityPanel.innerHTML='<div class="section-head"><h2>场景制作方式</h2><select id="sceneEngine"><option value="fidelity">原图保真替换（默认）</option><option value="ai">AI 创意融合（人物细节可能变化）</option></select></div><p id="fidelityHint" class="muted">人物PNG仅做整体透视，不重画手指、动作和五官。每个场景先标定并确认干净背景，之后本地批量合成，0次生图。</p><button class="ghost" id="editFidelity">标定 / 管理已选场景</button>';
document.querySelector('#scene .intro').after(fidelityPanel);
const fd=document.createElement('dialog');fd.id='fidelityDialog';
fd.innerHTML='<div class="modalbar"><b>场景模板 · 原图保真</b><button id="fcClose" class="ghost">关闭</button></div><div class="fc-body"><div class="fc-controls"><label>当前场景<select id="fcScene"></select></label><label>位置参考立牌<select id="fcProduct"></select></label><div class="fc-toolbar"><button id="fcMove" class="ghost">调整立牌位置</button><button id="fcPaint" class="ghost">涂抹旧立牌</button><label>画笔<input id="fcBrush" type="range" min="4" max="100" value="30"></label><button id="fcErase" class="ghost">橡皮擦</button><button id="fcClear" class="ghost">清空本次涂抹</button></div><p class="muted">蓝色四角代表立牌完整平面：拖动角点调整透视，拖动蓝框内部整体移动。涂抹模式请覆盖旧立牌、配套图案与阴影，避开不需要修改的区域。</p></div><div class="fc-columns"><div><canvas id="fcCanvas"></canvas><div class="fc-toolbar"><button id="fcLeft" class="ghost">↶ 旋转5°</button><button id="fcRight" class="ghost">↷ 旋转5°</button><button id="fcReset" class="ghost">重置位置</button></div></div><div><h3>点击原图标记承托位置</h3><img id="fcSource" class="checker" style="height:160px;width:auto;max-width:100%;cursor:crosshair" alt="点击肘部或衣袖搭边位置"><p id="fcAnchorText" class="muted"></p><h3>精确本地预览</h3><img id="fcPreview" alt="保存标定后点击预览" class="checker"><p id="fcStatus" class="muted">尚未读取模板</p><label class="field">人物承托线位置（从上到下）<input id="fcAnchor" type="range" min="0" max="1" step=".01" value=".72"></label><label class="field">场景承托线位置（从上到下）<input id="fcSupport" type="range" min="0" max="1" step=".01" value=".45"></label><button id="fcAlign" class="ghost">将人物承托线对齐到场景线</button><label class="field">接触阴影<input id="fcShadow" type="range" min="0" max=".5" step=".01" value=".15"></label><label class="field">透明切边<input id="fcRim" type="range" min="0" max=".4" step=".01" value=".12"></label></div></div><div class="fc-actions"><button id="fcSave" class="ghost">保存标定</button><button id="fcUseOriginal" class="ghost">原场景已无立牌，直接使用</button><label class="filebtn">上传同尺寸干净背景<input id="fcCleanFile" type="file" accept="image/png,image/jpeg,image/webp"></label><button id="fcCleanAI" class="ghost">AI 清理涂抹区域 · 1次生图</button><button id="fcPreviewButton" class="ghost">精确预览（免费）</button><button id="fcApprove" class="primary">已检查干净背景，确认可复用</button></div><p class="muted">AI只恢复涂抹区域背景，不接收人物立牌PNG。画笔范围外保留原场景像素；检查通过前不能批量合成。预览中仍有旧立牌时请先清理，不能仅用新人物遮盖。不同造型会等比例放入同一透视平面，请逐场景检查接触位置。</p><div id="fcMessage" role="status"></div></div>';
document.body.append(fd);
const fc={scene:null,product:null,template:null,quad:null,aspect:1,base:null,clean:null,mask:document.createElement('canvas'),mode:'move',dirtyMask:false,pointer:null,request:0};
const fcanvas=$('fcCanvas'),fctx=fcanvas.getContext('2d');
function fmsg(text,error=false){$('fcMessage').textContent=text;$('fcMessage').style.color=error?'#b7492f':'#537257'}
function fimage(url){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('无法读取图片'));im.src=url})}
function fdefault(){let width=.36,height=width*fc.base.width/fc.base.height/fc.aspect;if(height>.72){height=.72;width=height*fc.base.height/fc.base.width*fc.aspect}let top=Number($('fcSupport').value)-height*Number($('fcAnchor').value);top=Math.max(.03,Math.min(1-height-.03,top));return [[.5-width/2,top],[.5+width/2,top],[.5+width/2,top+height],[.5-width/2,top+height]]}
function fdraw(){
 if(!fc.base||!fc.quad)return;
 fctx.clearRect(0,0,fcanvas.width,fcanvas.height);fctx.drawImage(fc.mode==='move'&&fc.clean?fc.clean:fc.base,0,0,fcanvas.width,fcanvas.height);
 if(fc.mode!=='move'){const tinted=document.createElement('canvas');tinted.width=fc.mask.width;tinted.height=fc.mask.height;const c=tinted.getContext('2d');c.drawImage(fc.mask,0,0);c.globalCompositeOperation='source-in';c.fillStyle='#f44242';c.fillRect(0,0,tinted.width,tinted.height);fctx.globalAlpha=.5;fctx.drawImage(tinted,0,0);fctx.globalAlpha=1}
 const pts=fc.quad.map(([x,y])=>[x*fcanvas.width,y*fcanvas.height]);fctx.lineWidth=Math.max(2,fcanvas.width/450);fctx.strokeStyle='#2986d1';fctx.beginPath();pts.forEach(([x,y],i)=>i?fctx.lineTo(x,y):fctx.moveTo(x,y));fctx.closePath();fctx.stroke();
 pts.forEach(([x,y],i)=>{fctx.beginPath();fctx.arc(x,y,Math.max(6,fcanvas.width*.008),0,Math.PI*2);fctx.fillStyle='white';fctx.fill();fctx.stroke();fctx.fillStyle='#206aab';fctx.font=Math.max(14,fcanvas.width*.018)+'px sans-serif';fctx.fillText(String(i+1),x+10,y-10)});
 const anchor=Number($('fcAnchor').value),left=[pts[0][0]*(1-anchor)+pts[3][0]*anchor,pts[0][1]*(1-anchor)+pts[3][1]*anchor],right=[pts[1][0]*(1-anchor)+pts[2][0]*anchor,pts[1][1]*(1-anchor)+pts[2][1]*anchor];
 fctx.setLineDash([8,6]);fctx.strokeStyle='#24a09a';fctx.beginPath();fctx.moveTo(...left);fctx.lineTo(...right);fctx.stroke();fctx.strokeStyle='#eb9d30';fctx.beginPath();fctx.moveTo(0,Number($('fcSupport').value)*fcanvas.height);fctx.lineTo(fcanvas.width,Number($('fcSupport').value)*fcanvas.height);fctx.stroke();fctx.setLineDash([]);
}
async function fload(){
 const request=++fc.request;const scene=$('fcScene').value;const product=$('fcProduct').value;
 if(!scene||!product)throw Error('请先选择场景和透明立牌');
 const [result,base,fg]=await Promise.all([api('/api/fidelity/get',{scene,product}),fimage('/media/'+scene),fimage('/media/'+product)]);
 if(request!==fc.request)return;
 fc.scene=scene;fc.product=product;fc.template=result.template;fc.base=base;fc.clean=null;
 fcanvas.width=base.naturalWidth;fcanvas.height=base.naturalHeight;fc.mask.width=fcanvas.width;fc.mask.height=fcanvas.height;fc.dirtyMask=false;fc.clearMask=false;
 if(result.mask){const savedMask=await fimage('data:image/png;base64,'+result.mask);if(request!==fc.request)return;fc.mask.getContext('2d').drawImage(savedMask,0,0);}
 const tmp=document.createElement('canvas');tmp.width=fg.naturalWidth;tmp.height=fg.naturalHeight;const c=tmp.getContext('2d');c.drawImage(fg,0,0);const pixels=c.getImageData(0,0,tmp.width,tmp.height).data;let x0=tmp.width,y0=tmp.height,x1=0,y1=0;for(let y=0;y<tmp.height;y++)for(let x=0;x<tmp.width;x++)if(pixels[(y*tmp.width+x)*4+3]>3){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y)}
 fc.aspect=result.template?.aspect||((x1-x0+1)/(y1-y0+1));
 const cropped=document.createElement('canvas');cropped.width=x1-x0+1;cropped.height=y1-y0+1;cropped.getContext('2d').drawImage(fg,x0,y0,cropped.width,cropped.height,0,0,cropped.width,cropped.height);$('fcSource').src=cropped.toDataURL('image/png');fc.sourceAnchor=result.source_anchor??.86;$('fcAnchorText').textContent='人物承托位置：'+Math.round(fc.sourceAnchor*100)+'% · 点击肘部或袖底位置可更改';
 const t=result.template||{};for(const [id,key,value]of [['fcAnchor','anchor',.84],['fcSupport','support',.43],['fcShadow','shadow',.15],['fcRim','rim',.12]])$(id).value=t[key]??value;
 fc.quad=t.quad||fdefault();fc.mode='move';
 if(t.clean_asset){const clean=await fimage('/media/'+t.clean_asset);if(request!==fc.request)return;fc.clean=clean;}
 $('fcStatus').textContent=result.ready?'干净背景已确认，可复用':'背景尚未确认，需清理或提供干净场景';
 $('fcPreview').removeAttribute('src');fdraw();fmsg('已读取场景。涂抹蒙版会在按“保存标定”时保存；已有清理区域无需重画即可再清理。');
}
async function fsave(extra={}){
 if(!fc.scene)throw Error('请先读取场景');
 const body={scene:fc.scene,product:fc.product,source_anchor:fc.sourceAnchor,quad:fc.quad,aspect:fc.aspect,anchor:Number($('fcAnchor').value),support:Number($('fcSupport').value),shadow:Number($('fcShadow').value),rim:Number($('fcRim').value),...extra};
 if(fc.clearMask)body.clear_mask=true;
 if(fc.dirtyMask)body.mask=fc.mask.toDataURL('image/png').split(',')[1];
 fc.template=await api('/api/fidelity/save',body);fc.dirtyMask=false;fc.clearMask=false;fmsg('标定已保存；人物只使用原PNG。');return fc.template;
}
$('editFidelity').onclick=()=>action(async()=>{
 if(!sceneAssets.length)throw Error('请先读取场景目录');
 const products=state.assets.filter(a=>productIds.has(a.id)&&a.transparent);
 if(!products.length)throw Error('请先选择一张透明立牌');
 $('fcScene').innerHTML=sceneAssets.map(a=>'<option value="'+a.id+'">'+esc(a.name)+'</option>').join('');
 $('fcProduct').innerHTML=products.map(a=>'<option value="'+a.id+'">'+esc(a.name)+'</option>').join('');
 fd.showModal();await fload();
});
$('fcClose').onclick=()=>fd.close();$('fcScene').onchange=()=>action(fload);$('fcProduct').onchange=()=>action(fload);
$('fcMove').onclick=()=>{fc.mode='move';fdraw()};$('fcPaint').onclick=()=>{fc.mode='paint';fdraw()};$('fcErase').onclick=()=>{fc.mode='erase';fdraw()};
$('fcClear').onclick=()=>{fc.mask.getContext('2d').clearRect(0,0,fc.mask.width,fc.mask.height);fc.dirtyMask=false;fc.clearMask=true;fdraw();fmsg('清理范围已清空，保存后生效。请重新涂抹或重新选择干净背景。')};
$('fcReset').onclick=()=>{fc.quad=fdefault();fdraw()};
for(const id of ['fcAnchor','fcSupport','fcShadow','fcRim'])$(id).oninput=fdraw;
$('fcAlign').onclick=()=>{const a=Number($('fcAnchor').value),y=(fc.quad[0][1]*(1-a)+fc.quad[3][1]*a+fc.quad[1][1]*(1-a)+fc.quad[2][1]*a)/2,dy=Number($('fcSupport').value)-y;const q=fc.quad.map(([x,y])=>[x,y+dy]);if(q.some(([x,y])=>y<0||y>1)){fmsg('对齐会超出画布，请先缩小立牌平面',true);return}fc.quad=q;fdraw()};
function frotate(deg){const cx=fc.quad.reduce((n,p)=>n+p[0],0)/4,cy=fc.quad.reduce((n,p)=>n+p[1],0)/4;const a=deg*Math.PI/180,w=fc.base.width,h=fc.base.height;const q=fc.quad.map(([x,y])=>[cx+((x-cx)*w*Math.cos(a)-(y-cy)*h*Math.sin(a))/w,cy+((x-cx)*w*Math.sin(a)+(y-cy)*h*Math.cos(a))/h]);if(q.some(p=>p.some(v=>v<0||v>1))){fmsg('旋转后超出画布，请先移动或缩小',true);return}fc.quad=q;fdraw()}
$('fcLeft').onclick=()=>frotate(-5);$('fcRight').onclick=()=>frotate(5);
function fpoint(e){const rect=fcanvas.getBoundingClientRect();return [(e.clientX-rect.left)/rect.width,(e.clientY-rect.top)/rect.height]}
fcanvas.onpointerdown=e=>{
 e.preventDefault();fcanvas.setPointerCapture(e.pointerId);const p=fpoint(e);
 if(fc.mode==='move'){let i=fc.quad.findIndex(q=>Math.hypot((q[0]-p[0])*fcanvas.clientWidth,(q[1]-p[1])*fcanvas.clientHeight)<22);fc.pointer={start:p,quad:fc.quad.map(q=>[...q]),corner:i};}
 else {fc.pointer={start:p};fpaint(p,p)}
};
function fpaint(a,b){const c=fc.mask.getContext('2d');c.globalCompositeOperation=fc.mode==='erase'?'destination-out':'source-over';c.strokeStyle='white';c.lineWidth=Number($('fcBrush').value)*fcanvas.width/700;c.lineCap='round';c.beginPath();c.moveTo(a[0]*fc.mask.width,a[1]*fc.mask.height);c.lineTo(b[0]*fc.mask.width+.01,b[1]*fc.mask.height+.01);c.stroke();fc.dirtyMask=true;fdraw()}
fcanvas.onpointermove=e=>{
 if(!fc.pointer)return;const p=fpoint(e);
 if(fc.mode!=='move'){fpaint(fc.pointer.start,p);fc.pointer.start=p;return}
 const drag=fc.pointer;
 if(drag.corner>=0){fc.quad[drag.corner]=p.map(v=>Math.max(0,Math.min(1,v)));}
 else {let dx=p[0]-drag.start[0],dy=p[1]-drag.start[1];dx=Math.max(-Math.min(...drag.quad.map(q=>q[0])),Math.min(1-Math.max(...drag.quad.map(q=>q[0])),dx));dy=Math.max(-Math.min(...drag.quad.map(q=>q[1])),Math.min(1-Math.max(...drag.quad.map(q=>q[1])),dy));fc.quad=drag.quad.map(q=>[q[0]+dx,q[1]+dy]);}
 fdraw();
};
fcanvas.onpointerup=()=>fc.pointer=null;fcanvas.onpointercancel=()=>fc.pointer=null;
function fbutton(id,fn){$(id).onclick=()=>withButton($(id),async()=>{try{await fn()}catch(e){fmsg(e.message,true);throw e}})}
fbutton('fcSave',()=>fsave());
fbutton('fcUseOriginal',async()=>{await fsave({use_original:true});fc.clean=fc.base;fdraw();fmsg('原场景已选为干净背景；请检查无旧立牌后点击确认可复用。')});
$('fcCleanFile').onchange=()=>action(async()=>{const file=$('fcCleanFile').files[0];if(!file)return;const a=await upload(file,'cleanplate');await fsave({clean_asset:a.id});fc.clean=await fimage(a.url);fdraw();fmsg('干净背景已上传，请检查后确认可复用。')});
fbutton('fcCleanAI',async()=>{await fsave();const body={mode:'background',scene:fc.scene,channel:$('imageChannel').value};await api('/api/plan',body);await api('/api/jobs',{...body,nonce:crypto.randomUUID()});fmsg('已提交1次背景清理，人物PNG没有发送给模型。请到任务页查看完成后重新读取此场景，检查并确认。');fd.close();await refresh();tab('jobs')});
fbutton('fcPreviewButton',async()=>{await fsave();const a=await api('/api/fidelity/preview',{scene:fc.scene,product:fc.product});$('fcPreview').src=a.url;fmsg('已用原始PNG生成本地精确预览，没有调用生图。')});
fbutton('fcApprove',async()=>{await fsave();await api('/api/fidelity/approve',{scene:fc.scene});$('fcStatus').textContent='已确认，可用于批量保真合成';fmsg('干净背景与模板已确认，可关闭并选择下一个场景。')});
const fidelityOldApi=api;
api=async function(path,body){if(body?.mode==='scenes'&&(path==='/api/plan'||path==='/api/jobs'))body={...body,scene_engine:body.scene_engine||$('sceneEngine').value};return fidelityOldApi(path,body)};
const fidelityEstimates=estimates;
estimates=function(){fidelityEstimates();if($('sceneEngine').value==='fidelity'){$('sceneEstimate').textContent=$('sceneEstimate').textContent.replace(/ · .*次生图/,' · 本地合成，0次生图');$('startScenes').textContent='开始批量保真合成';$('sceneEstimate').nextElementSibling.textContent='本地合成不调用生图；仅首次AI清理背景按次计费'}else {$('startScenes').textContent='开始批量AI替换';$('sceneEstimate').nextElementSibling.textContent='每张成品为一次所选通道生图'}};
$('sceneEngine').onchange=()=>{localStorage.setItem('papapai-scene-engine',$('sceneEngine').value);$('editFidelity').disabled=$('sceneEngine').value!=='fidelity';estimates()};
$('sceneEngine').value=localStorage.getItem('papapai-scene-engine')==='ai'?'ai':'fidelity';estimates();
$('fcSource').onclick=e=>{const box=e.currentTarget.getBoundingClientRect();fc.sourceAnchor=Math.max(.01,Math.min(.99,(e.clientY-box.top)/box.height));$('fcAnchorText').textContent='人物承托位置：'+Math.round(fc.sourceAnchor*100)+'% · 保存后可跨场景复用';fmsg('人物承托点已选择，请保存并预览；不同造型不会拉伸或重画。')};

function fsceneMarks(){for(const input of document.querySelectorAll('[data-scene]')){const card=input.closest('.pick');let mark=card.querySelector('.fc-ready');if(!mark){mark=document.createElement('span');mark.className='fc-ready';card.append(mark)}const st=state.scene_templates?.[input.dataset.scene];mark.textContent=st?.ready?'模板已就绪':st?.calibrated?'待确认背景':'未标定';mark.style.background=st?.ready?'#e3f2df':'#fff1d9'}}
const fOldSceneRender=renderScenes;renderScenes=function(){fOldSceneRender();fsceneMarks()};
const fOldRefresh=refresh;refresh=async function(){await fOldRefresh();fsceneMarks()};
