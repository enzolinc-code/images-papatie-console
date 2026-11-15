// Papapai handoff: show an explicit directory-read button; never auto-generate or publish.
window.addEventListener('load',()=>{const q=new URLSearchParams(location.search);if(q.get('from')!=='papapai'||!q.get('folder'))return;
 const folder=q.get('folder');show('batch');const banner=document.createElement('div');banner.className='note';
 const text=document.createElement('p');text.textContent='收到趴趴立牌成品目录：'+folder+'。读取后可分配给账号；未生成文案、未发布。';banner.append(text);
 const button=document.createElement('button');button.className='btn primary';button.textContent='读取这批成品';button.onclick=()=>guard(async()=>{$('batchFolder').value=folder;await loadCatalog();});banner.append(button);
 document.getElementById('batch').prepend(banner);
});
