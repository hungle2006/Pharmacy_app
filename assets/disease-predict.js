/* Model rankings -> explicit ICD choice -> sourced MEDI/RxNorm/DAV evidence. */
(() => {
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=id=>document.getElementById(id),pct=v=>(v*100).toLocaleString('vi-VN',{maximumFractionDigits:2})+'%';
let report=null,reportError='',reportLoading=false,lastReport=0,active=false,predictions=[],icds=[],pending=false;
let predictionIndex=0,icdIndex=0,evidenceIndex=0,evidenceTab='meds',evidenceData=null,modelRun='',resultStage='rank';
const requests={predict:null,map:null,evidence:null};
const errors={DISEASE_API_NOT_CONFIGURED:'Dịch vụ dự đoán chưa được kết nối. Quản trị viên cần cấu hình kết nối model cho Pharmacy.',DISEASE_SERVICE_UNAVAILABLE:'Model chưa sẵn sàng. Có thể chưa có checkpoint được công bố hoặc dịch vụ đang khởi động. Hãy thử lại sau.',MODEL_TIMEOUT:'Model đang khởi động lâu. Hãy đợi một chút rồi thử lại; nội dung bạn nhập vẫn được giữ.',INVALID_MODEL_RESPONSE:'Phản hồi model chưa đúng định dạng. Chưa hiển thị kết quả để tránh diễn giải sai.',INVALID_INPUT:'Nhập mô tả từ 5 đến 4.000 ký tự.'};
const explanation='Điểm softmax chưa được hiệu chỉnh: chỉ thể hiện cách mô hình xếp hạng trong tập nhãn đã học, không phải xác suất bạn mắc bệnh. Mô hình vẫn có thể trả về một nhãn khi mô tả nằm ngoài dữ liệu học.';
const scope='Dữ liệu học gồm mô tả tổng hợp / theo mẫu; kết quả test cùng nguồn chưa xác nhận khả năng chẩn đoán trên bệnh nhân thực tế. Kết quả phục vụ nghiên cứu, cần được nhân viên y tế đánh giá.';
function cancel(...keys){for(const key of keys){requests[key]?.abort();requests[key]=null;}}
async function get(url,options,controller){
 const timer=setTimeout(()=>controller.abort(),55000);
 try{const r=await fetch(url,{cache:'no-store',...options,signal:controller.signal});const d=await r.json();if(!r.ok)throw Error(errors[d.error]||d.notice||'Chưa đọc được dữ liệu. Hãy thử lại sau.');return d;}
 finally{clearTimeout(timer);}
}
function status(text){$('dp-status').textContent=text;$('dp-status').hidden=!text;}
function ensure(){
 const root=$('disease-predict-panel');if(!root||root.dataset.ready)return;
 root.dataset.ready='true';root.classList.add('dp-workspace');
 root.innerHTML=`<section class="dp-card"><span class="dp-kicker">NGHIÊN CỨU PHÂN LOẠI VĂN BẢN Y TẾ</span><h2>Từ mô tả triệu chứng đến bằng chứng có thể đối chiếu</h2><p>Mô hình đọc mô tả, xếp hạng các tên bệnh đã học. Sau đó đối chiếu tên với danh mục ICD và khám phá dữ liệu thuốc liên quan có nguồn.</p><div class="dp-steps"><article class="dp-step"><strong>Mô tả vấn đề</strong><p>Nêu triệu chứng, thời gian xuất hiện và diễn tiến. Không nhập tên hoặc thông tin nhận dạng cá nhân.</p></article><article class="dp-step"><strong>Đọc &amp; đối chiếu</strong><p>So sánh các nhãn model dự đoán, rồi tự chọn đúng mã ICD. Tên gần giống chưa xác nhận cùng bệnh.</p></article><article class="dp-step"><strong>Xem bằng chứng thuốc</strong><p>Chỉ đọc liên kết MEDI, RxNorm và DAV đáp ứng điều kiện dữ liệu. Không tự suy ra thuốc hay liều dùng.</p></article></div></section>
 <div class="dp-grid"><section class="dp-card"><h3>1. Bạn đang gặp triệu chứng gì?</h3><form id="dp-form" class="dp-form"><label for="dp-text">Mô tả bằng tiếng Việt hoặc tiếng Anh</label><textarea id="dp-text" minlength="5" maxlength="4000" required aria-describedby="dp-input-help dp-count" placeholder="Ví dụ: Tôi ho khan vài ngày, kèm sốt nhẹ và mệt. Triệu chứng tăng về đêm…"></textarea><small id="dp-input-help">Chỉ nhập triệu chứng và diễn tiến. Hệ thống gửi văn bản tới dịch vụ suy luận; giao diện không lưu mô tả vào localStorage.</small><small id="dp-count">0 / 4.000 ký tự</small><div class="dp-actions"><button class="dp-primary" id="dp-submit" type="submit">Phân tích mô tả ↗</button><button id="dp-clear" type="button">Xóa mô tả</button></div></form><p class="dp-warning">Công cụ nghiên cứu không thay thế thăm khám, chẩn đoán hoặc kê đơn. Không chờ kết quả của công cụ nếu bạn cần trợ giúp y tế khẩn cấp.</p><div class="dp-status" id="dp-status" role="status" aria-live="polite" hidden></div></section>
 <section class="dp-card dp-results" id="dp-result-panel" aria-labelledby="dp-ranking-title" tabindex="-1"><div class="dp-results-heading"><span class="dp-kicker">KẾT QUẢ THEO TỪNG THẺ</span><h3 id="dp-ranking-title">2. Những tên bệnh nào được xếp hạng?</h3><p class="dp-muted" id="dp-results-hint">Mỗi lần chỉ xem một nhãn. Điểm số softmax chưa hiệu chỉnh, không phải xác suất mắc bệnh.</p></div><div class="dp-stage-back" id="dp-stage-back" hidden><button type="button" id="dp-back" aria-label="Quay lại bước trước">← Quay lại kết quả</button><span id="dp-stage-position"></span></div><div id="dp-ranking" aria-live="polite"><div class="dp-status">Chưa có kết quả. Nhập mô tả và chọn “Phân tích mô tả”.</div></div><section id="dp-mapping" hidden aria-labelledby="dp-mapping-title"><h3 id="dp-mapping-title">Đối chiếu danh mục ICD</h3><p id="dp-map-label"></p><p class="dp-muted">Chọn mã ICD phù hợp với mô tả. Một tên giống nhau không xác nhận cùng bệnh.</p><div id="dp-icds" aria-live="polite"></div></section><section id="dp-evidence" hidden aria-live="polite"></section><p class="dp-warning dp-results-warning" id="dp-results-warning">${explanation}</p></section></div>
 <section class="dp-card"><details><summary>Mô hình biết gì và chưa chứng minh được điều gì?</summary><p>${scope}</p><p>Pipeline dùng Transformer đa ngôn ngữ, giữ riêng validation / test theo nhóm văn bản; chọn checkpoint bằng Macro-F1 validation. Benchmark cố định giúp so sánh các lần cập nhật tháng. Chưa có kiểm định lâm sàng độc lập, chưa hiệu chỉnh xác suất và chưa có ngưỡng đã xác minh để phát hiện mô tả ngoài phạm vi.</p><p>Nhãn model và mã ICD thuộc hai hệ danh mục khác nhau. Hệ thống tìm ứng viên theo tên để bạn đối chiếu, không tự ép nhãn sang một mã ICD. Liên kết hoạt chất–bệnh cũng không khẳng định mọi sản phẩm chứa hoạt chất có chỉ định cho bệnh đó.</p></details><div id="dp-model-summary"></div></section>`;
 $('dp-form').addEventListener('submit',predict);
 $('dp-text').addEventListener('input',()=>{$('dp-count').textContent=$('dp-text').value.length.toLocaleString('vi-VN')+' / 4.000 ký tự';if(predictions.length)status('Mô tả đã thay đổi. Kết quả bên cạnh thuộc lần phân tích trước; hãy phân tích lại.');});
 $('dp-clear').onclick=()=>{cancel('predict','map','evidence');pending=false;predictions=[];icds=[];evidenceData=null;predictionIndex=0;icdIndex=0;resultStage='rank';$('dp-text').value='';$('dp-count').textContent='0 / 4.000 ký tự';$('dp-ranking').innerHTML='<div class="dp-status">Đã xóa mô tả và kết quả.</div>';showStage('rank');$('dp-submit').disabled=false;$('dp-submit').textContent='Phân tích mô tả ↗';status('');$('dp-text').focus();};
 root.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.matches('[data-dp-prediction]'))mapLabel(Number(b.dataset.dpPrediction));
  else if(b.matches('[data-dp-icd]'))loadEvidence(Number(b.dataset.dpIcd));
  else if(b.id==='dp-back')showStage(resultStage==='evidence'?'map':'rank');
  else if(b.hasAttribute('data-dp-prev'))shiftCard(-1);
  else if(b.hasAttribute('data-dp-next'))shiftCard(1);
  else if(b.hasAttribute('data-dp-tab')){evidenceTab=b.dataset.dpTab;evidenceIndex=0;renderEvidence();}
  else if(b.hasAttribute('data-dp-dot')){predictionIndex=Number(b.dataset.dpDot);renderRanking();}
 });
 root.querySelector('#dp-result-panel').addEventListener('keydown',e=>{
   if(!e.target.closest('.dp-flash-card')||e.target.closest('button,a,input,select,textarea'))return;
   if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();shiftCard(e.key==='ArrowRight'?1:-1);}
 });
 let start=null;
 root.querySelector('#dp-result-panel').addEventListener('touchstart',e=>{if(e.touches.length===1){start={x:e.touches[0].clientX,y:e.touches[0].clientY};}},{passive:true});
 root.querySelector('#dp-result-panel').addEventListener('touchend',e=>{
   if(!start||!e.changedTouches.length)return;
   const dx=e.changedTouches[0].clientX-start.x,dy=e.changedTouches[0].clientY-start.y;start=null;
   if(Math.abs(dx)>65&&Math.abs(dx)>Math.abs(dy)*1.7&&e.target.closest('.dp-flash-card'))shiftCard(dx<0?1:-1);
 },{passive:true});

}

