/* Task charts use public aggregates, with explicit grains and source inspection. */
(() => {
'use strict';
const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const n=v=>finite(v)?Number(v):0;
function groupOther(rows,limit=6){const a=(rows||[]).map(r=>({...r,value:n(r.value)})).filter(r=>r.value>=0).sort((a,b)=>b.value-a.value);return a.length>limit?[...a.slice(0,limit-1),{name:'Các nhóm khác',value:a.slice(limit-1).reduce((s,r)=>s+r.value,0),other:true}]:a;}
function monthIndex(name){return /^\d{4}-\d{2}$/.test(name)?Number(name.slice(0,4))*12+Number(name.slice(5,7))-1:null;}
function recent(rows,range){const a=(rows||[]).filter(r=>monthIndex(r.name)!==null).sort((a,b)=>a.name.localeCompare(b.name));if(!a.length||range==='all')return a;const end=monthIndex(a.at(-1).name);return a.filter(r=>monthIndex(r.name)>end-Number(range));}
function spreads(rows){return (rows||[]).filter(r=>finite(r.median)&&Number(r.median)>0&&finite(r.p10)&&finite(r.p90)).map(r=>({...r,low:Number(r.p10)/Number(r.median)*100,high:Number(r.p90)/Number(r.median)*100}));}
function completeness(q){return Object.entries({drug_name:'Tên thuốc',ingredient:'Hoạt chất',strength:'Hàm lượng',dosage_form:'Dạng bào chế',manufacturer:'Nhà sản xuất',country:'Quốc gia',unit:'Đơn vị giá'}).map(([key,name])=>({key,name,value:Math.max(0,n(q?.[key])),missing:Math.max(0,n(q?.total)-n(q?.[key]))})).sort((a,b)=>b.missing-a.missing);}
const exports={groupOther,monthIndex,recent,spreads,completeness};
if(typeof module!=='undefined'&&module.exports)module.exports=exports;
if(typeof window==='undefined')return;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(v,d=0)=>finite(v)?Number(v).toLocaleString('vi-VN',{maximumFractionDigits:d}):'—';
const pct=(a,b)=>n(b)>0?num(n(a)/n(b)*100,1)+'%':'—';
const C=window.PharmaCharts;
const state={range:'24',mode:'count',limit:6,share:false,manufacturer:'products'};
let active=null;
const tip=(a,b)=>'tabindex="0" data-tip="'+esc(a)+'" data-value="'+esc(b)+'"';
const note=t=>'<p class="depth-reading">'+esc(t)+'</p>';
const grid=(a,b)=>'<div class="depth-grid">'+a+b+'</div>';
const panel=(id,title,sub,body,read='')=>'<section class="panel depth-panel" id="chart-'+id+'"><div class="panel-head"><div><h2>'+esc(title)+'</h2><p>'+esc(sub)+'</p></div></div>'+body+(read?note(read):'')+'</section>';
const table=(headers,rows)=>'<div class="table-scroll"><table><thead><tr>'+headers.map(t=>'<th scope="col">'+esc(t)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(t=>'<td>'+esc(t)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
const source=(headers,rows,scope)=>'<details class="depth-source"><summary>Số liệu và cách tính</summary><p>'+esc(scope)+'</p>'+table(headers,rows)+'</details>';
const controls=(key,items,value)=>'<div class="depth-controls" role="group" aria-label="'+esc(key)+'">'+items.map(([v,l])=>'<button data-depth-key="'+key+'" data-depth-value="'+v+'" aria-pressed="'+(String(value)===String(v))+'">'+esc(l)+'</button>').join('')+'</div>';
const step=(number,title,description)=>'<div class="depth-step"><span>'+number+'</span><div><h3>'+esc(title)+'</h3><p>'+esc(description)+'</p></div></div>';
function findings(items){return '<div class="depth-findings">'+items.map(([k,v,t])=>'<article><span>'+esc(k)+'</span><strong>'+esc(v)+'</strong><p>'+esc(t)+'</p></article>').join('')+'</div>';}
function ranking(rows,{unit='sản phẩm',total=null,filter=null,limit=state.limit,share=state.share,ordered=false}={}){
 const input=(rows||[]).map(r=>({...r,value:n(r.value)}));const a=(ordered?input:input.sort((a,b)=>b.value-a.value)).slice(0,limit==='all'?50:Number(limit));
 if(!a.length)return note('Không có nhóm để vẽ trong phạm vi đang chọn.');
 share=share&&n(total)>0;
 const max=share?100:Math.max(1,...a.map(r=>r.value));
 return '<div class="depth-axis"><span>'+esc(share?'Tỷ lệ trên mẫu số đã ghi':'Số '+unit)+'</span><span>0 → '+num(max)+(share?'%':'')+'</span></div>'+a.map((r,i)=>{const v=share?r.value/n(total)*100:r.value;return '<div class="depth-rank"><span class="depth-order">'+(i+1)+'</span>'+(filter&&!r.other?'<button class="depth-name" data-key="'+filter+'" data-filter="'+esc(r.name)+'">'+esc(r.name)+'</button>':'<span class="depth-name">'+esc(r.name)+'</span>')+'<div class="depth-bar-track" '+tip(r.name,num(r.value)+' '+unit+(n(total)?' · '+pct(r.value,total):''))+'><i style="width:'+Math.min(100,Math.max(0,v/max*100))+'%;'+(r.other?'background:var(--chart-other)':'')+'"></i></div><strong>'+num(r.value)+(n(total)?'<small>'+pct(r.value,total)+'</small>':'')+'</strong></div>';}).join('')+source(['Nhóm',unit,'Tỷ lệ'],a.map(r=>[r.name,num(r.value),total===null?'Không áp dụng':pct(r.value,total)]),'Thang bắt đầu từ 0. '+(total===null?'Tập xếp hạng, không phải toàn bộ tổng thể.':'Mẫu số: '+num(total)+' '+unit+'.'));
}
function mix(rows,total){
 const a=groupOther(rows,6),sum=a.reduce((s,r)=>s+r.value,0);if(!sum)return note('Không có dữ liệu để tính cơ cấu.');
 return '<div class="depth-stack" role="img" aria-label="Cơ cấu cộng thành 100%">'+a.map((r,i)=>'<div style="width:'+r.value/sum*100+'%;background:'+(r.other?'var(--chart-other)':C.color(r.name,i))+'" '+tip(r.name,num(r.value)+' / '+num(total??sum)+' · '+pct(r.value,total??sum))+'></div>').join('')+'</div><div class="depth-legend">'+a.map((r,i)=>'<span><i style="background:'+(r.other?'var(--chart-other)':C.color(r.name,i))+'"></i>'+esc(r.name)+' <b>'+pct(r.value,total??sum)+'</b></span>').join('')+'</div>'+source(['Nhóm','Số dòng','Tỷ lệ'],a.map(r=>[r.name,num(r.value),pct(r.value,total??sum)]),'Nhóm loại trừ nhau; nhóm khác là tổng các nhóm nhỏ. Tổng '+num(sum)+' trên mẫu số '+num(total??sum)+'.');
}
function timeChart(d){
 const mode=state.mode,a=recent(d.timeline,state.range).filter(r=>finite(mode==='median'?r.median:r.value));
 const buttons=controls('range',[['6','6 tháng'],['12','12 tháng'],['24','24 tháng'],['all','Toàn bộ']],state.range)+controls('mode',[['count','Số quan sát'],['median','Trung vị giá']],mode);
 if(!a.length)return buttons+note('Không có quan sát có ngày trong khoảng này.');
 const get=r=>n(mode==='median'?r.median:r.value),max=Math.max(1,...a.map(get)),lo=monthIndex(a[0].name),hi=monthIndex(a.at(-1).name),span=Math.max(1,hi-lo);
 const left=86,right=850,top=25,bottom=247,x=r=>lo===hi?(left+right)/2:left+(monthIndex(r.name)-lo)/span*(right-left),y=v=>bottom-v/max*(bottom-top);
 let marks='';for(let t=0;t<=4;t++){const v=max*t/4,yy=y(v);marks+='<line x1="'+left+'" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" class="depth-gridline"/><text x="'+(left-12)+'" y="'+(yy+5)+'" text-anchor="end">'+esc(C.compact(v))+'</text>';}
 const width=Math.max(1,Math.min(28,(right-left)/(span+1)*.65));
 a.forEach((r,i)=>{const xx=x(r),yy=y(get(r)),text=num(get(r))+(mode==='median'?' ₫':' quan sát')+' · '+num(r.value)+' quan sát tháng';if(mode==='count')marks+='<rect x="'+(xx-width/2)+'" y="'+yy+'" width="'+width+'" height="'+(bottom-yy)+'" class="depth-mark" '+tip(r.name,text)+'/>';else{if(i&&monthIndex(r.name)-monthIndex(a[i-1].name)===1)marks+='<line x1="'+x(a[i-1])+'" x2="'+xx+'" y1="'+y(get(a[i-1]))+'" y2="'+yy+'" class="depth-line"/>';marks+='<circle cx="'+xx+'" cy="'+yy+'" r="4" class="depth-dot" '+tip(r.name,text)+'/>';}});
 const indexes=[0,Math.floor((a.length-1)/2),a.length-1].filter((v,i,b)=>b.indexOf(v)===i);indexes.forEach((i,j)=>{const r=a[i];marks+='<text x="'+x(r)+'" y="278" text-anchor="'+(j===0?'start':j===indexes.length-1?'end':'middle')+'">'+esc(r.name)+'</text>';});
 return buttons+'<div class="depth-axis"><span>'+esc(mode==='median'?'Trung vị · VND / đơn vị nguồn':'Số quan sát giá VND')+'</span><span>'+a[0].name+' → '+a.at(-1).name+'</span></div><div class="depth-svg-scroll"><svg viewBox="0 0 920 300" class="depth-svg" role="img" aria-label="'+esc(mode==='median'?'Trung vị giá theo tháng':'Số quan sát theo tháng')+'">'+marks+'</svg></div>'+source(['Tháng','Quan sát','Trung vị (VND)'],a.map(r=>[r.name,num(r.value),num(r.median)]),'Ngày từ declaration_date. Khoảng trống đúng thời gian thực; chỉ nối tháng liên tiếp. Tháng gần nhất có thể chưa kết thúc.');
}
function priceBands(d){
 const labels=['Dưới 1.000','1.000–<5.000','5.000–<10.000','10.000–<50.000','50.000–<100.000','Từ 100.000'],map=new Map((d.bins||[]).map(r=>[Number(r.bucket),n(r.value)]));
 return ranking(labels.map((name,i)=>({name:name+' ₫',value:map.get(i)||0})),{unit:'quan sát',total:d.summary.priced,limit:6,share:false,ordered:true});
}
function relativeRanges(rows){
 const a=spreads(rows).slice(0,8);if(!a.length)return note('Không có nhóm so sánh với trung vị dương và đủ phân vị.');
 const max=Math.max(100,...a.map(r=>r.high)),x=v=>Math.min(100,v/max*100);
 return '<div class="depth-axis"><span>Giá tương đối · trung vị từng nhóm = 100</span><span>0 → '+num(max)+'</span></div>'+a.map((r,i)=>'<div class="depth-range-row"><div><b>Nhóm '+(i+1)+'</b><span>'+esc(r.ingredient+' · '+r.strength)+'</span><small>'+esc(r.dosage_form+' / '+r.unit)+' · '+num(r.products)+' sản phẩm</small></div><div class="depth-range-track" '+tip(r.ingredient,'P10 '+num(r.p10)+' · Trung vị '+num(r.median)+' · P90 '+num(r.p90)+' ₫')+'><em style="left:'+x(100)+'%"></em><i style="left:'+x(r.low)+'%;width:'+(x(r.high)-x(r.low))+'%"></i><b style="left:'+x(100)+'%"></b></div><strong>'+num(r.low)+'–'+num(r.high)+'</strong></div>').join('')+note('Đoạn ngang = P10–P90; chấm = trung vị 100; vạch chung = 100. Chỉ so độ phân tán tương đối. Tối đa 8 nhóm có nhiều quan sát nhất; phân vị tính trên quan sát, không cân đều sản phẩm.');
}
function makerScatter(rows){
 const a=(rows||[]).filter(r=>finite(r.ingredients)&&finite(r.value));if(!a.length)return note('Không có nhà sản xuất đủ dữ liệu để vẽ.');
 const maxX=Math.max(1,...a.map(r=>n(r.ingredients))),maxY=Math.max(1,...a.map(r=>n(r.value))),left=80,right=775,top=35,bottom=295;
 let marks='';for(let t=0;t<=4;t++){const xx=left+(right-left)*t/4,yy=bottom-(bottom-top)*t/4;marks+='<line x1="'+left+'" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" class="depth-gridline"/><text x="65" y="'+(yy+5)+'" text-anchor="end">'+num(maxY*t/4)+'</text><text x="'+xx+'" y="322" text-anchor="middle">'+num(maxX*t/4)+'</text>';}
 const points=a.map(r=>({x:left+n(r.ingredients)/maxX*(right-left),y:bottom-n(r.value)/maxY*(bottom-top)})),placed=[];
 a.forEach((r,i)=>{const {x,y}=points[i];const offsets=[[12,-14],[14,19],[-28,-12],[-30,19],[25,-3],[-39,-3],[12,-28]];
 const [dx,dy]=offsets.find(([dx,dy])=>{const px=x+dx,py=y+dy;return !placed.some(p=>Math.abs(p.x-px)<23&&Math.abs(p.y-py)<17)&&!points.some((p,j)=>j!==i&&Math.abs(p.x-(px+7))<16&&Math.abs(p.y-(py-5))<14);})||offsets.at(-1);
 placed.push({x:x+dx,y:y+dy});
 marks+='<circle cx="'+x+'" cy="'+y+'" r="6" class="depth-dot" '+tip(r.name,num(r.ingredients)+' hoạt chất · '+num(r.value)+' sản phẩm')+'/><text x="'+(x+dx)+'" y="'+(y+dy)+'" class="depth-point-label">'+(i+1)+'</text>';});
 return '<div class="depth-axis"><span>Trục dọc: số sản phẩm</span><span>Mỗi chấm: một nhà sản xuất</span></div><div class="depth-svg-scroll"><svg viewBox="0 0 850 365" class="depth-svg" role="img" aria-label="Số hoạt chất và sản phẩm trong top nhà sản xuất">'+marks+'<text x="430" y="355" text-anchor="middle">Trục ngang: số tên hoạt chất phân biệt</text></svg></div>'+source(['Chấm','Nhà sản xuất','Sản phẩm','Hoạt chất'],a.map((r,i)=>[i+1,r.name,num(r.value),num(r.ingredients)]),'Chỉ top '+a.length+' nhà sản xuất theo số sản phẩm. Không đại diện toàn bộ thị trường, không kết luận nhân quả.');
}
function qualityBars(q){
 if(!n(q?.total))return note('Không có sản phẩm trong bộ lọc.');
 return '<div class="depth-axis"><span>Tỷ lệ có / thiếu thông tin</span><span>Mẫu số '+num(q.total)+' sản phẩm</span></div>'+completeness(q).map(r=>'<div class="depth-quality"><span>'+r.name+'</span><div class="depth-quality-track" '+tip(r.name,num(r.value)+' có · '+num(r.missing)+' thiếu')+'><i style="width:'+r.value/n(q.total)*100+'%"></i><b style="width:'+r.missing/n(q.total)*100+'%"></b></div><strong>'+num(r.missing)+'<small>thiếu · '+pct(r.missing,q.total)+'</small></strong></div>').join('')+'<div class="depth-key"><span><i></i>Có thông tin</span><span><i class="missing"></i>Thiếu thông tin</span></div>'+source(['Trường','Có','Thiếu','Tỷ lệ thiếu'],completeness(q).map(r=>[r.name,num(r.value),num(r.missing),pct(r.missing,q.total)]),'Sản phẩm phân biệt; có = khác NULL/rỗng theo API. Một sản phẩm có thể thiếu nhiều trường; không cộng các hàng thành số sản phẩm lỗi.');
}
function flagBars(m){return [['Chấp nhận phục vụ',m.accepted],['Cần rà soát',m.review],['Khóa SCD hợp lệ',m.valid_fk]].map(([name,v])=>'<div class="depth-flag"><div><span>'+name+'</span><strong>'+num(v)+' · '+pct(v,m.total)+'</strong></div><div '+tip(name,num(v)+' / '+num(m.total))+'><i style="width:'+(n(m.total)?n(v)/n(m.total)*100:0)+'%"></i></div></div>').join('');}
function rankControls(){return controls('limit',[[6,'6 nhóm'],[10,'10 nhóm'],['all','Tối đa 50']],state.limit)+controls('share',[['false','Số lượng'],['true','Tỷ lệ %']],String(state.share));}
function nextActions(rows){return '<div class="depth-next">'+rows.map(([view,title,sub])=>'<button data-view="'+view+'"><b>'+esc(title)+' ↗</b><span>'+esc(sub)+'</span></button>').join('')+'</div>';}

function overview(d){
 const s=d.summary,top=d.countries?.[0],lead=d.ingredients?.[0],q=completeness(d.quality)[0];
 return findings([['NGUỒN CUNG DẪN ĐẦU',top?.name||'—',num(top?.value)+' / '+num(s.products)+' sản phẩm · '+pct(top?.value,s.products)],['ĐỘ PHỦ GIÁ',num(s.priced)+' quan sát','Số lần ghi nhận giá khác số sản phẩm.'],['CẦN ĐỐI CHIẾU',q?.name||'—',num(q?.missing)+' sản phẩm thiếu; ảnh hưởng phân nhóm và so sánh.']])+
 step('01','Đọc quy mô và nhịp ghi nhận','Cột thể hiện số giá đã thu thập theo tháng. Nhiều quan sát hơn chưa có nghĩa giá hoặc nhu cầu tăng.')+
 panel('overview-time','Nhịp ghi nhận dữ liệu giá','Ngày kê khai thực tế · bộ lọc hiện tại',timeChart(d),'Trung vị tháng mô tả cơ cấu quan sát. Task Dự báo đọc biến động theo lịch sử của cùng nhóm thuốc.')+
 step('02','Đọc cơ cấu nguồn cung','Đếm sản phẩm DAV phân biệt. Giữ nhóm chưa xác định và nhãn quốc gia theo nguồn.')+
 grid(panel('overview-country','Cơ cấu nhãn quốc gia','Top 5 nhãn và phần còn lại · sản phẩm',mix(d.countries,s.products),'Một quốc gia có thể có nhiều cách ghi; cần bảng quy đổi trước khi tổng hợp quốc gia chính thức.'),
 panel('overview-ingredient','Hoạt chất nổi bật trong danh mục','Top 8 theo số sản phẩm · bấm tên để lọc',ranking(d.ingredients,{total:s.products,filter:'ingredient',limit:8}),lead?lead.name+' có '+num(lead.makers)+' nhà sản xuất. Tên hoạt chất giữ theo văn bản nguồn.':''))+
 step('03','Chọn câu hỏi cần đi sâu','Giá → nhóm tương đồng. Nguồn cung → nhà sản xuất. Độ tin cậy → trường thiếu và bằng chứng mapping.')+
 nextActions([['pricing','Đọc chênh lệch giá','Phân vị trong nhóm cùng cấu hình'],['competition','Đọc cấu trúc nguồn cung','Danh mục rộng hay tập trung'],['quality','Kiểm tra độ tin cậy','Trường thiếu và liên kết cần rà soát']]);
}
function pricing(d){
 const s=d.summary,range=n(s.p10)>0?n(s.p90)/n(s.p10):null;
 return findings([['VỊ TRÍ GIỮA',num(s.median)+' ₫','Trung vị trên '+num(s.priced)+' quan sát VND; cần giữ ngữ cảnh đơn vị.'],['KHOẢNG P10–P90',num(s.p10)+' → '+num(s.p90)+' ₫','80% vị trí phân phối; không phải khoảng tin cậy.'],['ĐỘ RỘNG TỔNG HỢP',range===null?'—':num(range,1)+' lần','P90/P10 đang gộp cấu hình; không dùng xếp thuốc đắt/rẻ.']])+
 step('01','Nhìn phân bố trước khi đọc giá đại diện','Đọc tần suất theo khoảng cùng trung vị. Không so trực tiếp viên, hộp, ống hoặc các loại giá khác nhau.')+
 panel('pricing-bands','Số quan sát trong các khoảng giá','Tần suất theo khoảng VND · bề rộng khoảng không đều',priceBands(d),'Thanh ngang thể hiện số quan sát trong nhóm, không phải mật độ histogram. Lọc đơn vị và loại giá trước khi diễn giải.')+
 step('02','Đưa các nhóm về cùng mốc trung vị','Giữ chung hoạt chất, hàm lượng, dạng, đơn vị và loại giá. Mốc 100 giúp so độ rộng tương đối.')+
 panel('pricing-ranges','Khoảng giá tương đối trong nhóm thuốc tương đồng','P10–P90 và trung vị chuẩn hóa = 100',relativeRanges(d.comparable),'Chưa chuẩn hóa đường dùng, quy cách và thời điểm. Đối chiếu hồ sơ trước khi dùng để mua sắm.')+
 panel('pricing-comparable','Đối chiếu mức tiền và cỡ mẫu từng nhóm','Tối đa 15 nhóm nhiều quan sát nhất · ít nhất 2 sản phẩm',table(['Hoạt chất / Hàm lượng','Dạng · Đơn vị · Loại giá','Sản phẩm / Quan sát','Nhà SX','P10 (₫)','Trung vị (₫)','P90 (₫)'],(d.comparable||[]).map(r=>[r.ingredient+' / '+r.strength,r.dosage_form+' · '+r.unit+' · '+(r.price_type==='EXPECTED_WHOLESALE_PRICE_VAT'?'Bán buôn dự kiến VAT':r.price_type),num(r.products)+' / '+num(r.observations),num(r.makers),num(r.p10),num(r.median),num(r.p90)])))+
 step('03','Kiểm tra thời gian và độ phủ','Chuyển số quan sát / trung vị để kiểm tra lượng dữ liệu thu thập trong cùng khoảng thời gian.')+
 panel('pricing-time','Giá trung vị và số quan sát theo tháng','Cùng phạm vi lọc; không nội suy tháng thiếu',timeChart(d),'Trung vị có thể đổi khi cơ cấu thuốc đổi. Đây chưa phải chỉ số giá của một rổ thuốc cố định.');
}
function competition(d){
 const makers=d.manufacturers||[],s=d.summary,top=makers[0],sum=makers.reduce((v,r)=>v+n(r.value),0),field=state.manufacturer==='ingredients'?'ingredients':'value';
 return findings([['NHÀ SẢN XUẤT DẪN ĐẦU',num(top?.value)+' sản phẩm',top?.name||'Chưa có dữ liệu'],['TOP '+makers.length+' TRONG DANH MỤC',pct(sum,s.products),num(sum)+' / '+num(s.products)+' sản phẩm theo tên nhà sản xuất nguồn.'],['CÁCH ĐỌC CẠNH TRANH','Độ phủ danh mục','Chưa có doanh số để tính thị phần doanh thu.']])+
 step('01','Phân biệt danh mục lớn với danh mục rộng','Sản phẩm đo quy mô; hoạt chất đo độ rộng. Chấm cao và lệch phải thể hiện cả hai trong tập đang hiển thị.')+
 panel('competition-scatter','Quy mô sản phẩm và độ rộng hoạt chất','Top '+makers.length+' nhà sản xuất theo số sản phẩm',makerScatter(makers),'Chấm cùng kích thước; số bên chấm đối chiếu với bảng nguồn. Không tính tương quan từ tập top đã chọn để suy toàn thị trường.')+
 grid(panel('competition-rank','Xếp hạng danh mục nhà sản xuất','Đổi thước đo trong cùng tập top '+makers.length,controls('manufacturer',[['products','Sản phẩm'],['ingredients','Hoạt chất']],state.manufacturer)+ranking(makers.map(r=>({name:r.name,value:r[field]})),{unit:field==='value'?'sản phẩm':'hoạt chất',total:field==='value'?s.products:null,limit:10}),'Đổi thước đo sắp xếp lại tập top theo sản phẩm; không tạo top toàn thị trường theo hoạt chất.'),
 panel('competition-coverage','Nhà sản xuất theo hoạt chất nổi bật','Hoạt chất được chọn theo số sản phẩm',ranking((d.ingredients||[]).map(r=>({name:r.name,value:r.makers})),{unit:'nhà sản xuất',filter:'ingredient',limit:8,share:false}),'Một nhà sản xuất tham gia nhiều hoạt chất; không cộng các hàng thành tổng nhà sản xuất.'))+
 panel('competition-detail','Độ tập trung trong danh mục','Tỷ số sản phẩm trên tên hoạt chất của cùng nhà sản xuất',table(['Nhà sản xuất','Sản phẩm','Hoạt chất','Sản phẩm / hoạt chất'],makers.map(r=>[r.name,num(r.value),num(r.ingredients),n(r.ingredients)?num(n(r.value)/n(r.ingredients),2):'—'])),'Tỷ số cao gợi ý nhiều sản phẩm trên một nhóm tên hoạt chất, chưa chứng minh chất lượng hoặc cạnh tranh giá.');
}
function portfolio(d){
 const forms=d.forms||[],countries=d.countries||[],s=d.summary,lead=forms[0],total=forms.reduce((a,r)=>a+n(r.value),0);
 return findings([['DẠNG PHỔ BIẾN',lead?.name||'—',num(lead?.value)+' sản phẩm · '+pct(lead?.value,total)],['NHÃN QUỐC GIA',num(countries.length),'Có thể nhiều cách ghi cho cùng một quốc gia.'],['TÊN HOẠT CHẤT',num(s.ingredients),'Tên phân biệt; chưa gộp mọi cách viết tương đương.']])+
 step('01','Danh mục tập trung vào dạng bào chế nào?','Cơ cấu trả lời tỷ trọng; xếp hạng giúp đọc chính xác nhóm lớn và thông tin còn thiếu.')+
 panel('portfolio-mix','Cơ cấu dạng bào chế','Top 5 dạng và phần còn lại · sản phẩm trong bộ lọc',mix(forms,s.products),'Cần nhu cầu, doanh số và cạnh tranh để đánh giá cơ hội kinh doanh.')+
 grid(panel('portfolio-forms','Chi tiết dạng bào chế','Đổi số nhóm và thang số lượng / tỷ lệ',rankControls()+ranking(forms,{total:s.products,limit:state.limit}),'“Chưa xác định” giữ riêng, không gộp để che dữ liệu thiếu.'),
 panel('portfolio-countries','Chi tiết nhãn quốc gia nguồn','Bấm nhãn để lọc dashboard',ranking(countries,{total:s.products,filter:'country',limit:state.limit}),'Không tự gộp India / Ấn Độ hoặc Germany / Đức khi chưa có quy đổi đã kiểm tra.'))+
 panel('portfolio-ingredients','Độ phủ trong từng hoạt chất','Top 8 hoạt chất theo số sản phẩm',table(['Hoạt chất','Sản phẩm','Nhà SX','Sản phẩm / Nhà SX'],(d.ingredients||[]).map(r=>[r.name,num(r.value),num(r.makers),n(r.makers)?num(n(r.value)/n(r.makers),2):'—'])),'Cùng hoạt chất có nhiều hàm lượng, dạng và quy cách. Mở Phân tích giá để so cấu hình tương đồng.')+
 nextActions([['pricing','Đối chiếu giá trong danh mục','Giữ chung cấu hình trước khi so'],['preparation','Chuẩn hóa cách ghi','Tên, quốc gia, hàm lượng và đơn vị']]);
}
const statusLabels={UNMATCHED_REVIEW:'Chưa khớp · cần rà soát',VERIFIED_SCD:'SCD đã xác minh',UNMAPPED:'Chưa liên kết',CANDIDATE_REVIEW:'Ứng viên cần rà soát',INGREDIENT_SET_ONLY:'Chỉ khớp tập hoạt chất',SCD_MATCH_REVIEW_REQUIRED:'SCD cần rà soát',PARTIAL_INGREDIENT_MAPPING:'Khớp một phần hoạt chất',INGREDIENT_STRENGTH_FORM_CONFLICT:'Xung đột cấu hình',NO_SCD_FOR_INGREDIENT_SET:'Chưa có SCD phù hợp',AMBIGUOUS_SCD:'Nhiều SCD ứng viên'};
function quality(d){
 const q=d.quality||{},m=d.mapping||{},worst=completeness(q)[0],statuses=(m.statuses||[]).map(r=>({...r,name:statusLabels[r.name]||r.name}));
 return findings([['ƯU TIÊN BỔ SUNG',worst?.name||'—',num(worst?.missing)+' / '+num(q.total)+' sản phẩm thiếu.'],['MAPPING CHẤP NHẬN',m.unavailable?'—':pct(m.accepted,m.total),num(m.accepted)+' / '+num(m.total)+' dòng toàn bảng.'],['CẦN RÀ SOÁT',num(m.review),'Cờ review độc lập với kiểm tra khóa; không cộng các cờ.']])+
 step('01','Kiểm tra khả năng dùng theo mục đích','Thiếu dạng hoặc hàm lượng ảnh hưởng so giá và mapping. Đủ tên vẫn chưa chứng minh tên đã chuẩn hóa đúng.')+
 panel('quality-fields','Độ đầy đủ theo trường DAV','Bộ lọc sản phẩm hiện tại · xếp theo số thiếu giảm dần',qualityBars(q),'Đơn vị có thể từ quan sát giá hoặc hồ sơ DAV. Phép đo này khác hồ sơ thô của từng bảng trong Report 3.')+
 step('02','Tách trạng thái liên kết khỏi các cờ','Trạng thái loại trừ nhau; accepted / review / khóa hợp lệ là các phép kiểm tra độc lập.')+
 grid(panel('quality-status','Trạng thái DAV ↔ RxNorm','Toàn bảng mapping · độc lập bộ lọc sản phẩm',m.unavailable?note('Chưa đọc được bảng mapping.'):ranking(statuses,{unit:'dòng mapping',total:m.total,limit:10,share:false}),'Giữ riêng xung đột, ứng viên và chưa khớp để xác định cách xử lý.'),
 panel('quality-flags','Các cờ kỹ thuật độc lập','Mỗi tỷ lệ trên '+num(m.total)+' dòng mapping',m.unavailable?note('Nguồn mapping chưa sẵn sàng.'):flagBars(m),'Khóa SCD hợp lệ là kiểm tra kỹ thuật; chưa chứng minh tương đương điều trị.'))+
 panel('quality-actions','Từ kiểm tra đến việc cần làm','Ưu tiên dựa trên mục đích sử dụng',table(['Phép kiểm tra','Tác động','Cách xử lý'],[['Thiếu hàm lượng / dạng','Không đủ cấu hình so sánh','Đối chiếu nguồn; giữ NULL nếu chưa xác minh'],['Nhiều cách ghi quốc gia','Tách một nhóm thành nhiều nhãn','Bảng quy đổi có nguồn và ngoại lệ'],['Mapping ứng viên / xung đột','Chưa đủ bằng chứng','Đọc bằng chứng từng thành phần'],['Khóa hợp lệ','Biết bản ghi đích tồn tại','Kiểm tra tiếp ngữ nghĩa và cờ chấp nhận']]))+
 nextActions([['reports','Kiểm tra 9 bảng Gold','Hồ sơ cột, thiếu, unique và phân bố'],['preparation','Xem quy tắc làm sạch','Không dựng số trước–sau khi chưa đo']]);
}

function research(view,{full,rx,links,market}={}){
 if(view==='business')return panel('business-readiness','Dữ liệu hiện tại hỗ trợ được quyết định nào?','Phân biệt năng lực đã có, kết luận có điều kiện và dữ liệu cần bổ sung',table(['Câu hỏi','Bằng chứng hiện có','Điều kiện / phần còn thiếu'],[['Có những thuốc và nhà cung cấp nào?','DAV, hoạt chất, nhà sản xuất','Tên nguồn nhiều cách ghi; chưa phải danh mục pháp lý tức thời'],['Các giá có so sánh được không?','Giá, loại giá, đơn vị và cấu hình','Cần quy cách, thời điểm, đường dùng; chưa có giao dịch'],['Thuốc và bệnh liên quan thế nào?','RxNorm, ICD, MEDI và trạng thái nối','Quan hệ không tự thành chỉ định đã xác minh'],['Thị trường bán được bao nhiêu?','Chưa có giao dịch trong nguồn','Cần số lượng, doanh thu, kênh và tồn kho'],['Giá tương lai biến động bao nhiêu?','Baseline, validation và test','Chỉ công bố đạt chuẩn khi vượt quality gate']]),'Task này xác định câu hỏi và điều kiện dùng dữ liệu. Không vẽ doanh thu hoặc thị phần khi chưa có biến đo tương ứng.')+nextActions([['lookup','Đi từ hồ sơ cụ thể','Tên → cấu hình → bằng chứng'],['pricing','Đi từ câu hỏi giá','Phân bố → nhóm tương đồng → thời gian'],['modeling','Đi từ câu hỏi dự báo','Baseline → validation → test']]);
 if(view==='workflow')return panel('workflow-grain','Đơn vị đếm và quan hệ giữa các bảng','Đọc đúng quan hệ một–nhiều, tránh nhân bản khi JOIN',table(['Bảng','Một dòng là gì?','Khóa / quan hệ cần nhớ'],[['dav_product','Một hồ sơ sản phẩm','dav_row_id → nhiều price_record'],['price_record','Một quan sát giá','Nhiều giá có thể cùng một DAV'],['rxnorm_concept','Một khái niệm Gold','Khác dòng thuật ngữ Silver'],['rxnorm_scd / component','Cấu hình / thành phần','Một SCD có nhiều thành phần'],['mapping / evidence','Liên kết / bằng chứng','Một liên kết có nhiều bằng chứng'],['disease / medi_relation','Mã bệnh / quan hệ','Kiểm tra code_system trước khi nối']]),'Số dòng các bảng không phải các chặng của cùng đoàn hệ; không dùng funnel để suy tỷ lệ mất dữ liệu.')+
 panel('workflow-trace','Truy vết một hồ sơ từ kết quả phân tích','Ví dụ thật từ trang bản ghi Gold hiện tại',full?.records?.length?table(['Thuộc tính','Giá trị nguồn'],[['Tên thuốc',full.records[0].drug_name],['Hoạt chất',full.records[0].ingredient],['Số đăng ký',full.records[0].registration_no],['Đơn vị giá',full.records[0].unit],['Giá',num(full.records[0].price_vnd)+' ₫'],['Ngày',full.records[0].snapshot_date||'Chưa có ngày']]):note('Chưa tải được hồ sơ từ nguồn; không tạo ví dụ thay thế.'),'Ví dụ truy nguồn; không khẳng định đại diện toàn bộ dữ liệu.');
 if(view==='eda'&&full)return panel('eda-screening','Sàng lọc độ đầy đủ trước khi đọc phân bố','DAV toàn bộ nguồn · không đo độ đúng ngữ nghĩa',qualityBars(full.quality),'Nhóm nhỏ hoặc tên dài là dấu hiệu điều tra. Chỉ kiểm định khi có câu hỏi, biến đo và giả định phù hợp.')+
 panel('eda-questions','Mỗi nguồn cần kiểm tra cấu trúc khác nhau','Giữ đơn vị đếm ổn định trong từng câu hỏi',table(['Nguồn','Phân bố nên xem','Đối chiếu cần làm'],[['DAV / giá','Dạng, quốc gia, khoảng giá, thời gian','Giá cùng cấu hình; không thiếu đơn vị'],['RxNorm','Loại tên, nguồn tên, số tên / RxCUI','Đồng nghĩa hợp lệ khác dòng trùng hoàn toàn'],['ICD-10','Chương bệnh, độ đầy đủ tên','Số mã không phản ánh số người mắc'],['MEDI','Hệ mã, trạng thái nối','Quan hệ nguồn khác liên kết xác minh']]))+nextActions([['reports','Mở EDA cả 9 bảng Gold','Xem toàn bộ cột và phân bố từng bảng']]);
 if(view==='preparation'&&full){
 const actions={dosage_form:'Mất điều kiện so cấu hình; đối chiếu hồ sơ nguồn',strength:'Không so cùng hàm lượng; kiểm tra đơn vị / nồng độ',ingredient:'Khó nhóm và mapping; kiểm tra nhiều thành phần',country:'Sai cơ cấu; chưa tự đoán quốc gia',manufacturer:'Đếm nguồn cung chưa đủ',unit:'Không so mức tiền; kiểm tra đơn vị kê khai',drug_name:'Khó tìm và truy hồ sơ'};
 return panel('preparation-priority','Ưu tiên làm sạch theo tác động sử dụng','Đếm độc lập từng trường trên sản phẩm DAV toàn bộ nguồn',table(['Trường','Thiếu','Tỷ lệ','Ảnh hưởng / đối chiếu'],completeness(full.quality).map(r=>[r.name,num(r.missing),pct(r.missing,full.quality.total),actions[r.key]])),'Không cộng số thiếu; không tự điền thông tin y dược bằng suy đoán từ tên.')+
 panel('preparation-contract','Một lần làm sạch cần lưu bằng chứng gì?','Tiêu chí kiểm tra; chưa phải số dòng đã sửa',table(['Nhóm','Quy tắc','Bằng chứng cần lưu'],[['Nguồn','Không ghi đè giá trị gốc','ID, giá trị, timestamp, phiên bản'],['Văn bản','Unicode, khoảng trắng, hoa/thường','Giá trị chuẩn hóa và quy tắc'],['Mã / khóa','Cú pháp và khóa đích','Cờ hợp lệ và lý do lỗi riêng'],['Trùng','Định nghĩa khóa theo grain','Nhóm trùng và quyết định giữ / gộp'],['Mapping','Đủ thành phần, hàm lượng, dạng','Ứng viên, bằng chứng, accepted / review'],['Trước–sau','Có snapshot đối chiếu','Đầu vào, đầu ra, loại, sửa và ngoại lệ']]));
 }
 if(view==='modeling'&&market)return horizonComparison(market);
 return '';
}
function horizonComparison(market){
 const rows=[3,6,12].map(h=>({h,item:market.horizons?.[String(h)]||{}}));
 return panel('modeling-horizons','So kết quả giữa 3, 6 và 12 tháng','Ba bài toán riêng theo kỳ hạn',table(['Kỳ hạn','Trạng thái','Mô hình chọn','Validation baseline','Test log-MAE','Cải thiện test','Mẫu test'],rows.map(({h,item:i})=>[h+' tháng',i.status==='approved'?'Đạt kiểm định':'Chưa đạt',i.selected_model||'Chưa chọn',num(i.validation_baseline_log_mae,6),num(i.test_log_mae,6),finite(i.test_gain_fraction)?num(Number(i.test_gain_fraction)*100,3)+'%':'Chưa đánh giá',num(i.n_test)])),'Không đổi thiếu thành 0. Log-MAE không có đơn vị VND. Kỳ hạn có độ phủ khác nhau; không xếp độ chính xác chỉ từ một cột sai số.')+
 panel('modeling-readout','Bằng chứng cần đọc trước khi dùng dự báo','P10–P90 lịch sử không phải khoảng tin cậy dự báo',table(['Câu hỏi','Bằng chứng','Nếu chưa đủ'],[['Hơn giữ nguyên giá không?','Validation giảm log-MAE ít nhất 1%','Không chọn để công bố đạt chuẩn'],['Tổng quát được không?','Test cuối độc lập, cải thiện và cỡ mẫu','Ghi chưa đánh giá / chưa đạt'],['Độ phủ đủ rộng không?','Số mẫu, số đăng ký và tập tham chiếu','Giới hạn kết luận'],['Chắc chắn đến đâu?','Bootstrap test nếu có','Không vẽ dải sai số tự tạo'],['Tái lập được không?','Phiên bản, nguồn và mốc thời gian','Giữ kết quả theo snapshot']]));
}
function lookupGuide(){return '<details class="depth-guide"><summary>Cách đọc kết quả: hồ sơ → cấu hình → giá → bằng chứng</summary>'+table(['Bước','Cần đọc','Để phân biệt'],[['1 · Hồ sơ','Tên, số đăng ký, nhà sản xuất','Cùng tên chưa chắc cùng sản phẩm'],['2 · Cấu hình','Hoạt chất, hàm lượng, dạng, quy cách','Khác đơn vị / nồng độ không so trực tiếp'],['3 · Giá','Loại giá, đơn vị, ngày kê khai','Giá nguồn khác giá giao dịch'],['4 · Liên kết','SCD, accepted / review, bằng chứng','Ứng viên khác liên kết chấp nhận']])+'</details>';}

function forecastIntervals(report){
 const a=[3,6,12].map(h=>({h,...report.horizons?.[String(h)]})).filter(r=>finite(r.p10_pct)&&finite(r.p90_pct)&&finite(r.historical_change_pct));
 if(!a.length)return note('Chưa có phân vị lịch sử để so giữa các kỳ hạn.');
 const low=Math.min(0,...a.map(r=>Number(r.p10_pct))),high=Math.max(0,...a.map(r=>Number(r.p90_pct))),span=Math.max(.001,high-low),x=v=>(Number(v)-low)/span*100;
 return panel('forecast-history','Độ phân tán biến động lịch sử theo kỳ hạn','P10–P90 và trung vị · % thay đổi · cùng thang đo',
 '<div class="depth-axis"><span>'+num(low,1)+'%</span><span>Vạch dọc = 0% · '+num(high,1)+'%</span></div>'+a.map(r=>'<div class="depth-range-row"><div><b>'+r.h+' THÁNG</b><span>'+num(r.n_products)+' mã thuốc</span><small>'+num(r.n_pairs)+' cặp giá</small></div><div class="depth-range-track" '+tip(r.h+' tháng','P10 '+num(r.p10_pct,2)+'% · Trung vị '+num(r.historical_change_pct,2)+'% · P90 '+num(r.p90_pct,2)+'%')+'><em style="left:'+x(0)+'%"></em><i style="left:'+x(r.p10_pct)+'%;width:'+(x(r.p90_pct)-x(r.p10_pct))+'%"></i><b style="left:'+x(r.historical_change_pct)+'%"></b></div><strong>'+num(r.historical_change_pct,2)+'%</strong></div>').join('')+source(['Kỳ hạn','Mã thuốc','Cặp giá','P10 (%)','Trung vị (%)','P90 (%)'],a.map(r=>[r.h+' tháng',num(r.n_products),num(r.n_pairs),num(r.p10_pct,2),num(r.historical_change_pct,2),num(r.p90_pct,2)]),'Nguồn /api/market-forecast · mỗi kỳ hạn có tập thuốc và cặp giá riêng.'),
 'Đoạn ngang thể hiện phân bố thay đổi đã quan sát; chấm là trung vị. Đây không phải khoảng dự báo hoặc khoảng tin cậy. Không so cỡ mẫu các kỳ như cùng một đoàn hệ.');
}
document.addEventListener('pharmabiz:market-report',event=>{const host=document.getElementById('market-history-ranges');if(host&&event.detail?.kind==='dav-market-price-trend')host.innerHTML=forecastIntervals(event.detail);});

function render(view,d){active={view,d};const fn={overview,pricing,competition,portfolio,quality}[view];return fn?fn(d):'';}
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-depth-key]');if(!button||!active)return;
 const key=button.dataset.depthKey,val=button.dataset.depthValue;if(!Object.hasOwn(state,key))return;
 state[key]=key==='share'?val==='true':key==='limit'&&val!=='all'?Number(val):val;
 const root=button.closest('.depth-panel'),id=root?.id,position=root?.getBoundingClientRect().top;
 const host=document.getElementById('depth-analytical');if(host){
 host.innerHTML=render(active.view,active.d);
 const target=id?document.getElementById(id):null;if(target&&Number.isFinite(position))window.scrollBy({top:target.getBoundingClientRect().top-position,behavior:'instant'});
 document.querySelector('[data-depth-key="'+key+'"][data-depth-value="'+val+'"]')?.focus({preventScroll:true});
 }
});
window.PharmaDepth=Object.freeze({render,research,lookupGuide,...exports});
})();
