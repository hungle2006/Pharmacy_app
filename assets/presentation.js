(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=v=>v===null||v===undefined?'—':Number(v).toLocaleString('vi-VN',{maximumFractionDigits:0});
  const money=v=>v===null||v===undefined?'—':fmt(v)+' ₫';
  const short=v=>window.PharmaCharts.compact(v);
  const displayName=v=>({'EXPECTED_WHOLESALE_PRICE_VAT':'Giá bán buôn dự kiến (VAT)','VERIFIED_SCD':'Đã xác minh SCD','UNMAPPED':'Chưa liên kết','INGREDIENT_SET_ONLY':'Khớp tập hoạt chất','SCD_MATCH_REVIEW_REQUIRED':'SCD cần kiểm tra','PARTIAL_INGREDIENT_MAPPING':'Khớp một phần hoạt chất','INGREDIENT_STRENGTH_FORM_CONFLICT':'Xung đột cấu hình','NO_SCD_FOR_INGREDIENT_SET':'Chưa có SCD phù hợp','AMBIGUOUS_SCD':'Nhiều SCD ứng viên'}[v]||v);
  const C=window.PharmaCharts;
  const views=[
    ['overview','◫','Tổng quan thị trường','THE BIG PICTURE','Góc nhìn toàn cảnh từ dữ liệu dược Việt Nam.'],
    ['lookup','⌕','Tra cứu thuốc','DRUG DISCOVERY','Tìm thuốc DAV, tra cứu hoạt chất, giá và bằng chứng RxNorm trực tiếp từ Neon Gold.'],
    ['market-forecast','↗','Dự báo thị trường thuốc','DAV MARKET OUTLOOK','Biến động giá toàn thị trường theo 3, 6 và 12 tháng; kiểm định và thống kê lịch sử.'],
    ['pricing','▤','Phân tích giá thuốc','PRICING INTELLIGENCE','Phân bố giá, nhóm so sánh và các quan sát theo thời gian.'],
    ['competition','▥','Phân tích cạnh tranh','COMPETITIVE LANDSCAPE','Nhà sản xuất, độ phủ hoạt chất và quy mô danh mục.'],
    ['portfolio','◇','Danh mục sản phẩm','PORTFOLIO ANALYTICS','Khám phá cơ cấu quốc gia, hoạt chất và dạng bào chế.'],
    ['quality','✓','Chất lượng dữ liệu','TRUST THE DATA','Độ đầy đủ, trạng thái mapping và khả năng sử dụng dữ liệu.'],
    ['business','◎','Business Understanding','FROM DATA TO DECISIONS','Câu hỏi kinh doanh, KPI và giá trị của dashboard.'],
    ['workflow','⬡','Data Understanding','CONNECTED DATA','Nguồn dữ liệu, luồng xử lý và kiến trúc phân tích.'],
    ['reports','▧','Report 3 & 4','DATA EXPLORER','Khám phá và trực quan hóa từng bảng: cấu trúc, chất lượng, phân bố và bước xử lý tiếp theo.'],
    ['eda','◷','EDA dữ liệu','EXPLORE THE DATA','Khám phá DAV, RxNorm, ICD-10 và MEDI: nhìn phân bố trước khi kết luận.'],
    ['preparation','⚒','Làm sạch dữ liệu','DATA PREPARATION','Giữ nguồn, chuẩn hóa, kiểm tra thiếu và trùng, theo dõi phần cần rà soát.'],
    ['modeling','⌁','Modeling & Evaluation','MODELS & EVIDENCE','Thuật toán, chia dữ liệu theo thời gian, sai số và quality gate của mô hình đang chạy.']
  ];
  let data=null,inventory=null,page=1,view='overview',controller=null,seq=0,timeout=null,toastTimer,optionsLoaded=false,trendRange='all',trendMode=null;
  const theory=()=>['business','workflow','eda','preparation','modeling','reports'].includes(view);
  const lookupView=()=>view==='lookup';
  const marketForecastView=()=>view==='market-forecast';
  const filters=()=>{const p=new URLSearchParams();for(const [key,id] of [['q','search'],['ingredient','ingredient'],['country','country'],['kind','kind'],['unit','unit']])if($(id).value.trim())p.set(key,$(id).value.trim());p.set('page',page);p.set('options',optionsLoaded?'0':'1');return p;};
  function tip(label,value){return 'data-tip="'+esc(label)+'" data-value="'+esc(value)+'" tabindex="0"';}
  function panel(title,sub,body,tag=''){return '<section class="panel"><div class="panel-head"><div><h2>'+esc(title)+'</h2><p>'+esc(sub)+'</p></div>'+(tag?'<span class="tag">'+esc(tag)+'</span>':'')+'</div>'+body+'</section>';}
  const note=t=>'<p class="chart-note">'+esc(t)+'</p>';
  const empty=t=>'<div class="empty">'+esc(t||'Không có dữ liệu trong phạm vi bộ lọc.')+'</div>';
  function table(headers,rows){return '<div class="table-scroll"><table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map((x,i)=>'<td>'+(i===0?'<strong>'+esc(x)+'</strong>':esc(x))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
  function card(n,title,body){return '<article class="story-card"><div class="eyebrow">'+esc(n)+'</div><h3>'+esc(title)+'</h3><p>'+esc(body)+'</p></article>';}
  function metric(label,value,detail,icon){return '<article class="metric"><div class="metric-top"><span>'+esc(label)+'</span><span class="metric-icon">'+icon+'</span></div><div class="metric-value">'+esc(value)+'</div><div class="metric-note">'+esc(detail)+'</div></article>';}
  function bars(items,key,unit='sản phẩm'){if(!items?.length)return empty();let max=Math.max(...items.map(i=>Number(i.value)),1);return items.map((r,i)=>'<div class="bar-row"><button class="bar-label" title="'+esc(r.name)+'" '+(key?'data-filter="'+esc(r.name)+'" data-key="'+key+'"':'')+'>'+esc(r.name)+'</button><div class="bar-track" '+tip(r.name,fmt(r.value)+' '+unit)+'><div class="bar-fill" style="width:'+Math.max(0,Number(r.value)/max*100)+'%;animation-delay:'+i*.04+'s"></div></div><b>'+fmt(r.value)+'</b></div>').join('');}
  function donut(input,key,label){
    if(!input?.length)return empty();
    const total=input.reduce((sum,row)=>sum+Number(row.value),0);if(!total)return empty();
    const items=input.slice(0,5).map(x=>({...x}));
    if(input.length>5)items.push({name:'Các nhóm khác',value:input.slice(5).reduce((sum,row)=>sum+Number(row.value),0),other:true});
    let accumulated=0;
    const circles=items.map((row,index)=>{
      const share=Number(row.value)/total*100;
      const mark='<circle class="donut-segment" cx="115" cy="115" r="78" fill="none" stroke="'+C.color(row.name,index)+'" stroke-width="30" pathLength="100" stroke-dasharray="'+share+' '+(100-share)+'" stroke-dashoffset="'+(-accumulated)+'" transform="rotate(-90 115 115)" '+tip(row.name,fmt(row.value)+' sản phẩm · '+C.percent(share))+(key&&!row.other?' data-filter="'+esc(row.name)+'" data-key="'+key+'"':'')+'><title>'+esc(row.name)+' '+C.percent(share)+'</title></circle>';
      accumulated+=share;return mark;
    }).join('');
    return '<div class="donut-wrap"><svg viewBox="0 0 230 230" role="img" aria-label="'+esc(label)+'">'+circles+'<text x="115" y="112" text-anchor="middle" font-size="27" font-weight="700">'+short(total)+'</text><text x="115" y="134" text-anchor="middle" font-size="12">sản phẩm</text></svg><div class="donut-legend">'+items.map((row,index)=>'<button '+(key&&!row.other?'data-filter="'+esc(row.name)+'" data-key="'+key+'"':'disabled')+' title="'+esc(row.name)+'"><i class="legend-dot" style="background:'+C.color(row.name,index)+'"></i><span>'+esc(row.name)+'</span><b>'+C.percent(Number(row.value)/total*100)+'</b></button>').join('')+'</div></div>';
  }
  function histogram(){
    const labels=['< 1','1–5','5–10','10–50','50–100','≥ 100'];
    const bins=Array(6).fill(0);(data.bins||[]).forEach(row=>{bins[Number(row.bucket)]=Number(row.value);});
    const peak=Math.max(...bins,1),scale=peak>=1000?1000:1;if(!bins.some(Boolean))return empty('Chưa có giá VND hợp lệ để tạo phân phối.');
    const left=83,right=735,top=32,bottom=255,step=(right-left)/bins.length;
    let marks='';
    for(let tick=0;tick<5;tick++){
      const y=bottom-(bottom-top)*tick/4;
      marks+='<line class="chart-gridline" x1="'+left+'" x2="'+right+'" y1="'+y+'" y2="'+y+'"/><text x="'+(left-12)+'" y="'+(y+4)+'" text-anchor="end">'+C.number(peak*tick/4/scale,scale===1?0:1)+'</text>';
    }
    bins.forEach((value,index)=>{
      const height=value/peak*(bottom-top),x=left+index*step+step*.1,width=step*.8;
      marks+='<rect class="chart-bar" x="'+x+'" y="'+(bottom-height)+'" width="'+width+'" height="'+height+'" rx="2" '+tip(labels[index]+' nghìn VND',fmt(value)+' quan sát')+'><title>'+esc(labels[index])+': '+fmt(value)+'</title></rect><text x="'+(x+width/2)+'" y="278" text-anchor="middle">'+esc(labels[index])+'</text>';
    });
    return '<div class="ui-chart-caption"><span>Số quan sát'+(scale===1000?' (nghìn)':'')+'</span><span>Giá · nghìn VND / đơn vị nguồn</span></div><svg viewBox="0 0 760 310" class="chart-svg" role="img" aria-label="Số quan sát theo nhóm giá VND">'+marks+'</svg>'+note('Các cột là tần suất của nhóm giá có bề rộng khác nhau; không phải mật độ phân phối. Lọc hoạt chất, loại giá và đơn vị để so sánh phù hợp.');
  }
  function trend(field='value'){
    field=trendMode||field;const source=data.timeline||[];
    const month=row=>Number(row.name.slice(0,4))*12+Number(row.name.slice(5,7));
    const end=source.length?month(source.at(-1)):0;
    const rows=source.filter(row=>row[field]!==null&&Number.isFinite(Number(row[field]))&&(trendRange==='all'||month(row)>end-Number(trendRange)));
    if(!rows.length)return trendControls(field)+empty('Chưa có quan sát giá có ngày hợp lệ trong khoảng thời gian này.');
    const peak=Math.max(...rows.map(row=>Number(row[field])),1),scale=peak>=1e6?1e6:peak>=1000?1000:1,left=83,right=730,top=30,bottom=255;
    const first=month(rows[0]),span=Math.max(1,month(rows.at(-1))-first);
    const points=rows.map(row=>[rows.length===1?(left+right)/2:left+(month(row)-first)/span*(right-left),bottom-Number(row[field])/peak*(bottom-top)]);
    let marks='';
    for(let tick=0;tick<5;tick++){
      const y=bottom-(bottom-top)*tick/4;
      marks+='<line class="chart-gridline" x1="'+left+'" x2="'+right+'" y1="'+y+'" y2="'+y+'"/><text x="'+(left-12)+'" y="'+(y+4)+'" text-anchor="end">'+C.number(peak*tick/4/scale,scale===1?0:1)+'</text>';
    }
    let lastLabelX=-Infinity;
    points.forEach((point,index)=>{
      const row=rows[index],value=field==='median'?money(row.median):fmt(row.value)+' quan sát';
      if(index>0&&month(row)-month(rows[index-1])===1)marks+='<line class="chart-line" x1="'+points[index-1][0]+'" y1="'+points[index-1][1]+'" x2="'+point[0]+'" y2="'+point[1]+'"/>';
      marks+='<circle class="chart-point" cx="'+point[0]+'" cy="'+point[1]+'" r="3.5" '+tip(row.name,value)+'><title>'+esc(row.name)+' '+esc(value)+'</title></circle>';
      if(index===0||index===rows.length-1||(point[0]-lastLabelX>=(innerWidth<=760?230:130)&&right-point[0]>=(innerWidth<=760?230:130))){
        lastLabelX=point[0];marks+='<text x="'+point[0]+'" y="282" text-anchor="'+(index===0?'start':index===rows.length-1?'end':'middle')+'">'+esc(row.name)+'</text>';
      }
    });
    return trendControls(field)+'<div class="ui-chart-caption"><span>'+(field==='median'?'Giá trung vị':'Số quan sát')+(scale===1e6?' (triệu)':scale===1000?' (nghìn)':'')+(field==='median'?' · VND':'')+'</span><span>'+esc(rows[0].name)+' → '+esc(rows.at(-1).name)+'</span></div><svg viewBox="0 0 760 310" class="chart-svg" role="img" aria-label="'+(field==='median'?'Giá trung vị theo tháng':'Số quan sát giá theo tháng')+'">'+marks+'</svg>'+note(field==='median'?'Trung vị theo tháng chịu ảnh hưởng của cơ cấu sản phẩm; chưa phải chỉ số tăng giảm giá thị trường. Các tháng thiếu dữ liệu không được nội suy.':'Số quan sát phản ánh dữ liệu đã thu thập, không đại diện doanh số. Các tháng thiếu dữ liệu không được nối hoặc nội suy.');
  }
  function comparison(){const items=data.comparable||[];if(!items.length)return empty('Chưa có nhóm đủ thông tin và ít nhất hai sản phẩm để so sánh.');return table(['Hoạt chất · Hàm lượng','Dạng / Đơn vị / Loại giá','Sản phẩm','Nhà SX','P10','Trung vị','P90'],items.map(x=>[x.ingredient+' · '+x.strength,x.dosage_form+' / '+x.unit+' / '+displayName(x.price_type),fmt(x.products),fmt(x.makers),money(x.p10),money(x.median),money(x.p90)]))+note('Nhóm theo hoạt chất, hàm lượng, dạng bào chế, đơn vị và loại giá. Chưa chuẩn hóa đường dùng, quy cách đóng gói hoặc thời điểm; cần kiểm tra trước quyết định mua sắm.');}
  function overview(){
    const s=data.summary,top=data.ingredients?.[0];
    return '<div class="chart-grid">'+panel('Quan sát giá theo thời gian','Số quan sát có giá theo tháng kê khai',trend(),'FULL DATABASE')+panel('Cơ cấu quốc gia sản xuất','Tỷ trọng theo sản phẩm phân biệt',donut(data.countries,'country','Cơ cấu quốc gia'),'CLICK TO FILTER')+'</div>'+
    '<div class="insight-banner"><div><div class="eyebrow">✦ DATA-DRIVEN INSIGHT</div><h3>'+esc(top?'Hoạt chất dẫn đầu danh mục: '+top.name:'Khám phá góc nhìn từ dữ liệu')+'</h3><p>'+esc(top?fmt(top.value)+' sản phẩm trong phạm vi bộ lọc, đến từ '+fmt(top.makers)+' nhà sản xuất. Có '+fmt(s.priced)+' quan sát giá VND hợp lệ để tiếp tục phân tích.':'Thử thay đổi bộ lọc để khám phá danh mục và các quan sát giá.')+'</p></div><button data-view="competition">Khám phá cạnh tranh &nbsp; ↗</button></div>'+
    '<div class="equal-grid">'+panel('Top hoạt chất','Xếp hạng theo số sản phẩm; nhấn để lọc',bars(data.ingredients,'ingredient'),'TOP 8')+panel('Phân phối giá quan sát','Nhận diện cơ cấu và độ lệch của dữ liệu giá',histogram(),'VND')+'</div>';
  }
  function pricing(){return '<div class="chart-grid">'+panel('Phân phối giá quan sát','Số quan sát theo khoảng giá',histogram()+priceRange(),'PRICE DISTRIBUTION')+panel('Đọc giá trong đúng ngữ cảnh','Lọc loại giá và đơn vị trước khi so sánh','<div class="story-card" style="border:0;padding:0">'+ '<h3>'+money(data.summary.median)+'</h3><p>Trung vị trên '+fmt(data.summary.priced)+' quan sát VND. Giá của các sản phẩm khác hoạt chất hoặc khác đơn vị không tạo thành một chỉ số giá thị trường.</p><h3>Chuẩn hóa nhóm so sánh</h3><p>Bảng bên dưới tách theo hoạt chất, hàm lượng, dạng bào chế, đơn vị và loại giá. Các nhóm thiếu trường quan trọng được loại khỏi bảng so sánh.</p></div>')+'</div>'+panel('Quan sát giá trung vị theo tháng','Dựa trên declaration_date trong price_record',trend('median'),'TIME SERIES')+panel('Các nhóm sản phẩm có thể khảo sát','Ít nhất hai sản phẩm khác nhau trong cùng cấu hình',comparison(),'BENCHMARKING');}
  function competition(){return '<div class="equal-grid">'+panel('Nhà sản xuất có danh mục lớn','Số sản phẩm phân biệt, không phải thị phần',bars(data.manufacturers,'q'),'TOP 10')+panel('Độ phủ nhà sản xuất theo hoạt chất','Số nhà sản xuất khác nhau trong các hoạt chất nổi bật',bars((data.ingredients||[]).map(x=>({name:x.name,value:x.makers})),'ingredient','nhà sản xuất'),'CATALOG COVERAGE')+'</div>'+panel('Cấu trúc danh mục nhà sản xuất','Xếp hạng theo số sản phẩm trong phạm vi lọc',table(['Nhà sản xuất','Sản phẩm','Hoạt chất phân biệt'],(data.manufacturers||[]).map(x=>[x.name,fmt(x.value),fmt(x.ingredients)])))+'<div class="insight-banner"><div><div class="eyebrow">INTERPRETATION</div><h3>Cạnh tranh danh mục là một góc nhìn về nguồn cung.</h3><p>Số sản phẩm và số nhà sản xuất giúp khảo sát độ phủ. Cần dữ liệu bán hàng để tính thị phần doanh thu và tốc độ tăng trưởng.</p></div><button data-view="business">Business context &nbsp; ↗</button></div>';}
  function portfolio(){return '<div class="equal-grid">'+panel('Cơ cấu dạng bào chế','Phân biệt sản phẩm trước khi phân tích giá',donut(data.forms,null,'Cơ cấu dạng bào chế'),'PRODUCT MIX')+panel('Quốc gia sản xuất','Nhấn tên quốc gia để lọc toàn dashboard',donut(data.countries,'country','Cơ cấu quốc gia'),'COUNTRY MIX')+'</div>'+panel('Độ phủ hoạt chất','Số sản phẩm và nhà sản xuất trong các nhóm nổi bật',table(['Hoạt chất','Sản phẩm','Nhà sản xuất'],(data.ingredients||[]).map(x=>[x.name,fmt(x.value),fmt(x.makers)])));}
  function quality(){
    const q=data.quality||{},m=data.mapping||{},total=Number(q.total)||0;
    const completeness=[['drug_name','Tên thuốc'],['ingredient','Hoạt chất'],['strength','Hàm lượng'],['dosage_form','Dạng bào chế'],['manufacturer','Nhà sản xuất'],['country','Quốc gia'],['unit','Đơn vị giá']].map(([key,name])=>{let p=total?Number(q[key])/total*100:0;return '<div class="quality-row"><div class="quality-label"><span>'+name+'</span><span>'+p.toFixed(1)+'%</span></div><div class="quality-track"><span style="width:'+p+'%"></span></div></div>';}).join('');
    return '<div class="equal-grid">'+panel('Độ đầy đủ của danh mục','Tính trên sản phẩm phân biệt trong phạm vi bộ lọc',completeness,'COMPLETENESS')+panel('Trạng thái DAV → RxNorm','Toàn bộ bảng mapping, không áp dụng bộ lọc sản phẩm',m.unavailable?empty('Chưa đọc được bảng mapping.'):bars((m.statuses||[]).map(x=>({...x,name:displayName(x.name)})),null,'bản ghi mapping'),'FULL MAPPING TABLE')+'</div><div class="cards-three">'+card('01 / ACCEPTED','Mapping được chấp nhận',m.unavailable?'Chưa có dữ liệu.':fmt(m.accepted)+' / '+fmt(m.total)+' dòng có accepted_for_serving = 1. Trạng thái này lấy trực tiếp từ dữ liệu nguồn.')+card('02 / REVIEW','Cần kiểm tra thủ công',m.unavailable?'Chưa có dữ liệu.':fmt(m.review)+' dòng có review_required = 1. Nên ưu tiên kiểm tra hoạt chất, hàm lượng, dạng và bằng chứng mapping.')+card('03 / RELATION','Tính hợp lệ của khóa',m.unavailable?'Chưa có dữ liệu.':fmt(m.valid_fk)+' dòng có selected_scd_fk_valid = 1. Khóa hợp lệ là điều kiện kỹ thuật, chưa chứng minh quan hệ lâm sàng.')+'</div>'+panel('Giới hạn cần kiểm soát','Đọc các chỉ số cùng định nghĩa',table(['Phạm vi','Cách diễn giải'],[['Sản phẩm','COUNT(DISTINCT dav_row_id), tránh nhân bản do một sản phẩm có nhiều giá.'],['Giá quan sát','Chỉ tính giá không âm, đồng VND hoặc chưa ghi currency; cần rà soát nguồn.'],['Độ đầy đủ','Trường không trống; chưa đo mức chính xác ngữ nghĩa.'],['Mapping','Trạng thái do nguồn cung cấp, không tự gán chính xác.'],['Phân tích giá','Tách loại giá, đơn vị và cấu hình; chưa có doanh số hoặc thị phần.']]));}
  function render(){
    const special=theory()||lookupView()||marketForecastView();
    $('lookup-panel').hidden=!lookupView();
    $('market-forecast-panel').hidden=!marketForecastView();
    $('status').hidden=lookupView()||marketForecastView();
    $('filters').hidden=special;$('metrics').hidden=special;$('records-panel').hidden=special;$('export').hidden=special;
    if($('filter-context')){$('filter-context').hidden=special||!data;}
    if(theory()){$('status').hidden=true;$('visuals').innerHTML=PharmaTasks.render(view);return;}
    if(lookupView()||marketForecastView()){$('lookup-task-story').innerHTML=lookupView()?PharmaTasks.intro(view)+PharmaDepth.lookupGuide():'';$('market-task-story').innerHTML=marketForecastView()?PharmaTasks.intro(view):'';$('visuals').innerHTML='';return;}
    if(!data){$('metrics').innerHTML=[['Sản phẩm','◫'],['Hoạt chất','◇'],['Nhà sản xuất','▥'],['Giá trung vị','↗']].map(([l,i])=>metric(l,'—','Đang chờ dữ liệu nguồn',i)).join('');$('visuals').innerHTML=panel('Kết nối dữ liệu phân tích','Không sử dụng số liệu mô phỏng','<div class="empty"><strong>Đang chờ dữ liệu từ Neon</strong>Nhấn làm mới để thử lại nếu kết nối chưa sẵn sàng.</div>');$('records').innerHTML='<tr><td colspan="5">Chưa có dữ liệu nguồn.</td></tr>';$('records-count').textContent='—';$('range').textContent='Chưa có bản ghi';$('pageinfo').textContent='—';$('prev').disabled=true;$('next').disabled=true;return;}
    const s=data.summary||{};renderFilterContext();
    $('metrics').innerHTML=view==='pricing'?metric('Giá P10',money(s.p10),'Phân vị 10% · VND','↓')+metric('Giá trung vị',money(s.median),'Phân vị 50% · VND','◫')+metric('Giá P90',money(s.p90),'Phân vị 90% · VND','↑')+metric('Quan sát có giá',fmt(s.priced),'Giá không âm · VND','▤'):metric('Sản phẩm phân biệt',fmt(s.products),'ID sản phẩm DAV trong bộ lọc','◫')+metric('Tên hoạt chất nguồn',fmt(s.ingredients),'Tên phân biệt từ dữ liệu nguồn','◇')+metric('Nhà sản xuất',fmt(s.manufacturers),'Tên nhà sản xuất phân biệt','▥')+metric('Giá trung vị',money(s.median),fmt(s.priced)+' quan sát giá VND','↗');
    $('visuals').innerHTML=PharmaTasks.intro(view,data)+'<div id="depth-analytical">'+PharmaDepth.render(view,data)+'</div>';
    $('records').innerHTML=(data.records||[]).map(r=>'<tr><td><strong>'+esc(r.drug_name||'Chưa có tên')+'</strong><small>'+esc([r.ingredient,r.strength].filter(Boolean).join(' · ')||'—')+'</small></td><td>'+esc(r.manufacturer||'—')+'</td><td>'+esc(r.country||'—')+'</td><td>'+esc(displayName(r.price_type)||'—')+'<small>'+esc(r.unit||'Chưa có đơn vị')+'</small></td><td class="numeric"><strong>'+money(r.price_vnd)+'</strong><small>'+esc(r.snapshot_date?String(r.snapshot_date).slice(0,10):'Chưa có ngày')+'</small></td></tr>').join('')||'<tr><td colspan="5">Không có bản ghi phù hợp.</td></tr>';
    const total=Number(s.observations)||0, maxPage=Math.max(1,Math.ceil(total/12));$('records-count').textContent=fmt(total)+' quan sát';$('range').textContent='Hiển thị '+(total?(page-1)*12+1:0)+'–'+Math.min(page*12,total)+' / '+fmt(total)+' bản ghi';$('pageinfo').textContent=page+' / '+maxPage;$('prev').disabled=page<=1;$('next').disabled=page>=maxPage;
  }
  function options(o){for(const [id,title] of [['ingredient','Tất cả hoạt chất'],['country','Tất cả quốc gia'],['kind','Tất cả loại giá'],['unit','Tất cả đơn vị']]){const current=$(id).value;$(id).innerHTML='<option value="">'+title+'</option>'+(o?.[id]||[]).map(x=>'<option value="'+esc(x)+'">'+esc(id==='kind'?displayName(x):x)+'</option>').join('');$(id).value=current;}}
  function setStatus(error,text){$('status').classList.toggle('error',error);$('status').innerHTML='<span class="signal"></span><span>'+esc(text)+'</span>';$('connection').classList.toggle('error',error);$('connection').textContent=error?'KẾT NỐI GIÁN ĐOẠN':'NEON CONNECTED';$('db-status').textContent=error?'Nguồn chưa sẵn sàng':'Dữ liệu đang kết nối';$('db-dot').style.background=error?'#c29862':'';}
  async function load(){
    controller?.abort();controller=new AbortController();const activeController=controller;const current=++seq;$('content').classList.add('loading');$('content').setAttribute('aria-busy','true');$('status').innerHTML='<span class="signal"></span><span>Đang cập nhật phân tích từ database…</span>';const abortTimer=setTimeout(()=>activeController.abort(),45000);
    try{const response=await fetch('/api/analytics?'+filters(),{signal:activeController.signal,cache:'no-store'});const result=await response.json();if(!response.ok||result.mode!=='database')throw new Error(result.notice||'Không thể đọc nguồn dữ liệu.');if(current!==seq)return;data=result;if(data.options){options(data.options);optionsLoaded=true;}setStatus(false,'Neon Gold · Cập nhật '+new Date(data.refreshedAt).toLocaleString('vi-VN')+' · Số liệu theo bộ lọc hiện tại.');render();}
    catch(e){if(current!==seq)return;if(e.name==='AbortError'&&activeController.signal.aborted){data=null;setStatus(true,'Kết nối quá thời gian chờ. Nhấn làm mới để thử lại.');}else{data=null;setStatus(true,e.message||'Không thể kết nối dữ liệu. Nhấn làm mới để thử lại.');}render();}
    finally{clearTimeout(abortTimer);if(current===seq){$('content').classList.remove('loading');$('content').setAttribute('aria-busy','false');}}
  }
  function navigate(id,updateUrl=true){if(!views.some(v=>v[0]===id))return;view=id;trendMode=null;const v=views.find(v=>v[0]===id);$('crumb').textContent=v[2];$('page-title').innerHTML=esc(v[2])+'<span>.</span>';$('page-kicker').textContent=v[3];$('page-desc').textContent=v[4];document.querySelectorAll('.nav-button').forEach(b=>{b.classList.toggle('active',b.dataset.view===id);b.setAttribute('aria-current',b.dataset.view===id?'page':'false');});$('tooltip').hidden=true;closeMenu();render();PharmaTasks.load(view);document.dispatchEvent(new CustomEvent('pharmabiz:lookup-view',{detail:{active:lookupView()}}));document.dispatchEvent(new CustomEvent('pharmabiz:market-forecast-view',{detail:{active:marketForecastView()}}));if(updateUrl){const url=new URL(location);url.searchParams.set('view',id);history.replaceState(null,'',url);}$('visuals').classList.remove('enter-page');requestAnimationFrame(()=>$('visuals').classList.add('enter-page'));window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});}
  function toast(message){clearTimeout(toastTimer);$('toast').textContent=message;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,3500);}
  function closeMenu(){$('sidebar').classList.remove('open');$('backdrop').hidden=true;$('menu').setAttribute('aria-expanded','false');}
  function navIcon(id){const paths={overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',lookup:'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',pricing:'M3 18l5-5 4 2 8-10 M15 5h5v5',competition:'M4 21V9h5v12 M10 21V3h5v18 M16 21v-8h5v8',portfolio:'M3 7l9-4 9 4-9 4z M3 12l9 4 9-4 M3 17l9 4 9-4',quality:'M12 2l8 4v6c0 5-8 10-8 10S4 17 4 12V6z M8 12l3 3 5-6',business:'M4 4h16v16H4z M8 8h8 M8 12h8 M8 16h5',workflow:'M4 3h6v6H4z M14 15h6v6h-6z M7 9v9h7 M10 6h7v9',reports:'M4 3h16v18H4z M8 16v-4 M12 16V7 M16 16v-6',eda:'M4 19V5 M4 19h17 M8 14l4-6 4 3 4-6',preparation:'M4 7h16 M7 3v8 M4 17h16 M16 13v8',modeling:'M3 17l5-7 5 4 7-10 M3 21h18','market-forecast':'M3 17l6-6 4 3 8-10 M16 4h5v5'};return '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="'+paths[id]+'"/></svg>';}
  $('nav').innerHTML=views.map((v,i)=>(v[0]==='business'?'<div class="nav-divider"></div><div class="nav-caption">NGHIÊN CỨU DỮ LIỆU</div>':'')+'<button class="nav-button" data-view="'+v[0]+'"><span class="nav-icon">'+navIcon(v[0])+'</span><span>'+v[2]+'</span><span class="nav-arrow">↗</span></button>').join('');
  document.addEventListener('click',e=>{const range=e.target.closest('[data-trend-range]');if(range){trendRange=range.dataset.trendRange;render();return;}const mode=e.target.closest('[data-trend-mode]');if(mode){trendMode=mode.dataset.trendMode;render();return;}const remove=e.target.closest('[data-remove-filter]');if(remove){$(remove.dataset.removeFilter).value='';page=1;load();return;}const nav=e.target.closest('[data-view]');if(nav)navigate(nav.dataset.view);const filter=e.target.closest('[data-filter]');if(filter){const key=filter.dataset.key;const id=key==='q'?'search':key;if($(id)){if(id!=='search'&&![...$(id).options].some(o=>o.value===filter.dataset.filter))return;$(id).value=filter.dataset.filter;page=1;load();toast('Đã lọc: '+filter.dataset.filter);}}});
  $('menu').onclick=()=>{const open=!$('sidebar').classList.contains('open');$('sidebar').classList.toggle('open',open);$('backdrop').hidden=!open;$('menu').setAttribute('aria-expanded',String(open));};$('backdrop').onclick=closeMenu;
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeMenu();$('tooltip').hidden=true;}if((e.key==='Enter'||e.key===' ')&&e.target.matches('circle[data-filter]')){e.preventDefault();e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}});
  document.addEventListener('pharmabiz:task-context',()=>{if(theory())render();});
  $('refresh').onclick=()=>{if(theory()){PharmaTasks.refresh(view);return;}if(lookupView())document.dispatchEvent(new Event('pharmabiz:lookup-refresh'));else{optionsLoaded=false;load();fetchInventory();}};$('search').addEventListener('input',()=>{clearTimeout(timeout);timeout=setTimeout(()=>{page=1;load();},350);});
  for(const id of ['ingredient','country','kind','unit'])$(id).onchange=()=>{page=1;load();};
  $('reset').onclick=()=>{clearTimeout(timeout);for(const id of ['search','ingredient','country','kind','unit'])$(id).value='';page=1;load();};
  $('prev').onclick=()=>{page=Math.max(1,page-1);load();};$('next').onclick=()=>{page++;load();};
  $('export').onclick=()=>{if(!data?.records?.length)return toast('Chưa có dữ liệu để xuất.');const keys=['id','drug_name','ingredient','strength','dosage_form','manufacturer','country','price_type','unit','price_vnd','snapshot_date','registration_no'];const quote=v=>'"'+String(v??'').replace(/"/g,'""').replace(/^[=+@-]/,"'$&")+'"';const text='\uFEFF'+[keys.join(','),...data.records.map(x=>keys.map(k=>quote(x[k])).join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='pharmabiz_records_page_'+page+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Đã xuất '+data.records.length+' bản ghi của trang hiện tại.');};
  $('present').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{toast('Có thể dùng phím F11 để mở toàn màn hình.');}};
  $('back-top').onclick=()=>window.scrollTo({top:0,behavior:'smooth'});
  function showTip(target,x,y){$('tooltip').innerHTML='<strong>'+esc(target.dataset.tip)+'</strong>'+esc(target.dataset.value);$('tooltip').hidden=false;const b=$('tooltip').getBoundingClientRect();$('tooltip').style.left=Math.min(innerWidth-b.width-10,Math.max(10,x+12))+'px';$('tooltip').style.top=Math.min(innerHeight-b.height-10,Math.max(10,y+12))+'px';}
  document.addEventListener('pointermove',e=>{const t=e.target.closest('[data-tip]');if(t)showTip(t,e.clientX,e.clientY);else $('tooltip').hidden=true;});document.addEventListener('focusin',e=>{const t=e.target.closest('[data-tip]');if(t){const b=t.getBoundingClientRect();showTip(t,b.x+b.width/2,b.y+b.height/2);}});document.addEventListener('focusout',()=>$('tooltip').hidden=true);
  async function fetchInventory(){try{const r=await fetch('/api/insights',{cache:'no-store'});if(r.ok){inventory=await r.json();if(view==='workflow')render();}}catch{}}

  function updateTheme(){
    const dark=document.documentElement.dataset.theme==='dark';
    for(const b of document.querySelectorAll('[data-theme-toggle]')){b.setAttribute('aria-pressed',String(dark));b.setAttribute('aria-label',dark?'Chuyển sang giao diện sáng':'Chuyển sang giao diện tối');b.querySelector('[data-theme-icon]').textContent=dark?'☀':'☾';b.querySelector('[data-theme-label]').textContent=dark?'Sáng':'Tối';}
    document.querySelector('meta[name="theme-color"]').content=dark?'#0d1b17':'#ecf4ed';
  }
  for(const b of document.querySelectorAll('[data-theme-toggle]'))b.onclick=()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;try{localStorage.setItem('pharmabiz-theme',theme);}catch{}updateTheme();};
  updateTheme();
  function trendControls(field){return '<div class="chart-controls"><div class="segmented" role="group" aria-label="Chỉ số biểu đồ thời gian">'+[['value','Số quan sát'],['median','Giá trung vị']].map(([v,l])=>'<button data-trend-mode="'+v+'" aria-pressed="'+(field===v)+'">'+l+'</button>').join('')+'</div><div class="segmented" role="group" aria-label="Khoảng thời gian">'+[['6','6 tháng'],['12','12 tháng'],['all','Tất cả']].map(([v,l])=>'<button data-trend-range="'+v+'" aria-pressed="'+(trendRange===v)+'">'+l+'</button>').join('')+'</div></div>';}
  function priceRange(){const s=data.summary;if(s.p10===null||s.p90===null)return '';return '<div class="price-range"><div class="range-track" aria-hidden="true"></div><div class="range-labels">'+[['P10',s.p10],['P50 · Trung vị',s.median],['P90',s.p90]].map(([l,v])=>'<span>'+l+'<strong>'+money(v)+'</strong></span>').join('')+'</div></div>'+note('P10–P90 bao quát 80% vị trí trong phân phối giá. Các giá trị phân vị có thể được nội suy giữa hai quan sát.');}
  function analysisBrief(){
    const s=data.summary,total=Number(s.products),country=data.countries?.[0],group=data.ingredients?.[0];if(!total)return '';
    const ratio=(n,d)=>d?(100*Number(n)/d).toLocaleString('vi-VN',{maximumFractionDigits:1})+'%':'—';
    const broad=!$('unit').value||!$('ingredient').value;
    return '<section class="analysis-brief" aria-label="Nhận xét từ dữ liệu đang lọc">'+
      '<article class="analysis-card"><div class="eyebrow">CƠ CẤU NGUỒN CUNG</div><h3>'+esc(country?country.name:'Chưa xác định')+' · '+ratio(country?.value,total)+'</h3><p>'+fmt(country?.value)+' / '+fmt(total)+' sản phẩm thuộc nhóm quốc gia dẫn đầu. Tên quốc gia giữ theo nguồn dữ liệu.</p><button data-view="portfolio">Xem cơ cấu danh mục ↗</button></article>'+
      '<article class="analysis-card"><div class="eyebrow">PHẠM VI GIÁ QUAN SÁT</div><h3>'+money(s.p10)+' → '+money(s.p90)+'</h3><p>Khoảng P10–P90 trên '+fmt(s.priced)+' quan sát VND. '+(broad?'Lọc hoạt chất và đơn vị để so sánh có ý nghĩa hơn.':'Cần kiểm tra thêm hàm lượng, dạng bào chế và quy cách.')+'</p><button data-view="pricing">Khảo sát phân phối giá ↗</button></article>'+
      '<article class="analysis-card"><div class="eyebrow">HOẠT CHẤT NỔI BẬT</div><h3>'+esc(group?.name||'Chưa xác định')+'</h3><p>'+fmt(group?.value)+' sản phẩm · '+fmt(group?.makers)+' nhà sản xuất. Chiếm '+ratio(group?.value,total)+' danh mục trong phạm vi đang lọc.</p>'+(group?'<button data-key="ingredient" data-filter="'+esc(group.name)+'">Phân tích nhóm này ↗</button>':'')+'</article></section>';
  }
  function renderFilterContext(){
    let element=$('filter-context');if(!element){element=document.createElement('div');element.id='filter-context';element.className='filter-context';$('filters').after(element);}
    element.hidden=theory();const labels={search:'Tìm kiếm',ingredient:'Hoạt chất',country:'Quốc gia',kind:'Loại giá',unit:'Đơn vị'};
    const active=Object.entries(labels).filter(([id])=>$(id).value);
    element.innerHTML='<span>'+(active.length?'Phạm vi đang lọc:':'Toàn bộ danh mục')+'</span>'+active.map(([id,l])=>'<button data-remove-filter="'+id+'" aria-label="Bỏ lọc '+esc(l)+'">'+l+': '+esc(displayName($(id).value))+' ×</button>').join('')+'<span>· '+fmt(data.summary.products)+' sản phẩm · '+esc(data.summary.date_from||'—')+' → '+esc(data.summary.date_to||'—')+'</span>';
  }

  const requested=new URLSearchParams(location.search).get('view');navigate(views.some(v=>v[0]===requested)?requested:'overview',true);load();fetchInventory();
})();
