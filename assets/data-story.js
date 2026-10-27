(() => {
'use strict';
const $=id=>document.getElementById(id), C=window.PharmaCharts;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(n,d=0)=>n===null||n===undefined||!Number.isFinite(Number(n))?'—':Number(n).toLocaleString('vi-VN',{maximumFractionDigits:d});
const pct=(a,b)=>Number(b)>0?num(Number(a)/Number(b)*100,1)+'%':'—';
const money=v=>num(v)+' ₫';
let gold=null,rx=null,relations=null,source='dav',pattern='country',stat='distribution',loading=false;
const names={SY:'SY · Tên đồng nghĩa',PSN:'PSN · Tên kê đơn',SCD:'SCD · Thuốc lâm sàng',SCDC:'SCDC · Thành phần thuốc',TMSY:'TMSY · Đồng nghĩa viết hoa',SBD:'SBD · Thuốc có thương hiệu',IN:'IN · Hoạt chất',VERIFIED_SCD:'Đã xác minh SCD',UNMAPPED:'Chưa liên kết',UNMATCHED_REVIEW:'Chưa khớp · Cần rà soát',CANDIDATE_REVIEW:'Có ứng viên · Cần rà soát',INGREDIENT_SET_ONLY:'Khớp tập hoạt chất',SCD_MATCH_REVIEW_REQUIRED:'SCD cần kiểm tra',PARTIAL_INGREDIENT_MAPPING:'Khớp một phần hoạt chất',INGREDIENT_STRENGTH_FORM_CONFLICT:'Xung đột cấu hình',NO_SCD_FOR_INGREDIENT_SET:'Chưa có SCD phù hợp',AMBIGUOUS_SCD:'Nhiều SCD ứng viên'};
const label=v=>names[v]||v;
const unavailableMessage='<p class="error-note">Chưa đọc được nguồn này. Không thay bằng số liệu mẫu. Bấm “Tải lại nguồn” phía trên để thử lại.</p>';
let unavailable='<p class="waiting">Đang đọc số liệu từ nguồn…</p>';
const tip=(name,value)=>`tabindex="0" data-tip="${esc(name)}" data-value="${esc(value)}" aria-label="${esc(name+': '+value)}"`;
function table(head,rows){return '<div class="source-table"><table><thead><tr>'+head.map(x=>'<th scope="col">'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
function evidence(element,head,rows,method){$(element).innerHTML='<p>'+esc(method)+'</p>'+table(head,rows);}
function read(title,text){return '<b>'+esc(title)+'</b><p>'+esc(text)+'</p>';}
function metric(value,description){return '<div class="source-metric"><strong>'+esc(value)+'</strong><span>'+esc(description)+'</span></div>';}
function bars(rows,{total=null,unit='bản ghi',percent=false,max=null,digits=0}={}){
 if(!rows?.length)return '<p class="waiting">Nguồn trả về 0 nhóm dữ liệu.</p>';
 const scale=max??Math.max(1,...rows.map(r=>Number(r.value)));
 return '<div class="chart-caption"><span>'+(percent?'Tỷ lệ có thông tin':'Số '+esc(unit))+'</span><span>Thang từ 0 · '+(percent?'100%':num(scale,digits))+'</span></div>'+rows.map(r=>{
  const v=Number(r.value),width=Math.min(100,Math.max(0,v/scale*100));
  const value=percent?num(v,1)+'%':num(v,digits);
  return '<div class="chart-row"><span class="chart-row-label">'+esc(label(r.name))+'</span><div class="bar-track" '+tip(label(r.name),value+' '+(percent?'':unit))+'><div class="story-bar" style="width:'+width+'%;'+(['Khác','Chưa phân chương'].includes(r.name)?'background:var(--chart-other)':'')+'"></div></div><strong>'+value+(total!==null&&!percent?'<small>'+pct(v,total)+'</small>':'')+'</strong></div>';
 }).join('');
}
function grouped(rows,limit=7){const sorted=rows.map(r=>({...r,value:Number(r.value)})).sort((a,b)=>b.value-a.value);if(sorted.length<=limit)return sorted;return [...sorted.slice(0,limit-1),{name:'Khác',value:sorted.slice(limit-1).reduce((s,r)=>s+r.value,0)}];}
function renderSource(){
 let html,metrics,desc,title,unit;
 if(source==='dav'){
  title='Những sản phẩm nào đang có trong danh mục?';desc='DAV cho biết tên thuốc, hoạt chất, nhà sản xuất và các lần kê khai giá. Một sản phẩm có thể có nhiều quan sát giá, nên hai số này được đếm riêng.';unit='Nguồn: Neon Gold · dav_product × price_record · tổng hợp toàn bộ danh mục, không lọc.';
  metrics=gold?metric(num(gold.summary.products),'sản phẩm phân biệt theo ID DAV')+metric(num(gold.summary.priced),'quan sát có giá VND hợp lệ'):unavailable;
 }else if(source==='rxnorm'){
  title='Cùng một khái niệm thuốc có thể có bao nhiêu tên?';desc='RxNorm giúp đưa các cách gọi thuốc về mã khái niệm RxCUI. Tên đồng nghĩa, tên hoạt chất và tên thuốc có thương hiệu có vai trò khác nhau.';unit='Nguồn: snapshot Silver · silver/rxnorm.csv. Dòng thuật ngữ khác mã khái niệm.';
  metrics=rx?metric(num(rx.report_3_eda.total_rows),'dòng thuật ngữ nguồn')+metric(num(rx.report_3_eda.distinct_rxcui_mapping_ready),'RxCUI đủ điều kiện mapping'):unavailable;
 }else if(source==='icd'){
  title='Mỗi tên bệnh được nhận diện bằng mã nào?';desc='ICD-10 là danh mục mã bệnh. Tên tiếng Việt, tiếng Anh và mã giúp người dùng chọn đúng mục khi tìm kiếm, kể cả khi cách viết gần giống.';unit='Nguồn: Neon Gold · disease. Đây là số mã trong danh mục, không phải số ca mắc bệnh.';
  metrics=relations?.disease?metric(num(relations.disease.total),'dòng mã ICD trong Gold')+metric(num(relations.disease.named_vi),'dòng có tên tiếng Việt'):unavailable;
 }else{
  title='Dữ liệu ghi nhận những liên quan thuốc–bệnh nào?';desc='MEDI cung cấp quan hệ giữa thuật ngữ thuốc và mã bệnh. Phải đối chiếu hệ mã và trạng thái khớp trước khi dùng một đường liên kết cho tra cứu.';unit='Nguồn: Neon Gold · medi_relation. Một dòng quan hệ không phải một chỉ định điều trị đã xác minh.';
  metrics=relations?.medi?metric(num(relations.medi.total),'dòng quan hệ MEDI')+metric(num(relations.medi.concepts),'RxCUI khác nhau được nhắc tới'):unavailable;
 }
 html='<div><span class="chart-label">'+esc(source.toUpperCase())+' / VAI TRÒ CỦA NGUỒN</span><h3>'+esc(title)+'</h3><p>'+esc(desc)+'</p><p class="source-grain">'+esc(unit)+'</p></div><div class="source-metrics">'+metrics+'</div>';
 $('source-content').innerHTML=html;$('source-content').setAttribute('aria-labelledby','tab-'+source);
}
function renderQuality(){
 if(gold){
  const q=gold.quality,fields={drug_name:'Tên thuốc',ingredient:'Hoạt chất',strength:'Hàm lượng',dosage_form:'Dạng bào chế',manufacturer:'Nhà sản xuất',country:'Quốc gia',unit:'Đơn vị'};
  const rows=Object.entries(fields).map(([k,name])=>({name,value:Number(q.total)>0?Number(q[k])/Number(q.total)*100:0,count:Number(q[k])}));
  $('quality-chart').innerHTML=Number(q.total)>0?bars(rows,{percent:true,max:100}):'<p>Không có sản phẩm để tính tỷ lệ.</p>';
  const least=[...rows].sort((a,b)=>a.value-b.value)[0];
  $('quality-reading').innerHTML=read('Đọc hình → quyết định xử lý',Number(q.total)>0?'Cột ngắn nhất là “'+least.name+'”: '+num(least.count)+' / '+num(q.total)+' sản phẩm có thông tin. Cột còn thiếu cần được kiểm tra trước khi dùng để lọc hoặc so sánh.':'Không tính tỷ lệ trên mẫu số 0.');
  evidence('quality-source',['Trường','Có thông tin','Tổng sản phẩm','Tỷ lệ'],rows.map(r=>[r.name,num(r.count),num(q.total),pct(r.count,q.total)]),'Nguồn: /api/analytics?options=0 · Gold. Mỗi ID DAV xuất hiện một lần; có thông tin nghĩa là giá trị khác rỗng/NULL. Độ đầy đủ không đồng nghĩa độ chính xác.');
 }else{$('quality-chart').innerHTML=unavailable;}
 if(rx){const e=rx.report_3_eda,m=rx.report_3_multivariate;$('names-visual').innerHTML='<div><strong>'+num(e.total_rows)+'</strong><small>dòng thuật ngữ nguồn</small></div><span class="equals">≠</span><div><strong>'+num(e.distinct_rxcui_mapping_ready)+'</strong><small>mã RxCUI đủ điều kiện</small></div>';$('names-visual').insertAdjacentHTML('afterend','<p id="multiple-reading"><b>'+pct(m.cross_column_quality.concepts_with_multiple_names,e.distinct_rxcui_mapping_ready)+'</b> mã RxCUI có nhiều tên. Đây là cấu trúc của dữ liệu, không tự động là lỗi trùng.</p>');}
}
function renderPattern(){
 let rows,total,title,scope,unit,reading,meaning,limit;
 if(pattern==='country'){
  rows=gold?.countries;total=gold?.summary.products;title='Sản phẩm trong danh mục đến từ những quốc gia nào?';scope='DAV · CƠ CẤU DANH MỤC';unit='Đơn vị: sản phẩm DAV phân biệt. Nhãn quốc gia giữ nguyên nguồn; Ấn Độ / India chưa gộp. Không phải thị phần bán hàng.';
  const top=rows?.[0];reading=top?`${top.name} đứng đầu với ${num(top.value)} / ${num(total)} sản phẩm.`:'';meaning='Danh mục cho thấy nguồn cung được ghi nhận, không phải doanh số. Ấn Độ và India đang là hai nhãn nguồn riêng: cần chuẩn hóa cách ghi trước khi so sánh giữa các quốc gia.';limit=7;
 }else if(pattern==='tty'){
  rows=rx?.report_4_statistics.tty_distribution?.map(r=>({name:r.tty??r.label,value:r.count}));total=rx?.report_4_statistics.n_terms;title='Tên gọi trong RxNorm có những vai trò nào?';scope='RXNORM · LOẠI THUẬT NGỮ TTY';unit='Đơn vị: dòng thuật ngữ đủ điều kiện mapping; không phải sản phẩm DAV.';
  const top=rows?.[0];reading=top?`${label(top.name)} có ${num(top.value)} dòng. Đây là số tên, không phải số thuốc khác nhau.`:'';meaning='Khi so khớp tên thuốc cần biết đang so tên hoạt chất, tên lâm sàng hay tên thương hiệu.';limit=7;
 }else if(pattern==='icd'){
  rows=relations?.disease?.chapters?.map(r=>({name:r.name==='Chưa phân chương'?r.name:'Chương '+r.name,value:r.value}));total=relations?.disease?.total;title='Các mã bệnh được phân bố giữa các chương ra sao?';scope='ICD-10 · PHÂN BỐ DANH MỤC';unit='Đơn vị: dòng mã ICD trong Gold. Không suy ra tỷ lệ người mắc bệnh.';
  const top=rows?.[0];reading=top?(top.name==='Chưa phân chương'?`${num(top.value)} / ${num(total)} mã chưa có thông tin chương trong Gold. Đây là phần metadata cần bổ sung.`:`${top.name} có ${num(top.value)} mã. Chương có nhiều mã có thể chi tiết hơn về cách phân loại.`):'';meaning=top?.name==='Chưa phân chương'?'Cần rà soát phần chưa phân chương trước khi kết luận cơ cấu danh mục. Số mã nhiều không phản ánh số ca mắc bệnh.':'Một chương có nhiều mã không có nghĩa bệnh phổ biến hơn. Muốn phân tích dịch tễ phải có dữ liệu ca bệnh.';limit=7;
 }else{
  rows=relations?.medi?.systems;total=relations?.medi?.total;title='MEDI sử dụng những hệ mã bệnh nào?';scope='MEDI · HỆ MÃ CỦA QUAN HỆ';unit='Đơn vị: dòng quan hệ MEDI trong Gold; một RxCUI có thể xuất hiện nhiều dòng.';
  const top=rows?.[0];reading=top?`${top.name} xuất hiện ở ${num(top.value)} dòng quan hệ.`:'';meaning='Trước khi nối với ICD-10 Việt Nam, cần kiểm tra hệ mã. Tên gần nhau hay mã giống nhau chưa đủ để bỏ qua khác biệt hệ thống.';limit=7;
 }
 $('pattern-kicker').textContent=scope;$('pattern-title').textContent=title;$('pattern-unit').textContent=unit;
 if(!rows){$('pattern-chart').innerHTML=unavailable;$('pattern-reading').innerHTML='';$('pattern-source').innerHTML='Chưa có dữ liệu nguồn.';return;}
 const visible=grouped(rows,limit),top=[...rows].sort((a,b)=>Number(b.value)-Number(a.value))[0];
 $('pattern-chart').innerHTML=bars(visible,{total,unit:pattern==='icd'?'mã ICD':pattern==='country'?'sản phẩm':pattern==='tty'?'thuật ngữ':'quan hệ'});
 $('pattern-reading').innerHTML='<strong class="big">'+pct(top?.value,total)+'</strong><p>'+esc(reading)+'</p><h4>Ý nghĩa</h4><p>'+esc(meaning)+'</p><h4>Cách đọc</h4><p>Cột dài hơn nghĩa là có nhiều bản ghi hơn. “Khác” gom các nhóm còn lại; mở số liệu để xem mọi nhóm.</p>';
 evidence('pattern-source',['Nhóm','Số lượng','Tỷ trọng'],rows.map(r=>[label(r.name),num(r.value),pct(r.value,total)]),unit+' Tổng mẫu số: '+num(total)+'. Nguồn: '+(pattern==='country'?'/api/analytics?options=0':pattern==='tty'?'/assets/rxnorm-eda.json':'/api/story')+'. Các cột bắt đầu từ 0.');
}
function svgFrame(content,labelText,height=300){return '<div class="svg-scroll"><svg class="story-svg" viewBox="0 0 620 '+height+'" role="img" aria-label="'+esc(labelText)+'">'+content+'</svg></div>';}
function histogram(rows,{mean,median}={}){
 const W=620,H=300,L=45,R=12,T=30,B=55,max=Math.max(1,...rows.map(r=>r.count)),pw=W-L-R,ph=H-T-B,step=pw/rows.length;
 let out='';for(let i=0;i<=3;i++){const y=T+ph-i*ph/3;out+='<line class="grid" x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'"/><text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end">'+esc(C.compact(max*i/3))+'</text>';}
 out+='<text x="'+L+'" y="14">Số dòng thuật ngữ</text>';
 rows.forEach((r,i)=>{const x=L+i*step+1,y=T+ph-Number(r.count)/max*ph;out+='<rect class="mark" x="'+x+'" y="'+y+'" width="'+(step-2)+'" height="'+(T+ph-y)+'" '+tip(r.bin,num(r.count)+' thuật ngữ')+'/><text x="'+(x+step/2)+'" y="'+(H-B+21)+'" text-anchor="middle">'+esc(r.bin)+'</text>';});
 out+='<line class="axis" x1="'+L+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'"/><text x="'+(W/2)+'" y="'+(H-6)+'" text-anchor="middle">Độ dài tên · ký tự (100+ gom phần đuôi)</text>';
 return '<div class="desktop-distribution">'+svgFrame(out,'Phân bố độ dài tên theo khoảng ký tự. Khoảng 100+ có độ rộng khác các khoảng còn lại.')+'</div><div class="mobile-distribution">'+bars(rows.map(r=>({name:r.bin+' ký tự',value:r.count})),{unit:'thuật ngữ'})+'</div>';
}
function scatter(s){
 const pts=s.scatter_illustrative,W=620,H=310,L=48,R=18,T=28,B=48,pw=W-L-R,ph=H-T-B,maxY=Math.max(...pts.map(p=>p.avg_name_length),1),maxX=Math.max(...pts.map(p=>p.terms),2),x=v=>L+Math.log2(v)/Math.log2(maxX)*pw,y=v=>H-B-v/maxY*ph;
 let out='<text x="'+L+'" y="13">Độ dài tên trung bình · ký tự</text>';
 for(let i=0;i<=4;i++){let v=i*maxY/4;out+='<line class="grid" x1="'+L+'" x2="'+(W-R)+'" y1="'+y(v)+'" y2="'+y(v)+'"/><text x="'+(L-8)+'" y="'+(y(v)+4)+'" text-anchor="end">'+num(v)+'</text>';}
 for(let v=1;v<=maxX;v*=2)out+='<text x="'+x(v)+'" y="'+(H-B+23)+'" text-anchor="middle">'+v+'</text>';
 out+='<line class="axis" x1="'+L+'" x2="'+(W-R)+'" y1="'+(H-B)+'" y2="'+(H-B)+'"/><line class="axis" x1="'+L+'" x2="'+L+'" y1="'+T+'" y2="'+(H-B)+'"/>';
 pts.forEach(p=>out+='<circle class="point" cx="'+x(p.terms)+'" cy="'+y(p.avg_name_length)+'" r="3.4" '+tip('RxCUI '+p.rxcui,num(p.terms)+' tên · '+num(p.avg_name_length,2)+' ký tự trung bình')+'/>');
 out+='<text x="'+(W/2)+'" y="'+(H-3)+'" text-anchor="middle">Số tên / RxCUI · thang log₂</text>';
 return svgFrame(out,'Mẫu phân tầng '+num(pts.length)+' RxCUI. Mỗi điểm là một mã; trục số tên dùng log base 2.',H);
}
function renderStat(){
 if(!rx){$('stat-content').innerHTML=unavailable;return;}
 const s=rx.report_4_statistics,m=rx.report_3_multivariate,n=s.name_length;let html;
 if(stat==='distribution'){
  html='<div class="stat-layout"><div><span class="chart-label">HISTOGRAM / PHÂN PHỐI ĐỘ DÀI TÊN</span><h3>Tên “điển hình” dài bao nhiêu?</h3><div class="stat-numbers"><div><b>'+num(n.median)+' ký tự</b><span>Trung vị · điểm giữa</span></div><div><b>'+num(n.mean,2)+' ký tự</b><span>Trung bình · tổng chia số tên</span></div></div>'+histogram(s.histogram_name_length)+'</div><aside class="stat-explain"><h4>Vì sao có hai con số?</h4><p>Trung vị là vị trí giữa khi xếp tên từ ngắn đến dài. Trung bình cộng chịu ảnh hưởng của những tên rất dài.</p><p>Trong snapshot này, trung bình cao hơn trung vị. Biểu đồ giúp thấy phần đuôi tên dài thay vì chỉ nhìn một mức đại diện.</p><div class="plain-definition"><b>Độ lệch chuẩn '+num(n.std_dev,2)+' ký tự</b><br>Mô tả mức phân tán quanh trung bình. Không có nghĩa mọi tên đều lệch đúng chừng đó.</div><p>Cột 100+ gom nhiều độ dài, nên không so mật độ trực tiếp với các khoảng rộng 10 ký tự.</p></aside></div>'+
  '<details class="source-inspector"><summary>Công thức, đơn vị & số liệu</summary><p>Trung bình = tổng số ký tự / số thuật ngữ. Trung vị = phân vị 50%. SD = căn bậc hai trung bình bình phương độ lệch so với trung bình (ddof=0).</p>'+table(['Khoảng ký tự','Số thuật ngữ'],s.histogram_name_length.map(r=>[r.bin,num(r.count)]))+'<p>Nguồn: Silver RxNorm · '+num(s.n_terms)+' dòng đủ điều kiện. Không phải độ dài tên sản phẩm DAV.</p></details>';
 }else if(stat==='comparison'){
  const tests=m.welch_t_tests.filter(t=>t.status==='computed');
  html='<div class="stat-layout"><div><span class="chart-label">WELCH / SO SÁNH TRUNG BÌNH</span><h3>Tên các nhóm khác nhau bao nhiêu?</h3><p>Độ dài trung bình · ký tự. Mỗi cặp dùng các RxCUI độc lập của hai nhóm.</p>'+tests.map(t=>'<div class="test-pair"><b>'+esc(t.comparison)+'</b>'+bars([{name:t.group_a,value:t.mean_a},{name:t.group_b,value:t.mean_b}],{max:Math.max(...tests.flatMap(x=>[x.mean_a,x.mean_b])),unit:'ký tự trung bình',digits:2})+'<p style="font-size:11px">Chênh A − B: <b>'+num(t.difference,2)+' ký tự</b> · Cohen d = '+num(t.cohen_d,3)+'</p></div>').join('')+'</div><aside class="stat-explain"><h4>Khác biệt có lớn và rõ không?</h4><p>Chiều dài cột cho biết chênh lệch thực tế. Welch so mức chênh đó với độ bất định của dữ liệu; t mang dấu theo phép lấy A − B.</p><div class="plain-definition"><b>p nhỏ chưa chắc khác biệt lớn.</b><br>Đọc thêm chênh lệch ký tự và Cohen d. p-Holm hiệu chỉnh việc thử nhiều cặp, không phải phần trăm tin cậy.</div><p>Ví dụ SCD–SBD có p rất nhỏ nhưng |d| chỉ '+num(Math.abs(tests.find(t=>t.group_a==='SCD')?.cohen_d),3)+'. Với SY–PSN, loại các mã chung hai nhóm trước khi kiểm định.</p><a class="text-link" href="/rxnorm-eda.html?detail=rxnorm#r3-welch">Mở giả thuyết & công thức ↗</a></aside></div><details class="source-inspector"><summary>Xem cỡ mẫu, t và p-Holm</summary>'+table(['Cặp','nA / nB','t','p-Holm','Cohen d'],tests.map(t=>[t.comparison,num(t.n_a)+' / '+num(t.n_b),num(t.t,4),t.p_holm===0?'<1e−300 (giới hạn số học)':String(t.p_holm),num(t.cohen_d,3)]))+'<p>Nguồn: report_3_multivariate.welch_t_tests · đơn vị: RxCUI độc lập trong từng nhóm; không phải toàn bộ dòng TTY.</p></details>';
 }else if(stat==='chi'){
  const ch=m.chi_square;
  const rows=ch.observed.map((values,i)=>({name:ch.row_labels[i],values,total:values.reduce((sum,v)=>sum+v,0)}));
  const cells='<div class="heatmap-scroll"><table class="story-heatmap"><thead><tr><th>TTY / ký tự</th>'+ch.column_labels.map(v=>'<th>'+esc(v)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr><th scope="row">'+esc(r.name)+'</th>'+r.values.map((v,j)=>'<td '+tip(r.name+' · '+ch.column_labels[j],num(v)+' dòng · '+pct(v,r.total)+' của nhóm TTY')+'><span class="heat-color" style="opacity:'+((r.total?v/r.total:0)*.85+.05)+'"></span><b>'+pct(v,r.total)+'</b></td>').join('')+'</tr>').join('')+'</tbody></table></div>';
  html='<div class="stat-layout"><div><span class="chart-label">HEATMAP / CHI-SQUARE & CRAMÉR V</span><h3>Mỗi loại tên tập trung ở khoảng độ dài nào?</h3><p>Mỗi hàng cộng thành 100% (sai số làm tròn). Ô đậm hơn = tỷ lệ trong nhóm cao hơn.</p>'+cells+'<div class="heat-legend"><span>0%</span><i></i><span>100% trong hàng</span></div></div><aside class="stat-explain"><h4>Nhìn phân bố trước khi đọc kiểm định.</h4><p>Chi-square so số dòng quan sát trong các ô với số kỳ vọng nếu loại TTY và khoảng độ dài độc lập. χ² = '+num(ch.statistic,2)+' với '+num(ch.df)+' bậc tự do.</p><div class="plain-definition"><b>Cramér V = '+num(ch.cramers_v,3)+'</b><br>Mô tả độ mạnh liên hệ trên thang 0–1; không phải phần trăm chính xác của dữ liệu.</div><p>Một RxCUI có thể có nhiều dòng nên giả định độc lập chưa hoàn toàn đáp ứng. Đây là kết quả khám phá, không dùng p để khẳng định quan hệ tổng quát.</p></aside></div><details class="source-inspector"><summary>Xem số đếm trong từng ô & cách tính tỷ lệ</summary><p>Nguồn: report_3_multivariate.chi_square.observed · '+num(ch.n_rows)+' dòng thuật ngữ. Tỷ lệ ô = số dòng ở ô / tổng dòng của TTY đó. “Khác” gom các TTY còn lại.</p>'+table(['TTY',...ch.column_labels],rows.map(r=>[r.name,...r.values.map(v=>num(v))]))+'</details>';
 }else if(stat==='coherence'){
  const co=m.lexical_coherence,labels=['Ít trùng từ · <0,3','Trùng vừa · 0,3–<0,7','Trùng nhiều · ≥0,7'],rows=co.distribution.map((r,i)=>({name:labels[i],value:r.count}));
  html='<div class="stat-layout"><div><span class="chart-label">JACCARD / NHẤT QUÁN TỪ VỰNG</span><h3>Cùng một mã, các tên giống nhau đến đâu?</h3><p>Chỉ xét '+num(co.n_comparable_rxcui)+' RxCUI có nhiều tên để so sánh.</p>'+bars(rows,{total:co.n_comparable_rxcui,unit:'RxCUI'})+'<div class="stat-numbers"><div><b>'+num(co.mean,3)+'</b><span>Jaccard trung bình theo mã</span></div><div><b>'+num(co.median,3)+'</b><span>Jaccard trung vị</span></div></div></div><aside class="stat-explain"><h4>Điểm thấp là tín hiệu để đọc lại tên.</h4><p>Jaccard đo tỷ lệ từ chung trên toàn bộ từ khác nhau của hai tên. Mỗi mã được đối chiếu tối đa 15 tên với tên tham chiếu đầu tiên.</p><div class="plain-definition"><b>Jaccard = số từ chung / số từ trong hợp.</b><br>0: không trùng từ; 1: hai tập từ giống nhau.</div><p>Tên thương hiệu hoặc viết tắt có thể ít trùng từ mà vẫn hợp lệ. Điểm cao cũng không xác nhận tương đương điều trị.</p></aside></div><details class="source-inspector"><summary>Xem số liệu & giới hạn phương pháp</summary><p>Nguồn: report_3_multivariate.lexical_coherence. Phạm vi chỉ gồm mã có thể so sánh; không chia trên toàn bộ dòng thuật ngữ.</p>'+table(['Mức Jaccard','Số RxCUI','Tỷ trọng'],rows.map(r=>[r.name,num(r.value),pct(r.value,co.n_comparable_rxcui)]))+'</details>';
 }else{
  const corr=m.correlations[0];
  html='<div class="stat-layout"><div><span class="chart-label">SCATTER / MỐI LIÊN HỆ</span><h3>Nhiều tên có đi cùng tên dài hơn?</h3><p>Mỗi điểm = một RxCUI trong mẫu minh họa phân tầng '+num(s.scatter_sample_size)+' mã.</p>'+scatter(s)+'<div class="stat-numbers"><div><b>'+num(corr.pearson_r,4)+'</b><span>Pearson · mức tuyến tính</span></div><div><b>'+num(corr.spearman_rho,4)+'</b><span>Spearman · xu hướng theo hạng</span></div></div></div><aside class="stat-explain"><h4>Chấm tạo xu hướng, không tạo quan hệ nhân quả.</h4><p>Pearson xét mức đi cùng một đường thẳng. Spearman xét các mã có nhiều tên hơn có thường xếp hạng cao hơn về độ dài tên hay không.</p><div class="plain-definition">Hai hệ số tính trên toàn bộ <b>'+num(corr.n)+' RxCUI</b>. Các chấm chỉ là mẫu minh họa, không phải toàn bộ tập dùng tính hệ số.</div><p>Trong snapshot này, xu hướng đồng biến theo hạng rõ hơn quan hệ tuyến tính. Không kết luận “thêm tên sẽ làm tên dài hơn”.</p><a class="text-link" href="/rxnorm-eda.html?detail=rxnorm#r3-correlation">Mở cách tính tương quan ↗</a></aside></div><details class="source-inspector"><summary>Xem hệ số, mẫu minh họa & nguồn</summary><p>Nguồn: report_3_multivariate.correlations và report_4_statistics.scatter_illustrative. Trục X log₂ giúp tách các giá trị 1, 2, 4, 8… Mẫu số không đổi khi chuyển thang.</p>'+table(['RxCUI trong mẫu','Số tên','Độ dài TB (ký tự)'],s.scatter_illustrative.map(p=>[p.rxcui,num(p.terms),num(p.avg_name_length,2)]))+'</details>';
 }
 $('stat-content').innerHTML=html;
}
function renderMapping(){
 const m=gold?.mapping;
 if(!m||m.unavailable){$('mapping-chart').innerHTML=unavailable;}else{
  const rows=m.statuses||[];$('mapping-chart').innerHTML=bars(rows,{total:m.total,unit:'bản ghi mapping'});
  $('mapping-reading').innerHTML=read('Giữ lại trạng thái, không che phần chưa chắc chắn',num(m.accepted)+' / '+num(m.total)+' bản ghi mapping được chấp nhận để phục vụ tra cứu. Đây là trạng thái dữ liệu Gold, không phải tỷ lệ tương đương điều trị.');
  evidence('mapping-source',['Trạng thái','Số bản ghi','Tỷ trọng'],rows.map(r=>[r.name,num(r.value),pct(r.value,m.total)]),'Nguồn: /api/analytics · mapping không theo bộ lọc DAV, COUNT(*) trên dav_rxnorm_mapping. Các trạng thái là nhóm loại trừ nhau; cờ accepted và review có thể giao nhau nên không xếp chồng hai cờ thành tổng.');
 }
 const med=relations?.medi;
 $('link-evidence').innerHTML=med?'<div class="link-counter"><span>Tổng dòng quan hệ MEDI<small>Trong Gold, mọi hệ mã</small></span><b>'+num(med.total)+'</b></div><div class="link-counter"><span>Đủ bộ điều kiện mã để tra cứu<small>ICD10CM · exact ICD · RxNorm trong snapshot</small></span><b>'+num(med.eligible)+'</b></div><p style="font-size:10px;margin-top:12px">Nguồn: /api/story. Đây là kiểm tra liên kết mã; không phải xác minh chỉ định hay chất lượng lâm sàng.</p>':unavailable;
}
function renderPrice(){
 if(!gold){$('price-chart').innerHTML=unavailable;return;}
 const labels=['Dưới 1.000','1.000–<5.000','5.000–<10.000','10.000–<50.000','50.000–<100.000','Từ 100.000'];
 const bins=new Map(gold.bins.map(r=>[Number(r.bucket),Number(r.value)]));
 const rows=labels.map((name,i)=>({name,value:bins.get(i)||0}));const s=gold.summary;
 $('price-chart').innerHTML=bars(rows,{total:s.priced,unit:'quan sát giá'});
 $('price-reading').innerHTML=read('Phân vị giúp nhìn một khoảng, thay vì một mức giá',`P10 = ${money(s.p10)}, trung vị = ${money(s.median)}, P90 = ${money(s.p90)}. Khoảng P10–P90 bao quát 80% vị trí trong phân phối; các thuốc và đơn vị trong tổng quan đang được gộp chung.`);
 evidence('price-source',['Khoảng giá VND','Số quan sát','Tỷ trọng'],rows.map(r=>[r.name,num(r.value),pct(r.value,s.priced)]),'Nguồn: /api/analytics · price_record nối với dav_product, giá VND không âm. Tổng '+num(s.priced)+' quan sát. Các khoảng có bề rộng khác nhau và khoảng cuối mở, nên dùng cột rời để so tần suất, không diễn giải mật độ. Giá kê khai không phải giá bán thực tế, doanh thu hay giá một đơn vị chuẩn.');
}
function renderAll(){
 document.querySelectorAll('[data-count]').forEach(el=>{const k=el.dataset.count;el.textContent=k==='dav'?(gold?num(gold.summary.products)+' sản phẩm':'Nguồn chưa sẵn sàng'):k==='rxnorm'?(rx?num(rx.report_3_eda.total_rows)+' dòng thuật ngữ':'Nguồn chưa sẵn sàng'):k==='disease'?(relations?.disease?num(relations.disease.total)+' mã ICD':'Nguồn chưa sẵn sàng'):(relations?.medi?num(relations.medi.total)+' dòng quan hệ':'Nguồn chưa sẵn sàng');});
 $('multiple-reading')?.remove();renderSource();renderQuality();renderPattern();renderStat();renderMapping();renderPrice();
 const times=[gold?'Gold DAV: '+new Date(gold.refreshedAt).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):'',rx?'Snapshot RxNorm: '+new Date(rx.generated_utc).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):'',relations?'ICD / MEDI: '+new Date(relations.refreshedAt).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):''].filter(Boolean);
 $('source-timestamps').textContent=times.join(' · ')+' (giờ Việt Nam). Các nguồn có thời điểm cập nhật và mẫu số riêng; không cộng thành một tổng.';
}
async function get(url){const res=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(45000)});if(!res.ok)throw Error('Nguồn chưa sẵn sàng');return res.json();}
async function load(){
 if(loading)return;loading=true;unavailable='<p class="waiting">Đang đọc số liệu từ nguồn…</p>';renderAll();$('story-status').textContent='Đang đọc dữ liệu thật từ Gold và snapshot Silver…';
 const jobs=[['gold','/api/analytics?options=0'],['rx','/assets/rxnorm-eda.json'],['relations','/api/story']];
 await Promise.allSettled(jobs.map(async([key,url])=>{const value=await get(url);if(key==='gold'&&value.mode==='database')gold=value;if(key==='rx'&&value.report_3_eda)rx=value;if(key==='relations'&&value.mode==='database')relations=value;renderAll();}));
 const ready=[gold,rx,relations?.disease,relations?.medi].filter(Boolean).length;
 $('story-status').innerHTML='<span>'+ (ready===4?'Đã đọc các nguồn. Biểu đồ dùng số đếm thật; mở “Xem số liệu” để kiểm chứng.':'Đã đọc '+ready+'/4 nguồn. Phần chưa sẵn sàng được ghi rõ; không dùng số liệu thay thế.')+'</span><button id="retry-sources" type="button">Tải lại nguồn ↻</button>';
 loading=false;unavailable=unavailableMessage;renderAll();
}
document.addEventListener('click',e=>{
 const src=e.target.closest('[data-source]');if(src){source=src.dataset.source;document.querySelectorAll('[data-source]').forEach(b=>{const on=b===src;b.setAttribute('aria-selected',String(on));b.tabIndex=on?0:-1;});renderSource();}
 const pat=e.target.closest('[data-pattern]');if(pat){pattern=pat.dataset.pattern;document.querySelectorAll('[data-pattern]').forEach(b=>b.setAttribute('aria-pressed',String(b===pat)));renderPattern();}
 const st=e.target.closest('[data-stat]');if(st){stat=st.dataset.stat;document.querySelectorAll('[data-stat]').forEach(b=>b.setAttribute('aria-pressed',String(b===st)));renderStat();}
 if(e.target.closest('#retry-sources'))load();
});
document.querySelector('.source-tabs').addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const tabs=[...document.querySelectorAll('[data-source]')],i=tabs.indexOf(document.activeElement);const next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next].click();tabs[next].focus();});
const chapters=[...document.querySelectorAll('.chapter')],nav=[...document.querySelectorAll('.chapter-nav a')];
const observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){nav.forEach(a=>{const on=a.hash==='#'+e.target.id;a.classList.toggle('active',on);if(on)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});}},{rootMargin:'-15% 0px -60% 0px',threshold:0});chapters.forEach(s=>observer.observe(s));
C.installTooltips();load();
})();
