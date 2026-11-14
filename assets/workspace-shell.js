/* PharmaBiz focused workspace shell.
   Progressive disclosure, app-level task switcher and real-data detail sheet.
   Does not touch the Blender/Three.js Start scene. */
(() => {
  'use strict';
  const app=document.getElementById('app'),content=document.getElementById('content');
  if(!app||!content)return;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const mobile=matchMedia('(max-width: 980px)');
  const $=id=>document.getElementById(id);
  const icons={
    search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    layers:'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M8 9h8M8 13h8"/>',
    x:'<path d="M18 6 6 18M6 6l12 12"/>',
    left:'<path d="m12 19-7-7 7-7M5 12h14"/>',
    right:'<path d="m5 12 7 7 7-7"/>',
    document:'<rect x="5" y="2.5" width="14" height="19" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    book:'<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5V4.5A2.5 2.5 0 0 1 6.5 2Z"/>',
    chevron:'<path d="m9 18 6-6-6-6"/>',
    refresh:'<path d="M20 7v5h-5"/><path d="M4.6 10a8 8 0 0 1 13.9-4l1.5 1M4 17v-5h5M19.4 14a8 8 0 0 1-13.9 4L4 17"/>',
    spark:'<path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3ZM19 17l.7 2.3L22 20l-2.3.7L19 23l-.7-2.3L16 20l2.3-.7L19 17Z"/>',
    up:'<path d="m18 15-6-6-6 6M12 9v12M4 4h16"/>',
    menu:'<path d="M4 7h16M4 12h16M4 17h16"/>'
  };
  function icon(name){
    return '<svg class="ws-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+icons[name]+'</svg>';
  }
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  // Consistent small vector icons replace font-dependent character glyphs.
  for(const [id,name] of [['refresh','refresh'],['back-top','up'],['sidebar-close','x'],['menu','menu'],['prev','left'],['next','right']]){
    const b=$(id);if(!b)continue;
    b.innerHTML=icon(name);
    if(id==='refresh'&&!b.hasAttribute('aria-label'))b.setAttribute('aria-label','Làm mới dữ liệu');
  }

  const head=content.querySelector('.page-head');
  const actions=document.createElement('div');actions.className='ws-head-actions';
  const exportButton=$('export');
  if(exportButton){exportButton.innerHTML=icon('document')+'<span class="ws-export-label">Xuất CSV</span>';exportButton.setAttribute('aria-label','Xuất trang dữ liệu CSV');}
  const sourceAction=document.createElement('button');sourceAction.type='button';
  sourceAction.className='ws-action ws-source-action';
  sourceAction.innerHTML=icon('document')+'<span>Bản ghi</span>';
  sourceAction.title='Mở bản ghi và số liệu nguồn';sourceAction.setAttribute('aria-label','Mở danh sách bản ghi nguồn');
  // Task navigation stays in the desktop sidebar and mobile bottom bar.
  // The redundant "Chọn tác vụ" header button is deliberately removed.
  actions.append(sourceAction);
  if(exportButton)actions.append(exportButton);
  head.append(actions);

  // One reusable accessible overlay handles source tables and mobile drug detail.
  const layer=document.createElement('div');
  layer.id='ws-detail-layer';layer.className='ws-layer';layer.hidden=true;
  layer.innerHTML='<div class="ws-shade" data-ws-close></div><section class="ws-sheet" role="dialog" aria-modal="true" aria-labelledby="ws-sheet-heading" tabindex="-1"><header class="ws-sheet-header"><div><span class="ws-sheet-kicker">PHARMABIZ / CHI TIẾT</span><h2 id="ws-sheet-heading">Số liệu & nguồn</h2></div><button type="button" class="ws-close" data-ws-close aria-label="Đóng và quay lại">'+icon('x')+'</button></header><div class="ws-sheet-body" id="ws-sheet-body"></div><footer class="ws-sheet-footer"><button type="button" class="ws-back" data-ws-close>'+icon('left')+' Quay lại nội dung</button><span>Dữ liệu thực từ nguồn đã kết nối</span></footer></section>';
  app.append(layer);
  const sheetBody=$('ws-sheet-body');
  let current=null;
  function lock(){
    document.body.classList.toggle('ws-detail-active',!layer.hidden||!palette.hidden);
  }
  function closeSheet(restoreFocus=true){
    if(layer.hidden)return;
    layer.hidden=true;
    if(current){
      const {node,marker,wasOpen,wasHidden,trigger,kind}=current;
      node.classList.remove('ws-in-sheet');
      if(marker.isConnected)marker.replaceWith(node);
      else node.remove();
      if(node.tagName==='DETAILS')node.open=wasOpen;
      node.hidden=wasHidden;
      current=null;
      if(restoreFocus&&trigger?.isConnected)trigger.focus({preventScroll:true});
      if(kind==='lookup'&&restoreFocus&&!mobile.matches&&node.isConnected)node.focus({preventScroll:true});
    }
    sheetBody.textContent='';
    lock();
  }
  function openSheet(node,title,trigger,kind='source'){
    if(!node||!node.isConnected)return;
    closePalette(false);
    closeSheet(false);
    const marker=document.createComment('ws detail return point');
    node.before(marker);
    current={node,marker,trigger,kind,wasOpen:node.tagName==='DETAILS'?node.open:false,wasHidden:node.hidden};
    node.hidden=false;
    if(node.tagName==='DETAILS')node.open=true;
    node.classList.add('ws-in-sheet');
    sheetBody.append(node);
    $('ws-sheet-heading').textContent=title;
    layer.hidden=false;lock();
    layer.querySelector('.ws-close').focus({preventScroll:true});
  }
  layer.addEventListener('click',e=>{
    if(!e.target.closest('[data-ws-close]'))return;
    const lookupClose=current?.kind==='lookup'?current.node.querySelector('#lookup-detail-close'):null;
    closeSheet();
    if(lookupClose?.isConnected)lookupClose.click();
  });

  // Task switcher: a fast alternative to scrolling through 15 sidebar destinations.
  const palette=document.createElement('div');palette.id='ws-palette';palette.className='ws-palette';palette.hidden=true;
  palette.innerHTML='<div class="ws-palette-shade" data-ws-dismiss></div><div class="ws-palette-dialog" role="dialog" aria-modal="true" aria-label="Chuyển tác vụ"><div class="ws-palette-input">'+icon('search')+'<input id="ws-palette-search" type="search" autocomplete="off" spellcheck="false" placeholder="Tìm một tác vụ…" aria-label="Tìm tác vụ"><button type="button" data-ws-dismiss aria-label="Đóng bộ chọn">'+icon('x')+'</button></div><div class="ws-palette-results" id="ws-palette-results" role="listbox" aria-label="Các tác vụ"></div><p class="ws-palette-hint">Nhập để lọc · ↑ ↓ để chọn · Enter để mở · Esc để đóng</p></div>';
  app.append(palette);
  let paletteTrigger=null,paletteIndex=0,paletteItems=[];
  const input=$('ws-palette-search'),paletteResults=$('ws-palette-results');
  function options(){
    const q=input.value.toLocaleLowerCase('vi-VN').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim();
    const buttons=[...app.querySelectorAll('#nav .nav-button[data-view]')];
    const all=buttons.map((node,i)=>({
      node,id:node.dataset.view,text:node.getAttribute('aria-label')||node.textContent.trim(),index:i
    }));
    return all.filter(x=>x.text.toLocaleLowerCase('vi-VN').normalize('NFD').replace(/[\u0300-\u036f]/g,'').includes(q));
  }
  function paintPalette(){
    paletteItems=options();paletteIndex=Math.max(0,Math.min(paletteItems.length-1,paletteIndex));
    paletteResults.innerHTML=paletteItems.length?paletteItems.map((item,i)=>'<button type="button" class="ws-palette-item" data-ws-task="'+esc(item.id)+'" role="option" aria-selected="'+(i===paletteIndex)+'"><span class="ws-palette-item-icon">'+icon('chevron')+'</span><span>'+esc(item.text)+'</span><small>'+String(i+1).padStart(2,'0')+'</small></button>').join(''):'<p class="ws-palette-empty">Không có tác vụ khớp từ khóa.</p>';
  }
  function closePalette(restoreFocus=true){
    if(palette.hidden)return;
    palette.hidden=true;
    if(restoreFocus&&paletteTrigger?.isConnected)paletteTrigger.focus({preventScroll:true});
    lock();
  }
  function openPalette(trigger=$('menu')||$('page-title')){
    closeSheet(false);
    paletteTrigger=trigger;
    palette.hidden=false;input.value='';paletteIndex=0;paintPalette();lock();
    input.focus({preventScroll:true});
  }
  function choosePalette(id){
    const choice=paletteItems.find(v=>v.id===id);
    if(!choice)return;
    closePalette(false);
    choice.node.click();
    if(mobile.matches)$('page-title')?.focus({preventScroll:true});
  }
  palette.addEventListener('click',e=>{
    if(e.target.closest('[data-ws-dismiss]')){closePalette();return;}
    const button=e.target.closest('[data-ws-task]');if(button)choosePalette(button.dataset.wsTask);
  });
  input.addEventListener('input',()=>{paletteIndex=0;paintPalette();});
  input.addEventListener('keydown',e=>{
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){
      e.preventDefault();if(!paletteItems.length)return;
      paletteIndex=(paletteIndex+(e.key==='ArrowDown'?1:-1)+paletteItems.length)%paletteItems.length;paintPalette();
    }else if(e.key==='Enter'){e.preventDefault();if(paletteItems[paletteIndex])choosePalette(paletteItems[paletteIndex].id);}
  });
  sourceAction.addEventListener('click',()=>{
    const panel=$('records-panel');
    if(panel&&!panel.hidden)openSheet(panel,'Bản ghi dữ liệu nguồn',sourceAction,'records');
  });
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'&&!e.altKey){
      if(app.hidden)return;e.preventDefault();palette.hidden?openPalette(document.activeElement&&app.contains(document.activeElement)?document.activeElement:($('menu')||$('page-title'))):closePalette();
    }
    if(e.key==='Escape'){
      if(!palette.hidden){e.preventDefault();closePalette();}
      else if(!layer.hidden){
        e.preventDefault();
        const lookupClose=current?.kind==='lookup'?current.node.querySelector('#lookup-detail-close'):null;
        closeSheet();
        if(lookupClose?.isConnected)lookupClose.click();
      }
    }
    const overlay=!palette.hidden?palette:!layer.hidden?layer:null;
    if(!overlay||e.key!=='Tab')return;
    const dialog=overlay.querySelector('[role="dialog"]');
    const controls=[...dialog.querySelectorAll('button:not(:disabled):not([hidden]),input:not(:disabled),select:not(:disabled),a[href]')].filter(x=>x.getClientRects().length);
    if(!controls.length)return;
    const first=controls[0],last=controls.at(-1);
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
    else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
  },true);
  // A task change restores any moved DOM before the chart modules re-render.
  document.addEventListener('pharmabiz:workspace-before-view',()=>{
    closeSheet(false);closePalette(false);
  });
  document.addEventListener('click',e=>{
    if(e.target.closest('#logout')){closeSheet(false);closePalette(false);}
    const button=e.target.closest('#lookup-detail-close');
    if(button&&current?.kind==='lookup')closeSheet(false);
  },true);
  document.addEventListener('pharmabiz:lookup-detail-open',()=>{
    if(!mobile.matches)return;
    const node=$('lookup-details'),trigger=app.querySelector('.lookup-item.is-selected')||app.querySelector('#lookup-results');
    if(node)openSheet(node,'Chi tiết hồ sơ thuốc',trigger,'lookup');
  });
  mobile.addEventListener('change',()=>{if(!mobile.matches&&current?.kind==='lookup')closeSheet(false);});

  // Contextual affordance: source data opens in a panel and returns without a page-long scroll.
  function decorateDecks(){
    const decks=[...app.querySelectorAll('.focus-deck')];
    for(const deck of decks){
      const nav=deck.querySelector(':scope > .focus-toolbar .focus-navigation');
      if(!nav)continue;
      let sourceButton=nav.querySelector('.ws-open-source');
      if(!sourceButton){
        sourceButton=document.createElement('button');sourceButton.type='button';
        sourceButton.className='ws-open-source';sourceButton.title='Xem số liệu nguồn của phần hiện tại';
        sourceButton.innerHTML=icon('book')+'<span>Chi tiết</span>';
        nav.prepend(sourceButton);
        sourceButton.addEventListener('click',()=>{
          const page=[...deck.querySelectorAll(':scope > .focus-page')].find(p=>!p.hidden);
          const source=page?.querySelector('.depth-source,.report-evidence details,.explore-source');
          if(source)openSheet(source,'Số liệu và phương pháp',sourceButton);
        });
      }
      const page=[...deck.querySelectorAll(':scope > .focus-page')].find(p=>!p.hidden);
      const hasSource=Boolean(page?.querySelector('.depth-source,.report-evidence details,.explore-source'));
      if(sourceButton.hidden===hasSource)sourceButton.hidden=!hasSource;
    }
    sourceAction.hidden=!['overview','pricing','competition','portfolio','quality'].includes(document.body.dataset.activeView||'overview');
  }
  let queued=false;
  const observer=new MutationObserver(()=>{
    if(queued)return;queued=true;
    requestAnimationFrame(()=>{queued=false;decorateDecks();});
  });
  observer.observe(content,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
  document.addEventListener('change',e=>{
    if(e.target.closest('.focus-picker select'))requestAnimationFrame(decorateDecks);
  });
  document.addEventListener('click',e=>{
    if(e.target.closest('.focus-navigation button'))requestAnimationFrame(decorateDecks);
  });
  requestAnimationFrame(decorateDecks);

  // Permanent tiny status detail for touch navigation, without additional page scroll.
  const date=new Date();
  if($('back-top'))$('back-top').title='Về đầu trang';
})();
