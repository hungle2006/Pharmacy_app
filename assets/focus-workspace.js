/* Present existing source content in selectable chapters; preserve controls and API state. */
(() => {
  'use strict';
  const content=document.getElementById('content');
  if(!content)return;
  const selections=new Map();
  let scheduled=false,serial=0;
  const arrow=direction=>'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="'+(direction<0?'m14 6-6 6 6 6':'m10 6 6 6-6 6')+'"/></svg>';
  const view=()=>document.body.dataset.activeView||new URLSearchParams(location.search).get('view')||'overview';
  const text=node=>(node?.textContent||'').replace(/\s+/g,' ').trim();
  function fold(node,title,id){
    if(!node||node.parentElement?.classList.contains('focus-fold'))return node?.parentElement;
    const details=document.createElement('details');details.className='focus-fold';if(id)details.id=id;
    const summary=document.createElement('summary');summary.textContent=title;
    node.before(details);details.append(summary,node);return details;
  }
  function titleOf(node){
    return node.dataset.focusLabel||text(node.querySelector('h2,h3'))||({'depth-next':'Khám phá các tác vụ liên quan','study-bridge':'Tiếp tục nghiên cứu'}[node.className])||'Chi tiết dữ liệu';
  }
  function meaningful(node){
    if(node.matches('.study-opening,.task-kpis,.depth-findings,.depth-step,.task-scope,.task-tabs,.report-controls,.report-options,.task-reading,.focus-fold,.focus-deck'))return false;
    return node.matches('section,article,div')&&(node.querySelector('h2,h3')||node.matches('.depth-next,.study-bridge')||node.dataset.focusLabel);
  }
  function makeDeck(root){
    if(!root||root.querySelector(':scope > .focus-deck'))return;
    const entries=[];let pending=[];
    for(const node of [...root.children]){
      if(node.classList.contains('depth-findings')){fold(node,'Điểm nổi bật và giới hạn');continue;}
      if(node.classList.contains('depth-step')){pending.push(node);continue;}
      if(!meaningful(node))continue;
      const parts=node.matches('.overview-primary,.overview-secondary,.equal-grid,.depth-grid,.market-details')?[...node.children].filter(meaningful):[];
      if(parts.length>1){
        for(const [i,part]of parts.entries())entries.push({node:part,prefix:i===0?pending:[],container:node});
        pending=[];
      }else{entries.push({node,prefix:pending});pending=[];}
    }
    if(entries.length<2)return;
    const name=view()+':'+(root.id||'analysis');
    const deck=document.createElement('div');deck.className='focus-deck';deck.dataset.focusState=name;
    const toolbar=document.createElement('div');toolbar.className='focus-toolbar';
    const picker=document.createElement('div');picker.className='focus-picker';
    const pickerCaption=document.createElement('span');pickerCaption.className='focus-picker-caption';
    pickerCaption.textContent=root.id==='market-explore'?'KHÁM PHÁ BÁO CÁO':'GÓC NHÌN HIỆN TẠI';
    picker.append(pickerCaption);
    // Keep the original select as a hidden state mirror for existing research/chart modules.
    const select=document.createElement('select');select.className='focus-native-select';
    select.setAttribute('aria-hidden','true');select.tabIndex=-1;picker.append(select);
    const trigger=document.createElement('button');trigger.type='button';trigger.className='focus-current';
    trigger.setAttribute('aria-haspopup','menu');trigger.setAttribute('aria-expanded','false');
    trigger.setAttribute('aria-label','Mở danh sách các góc nhìn');
    trigger.innerHTML='<span class="focus-current-step"></span><span class="focus-current-text"></span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
    const menu=document.createElement('div');menu.className='focus-menu';menu.hidden=true;
    menu.id='focus-menu-'+(++serial);
    trigger.setAttribute('aria-controls',menu.id);
    menu.innerHTML='<label class="focus-menu-search"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg><input type="search" autocomplete="off" placeholder="Tìm nội dung…" aria-label="Tìm góc nhìn"></label><div class="focus-menu-list" role="menu" aria-label="Chọn góc nhìn phân tích"></div>';
    picker.append(trigger,menu);
    const menuSearch=menu.querySelector('input'),menuList=menu.querySelector('.focus-menu-list');
    const nav=document.createElement('div');nav.className='focus-navigation';
    const prev=document.createElement('button');prev.type='button';prev.innerHTML=arrow(-1);prev.setAttribute('aria-label','Phần trước');
    const next=document.createElement('button');next.type='button';next.innerHTML=arrow(1);next.setAttribute('aria-label','Phần tiếp theo');
    const counter=document.createElement('span');counter.className='focus-counter';
    nav.append(prev,counter,next);toolbar.append(picker,nav);deck.append(toolbar);
    const status=document.createElement('span');status.className='focus-status';status.setAttribute('role','status');deck.append(status);
    const anchor=entries[0].prefix[0]||entries[0].container||entries[0].node;anchor.before(deck);
    entries.forEach((entry,i)=>{
      const page=document.createElement('section');page.className='focus-page';page.id='focus-page-'+(++serial);page.dataset.focusKey=entry.node.id||entry.node.querySelector('[id]')?.id||titleOf(entry.node);page.setAttribute('role','region');
      const option=document.createElement('option');option.value=String(i);option.textContent=titleOf(entry.node);select.append(option);
      page.setAttribute('aria-label',option.textContent);page.append(...entry.prefix,entry.node);deck.append(page);
    });
    for(const entry of entries)if(entry.container&&!entry.container.children.length)entry.container.remove();
    const pages=[...deck.querySelectorAll(':scope > .focus-page')];
    const selected=selections.get(name);let index=pages.findIndex(page=>page.dataset.focusKey===selected);
    if(index<0){index=Math.max(0,pages.findIndex(page=>page.querySelector('[id^="chart-"]')));}
    function show(value,announce=false){
      index=Math.max(0,Math.min(pages.length-1,Number(value)||0));
      pages.forEach((page,i)=>{const hide=i!==index;if(page.hidden!==hide)page.hidden=hide;});
      select.value=String(index);select.setAttribute('aria-controls',pages[index].id);prev.disabled=index===0;next.disabled=index===pages.length-1;
      counter.textContent=(index+1)+' / '+pages.length;selections.set(name,pages[index].dataset.focusKey);
      updateTrigger();closeMenu(false);
      if(announce){
        status.textContent='Đang xem: '+select.options[index].textContent;
        // Keep the user's position when switching within the visible toolbar.
        // Only recover the toolbar if it is completely outside the viewport.
        const box=toolbar.getBoundingClientRect();
        if(box.bottom<0||box.top>window.innerHeight-42){
          const offset=matchMedia('(max-width:760px)').matches?66:82;
          window.scrollTo({top:Math.max(0,window.scrollY+box.top-offset),behavior:'auto'});
        }
      }
    }
    function updateTrigger(){
      const selectedTitle=select.options[index]?.textContent||'Chọn nội dung';
      const name=trigger.querySelector('.focus-current-text');
      if(name.textContent!==selectedTitle)name.textContent=selectedTitle;
      name.title=selectedTitle;
      trigger.querySelector('.focus-current-step').textContent=String(index+1).padStart(2,'0')+' / '+String(pages.length).padStart(2,'0');
      trigger.title=selectedTitle;
    }
    function closeMenu(restoreFocus=false){
      if(menu.hidden)return;
      menu.hidden=true;trigger.setAttribute('aria-expanded','false');
      if(restoreFocus)trigger.focus({preventScroll:true});
    }
    function optionsInMenu(){return [...menuList.querySelectorAll('.focus-menu-option')];}
    function drawMenu(){
      const query=menuSearch.value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('vi-VN').trim();
      menuList.replaceChildren();
      for(const [i,opt] of [...select.options].entries()){
        const label=opt.textContent;
        const normalized=label.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('vi-VN');
        if(query&&!normalized.includes(query))continue;
        const item=document.createElement('button');item.type='button';item.className='focus-menu-option';
        item.dataset.index=String(i);
        item.setAttribute('role','menuitemradio');item.setAttribute('aria-checked',String(index===i));
        const num=document.createElement('span');num.className='focus-menu-index';num.textContent=String(i+1).padStart(2,'0');
        const labelEl=document.createElement('span');labelEl.className='focus-menu-title';labelEl.textContent=label;
        const check=document.createElement('span');check.className='focus-menu-check';check.textContent=index===i?'✓':'';
        check.setAttribute('aria-hidden','true');
        item.append(num,labelEl,check);menuList.append(item);
      }
      if(!menuList.children.length){
        const empty=document.createElement('p');empty.className='focus-menu-empty';empty.textContent='Không có mục phù hợp.';
        menuList.append(empty);
      }
    }
    function openMenu(){
      // Close menus on other chapter toolbars before opening this one.
      document.dispatchEvent(new CustomEvent('pharmabiz:focus-menu-open',{detail:{source:menu}}));
      menuSearch.value='';drawMenu();menu.hidden=false;
      // Keep the list inside the visual viewport even if the toolbar is near its bottom.
      const box=trigger.getBoundingClientRect();
      const bottomSafe=matchMedia('(max-width:760px)').matches?82:18;
      const below=Math.max(0,innerHeight-bottomSafe-box.bottom-7);
      const above=Math.max(0,box.top-18);
      const openUp=below<Math.min(300,menu.scrollHeight)&&above>below;
      menu.classList.toggle('focus-menu-up',openUp);
      const room=openUp?above:below;
      menu.style.maxHeight=Math.max(118,Math.min(440,room-8))+'px';
      trigger.setAttribute('aria-expanded','true');
      menuSearch.focus({preventScroll:true});
    }
    function choose(number){
      const i=Number(number);
      if(!Number.isInteger(i)||i<0||i>=pages.length)return;
      select.value=String(i);select.dispatchEvent(new Event('change',{bubbles:true}));
      closeMenu(true);
    }
    trigger.addEventListener('click',()=>menu.hidden?openMenu():closeMenu(true));
    trigger.addEventListener('keydown',e=>{
      if(e.key==='ArrowDown'||e.key==='Enter'||e.key===' '){
        if(menu.hidden){e.preventDefault();openMenu();}
      }
    });
    menuSearch.addEventListener('input',drawMenu);
    menu.addEventListener('click',e=>{
      const item=e.target.closest('.focus-menu-option');
      if(item)choose(item.dataset.index);
    });
    menu.addEventListener('keydown',e=>{
      if(e.key==='Escape'){e.preventDefault();closeMenu(true);return;}
      const items=optionsInMenu();
      if(e.key==='Enter'&&e.target===menuSearch&&items.length){e.preventDefault();choose(items[0].dataset.index);return;}
      if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key)||!items.length)return;
      e.preventDefault();
      const current=items.indexOf(document.activeElement);
      const target=e.key==='Home'?0:e.key==='End'?items.length-1:
        e.key==='ArrowDown'?Math.min(items.length-1,current+1):Math.max(0,current-1);
      items[target].focus({preventScroll:true});
    });
    document.addEventListener('pointerdown',e=>{if(!menu.hidden&&!picker.contains(e.target))closeMenu();});
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape'&&!menu.hidden){e.preventDefault();closeMenu(true);}
    });
    document.addEventListener('pharmabiz:focus-menu-open',e=>{
      if(e.detail?.source!==menu)closeMenu();
    });
    deck.addEventListener('focus:titles-sync',()=>{updateTrigger();if(!menu.hidden)drawMenu();});
    select.addEventListener('change',()=>show(select.value,true));
    prev.addEventListener('click',()=>show(index-1,true));next.addEventListener('click',()=>show(index+1,true));
    deck.addEventListener('focus-main',()=>show(0,true));show(index);
  }
  function compactForm(){
    const grid=document.querySelector('#feature-price-form .fp-form-grid');
    if(!grid||grid.querySelector('.fp-optional'))return;
    const labels=[...grid.children].filter(node=>node.tagName==='LABEL'&&node.htmlFor!=='feature-input-ingredient');
    if(!labels.length)return;
    const details=document.createElement('details');details.className='focus-fold fp-optional';details.id='feature-optional';
    const summary=document.createElement('summary');summary.textContent='Bổ sung hàm lượng, dạng và nguồn thuốc';
    const fields=document.createElement('div');fields.className='fp-optional-grid';fields.append(...labels);details.append(summary,fields);grid.append(details);
  }
  function sync(){
    scheduled=false;
    const analysis=document.getElementById('depth-analytical')||document.getElementById('visuals');
    makeDeck(analysis);makeDeck(document.getElementById('market-explore'));compactForm();
    const records=document.getElementById('records-panel');
    const disclosure=records?.closest('.ws-sheet-body')?null:fold(records,'Khám phá bản ghi nguồn','records-disclosure');
    if(disclosure){if(disclosure.hidden!==records.hidden)disclosure.hidden=records.hidden;
      let count=disclosure.querySelector('.focus-record-count');if(!count){count=document.createElement('span');count.className='focus-record-count';disclosure.firstElementChild.append(count);}
      const countText=text(document.getElementById('records-count'));if(count.textContent!==countText)count.textContent=countText;
    }
    const disease=document.getElementById('disease-predict-panel');
    const intro=disease?.querySelector(':scope > .dp-card:first-child');if(intro?.querySelector('.dp-steps'))fold(intro,'Cách dùng và quy trình đối chiếu');
    const model=document.getElementById('dp-model-summary')?.parentElement;if(model?.classList.contains('dp-card'))fold(model,'Phạm vi và chất lượng mô hình');
    for(const deck of content.querySelectorAll('.focus-deck')){
      const pages=[...deck.querySelectorAll(':scope > .focus-page')],options=deck.querySelector('select').options;
      let updated=false;
      pages.forEach((page,i)=>{const node=[...page.children].find(n=>!n.classList.contains('depth-step'));const title=titleOf(node);if(options[i]&&options[i].textContent!==title){options[i].textContent=title;page.setAttribute('aria-label',title);updated=true;}});
      if(updated)deck.dispatchEvent(new Event('focus:titles-sync'));
    }
  }
  function queue(){if(!scheduled){scheduled=true;requestAnimationFrame(sync);}}
  new MutationObserver(queue).observe(content,{childList:true,subtree:true});
  document.addEventListener('change',event=>{
    if(event.target.id==='feature-example'&&event.target.value!=='')requestAnimationFrame(()=>{const optional=document.getElementById('feature-optional');if(optional)optional.open=true;});
  });
  document.addEventListener('click',event=>{if(event.target.closest('#market-horizons button'))document.querySelector('#market-explore > .focus-deck')?.dispatchEvent(new Event('focus-main'));});
  queue();
})();