function pager(current,total,label){
 if(total<=1)return '';
 return '<nav class="dp-card-pager" aria-label="'+esc(label)+'"><button type="button" data-dp-prev '+(current===0?'disabled':'')+' aria-label="Thẻ trước">←</button><span aria-live="polite">'+(current+1)+' / '+total+'</span><button type="button" data-dp-next '+(current===total-1?'disabled':'')+' aria-label="Thẻ tiếp theo">→</button></nav>';
}
function showStage(next){
 resultStage=next;
 $('dp-ranking').hidden=next!=='rank';
 $('dp-mapping').hidden=next!=='map';
 $('dp-evidence').hidden=next!=='evidence';
 $('dp-stage-back').hidden=next==='rank';
 $('dp-results-warning').hidden=next!=='rank';
 $('dp-results-hint').textContent=next==='rank'?'Chuyển qua từng thẻ để đọc top 5; điểm softmax chưa được hiệu chỉnh.':next==='map'?'Đối chiếu từng mã ICD; đây không phải bước xác nhận chẩn đoán.':'Xem từng bằng chứng MEDI, RxNorm và DAV; không suy ra chỉ định điều trị.';
 $('dp-back').textContent=next==='evidence'?'← Quay lại mã ICD':'← Quay lại kết quả';
 $('dp-stage-position').textContent=next==='rank'?'':next==='map'?'BƯỚC 2 / 3':'BƯỚC 3 / 3';
 if(next==='rank')cancel('map','evidence');
 if(next==='map')cancel('evidence');
}
function renderRanking(){
 const target=$('dp-ranking');if(!target||!predictions.length)return;
 predictionIndex=Math.max(0,Math.min(predictions.length-1,predictionIndex));
 const p=predictions[predictionIndex],i=predictionIndex;
 target.innerHTML='<div class="dp-flash-card" tabindex="0" aria-label="Tên bệnh được xếp hạng '+(i+1)+' trên '+predictions.length+'"><div class="dp-flash-meta"><span>NHÃN XẾP HẠNG '+String(i+1).padStart(2,'0')+'</span><span>TOP '+predictions.length+'</span></div><h4>'+esc(p.label)+'</h4><div class="dp-flash-value"><strong>'+pct(p.score)+'</strong><span>Điểm mô hình, không phải xác suất mắc bệnh</span></div><div class="dp-track" aria-hidden="true"><i style="width:'+Math.min(100,Math.max(0,p.score*100))+'%"></i></div><button class="dp-flash-action" type="button" data-dp-prediction="'+i+'">Đối chiếu mã ICD và dữ liệu thuốc →</button></div>'+pager(i,predictions.length,'Chuyển thẻ tên bệnh')+'<div class="dp-card-dots" role="group" aria-label="Chọn nhanh thẻ bệnh">'+predictions.map((_,idx)=>'<button type="button" data-dp-dot="'+idx+'" aria-label="Xem nhãn '+(idx+1)+'" aria-current="'+(idx===i?'true':'false')+'"></button>').join('')+'</div><p class="dp-provenance">Phiên bản model: '+esc(modelRun)+'</p>';
}
function renderIcd(){
 const target=$('dp-icds');if(!target)return;
 if(!icds.length){target.innerHTML='<div class="dp-status">Chưa tìm được mã ICD phù hợp cho nhãn này. Không suy đoán thuốc khi thiếu mã đối chiếu. Bạn có thể <a href="/disease-lookup.html">tra cứu danh mục ICD</a> theo tên khác.</div>';return;}
 icdIndex=Math.max(0,Math.min(icds.length-1,icdIndex));
 const x=icds[icdIndex];
 target.innerHTML='<div class="dp-flash-card" tabindex="0" aria-label="Mã ICD '+(icdIndex+1)+' trên '+icds.length+'"><div class="dp-flash-meta"><span>ỨNG VIÊN ICD</span><span>'+String(icdIndex+1).padStart(2,'0')+' / '+icds.length+'</span></div><h4>'+esc(x.icd_code)+' · '+esc(x.disease_name_vi||x.disease_name_en)+'</h4><p class="dp-muted">'+esc(x.disease_name_en||'')+'</p><p class="dp-flash-help">Kiểm tra tên bệnh và đặc điểm lâm sàng trước khi chọn mã.</p><button type="button" class="dp-flash-action" data-dp-icd="'+icdIndex+'">Xem bằng chứng thuốc cho mã này →</button></div>'+pager(icdIndex,icds.length,'Chuyển thẻ ICD');
}
function renderEvidence(){
 const target=$('dp-evidence');if(!target||!evidenceData)return;
 const d=evidenceData,meds=d.medications||[],products=d.products||[],items=evidenceTab==='products'?products:meds;
 evidenceIndex=Math.max(0,Math.min(items.length-1,evidenceIndex));
 const x=items[evidenceIndex];
 const content=!x?'<div class="dp-status">'+(evidenceTab==='products'?'Chưa có sản phẩm DAV qua liên kết SCD đã chấp nhận. Hệ thống không tự tạo sản phẩm hoặc thuốc thay thế.':'Chưa có quan hệ MEDI–RxNorm đủ điều kiện cho mã này. Không có dữ liệu không có nghĩa là không có điều trị.')+'</div>':
 evidenceTab==='meds'?'<div class="dp-flash-card" tabindex="0"><div class="dp-flash-meta"><span>MEDI / RXNORM</span><span>'+String(evidenceIndex+1).padStart(2,'0')+' / '+items.length+'</span></div><h4>'+esc(x.rxnorm_name||x.drug_description||'Chưa có tên')+'</h4><p class="dp-provenance">RxCUI '+esc(x.rxcui)+' · MEDI</p><p>'+esc(x.indication_description||'Chưa có mô tả quan hệ trong nguồn')+'</p></div>':
 '<div class="dp-flash-card" tabindex="0"><div class="dp-flash-meta"><span>HỒ SƠ SẢN PHẨM DAV</span><span>'+String(evidenceIndex+1).padStart(2,'0')+' / '+items.length+'</span></div><h4>'+esc(x.drug_name||'Chưa có tên')+'</h4><dl class="dp-facts"><dt>Hoạt chất</dt><dd>'+esc(x.ingredient||'Chưa ghi nhận')+'</dd><dt>Hàm lượng / dạng</dt><dd>'+esc([x.strength,x.dosage_form].filter(Boolean).join(' · ')||'Chưa đủ dữ liệu')+'</dd><dt>Số đăng ký</dt><dd>'+esc(x.registration_number||'Chưa ghi nhận')+'</dd><dt>Nhà sản xuất</dt><dd>'+esc(x.manufacturer||'Chưa ghi nhận')+'</dd></dl><a class="dp-flash-link" href="/?view=lookup&amp;q='+encodeURIComponent(x.registration_number||x.drug_name||'')+'">Tra cứu hồ sơ thuốc ↗</a></div>';
 target.innerHTML='<span class="dp-kicker">BẰNG CHỨNG · '+esc(d.disease.icd_code)+'</span><h3>Thông tin liên quan: '+esc(d.disease.disease_name_vi||d.disease.disease_name_en)+'</h3><p class="dp-warning">'+esc(d.important_note)+'</p><div class="dp-evidence-tabs" role="group" aria-label="Nguồn bằng chứng"><button type="button" data-dp-tab="meds" aria-pressed="'+(evidenceTab==='meds')+'">MEDI / RxNorm <span>'+meds.length+'</span></button><button type="button" data-dp-tab="products" aria-pressed="'+(evidenceTab==='products')+'">Sản phẩm DAV <span>'+products.length+'</span></button></div><p class="dp-muted">'+(evidenceTab==='meds'?'Tối đa 100 thuật ngữ có quan hệ MEDI cho mã ICD được chọn.':'Tối đa 35 sản phẩm qua liên kết SCD được chấp nhận; chưa xác minh chỉ định trên từng sản phẩm.')+'</p>'+content+pager(evidenceIndex,items.length,'Chuyển thẻ bằng chứng')+'<p class="dp-provenance">Nguồn: Neon Gold · disease, medi_relation, rxnorm_concept, rxnorm_scd_component, dav_rxnorm_mapping, dav_product. Liên kết dữ liệu không xác nhận liều dùng, chỉ định từng sản phẩm hay độ phù hợp cho người bệnh.</p>';
}
function shiftCard(delta){
 if(resultStage==='rank'){if(!predictions.length)return;predictionIndex=Math.max(0,Math.min(predictions.length-1,predictionIndex+delta));renderRanking();}
 else if(resultStage==='map'){if(!icds.length)return;icdIndex=Math.max(0,Math.min(icds.length-1,icdIndex+delta));renderIcd();}
 else if(resultStage==='evidence'){const total=(evidenceTab==='products'?evidenceData?.products:evidenceData?.medications)?.length||0;if(!total)return;evidenceIndex=Math.max(0,Math.min(total-1,evidenceIndex+delta));renderEvidence();}
}
async function predict(e){
 e.preventDefault();if(pending)return;
 const text=$('dp-text').value.trim();if(text.length<5||text.length>4000){status(errors.INVALID_INPUT);return;}
 cancel('predict','map','evidence');const c=new AbortController();requests.predict=c;pending=true;predictions=[];icds=[];evidenceData=null;predictionIndex=0;icdIndex=0;showStage('rank');
 $('dp-submit').disabled=true;$('dp-submit').textContent='Đang phân tích…';$('dp-ranking').innerHTML='<div class="dp-status">Đang chờ mô hình. Lần đầu có thể cần thời gian khởi động.</div>';status('Đang gửi mô tả để xếp hạng các nhãn bệnh…');
 try{
  const d=await get('/api/disease-predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,top_k:5})},c);if(requests.predict!==c)return;
  predictions=d.predictions;modelRun=d.model_run;renderRanking();
  status($('dp-text').value.trim()===text?'Đã xếp hạng. Sử dụng mũi tên để chuyển thẻ, chọn “Đối chiếu mã ICD” khi cần.':'Mô tả đã thay đổi trong khi chờ. Kết quả thuộc nội dung đã gửi trước đó; hãy phân tích lại.');
  if(matchMedia('(max-width:1000px)').matches)requestAnimationFrame(()=>$('dp-result-panel')?.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'}));
 }catch(e){if(requests.predict!==c)return;predictions=[];$('dp-ranking').innerHTML='<div class="dp-status">Chưa có dự đoán. Không hiển thị kết quả mô phỏng.</div>';status(e.name==='AbortError'?'Yêu cầu hết thời gian chờ. Bạn có thể thử lại.':e.message);}
 finally{if(requests.predict===c){requests.predict=null;pending=false;$('dp-submit').disabled=false;$('dp-submit').textContent='Phân tích mô tả ↗';}}
}
async function mapLabel(index){
 const p=predictions[index];if(!p)return;cancel('map','evidence');const c=new AbortController();requests.map=c;icds=[];icdIndex=0;evidenceData=null;
 predictionIndex=index;showStage('map');$('dp-map-label').textContent='Nhãn đang đối chiếu: '+p.label;
 $('dp-icds').innerHTML='<div class="dp-status">Đang tìm ứng viên tên bệnh trong ICD…</div>';
 if(p.label.length>100){$('dp-icds').innerHTML='<div class="dp-status">Nhãn quá dài để đối chiếu tự động. Hãy mở <a href="/disease-lookup.html">tra cứu ICD</a> để tìm tên phù hợp.</div>';return;}
 try{const d=await get('/api/disease-lookup?'+new URLSearchParams({q:p.label}),{},c);if(requests.map!==c)return;icds=d.suggestions||[];renderIcd();}
 catch(e){if(requests.map===c)$('dp-icds').textContent=e.name==='AbortError'?'Đối chiếu quá thời gian chờ. Quay lại kết quả và chọn lại nhãn để thử lại.':e.message;}
 finally{if(requests.map===c)requests.map=null;}
}
async function loadEvidence(index){
 const item=icds[index];if(!item)return;cancel('evidence');const c=new AbortController();requests.evidence=c;icdIndex=index;evidenceTab='meds';evidenceIndex=0;evidenceData=null;showStage('evidence');
 $('dp-evidence').innerHTML='<div class="dp-status">Đang đối chiếu MEDI → RxNorm → sản phẩm DAV được chấp nhận…</div>';
 try{const d=await get('/api/disease-lookup?'+new URLSearchParams({icd:item.icd_code}),{},c);if(requests.evidence!==c)return;evidenceData=d;renderEvidence();}
 catch(e){if(requests.evidence===c)$('dp-evidence').textContent=e.name==='AbortError'?'Đọc bằng chứng quá thời gian chờ. Quay lại và chọn lại mã ICD để thử lại.':e.message;}
 finally{if(requests.evidence===c)requests.evidence=null;}
}

function evaluation(){
 const intro='<section class="dp-card"><span class="dp-kicker">TRANSFORMER · PHÂN LOẠI MÔ TẢ BỆNH</span><h2>Mô hình nhận diện nhãn bệnh tốt đến đâu?</h2><p>Đầu vào là văn bản mô tả; mục tiêu là nhãn bệnh trong dữ liệu. Giá và thông tin thuốc không tham gia dự đoán. Chọn checkpoint bằng Macro-F1 validation, sau đó báo cáo test giữ riêng.</p><div class="dp-actions"><button type="button" data-view="disease-predict">Mở task dự đoán →</button><button type="button" data-dp-report-refresh>Tải lại kết quả model</button></div>';
 let body='';
 if(!report||report.status!=='ready')body='<div class="dp-status">'+esc(reportLoading?'Đang đọc báo cáo checkpoint đang phục vụ…':reportError||(report?.status==='not_trained'?'Chưa có checkpoint được công bố. Bảng điểm sẽ xuất hiện sau khi huấn luyện, đánh giá và promote thành công.':'Chưa tải báo cáo mô hình.'))+'</div>';
 else{
 const names={accuracy:'Top-1 accuracy',macro_f1:'Macro-F1',balanced_accuracy:'Balanced accuracy',top3_accuracy:'Top-3 accuracy',top5_accuracy:'Top-5 accuracy'},test=report.metrics.test||{};
 body='<h3>Kết quả trên tập test · cùng thang 0–100%</h3><div class="dp-metrics">'+Object.entries(names).map(([k,n])=>'<div class="dp-metric"><span>'+n+'</span><div class="dp-track" aria-hidden="true"><i style="width:'+(test[k]??0)*100+'%"></i></div><b>'+(test[k]===undefined?'Chưa có':pct(test[k]))+'</b></div>').join('')+'</div><div class="dp-table-wrap"><table class="dp-table"><thead><tr><th scope="col">Chỉ số</th><th scope="col">Validation</th><th scope="col">Test</th></tr></thead><tbody>'+Object.entries(names).map(([k,n])=>'<tr><td>'+n+'</td><td>'+(report.metrics.validation?.[k]===undefined?'Chưa có':pct(report.metrics.validation[k]))+'</td><td>'+(test[k]===undefined?'Chưa có':pct(test[k]))+'</td></tr>').join('')+'</tbody></table></div><p class="dp-provenance">Model run: '+esc(report.model_run)+'<br>Dataset revision: '+esc(report.dataset_revision)+'<br>Benchmark SHA-256: '+esc(report.benchmark_sha256)+'</p>';
 }
 return '<div class="dp-workspace">'+intro+body+'<p>Macro-F1 cho mỗi nhãn trọng số bằng nhau; accuracy đo tỷ lệ nhãn đứng đầu đúng. Top-3 / Top-5 chỉ đo nhãn thật có nằm trong danh sách, không xác nhận mọi bệnh được gợi ý đều đúng.</p><p class="dp-warning">'+scope+'</p><details><summary>Đọc đúng quy trình &amp; giới hạn</summary><p>GitHub kích hoạt pipeline Modal theo tháng. Các Parquet được đọc tại cùng một commit dữ liệu. Validation / test được đóng băng; nhãn mới cần benchmark mới. Checkpoint ứng viên chỉ thay phiên bản phục vụ khi vượt cổng validation của pipeline. Cổng này là điều kiện kỹ thuật, không phải chứng nhận lâm sàng.</p><p>Chưa có ma trận nhầm lẫn, kiểm định lâm sàng ngoài nguồn hoặc đo hiệu chỉnh xác suất trong báo cáo đang phục vụ. Không suy diễn các chỉ số chưa được tính.</p></details></section></div>';
}
async function loadReport(force=false){
 if(reportLoading||(!force&&lastReport&&Date.now()-lastReport<60000))return;
 reportLoading=true;reportError='';notify();
 try{const c=new AbortController();report=await get('/api/disease-predict',{},c);lastReport=Date.now();}
 catch(e){report=null;reportError=e.name==='AbortError'?'Quá thời gian đọc báo cáo. Hãy tải lại.':e.message;lastReport=Date.now();}
 finally{reportLoading=false;notify();}
}
function notify(){if($('dp-model-summary'))$('dp-model-summary').innerHTML='<p class="dp-provenance">'+esc(report?.status==='ready'?'Model đang phục vụ: '+report.model_run:reportLoading?'Đang kiểm tra checkpoint…':reportError||'Chưa có checkpoint được công bố.')+'</p>';document.dispatchEvent(new Event('pharmabiz:task-context'));}
function activate(view){active=view==='disease-predict';if(active){ensure();loadReport();}else{if(requests.map&&$('dp-icds'))$('dp-icds').textContent='Đã dừng chờ khi rời task. Chọn lại nhãn để đối chiếu.';if(requests.evidence&&$('dp-evidence'))$('dp-evidence').textContent='Đã dừng chờ khi rời task. Chọn lại mã ICD để xem bằng chứng.';cancel('predict','map','evidence');if(pending){pending=false;if($('dp-submit')){$('dp-submit').disabled=false;$('dp-submit').textContent='Phân tích mô tả ↗';$('dp-ranking').innerHTML='<div class="dp-status">Đã dừng chờ khi rời task. Phân tích lại để lấy kết quả.</div>';status('Yêu cầu đã dừng chờ. Nội dung mô tả vẫn được giữ.');}}}if(view==='modeling')loadReport();}
document.addEventListener('click',e=>{if(e.target.closest('[data-dp-report-refresh]'))loadReport(true);});
window.PharmaDisease=Object.freeze({activate,evaluation,loadReport});
})();
