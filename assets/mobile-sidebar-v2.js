/* Progressive phone-only sidebar enhancement: group toggles and task finder.
   Navigation buttons remain the real PharmaBiz controls; no routing logic replaced. */
(() => {
  'use strict';
  const sidebar=document.getElementById('sidebar');
  const nav=sidebar?.querySelector('#nav');
  if(!sidebar||!nav||nav.dataset.mobileEnhanced==='true')return;
  nav.dataset.mobileEnhanced='true';
  const phone=window.matchMedia('(max-width:760px)');
  const groups=[...nav.querySelectorAll('.task-nav-group')].map(group=>{
    const caption=group.querySelector('.nav-caption');
    const panel=group.querySelector('.task-nav-tiles');
    if(!caption||!panel)return null;
    const title=caption.textContent.trim();
    const items=[...panel.querySelectorAll('.nav-button[data-view]')];
    if(!panel.id)panel.id='mobile-nav-panel-'+group.dataset.group;
    caption.dataset.count=String(items.length).padStart(2,'0');
    const toggle=document.createElement('button');
    toggle.type='button';
    toggle.className='mobile-group-toggle';
    toggle.setAttribute('aria-controls',panel.id);
    toggle.setAttribute('aria-label','Mở nhóm '+title);
    toggle.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
    caption.append(toggle);
    const state={group,panel,title,items,toggle};
    toggle.addEventListener('click',event=>{
      event.stopPropagation();
      if(!phone.matches)return;
      const expanded=!group.classList.contains('is-collapsed');
      setExpanded(expanded?null:state);
    });
    caption.addEventListener('click',event=>{
      if(phone.matches&&!event.target.closest('.mobile-group-toggle'))toggle.click();
    });
    return state;
  }).filter(Boolean);
  if(!groups.length)return;
  const allButtons=groups.flatMap(g=>g.items);
  const search=document.createElement('div');
  search.className='mobile-nav-search';
  search.setAttribute('role','search');
  search.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg><input type="search" autocomplete="off" spellcheck="false" aria-label="Tìm tác vụ PharmaBiz" placeholder="Tìm tác vụ nhanh…"><button type="button" class="mobile-nav-clear" aria-label="Xóa nội dung tìm kiếm" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true" width="16" height="16"><path d="M18 6 6 18M6 6l12 12"/></svg></button>';
  sidebar.insertBefore(search,nav);
  const input=search.querySelector('input');
  const clear=search.querySelector('button');
  const empty=document.createElement('p');
  empty.className='mobile-nav-empty';
  empty.textContent='Không tìm thấy tác vụ phù hợp.';
  empty.hidden=true;
  nav.append(empty);
  const normalize=text=>String(text||'').toLocaleLowerCase('vi-VN').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').trim();
  function activeGroup(){
    const active=nav.querySelector('.nav-button.active[data-view]') || nav.querySelector('[aria-current="page"][data-view]');
    const id=active?.closest('.task-nav-group')?.dataset.group || document.body.dataset.taskGroup;
    return groups.find(g=>g.group.dataset.group===id)||groups[0];
  }
  function setExpanded(target){
    for(const g of groups){
      const shown=g===target;
      g.group.classList.toggle('is-collapsed',!shown);
      g.toggle.setAttribute('aria-expanded',String(shown));
      g.toggle.setAttribute('aria-label',(shown?'Thu gọn':'Mở')+' nhóm '+g.title);
    }
  }
  function filter(){
    if(!phone.matches){
      input.value='';
      clear.hidden=true;
      empty.hidden=true;
      for(const g of groups){
        g.group.hidden=false;
        g.group.classList.remove('is-collapsed');
        g.items.forEach(item=>item.hidden=false);
        g.toggle.tabIndex=-1;
        g.toggle.setAttribute('aria-hidden','true');
      }
      return;
    }
    for(const g of groups){
      g.toggle.tabIndex=0;
      g.toggle.removeAttribute('aria-hidden');
    }
    const q=normalize(input.value);
    clear.hidden=!q;
    if(!q){
      allButtons.forEach(item=>item.hidden=false);
      groups.forEach(g=>g.group.hidden=false);
      empty.hidden=true;
      setExpanded(activeGroup());
      return;
    }
    let total=0;
    for(const g of groups){
      let count=0;
      for(const item of g.items){
        const label=item.getAttribute('aria-label')||item.textContent;
        const match=normalize(label).includes(q);
        item.hidden=!match;
        if(match){count++;total++;}
      }
      g.group.hidden=count===0;
      g.group.classList.remove('is-collapsed');
      g.toggle.setAttribute('aria-expanded','true');
      g.toggle.setAttribute('aria-label','Thu gọn nhóm '+g.title);
    }
    empty.hidden=total!==0;
  }
  input.addEventListener('input',filter);
  clear.addEventListener('click',()=>{input.value='';filter();input.focus({preventScroll:true});});
  document.addEventListener('pharmabiz:workspace-before-view',event=>{
    if(!phone.matches)return;
    input.value='';
    const view=event.detail?.view;
    const target=groups.find(g=>g.items.some(b=>b.dataset.view===view))||activeGroup();
    allButtons.forEach(b=>b.hidden=false);
    groups.forEach(g=>g.group.hidden=false);
    clear.hidden=true;empty.hidden=true;
    setExpanded(target);
  });
  new MutationObserver(()=>{
    if(phone.matches&&sidebar.classList.contains('open')&&!input.value){
      setExpanded(activeGroup());
      nav.scrollTop=0;
    }
  }).observe(sidebar,{attributes:true,attributeFilter:['class']});
  phone.addEventListener('change',filter);
  filter();
})();
