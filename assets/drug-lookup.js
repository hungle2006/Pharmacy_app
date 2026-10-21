(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  if(!$('lookup-panel'))return;
  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','"':'&#39;'}[ch]));
  const fmt=value=>Number(value||0).toLocaleString('vi-VN');
  const price=value=>value===null||value===undefined?'Chưa có giá':fmt(value)+' ₫';
  const text=value=>value===null||value===undefined||String(value).trim()===''?'Chưa có thông tin':String(value);
  const reasons={
    MISSING_DAV_SOURCE_INGREDIENT:'Nguồn DAV thiếu thông tin hoạt chất',
    INGREDIENT_NOT_FOUND_IN_RXNORM:'Chưa tìm thấy hoạt chất tương ứng trong RxNorm',
    PARTIAL_INGREDIENT_EVIDENCE:'Chỉ có bằng chứng cho một phần hoạt chất',
    NO_EXACT_SCD_STRENGTH_FORM:'Chưa tìm thấy SCD khớp đủ hoạt chất, hàm lượng và dạng bào chế',
    SCD_CANDIDATE_NEEDS_CLINICAL_REVIEW:'Có ứng viên SCD, cần xét duyệt chuyên môn',
    NO_SCD_CANDIDATE_OR_EVIDENCE:'Chưa có ứng viên SCD hoặc bằng chứng phù hợp',
    LEGACY_ACCEPTED_MAPPING_NO_NEW_CANDIDATE:'Mapping được chấp nhận từ dữ liệu cũ, chưa có ứng viên Silver mới',
    LEGACY_SCD_ID_RESOLVED_NAME_ONLY:'Đã tra được tên SCD từ mã cũ; chưa xác minh quan hệ lâm sàng'
  };
  const state={active:false,mode:'dav',page:1,size:20,query:'',items:[],total:0,totalPages:0,selection:null,controller:null,detailController:null,requestId:0,detailRequestId:0,loaded:false,debounce:null};
  const results=$('lookup-results'),details=$('lookup-details'),message=$('lookup-message');
  const status=(messageText,kind='normal')=>{
    message.textContent=messageText;
    message.dataset.kind=kind;
  };
  const badge=(label,kind='muted')=>'<span class="lookup-pill lookup-pill-'+kind+'">'+esc(label)+'</span>';
  function setMode(mode) {
    state.mode=mode==='rx'?'rx':'dav';
    state.page=1;
    state.selection=null;
    $('lookup-tab-dav').setAttribute('aria-pressed',String(state.mode==='dav'));
    $('lookup-tab-rx').setAttribute('aria-pressed',String(state.mode==='rx'));
    $('lookup-current-control').hidden=state.mode==='rx';
    $('lookup-search').placeholder=state.mode==='rx'?'Nhập tên thuật ngữ hoặc mã RxCUI, ví dụ: acetaminophen':'Tên thuốc, hoạt chất, số đăng ký hoặc nhà sản xuất…';
    $('lookup-form').querySelector('.lookup-submit').firstChild.textContent=state.mode==='rx'?'Tra RxNorm ':'Tìm thuốc ';
    resetDetails();
    search();
  }
  function resetDetails() {
    details.innerHTML='<div class="lookup-detail-empty"><div class="lookup-detail-icon" aria-hidden="true">✳</div><h3>Chọn '+(state.mode==='dav'?'một thuốc':'một thuật ngữ')+' để xem chi tiết</h3><p>'+(state.mode==='dav'?'Bấm một kết quả để xem giá quan sát, thông tin DAV, ứng viên RxNorm và bằng chứng thành phần.':'Bấm một khái niệm để xem RxCUI, TTY và thông tin RxNorm hiện có.')+'</p></div>';
  }
  function loading() {
    results.innerHTML='<div class="lookup-skeleton"><span></span><span></span><span></span></div>';
    $('lookup-prev').disabled=true;
    $('lookup-next').disabled=true;
    $('lookup-summary').textContent='Đang truy vấn Gold…';
    $('lookup-result-count').textContent='…';
  }
  function renderItems() {
    const total=state.total;
    $('lookup-summary').textContent=fmt(total)+' '+(state.mode==='dav'?'sản phẩm DAV theo điều kiện tìm kiếm':'khái niệm RxNorm theo điều kiện tìm kiếm');
    $('lookup-result-count').textContent=fmt(total);
    $('lookup-pageinfo').textContent='Trang '+state.page+' / '+Math.max(1,state.totalPages);
    $('lookup-prev').disabled=state.page<=1;
    $('lookup-next').disabled=state.page>=state.totalPages;
    if(!state.items.length){
      results.innerHTML='<div class="lookup-empty-result"><span aria-hidden="true">⌕</span><strong>Không tìm thấy kết quả phù hợp</strong><p>Thử tên hoạt chất, số đăng ký khác hoặc tắt tùy chọn chỉ xem dữ liệu Silver hiện tại.</p></div>';
      return;
    }
    results.innerHTML=state.items.map((r,i)=>{
      const rx=state.mode==='rx';
      const name=rx?r.canonical_name:r.drug_name;
      const secondary=rx?('RxCUI '+text(r.rxcui)+' · '+text(r.canonical_tty)):text(r.ingredient);
      const status=rx
        ?badge(r.canonical_tty||'RXNORM','mint')
        :r.catalog_duplicate_status&&r.catalog_duplicate_status!=='LEGACY_UNRESOLVED'
          ?badge('Cần rà soát trùng','amber')
          :badge(r.product_source==='SILVER_R2'?'Dữ liệu Silver':'Dữ liệu cũ','mint');
      const meta=rx
        ?(r.scd_name?'Có thuật ngữ thuốc SCD':'Thuật ngữ RxNorm')
        :[r.strength,r.dosage_form].filter(Boolean).join(' · ')||'Chưa đủ thông tin hàm lượng / dạng';
      const right=rx?'RxCUI '+text(r.rxcui):price(r.price_vnd);
      return '<button type="button" class="lookup-item'+(state.selection===String(rx?r.rxcui:r.id)?' is-selected':'')+'" data-lookup-index="'+i+'" aria-pressed="'+(state.selection===String(rx?r.rxcui:r.id))+'">'+
        '<span class="lookup-item-header">'+status+'<small>'+(rx?'RXNORM':'DAV · '+esc(r.registration_no||r.id||'—'))+'</small></span>'+
        '<strong class="lookup-item-name">'+esc(name||'Chưa có tên')+'</strong>'+
        '<span class="lookup-item-sub">'+esc(secondary)+'</span>'+
        '<span class="lookup-item-bottom"><span>'+esc(meta)+'</span><b>'+esc(right)+' <span aria-hidden="true">↗</span></b></span>'+
        '</button>';
    }).join('');
  }
  async function search() {
    if(!state.active)return;
    const id=++state.requestId;
    state.controller?.abort();
    const controller=new AbortController();
    state.controller=controller;
    state.detailController?.abort();
    state.selection=null;
    state.items=[];
    state.query=$('lookup-search').value.trim();
    resetDetails();
    if(state.mode==='rx'&&!state.query){
      results.innerHTML='<div class="lookup-empty-result"><span aria-hidden="true">⌕</span><strong>Nhập tên thuật ngữ hoặc RxCUI</strong><p>Ví dụ: acetaminophen, amoxicillin, 161 hoặc 723.</p><div class="lookup-examples"><button type="button" data-lookup-example="acetaminophen">acetaminophen</button><button type="button" data-lookup-example="amoxicillin">amoxicillin</button></div></div>';
      state.total=0;state.totalPages=0;renderPagerEmpty();
      status('Nhập từ khóa để tra cứu thuật ngữ RxNorm.');
      return;
    }
    loading();
    status('Đang tìm kiếm trên Neon Gold…');
    const p=new URLSearchParams({page:state.page,pageSize:state.size});
    if(state.mode==='dav'){
      p.set('mode','products');
      if(state.query)p.set('q',state.query);
      if($('lookup-current').checked)p.set('currentOnly','true');
    }else p.set('q',state.query);
    try{
      const response=await fetch((state.mode==='dav'?'/api/data?':'/api/rxnorm?')+p,{signal:controller.signal,cache:'no-store'});
      const body=await response.json();
      if(!response.ok||body.mode!=='database')throw new Error(body.notice||body.reason||'Không đọc được dữ liệu');
      if(id!==state.requestId||!state.active)return;
      state.items=state.mode==='dav'?body.records||[]:body.items||[];
      state.total=Number(body.totalRows||0);
      state.totalPages=Number(body.totalPages||0);
      renderItems();
      status(state.total?'Kết quả từ Neon Gold · '+fmt(state.total)+' '+(state.mode==='dav'?'sản phẩm trong phạm vi tìm kiếm':'thuật ngữ phù hợp'):'Không có bản ghi phù hợp.');
    }catch(e){
      if(controller.signal.aborted||id!==state.requestId)return;
      state.total=0;state.totalPages=0;state.items=[];
      renderPagerEmpty();
      results.innerHTML='<div class="lookup-empty-result"><strong>Chưa tải được kết quả</strong><p>'+esc(e.message||'Lỗi kết nối')+'. Hãy thử lại.</p><button type="button" class="lookup-retry">Thử lại ↻</button></div>';
      status('Không kết nối được Neon Gold. Có thể thử lại mà không mất dữ liệu.','error');
    }
  }
  function renderPagerEmpty(){
    $('lookup-summary').textContent='Chưa có kết quả';
    $('lookup-result-count').textContent='0';
    $('lookup-pageinfo').textContent='Trang 1';
    $('lookup-prev').disabled=true;$('lookup-next').disabled=true;
  }
  const field=(label,value)=>'<div class="lookup-field"><dt>'+esc(label)+'</dt><dd>'+esc(text(value))+'</dd></div>';
  function renderDavDetail(d,raw) {
    const p=d.product;
    const accepted=Number(p.accepted_for_serving)===1;
    const candidate=Boolean(p.suggested_scd_rxcui);
    const scd=accepted?p.selected_scd_rxcui:p.suggested_scd_rxcui;
    const scdName=accepted?p.selected_scd_name||p.terminology_scd_name:p.candidate_scd_name||p.terminology_scd_name;
    const label=accepted?'Đã chấp nhận trong Gold':candidate?'Ứng viên chờ rà soát':'Chưa có SCD đối chiếu';
    const kind=accepted?'mint':candidate?'amber':'muted';
    const explanation=reasons[p.candidate_evidence_status]||p.candidate_evidence_status||p.review_reason||'Chưa có thông tin xác minh bổ sung';
    const components=(d.evidence||[]).map(e=>{
      const ok=Boolean(e.ingredient_candidate_rxcui);
      return '<div class="lookup-evidence"><div><strong>'+esc(e.component_raw||'Thiếu thành phần nguồn')+'</strong>'+badge(ok?'Ứng viên hoạt chất':'Chưa đối chiếu',ok?'amber':'muted')+'</div>'+
        '<p>'+(ok?'RxCUI '+esc(e.ingredient_candidate_rxcui)+' · '+esc(e.ingredient_candidate_name||'—'):esc(reasons[e.review_reason]||e.review_reason||'Chưa có RxNorm ứng viên'))+'</p></div>';
    }).join('');
    details.innerHTML='<div class="lookup-detail-top"><div class="eyebrow">DAV / PRODUCT RECORD</div><button id="lookup-detail-close" class="lookup-detail-close" type="button" aria-label="Đóng chi tiết">✕</button></div>'+
      '<h3 class="lookup-detail-title">'+esc(p.drug_name||raw.drug_name||'Thuốc chưa có tên')+'</h3>'+
      '<div class="lookup-badges">'+badge(label,kind)+badge('Dữ liệu '+(raw.product_source==='SILVER_R2'?'Silver':'Gold cũ'),'muted')+'</div>'+
      '<dl class="lookup-fields">'+field('Số đăng ký',p.registration_number)+field('Hoạt chất',p.active_ingredient_raw)+field('Hàm lượng',p.strength_raw)+field('Dạng bào chế',p.dosage_form_raw)+field('Nhà sản xuất',raw.manufacturer)+field('Giá quan sát gần nhất',raw.price_vnd===null?'Chưa có giá':price(raw.price_vnd))+
      field('Loại giá / đơn vị',[raw.price_type,raw.unit].filter(Boolean).join(' · '))+field('Ngày quan sát',raw.snapshot_date)+'</dl>'+
      '<section class="lookup-mapping"><div class="eyebrow">LINKED EVIDENCE / RXNORM</div><h4>Đối chiếu RxNorm</h4>'+
      '<p class="lookup-mapping-note">'+esc(explanation)+'</p>'+
      (scd?'<div class="lookup-scd"><span>RxCUI · '+esc(scd)+'</span><strong>'+esc(scdName||'Chưa có tên SCD')+'</strong><small>'+esc(p.dose_form_name||'')+'</small></div>':
        '<p class="lookup-muted">Không có mã RxCUI thuốc lâm sàng đủ căn cứ để hiển thị.</p>')+
      (p.ingredient_component_total!==null&&p.ingredient_component_total!==undefined?'<p class="lookup-coverage">Ứng viên hoạt chất: '+fmt(p.ingredient_component_matched)+' / '+fmt(p.ingredient_component_total)+' thành phần</p>':'')+
      '<h4>Chi tiết bằng chứng thành phần</h4>'+(components||'<p class="lookup-muted">Chưa có dòng bằng chứng thành phần từ Silver.</p>')+
      '<p class="lookup-warning">Mã ứng viên chưa được xác minh lâm sàng. Không sử dụng kết quả này để kê đơn hoặc tự điều trị.</p></section>';
    if(raw.catalog_duplicate_status&&raw.catalog_duplicate_status!=='LEGACY_UNRESOLVED')
      details.insertAdjacentHTML('beforeend','<p class="lookup-warning">Sản phẩm cũ đang được đánh dấu nghi trùng với bản Silver; dữ liệu giá và mapping lịch sử chưa bị xóa.</p>');
    bindClose();
  }
  function renderRxDetail(raw){
    details.innerHTML='<div class="lookup-detail-top"><div class="eyebrow">RXNORM / CONCEPT</div><button id="lookup-detail-close" class="lookup-detail-close" type="button" aria-label="Đóng chi tiết">✕</button></div>'+
      '<h3 class="lookup-detail-title">'+esc(raw.canonical_name||'Không có tên')+'</h3>'+
      '<div class="lookup-badges">'+badge(raw.canonical_tty||'TERM','mint')+badge('RxCUI '+text(raw.rxcui),'muted')+'</div>'+
      '<dl class="lookup-fields">'+field('RxCUI',raw.rxcui)+field('Loại thuật ngữ (TTY)',raw.canonical_tty)+field('Nguồn thuật ngữ (SAB)',raw.canonical_sab)+field('Các loại TTY',raw.tty_set)+field('SCD',raw.scd_name)+field('Dạng bào chế',raw.dose_form_name)+field('Số thành phần SCD',raw.component_count)+'</dl>'+
      '<p class="lookup-warning">Thông tin thuật ngữ RxNorm không tự xác nhận tương đương với thuốc DAV hoặc chỉ định điều trị.</p>';
    bindClose();
  }
  function bindClose(){
    $('lookup-detail-close').onclick=()=>{
      state.selection=null;resetDetails();renderItems();
    };
    if(matchMedia('(max-width: 980px)').matches)
      details.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth',block:'start'});
    details.focus({preventScroll:true});
  }
  async function selectItem(index){
    const raw=state.items[index];if(!raw)return;
    const rx=state.mode==='rx';
    state.selection=String(rx?raw.rxcui:raw.id);
    renderItems();
    state.detailController?.abort();
    const req=++state.detailRequestId;
    if(rx){renderRxDetail(raw);return;}
    details.innerHTML='<div class="lookup-detail-empty"><h3>Đang truy xuất chi tiết…</h3><p>Đọc bảng mapping và bằng chứng từ Neon Gold.</p></div>';
    const controller=new AbortController();state.detailController=controller;
    try {
      const response=await fetch('/api/rxnorm?'+new URLSearchParams({dav_row_id:raw.id}),{signal:controller.signal,cache:'no-store'});
      const data=await response.json();
      if(!response.ok||data.mode!=='database')throw new Error(data.notice||data.reason||'Không đọc được chi tiết');
      if(req!==state.detailRequestId||!state.active)return;
      renderDavDetail(data,raw);
    }catch(e){
      if(controller.signal.aborted||req!==state.detailRequestId)return;
      details.innerHTML='<div class="lookup-detail-empty"><h3>Không tải được chi tiết</h3><p>'+esc(e.message||'Lỗi kết nối')+'</p></div>';
    }
  }
  $('lookup-form').addEventListener('submit',event=>{event.preventDefault();clearTimeout(state.debounce);state.page=1;search();});
  $('lookup-search').addEventListener('input',()=>{
    clearTimeout(state.debounce);
    state.debounce=setTimeout(()=>{state.page=1;search();},450);
  });
  $('lookup-tab-dav').onclick=()=>setMode('dav');
  $('lookup-tab-rx').onclick=()=>setMode('rx');
  $('lookup-current').onchange=()=>{state.page=1;search();};
  $('lookup-prev').onclick=()=>{if(state.page>1){state.page--;search();}};
  $('lookup-next').onclick=()=>{if(state.page<state.totalPages){state.page++;search();}};
  results.addEventListener('click',event=>{
    const card=event.target.closest('[data-lookup-index]');
    if(card){selectItem(Number(card.dataset.lookupIndex));return;}
    const example=event.target.closest('[data-lookup-example]');
    if(example){$('lookup-search').value=example.dataset.lookupExample;state.page=1;search();return;}
    if(event.target.closest('.lookup-retry'))search();
  });
  document.addEventListener('pharmabiz:lookup-view',event=>{
    const active=Boolean(event.detail?.active);
    state.active=active;
    if(active&&!state.loaded){state.loaded=true;search();}
    if(!active){state.controller?.abort();state.detailController?.abort();}
  });
  document.addEventListener('pharmabiz:lookup-refresh',()=>{state.page=1;search();});
})();
