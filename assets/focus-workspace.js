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
    const picker=document.createElement('label');picker.className='focus-picker';picker.append(document.createTextNode(root.id==='market-explore'?'Khám phá báo cáo':'Chọn góc nhìn'));
    const select=document.createElement('select');select.setAttribute('aria-label',root.id==='market-explore'?'Chọn phần báo cáo thị trường':'Chọn phần phân tích');picker.append(select);
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
      if(announce){
        status.textContent='Đang xem: '+select.options[index].textContent;
        // Always return to the selected chapter's heading; never leave readers stranded
        // at the previous chapter's scroll position (especially on narrow screens).
        const offset=matchMedia('(max-width:760px)').matches?76:92;
        const target=Math.max(0,window.scrollY+deck.getBoundingClientRect().top-offset);
        if(Math.abs(window.scrollY-target)>12)window.scrollTo({
          top:target,behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'
        });
      }
    }
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
    const disclosure=fold(records,'Khám phá bản ghi nguồn','records-disclosure');
    if(disclosure){if(disclosure.hidden!==records.hidden)disclosure.hidden=records.hidden;
      let count=disclosure.querySelector('.focus-record-count');if(!count){count=document.createElement('span');count.className='focus-record-count';disclosure.firstElementChild.append(count);}
      const countText=text(document.getElementById('records-count'));if(count.textContent!==countText)count.textContent=countText;
    }
    const disease=document.getElementById('disease-predict-panel');
    const intro=disease?.querySelector(':scope > .dp-card:first-child');if(intro?.querySelector('.dp-steps'))fold(intro,'Cách dùng và quy trình đối chiếu');
    const model=document.getElementById('dp-model-summary')?.parentElement;if(model?.classList.contains('dp-card'))fold(model,'Phạm vi và chất lượng mô hình');
    for(const deck of content.querySelectorAll('.focus-deck')){
      const pages=[...deck.querySelectorAll(':scope > .focus-page')],options=deck.querySelector('select').options;
      pages.forEach((page,i)=>{const node=[...page.children].find(n=>!n.classList.contains('depth-step'));const title=titleOf(node);if(options[i]&&options[i].textContent!==title){options[i].textContent=title;page.setAttribute('aria-label',title);}});
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
