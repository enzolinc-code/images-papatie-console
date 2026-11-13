/* Eight AI-generated pose examples; no model calls on page load. */
function poseSvg(id){
 return '<img class="pose-photo" src="/pose-art/'+id+'.png?v=ai-poses-20261113-8" alt="人物线稿姿势示意" loading="eager">';
}
function poseCard(p){
 return '<label class="pose pose-illustrated"><input type="checkbox" data-pose="'+p.id+'" '+(poseIds.has(p.id)?'checked':'')+' aria-label="选择'+esc(p.name)+'"><span class="pose-tick" aria-hidden="true">✓</span><div class="pose-art">'+poseSvg(p.id)+'</div><span class="pose-kind">'+'AI生成姿势图'+'</span><b>'+esc(p.name)+'</b><small>'+esc(p.hint)+'</small><button type="button" class="pose-zoom" data-pose-zoom="'+p.id+'" aria-label="放大查看'+esc(p.name)+'">放大查看 ↗</button></label>'
}
document.addEventListener('DOMContentLoaded',()=>{
 const poses=document.getElementById('poses');
 const tools=document.createElement('div');tools.className='pose-tools';
 tools.innerHTML='<span>8种统一素体动作，均为AI生成；人物造型取自上传照片。</span><button type="button" id="allPoses" class="textbtn">全选</button><button type="button" id="clearPoses" class="textbtn">清空</button>';
 poses.before(tools);
 const strip=document.createElement('div');strip.id='poseSelectionStrip';poses.after(strip);
 const dialog=document.createElement('dialog');dialog.id='poseDiagramDialog';dialog.innerHTML='<div class="modalbar"><b id="poseDiagramTitle"></b><button id="closePoseDiagram" type="button" class="ghost">关闭</button></div><div id="poseDiagramArt"></div><p id="poseDiagramHint"></p><p class="muted">8张姿势图均由AI生成，仅示意动作；人物面貌与服装仍由上传参考图决定。</p>';document.body.append(dialog);
 document.getElementById('closePoseDiagram').onclick=()=>dialog.close();
 poses.addEventListener('click',e=>{
  const button=e.target.closest('[data-pose-zoom]');if(!button)return;
  e.preventDefault();e.stopPropagation();
  const p=state.poses.find(p=>p.id===button.dataset.poseZoom);
  document.getElementById('poseDiagramTitle').textContent=p.name;
  document.getElementById('poseDiagramArt').innerHTML=poseSvg(p.id);
  document.getElementById('poseDiagramHint').textContent=p.hint;dialog.showModal();
 });
 function setAll(all){poseIds=new Set(all?state.poses.map(p=>p.id):[]);poses.querySelectorAll('[data-pose]').forEach(el=>el.checked=poseIds.has(el.dataset.pose));estimates();persistSoon()}
 document.getElementById('allPoses').onclick=()=>setAll(true);
 document.getElementById('clearPoses').onclick=()=>setAll(false);
 const prior=estimates;estimates=function(){prior();strip.innerHTML=state.poses.filter(p=>poseIds.has(p.id)).map(p=>'<span class="pose-selected-chip" title="'+esc(p.name)+'">'+poseSvg(p.id)+'<span>'+esc(p.name)+'</span></span>').join('')||'<small class="muted">选择上方卡片，逐个姿势生成独立透明PNG。</small>'};
 if(state.poses.length){poses.innerHTML=state.poses.map(p=>poseCard(p)).join('');estimates()}
});