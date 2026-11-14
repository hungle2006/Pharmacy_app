/* PharmaBiz reference direction A: accessible searchable filters + source-safe detail tabs.
   Never decorates #cover or replaces the Blender capsule Start. */
(() => {
 'use strict';
 const app=document.getElementById('app');
 const filters=document.getElementById('filters');
 const lookup=document.getElementById('lookup-panel');
 const form=document.getElementById('lookup-form');
 const results=document.querySelector('.lookup-results-column');
 const details=document.getElementById('lookup-details');
 if(!app||!filters||!lookup||!form||!results||!details)return;
 const orig=document.createComment('original analytics filter position');
 filters.before(orig);
 const story=document.getElementById('lookup-task-story');
 const storyOrig=document.createComment('original task-guide position');
 if(story)story.before(storyOrig);
 const tabs=document.querySelector('.lookup-tabs');
 if(tabs)results.insertBefore(tabs,document.getElementById('lookup-results'));
 const labels={
  ingredient:['Hoạt chất','Tất cả hoạt chất'],
  country:['Quốc gia','Tất cả quốc gia'],
  kind:['Loại giá','Tất cả loại giá'],
  unit:['Đơn vị','Tất cả đơn vị']
 };
 const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const clean=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('vi-VN');
 const menus=[];
 let openMenu=null;
 function closeMenu(focus=false){
  if(!openMenu)return;
  const {popup,trigger}=openMenu;
  popup.hidden=true;trigger.setAttribute('aria-expanded','false');
  if(focus)trigger.focus({preventScroll:true});
  openMenu=null;
 }
 function syncAll(){for(const m of menus)m.sync();}
 for(const [name,[label,fallback]] of Object.entries(labels)){
  const native=document.getElementById(name);
  if(!native)continue;
  const wrap=document.createElement('div');
  wrap.className='ph-filter';
  wrap.dataset.filter=name;
  const trigger=document.createElement('button');
  trigger.type='button';trigger.className='ph-filter-trigger';
  trigger.setAttribute('aria-label','Lọc '+label);
  trigger.setAttribute('aria-haspopup','listbox');
  trigger.setAttribute('aria-expanded','false');
  const popup=document.createElement('div');
  popup.className='ph-filter-menu';popup.hidden=true;
  popup.innerHTML='<label class="ph-filter-search-label"><span>⌕</span><input type="search" autocomplete="off" placeholder="Tìm '+escape(label.toLowerCase())+'…" aria-label="Tìm trong '+escape(label)+'"></label><p class="ph-filter-selected"></p><div class="ph-filter-options" role="listbox" aria-label="Chọn '+escape(label)+'"></div><p class="ph-filter-foot"></p>';
  native.parentNode.insertBefore(wrap,native);
  wrap.append(native,trigger,popup);
  native.classList.add('ph-native-select');native.tabIndex=-1;
  const input=popup.querySelector('input');
  const list=popup.querySelector('.ph-filter-options');
  const count=popup.querySelector('.ph-filter-foot');
  const selected=popup.querySelector('.ph-filter-selected');
  const getOptions=()=>[...native.options].map(o=>({value:o.value,text:o.textContent.trim()}));
  function sync(){
   const current=native.selectedOptions[0]?.textContent?.trim()||fallback;
   trigger.innerHTML='<span class="ph-filter-label">'+escape(label)+'</span><span class="ph-filter-value" title="'+escape(current)+'">'+escape(current)+'</span><span class="ph-filter-chevron" aria-hidden="true">⌄</span>';
   if(!popup.hidden)draw();
  }
  function draw(){
   const options=getOptions(),q=clean(input.value.trim());
   const matches=q?options.filter(o=>clean(o.text).includes(q)):options;
   const shown=matches.slice(0,60);
   selected.innerHTML=native.value?'Đang lọc: <strong title="'+escape(native.selectedOptions[0]?.textContent)+'">'+escape(native.selectedOptions[0]?.textContent)+'</strong>':'Không giới hạn '+escape(label.toLowerCase());
   list.innerHTML=shown.map((o,i)=>'<button type="button" class="ph-filter-option" role="option" data-filter-index="'+i+'" data-value="'+escape(o.value)+'" aria-selected="'+(o.value===native.value)+'" title="'+escape(o.text)+'"><span class="ph-filter-check" aria-hidden="true">'+(o.value===native.value?'✓':'')+'</span><span>'+escape(o.text)+'</span></button>').join('')||'<p class="ph-filter-empty">Không tìm thấy giá trị phù hợp.</p>';
   count.textContent=matches.length>60?'Hiển thị 60 / '+matches.length+' mục. Nhập từ khóa để lọc danh sách.':matches.length+' lựa chọn · chọn một giá trị để áp dụng';
  }
  function choose(value){
   if(![...native.options].some(o=>o.value===value))return;
   if(native.value!==value){native.value=value;native.dispatchEvent(new Event('change',{bubbles:true}));}
   closeMenu(true);sync();
  }
  trigger.addEventListener('click',()=>{
   if(openMenu?.popup===popup){closeMenu(true);return;}
   closeMenu();
   openMenu={popup,trigger};
   popup.hidden=false;trigger.setAttribute('aria-expanded','true');
   input.value='';draw();input.focus({preventScroll:true});
  });
  input.addEventListener('input',draw);
  input.addEventListener('keydown',e=>{
   if(e.key==='Escape'){e.preventDefault();closeMenu(true);return;}
   if(e.key==='ArrowDown'){e.preventDefault();list.querySelector('.ph-filter-option')?.focus();return;}
   if(e.key==='Enter'){const b=list.querySelector('.ph-filter-option');if(b){e.preventDefault();choose(b.dataset.value);}}
  });
  list.addEventListener('click',e=>{const b=e.target.closest('.ph-filter-option');if(b)choose(b.dataset.value);});
  list.addEventListener('keydown',e=>{
   if(!['ArrowDown','ArrowUp','Home','End','Escape'].includes(e.key))return;
   e.preventDefault();
   if(e.key==='Escape'){closeMenu(true);return;}
   const items=[...list.querySelectorAll('.ph-filter-option')],i=items.indexOf(document.activeElement);
   if(!items.length)return;
   const next=e.key==='Home'?0:e.key==='End'?items.length-1:e.key==='ArrowDown'?Math.min(items.length-1,i+1):Math.max(0,i-1);
   items[next].focus();
  });
  native.addEventListener('change',sync);
  const observer=new MutationObserver(()=>requestAnimationFrame(sync));
  observer.observe(native,{childList:true,characterData:true,subtree:true});
  menus.push({sync,popup,trigger});
  sync();
 }
 document.addEventListener('pharmabiz:filters-sync',syncAll);
 document.addEventListener('click',e=>{if(openMenu&&!openMenu.popup.parentElement.contains(e.target))closeMenu();},true);
 document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu();});
 document.addEventListener('pharmabiz:lookup-view',e=>{
  const active=Boolean(e.detail?.active);
  closeMenu();
  if(active){form.after(filters);if(story)filters.after(story);filters.hidden=false;document.body.dataset.lookupMode=document.getElementById('lookup-tab-rx')?.getAttribute('aria-pressed')==='true'?'rx':'dav';}
  else{orig.after(filters);if(story)storyOrig.after(story);delete document.body.dataset.lookupMode;}
  syncAll();
 });
 document.getElementById('lookup-tab-dav')?.addEventListener('click',()=>{document.body.dataset.lookupMode='dav';closeMenu();});
 document.getElementById('lookup-tab-rx')?.addEventListener('click',()=>{document.body.dataset.lookupMode='rx';closeMenu();});

 function makePane(name,title,source){
  const pane=document.createElement('div');pane.className='lookup-detail-pane';pane.dataset.pane=name;
  pane.setAttribute('role','tabpanel');pane.setAttribute('aria-label',title);
  if(source)pane.append(source);
  return pane;
 }
 function splitFields(parent,positions){
  const dl=document.createElement('dl');dl.className='lookup-fields';
  for(const index of positions){const node=parent.children[index];if(node)dl.append(node);}
  return dl;
 }
 function decorateDetail(mode){
  const fieldList=details.querySelector(':scope > .lookup-fields');
  if(!fieldList)return;
  // Reuse the real server-provided fields. No text, price, dosage or mapping is invented.
  const all=[...fieldList.children];
  const tabBar=document.createElement('div');tabBar.className='lookup-detail-tabs';
  tabBar.setAttribute('role','tablist');tabBar.setAttribute('aria-label','Nội dung chi tiết');
  const views=mode==='dav'
   ?[['overview','Tổng quan'],['config','Cấu hình'],['evidence','Giá & bằng chứng']]
   :[['overview','Thông tin RxNorm'],['evidence','Thuốc DAV liên quan']];
  const panes=views.map(([id,label])=>makePane(id,label));
  if(mode==='dav'){
   for(const [pane,indexes] of [[panes[0],[0,1,4,5]],[panes[1],[2,3,6,7]]]){
    const dl=document.createElement('dl');dl.className='lookup-fields';
    indexes.forEach(i=>{if(all[i])dl.append(all[i]);});
    pane.append(dl);
   }
   const mapping=details.querySelector(':scope > .lookup-mapping');
   const market=details.querySelector(':scope > .lookup-ml');
   if(mapping)panes[2].append(mapping);
   if(market)panes[2].append(market);
   for(const warning of details.querySelectorAll(':scope > .lookup-warning'))panes[2].append(warning);
  }else{
   const dl=document.createElement('dl');dl.className='lookup-fields';
   all.forEach(el=>dl.append(el));panes[0].append(dl);
   const reverse=details.querySelector(':scope > .lookup-reverse');
   if(reverse)panes[1].append(reverse);
   for(const warning of details.querySelectorAll(':scope > .lookup-warning'))panes[0].append(warning);
  }
  fieldList.remove();
  views.forEach(([id,label],index)=>{
   const button=document.createElement('button');
   button.type='button';button.className='lookup-detail-tab';button.textContent=label;
   button.dataset.paneTarget=id;button.id='lookup-tab-'+id;
   button.setAttribute('role','tab');button.setAttribute('aria-selected',String(index===0));button.tabIndex=index===0?0:-1;
   panes[index].id='lookup-pane-'+id;panes[index].setAttribute('aria-labelledby',button.id);panes[index].hidden=index!==0;
   button.setAttribute('aria-controls',panes[index].id);tabBar.append(button);
  });
  const top=details.querySelector('.lookup-badges');
  top?.after(tabBar,...panes);
  details.dataset.detailMode=mode;
 }
 details.addEventListener('click',e=>{
  const tab=e.target.closest('[data-pane-target]');if(!tab)return;
  const id=tab.dataset.paneTarget;
  for(const btn of details.querySelectorAll('.lookup-detail-tab')){
   const selected=btn.dataset.paneTarget===id;
   btn.setAttribute('aria-selected',String(selected));btn.tabIndex=selected?0:-1;
  }
  for(const pane of details.querySelectorAll('.lookup-detail-pane'))pane.hidden=pane.dataset.pane!==id;
 });
 details.addEventListener('keydown',e=>{
  if(!e.target.matches('.lookup-detail-tab')||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
  e.preventDefault();const buttons=[...details.querySelectorAll('.lookup-detail-tab')],i=buttons.indexOf(e.target);
  const n=e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
  buttons[n].click();buttons[n].focus();
 });
 document.addEventListener('pharmabiz:lookup-detail-render',e=>decorateDetail(e.detail?.mode==='rx'?'rx':'dav'));
})();
