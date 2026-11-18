const poseLegacyAliases={chin:'p07',both:'p10',edge:'p02',heart:'p16',wave:'p18',cross:'p03',lean:'p09',pillow:'p14'};
/* Organized reference poses; preview photos are never sent as identity inputs. */
function poseSvg(id){const p=state.poses.find(p=>p.id===id);return '<img class="pose-photo" src="/pose-art/'+encodeURIComponent(id)+'.png?v=papatie20-20261116" alt="'+esc(p?.image_kind==='reference'?'动作参考照片':'AI姿势示意图')+'" loading="lazy">'}
function poseCard(p){const reference=p.image_kind==='reference';return '<label class="pose pose-illustrated"><input type="checkbox" data-pose="'+esc(p.id)+'" '+(poseIds.has(p.id)?'checked':'')+' aria-label="选择'+esc(p.name)+'"><span class="pose-tick" aria-hidden="true">✓</span><div class="pose-art">'+poseSvg(p.id)+'</div><span class="pose-kind">'+(reference?'动作参考照片 · '+esc(p.code):'原有AI姿势图')+'</span><b>'+esc(p.name)+'</b><small title="'+esc(p.hint)+'">'+esc(p.action||p.hint)+'</small>'+(reference?'<span class="pose-risk">'+esc(p.group)+' · 风险'+esc(p.risk)+'</span>':'')+'<button type="button" class="pose-zoom" data-pose-zoom="'+esc(p.id)+'" aria-label="放大查看'+esc(p.name)+'">查看动作要求 ↗</button></label>'}
document.addEventListener('DOMContentLoaded',()=>{
 const grid=$('poses');let group='常用',page=1;
 const tools=document.createElement('div');tools.className='pose-tools';tools.innerHTML='<span>新增20项整理动作，每页8项；原有姿势保留。</span><button type="button" id="allPoses" class="textbtn">全选本组</button><button type="button" id="clearPoses" class="textbtn">清空选择</button>';grid.before(tools);
 const filters=document.createElement('div');filters.className='pose-groups';filters.setAttribute('aria-label','动作分组');grid.before(filters);
 const pager=document.createElement('nav');pager.className='pose-pager';pager.setAttribute('aria-label','姿势翻页');grid.after(pager);
 const strip=document.createElement('div');strip.id='poseSelectionStrip';pager.after(strip);
 const dialog=document.createElement('dialog');dialog.id='poseDiagramDialog';dialog.innerHTML='<div class="modalbar"><b id="poseDiagramTitle"></b><button id="closePoseDiagram" type="button" class="ghost">关闭</button></div><div id="poseDiagramArt"></div><p id="poseDiagramHint"></p><p id="poseDiagramSource" class="muted"></p>';document.body.append(dialog);$('closePoseDiagram').onclick=()=>dialog.close();
 const tier=p=>p.tier||'原有';const current=()=>state.poses.filter(p=>tier(p)===group);
 function render(){
  if(!state.poses.length)return;
  if(!state.poses.some(p=>tier(p)===group))group=state.poses.some(p=>tier(p)==='常用')?'常用':'原有';
  const items=current(),pages=Math.max(1,Math.ceil(items.length/8));page=Math.max(1,Math.min(page,pages));
  filters.innerHTML=['常用','进阶','原有'].map(g=>'<button type="button" class="ghost '+(g===group?'selected':'')+'" aria-pressed="'+(g===group)+'" data-pose-group="'+g+'">'+g+' '+state.poses.filter(p=>tier(p)===g).length+'</button>').join('');
  grid.innerHTML=items.slice((page-1)*8,page*8).map(p=>poseCard(p)).join('');
  pager.innerHTML='<button type="button" class="ghost" data-pose-page="-1" '+(page===1?'disabled':'')+'>← 上一页</button><span aria-live="polite">'+page+' / '+pages+' 页 · 本组 '+items.length+' 项 · 已选 '+poseIds.size+' 项</span><button type="button" class="ghost" data-pose-page="1" '+(page===pages?'disabled':'')+'>下一页 →</button>';
  strip.innerHTML=state.poses.filter(p=>poseIds.has(p.id)).map(p=>'<span class="pose-selected-chip" title="'+esc(p.name)+'">'+poseSvg(p.id)+'<span>'+esc(p.name)+'</span></span>').join('')||'<small class="muted">选择动作后生成独立透明PNG；参考照片只用于页面预览，不作为人物身份图发送。</small>';
 }
 filters.onclick=e=>{const b=e.target.closest('[data-pose-group]');if(!b)return;group=b.dataset.poseGroup;page=1;render()};
 pager.onclick=e=>{const b=e.target.closest('[data-pose-page]');if(!b||b.disabled)return;page+=Number(b.dataset.posePage);render();filters.scrollIntoView({block:'start',behavior:'smooth'})};
 $('allPoses').onclick=()=>{for(const p of current())poseIds.add(p.id);estimates();persistSoon()};$('clearPoses').onclick=()=>{poseIds.clear();estimates();persistSoon()};
 grid.addEventListener('click',e=>{const b=e.target.closest('[data-pose-zoom]');if(!b)return;e.preventDefault();e.stopPropagation();const p=state.poses.find(p=>p.id===b.dataset.poseZoom);if(!p)return;$('poseDiagramTitle').textContent=p.name;$('poseDiagramArt').innerHTML=poseSvg(p.id);$('poseDiagramHint').textContent=p.hint;$('poseDiagramSource').textContent=p.image_kind==='reference'?'原图：'+p.source_file+'。照片仅用于动作预览；人物面貌和服装由上传图决定，生图使用动作文字要求。':'原有AI姿势图，仅示意动作。';dialog.showModal()});
 const prior=estimates;estimates=function(...args){render();return prior.apply(this,args)};window.renderPoseCards=render;if(state.poses.length){render();estimates()}
});
