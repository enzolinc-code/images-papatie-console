/* Innovation: source image + extensible style-card deck. */
(()=>{
let chosen=null,style='semi-realistic-refined',working=false,deckSerial='',sourceSerial='';
const button=document.createElement('button');button.id='stInnovateMode';button.innerHTML='<b>✦ 二次创新</b><small>保留人物动作 · 更换画风</small>';document.querySelector('#stMode .st-mode').append(button);
const panel=document.createElement('section');panel.id='innovation';panel.hidden=true;
panel.innerHTML=`<div class="in-steps"><span><i>1</i>放入原图</span><span><i>2</i>抽选画风</span><span><i>3</i>开始制作</span></div><div class="in-workspace"><section class="in-panel"><div class="in-head"><h2>人物原图</h2><small>JPG / PNG / WebP</small></div><div id="inSource" class="in-source" role="button" tabindex="0" aria-label="上传或更换需要创新的图片"></div><div class="in-source-actions"><label class="filebtn">上传图片<input id="inFile" type="file" accept="image/png,image/jpeg,image/webp" hidden></label><button class="ghost" id="inLibrary">从素材库选择</button></div><p class="in-help">保留原人物、服装和当前动作。<br>建议使用人物完整、手部清晰的图片。</p></section><section class="in-panel"><div class="in-head"><h2>选择画风</h2><small id="inStyleCount"></small></div><div id="inStyles" class="in-deck" role="group" aria-label="选择画风卡牌"></div><div class="in-switch"><button class="ghost" id="inPrev" aria-label="上一个画风">←</button><span id="inStylePosition" aria-live="polite"></span><button class="ghost" id="inNext" aria-label="下一个画风">→</button></div><div class="in-description"><b>这张卡决定画法，你的原图决定人物和动作。</b><br>左右切换卡牌，点击选择喜欢的画风。</div></section></div><div class="in-footer"><p><span id="inChosenStyle">半写实精绘</span> · 生成 1 张透明 PNG<br><small>固定使用 Image 2.6（通道3） · 原图保留</small></p><button class="primary" id="inGenerate">开始二次创新 · 1次生图</button></div><p class="in-help" id="inStatus" role="status">完成后请检查人物相似度、手指和抠图边缘。</p>`;
document.querySelector('main').insertBefore(panel,document.querySelector('main>footer'));
function items(){return state.styles||[];}
function card(s,side='center'){const selected=s.id===style;return `<button class="in-card in-card-${side}" data-in-style="${esc(s.id)}" aria-pressed="${selected}" aria-label="选择${esc(s.name)}" ${working?'disabled':''}>${selected?'<span class="in-selected">✓ 已选择</span>':''}<div class="in-art"><img src="${esc(s.preview)}" alt="${esc(s.name)}效果示例"></div><div class="in-card-info"><b>${esc(s.name)}</b><small>${esc(s.description|| (s.id==='semi-realistic-refined'?'细腻线条 · 柔和光影':'风格效果以卡牌示例为参考'))}</small></div></button>`;}
function draw(){
 const a=state.assets.find(a=>a.id===chosen&&!a.trashed&&!a.purged);if(!a)chosen=null;
 const ss=a?JSON.stringify([a.id,a.url,a.name]):'';if(ss!==sourceSerial||!$('inSource').childNodes.length){sourceSerial=ss;$('inSource').innerHTML=a?`<img src="${esc(a.url)}" alt="人物原图"><span>${esc(a.name)}</span>`:'<span class="in-plus">＋</span><span>放入需要创新的图片</span><small>照片、已有透明立牌都可以</small>';}
 const list=items();if(!list.some(s=>s.id===style)&&list.length)style=list[0].id;
 const index=list.findIndex(s=>s.id===style),current=list[index];const serial=JSON.stringify([list,style,working]);
 if(serial!==deckSerial){deckSerial=serial;let html='';
 if(current){if(list.length>1){html+=card(list[(index-1+list.length)%list.length],'left');if(list.length>2)html+=card(list[(index+1)%list.length],'right');}else{html='<div class="in-future in-future-left" aria-hidden="true"><span>✧</span>更多画风<small>待接入</small></div><div class="in-future in-future-right" aria-hidden="true"><span>✦</span>更多画风<small>待接入</small></div>';}
 html+=card(current);}
 else html='<p class="in-help">风格库暂未就绪，请稍后刷新。</p>';
 $('inStyles').innerHTML=html;}
 $('inStyleCount').textContent=list.length+' 款可用';$('inStylePosition').textContent=current?current.name+' · '+(index+1)+' / '+list.length:'暂无画风';$('inChosenStyle').textContent=current?.name||'请选择画风';
 for(const id of ['inPrev','inNext'])$(id).disabled=working||list.length<2;
 $('inGenerate').disabled=!chosen||working||!state.health?.innovation||!state.health?.key||!current;
 $('inLibrary').disabled=working;$('inFile').disabled=working;$('inSource').setAttribute('aria-disabled',String(working));$('inSource').tabIndex=working?-1:0;
 panel.querySelector('.in-description').innerHTML='<b>这张卡决定画法，你的原图决定人物和动作。</b><br>'+(list.length>1?'左右切换卡牌，点击选择喜欢的画风。':'当前仅半写实精绘可用；两侧为待接入的扩展卡。');
}
function move(delta){const list=items();if(working||list.length<2)return;const i=list.findIndex(s=>s.id===style);style=list[(i+delta+list.length)%list.length].id;draw();}
$('inPrev').onclick=()=>move(-1);$('inNext').onclick=()=>move(1);
$('inStyles').addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();move(e.key==='ArrowLeft'?-1:1);$('inStyles').querySelector('.in-card-center')?.focus();}});
const oldTab=tab;tab=function(name){const yes=name==='innovation';if(yes)oldTab('make');else oldTab(name);document.body.dataset.innovation=yes?'true':'false';panel.hidden=!yes;button.classList.toggle('active',yes);if(yes){draw();window.scrollTo(0,0)}};
$('stMaterialLibrary').addEventListener('click',e=>{if(document.body.dataset.innovation!=='true'||working)return;const pick=e.target.closest('[data-source]');if(!pick)return;e.preventDefault();e.stopImmediatePropagation();chosen=pick.dataset.source;draw();$('stMaterialLibrary').close()},true);
button.onclick=()=>tab('innovation');$('inLibrary').onclick=()=>{if(!working)$('stMaterialLibrary').showModal()};
document.addEventListener('click',e=>{if(document.body.dataset.innovation!=='true')return;const pick=e.target.closest('[data-source]');if(pick&&!working){chosen=pick.dataset.source;draw()}const c=e.target.closest('[data-in-style]');if(c&&!working&&items().some(s=>s.id===c.dataset.inStyle)){style=c.dataset.inStyle;draw()}});
function openSourceFile(){if(!working&&!$('inFile').disabled)$('inFile').click();}
$('inSource').onclick=openSourceFile;
$('inSource').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openSourceFile();}};
$('inFile').onchange=async e=>{const f=e.target.files[0];if(!f)return;working=true;draw();try{const a=await upload(f,'reference');chosen=a.id;await refresh();$('inStatus').textContent='图片已就绪。'}catch(err){notice(err.message,true)}finally{working=false;e.target.value='';draw()}};
$('inGenerate').onclick=()=>withButton($('inGenerate'),async()=>{if(working||!chosen||!items().some(s=>s.id===style))return;working=true;draw();try{const body={mode:'innovate',source:chosen,style,channel:'3'};await api('/api/plan',body);await api('/api/jobs',{...body,nonce:crypto.randomUUID()});await refresh();gv.view='tasks';tab('jobs');renderJobs(true);notice('已提交1张二次创新，原图保留。生成后自动抠图，请到成品库检查。')}catch(err){notice(err.message,true)}finally{working=false;draw()}});
const oldRefresh=refresh;refresh=async function(...args){const r=await oldRefresh.apply(this,args);if(!panel.hidden)draw();return r};draw();
})();