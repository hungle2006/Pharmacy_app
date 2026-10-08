
(function(){
  var schemaInfo=null;
  var chartColors=['#0d907b','#43b8aa','#7cadd9','#dda75d','#9f9bdc','#73a3a1','#bdc8d0','#527795'];
  var fmt1=function(n){return (Math.round(Number(n)*10)/10).toLocaleString('vi-VN');};
  var dataRows=function(){return typeof filtered==='undefined'?[]:filtered;};
  var pricedRows=function(){return dataRows().filter(function(x){return x.price_vnd!==null && x.price_vnd!==undefined && Number.isFinite(Number(x.price_vnd));});};
  var note=function(x){return '<div class="chart-caption">'+esc(x)+'</div>';};
  var simpleSVG=function(body){return '<svg viewBox="0 0 650 270" class="chart-svg" role="img" aria-label="Biểu đồ phân tích">'+body+'</svg>';};
  var axisText=function(x,y,str,anchor){return '<text x="'+x+'" y="'+y+'" fill="#879ba6" font-size="10" text-anchor="'+(anchor||'start')+'">'+esc(str)+'</text>';};
  function histogram(records){
    var vals=records.map(function(x){return Number(x.price_vnd);}).filter(Number.isFinite).sort(function(a,b){return a-b;});
    if(vals.length<3)return '<div class="empty">Chưa đủ dữ liệu giá hợp lệ để tạo biểu đồ phân phối.</div>';
    var p05=pct(vals,.05),p95=pct(vals,.95);
    if(p95<=p05)p95=p05+1;
    var bins=Array(9).fill(0),outliers=0;
    vals.forEach(function(v){if(v<p05||v>p95){outliers++;return;}bins[Math.min(8,Math.floor((v-p05)/(p95-p05)*9))]++;});
    var max=Math.max(1,...bins),out='';
    for(var i=0;i<9;i++){var barH=bins[i]/max*186,x=46+i*64;
      out+='<rect x="'+x+'" y="'+(220-barH)+'" width="39" height="'+barH+'" rx="6" fill="'+chartColors[i%chartColors.length]+'" opacity=".92"></rect>';
      out+=axisText(x+18,242,fmt1(p05+(p95-p05)*(i+.5)/9),'middle');
      out+=axisText(x+18,210-barH,String(bins[i]),'middle');
    }
    out+='<line x1="35" x2="635" y1="220" y2="220" stroke="#dfe8ec"/>';
    return simpleSVG(out)+note('Histogram giá quan sát: bỏ '+fmt(outliers)+' dòng ngoài P05–P95 để dễ xem. Trục X là VND theo đơn vị giá trong dữ liệu gốc; cần chuẩn hóa đơn vị trước khi kết luận.');
  }
  function donut(groups,title){
    if(!groups.length)return '<div class="empty">Chưa có dữ liệu</div>';
    var sum=groups.reduce(function(a,b){return a+b.value;},0)||1,acc=0,circles='';
    groups.slice(0,7).forEach(function(g,i){
      var len=g.value/sum*100;
      circles+='<circle r="71" cx="118" cy="118" fill="none" stroke="'+chartColors[i]+'" stroke-width="28" stroke-dasharray="'+len+' '+(100-len)+'" stroke-dashoffset="'+(-acc)+'" pathLength="100" transform="rotate(-90 118 118)"><title>'+esc(g.name)+': '+fmt1(len)+'%</title></circle>';
      acc+=len;
    });
    var leftover=Math.max(0,100-acc);
    if(leftover>0)circles+='<circle r="71" cx="118" cy="118" fill="none" stroke="#ccd6da" stroke-width="28" stroke-dasharray="'+leftover+' '+(100-leftover)+'" stroke-dashoffset="'+(-acc)+'" pathLength="100" transform="rotate(-90 118 118)"/>';
    var legend=groups.slice(0,7).map(function(g,i){return '<div><i style="background:'+chartColors[i]+'"></i><span title="'+esc(g.name)+'">'+esc(g.name)+'</span><b>'+fmt1(g.value/sum*100)+'%</b></div>';}).join('');
    return '<div class="chart-flex"><svg viewBox="0 0 236 236" class="donut-svg" role="img" aria-label="'+esc(title)+'"><circle cx="118" cy="118" r="71" stroke="#eaf0f2" fill="none" stroke-width="28"/>'+circles+'<text x="118" y="111" text-anchor="middle" fill="#1a3b43" font-size="23" font-weight="bold">'+fmt(sum)+'</text><text x="118" y="133" fill="#8298a0" font-size="11" text-anchor="middle">bản ghi</text></svg><div class="legend">'+legend+'</div></div>'+note('Tỷ trọng theo số bản ghi sản phẩm, không phải doanh số hoặc thị phần.');
  }
  function lineChart(g){
    if(g.length<2)return '<div class="empty">Chưa có đủ nhóm dữ liệu so sánh.</div>';
    g=g.slice(0,10);
    var max=Math.max(1,...g.map(function(x){return x.value;})),points=g.map(function(x,i){return [45+i*555/Math.max(1,g.length-1),212-x.value/max*160];});
    var pointStr=points.map(function(x){return x.join(',');}).join(' ');
    var area='M '+points[0][0]+' 219 L '+points.map(function(x){return x.join(' ');}).join(' L ')+' L '+points[points.length-1][0]+' 219 Z';
    var svg='<defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#54c7b1" stop-opacity=".31"/><stop offset="1" stop-color="#54c7b1" stop-opacity=".015"/></linearGradient></defs>';
    for(var j=0;j<5;j++)svg+='<line x1="38" x2="610" y1="'+(52+j*40)+'" y2="'+(52+j*40)+'" stroke="#eaf0f2" stroke-dasharray="3 5"/>';
    svg+='<path d="'+area+'" fill="url(#areaFill)"/><polyline points="'+pointStr+'" fill="none" stroke="#14917f" stroke-width="3" stroke-linejoin="round"/>';
    points.forEach(function(p,i){svg+='<circle cx="'+p[0]+'" cy="'+p[1]+'" r="5" fill="#fff" stroke="#159583" stroke-width="3"/>'+axisText(p[0],244,g[i].name.slice(0,9),'middle');});
    return simpleSVG(svg)+note('Giá trung vị theo nhóm hoạt chất (danh mục, không phải xu hướng theo thời gian). Không suy ra mức tăng giảm giá nếu không có chuỗi thời gian.');
  }
  function card(n,t,d){return '<article class="story-card"><div class="num">'+n+'</div><h3>'+t+'</h3><p>'+d+'</p></article>';}
  function headline(kicker,title,text){
    return '<div class="section-title"><div><span class="eyebrow">'+kicker+'</span><h2>'+title+'</h2><p>'+text+'</p></div><span class="pill">● Business Intelligence</span></div>';
  }
  function renderBusiness(){
    return headline('01 / BUSINESS UNDERSTANDING','Từ dữ liệu dược đến quyết định kinh doanh','Vấn đề, mục tiêu, stakeholder và tiêu chí thành công')+
      '<div class="cards3">'+card('01 — PROBLEM','Vấn đề kinh doanh','Dữ liệu thuốc, giá và nhà sản xuất phân tán nhiều bảng; khó so sánh danh mục, cạnh tranh và chất lượng dữ liệu.')+
      card('02 — OBJECTIVE','Mục tiêu phân tích','Xây dashboard hỗ trợ phân tích cơ cấu danh mục, độ phân tán giá, số đối thủ trong cùng phân khúc.')+
      card('03 — USER','Người sử dụng','Nhà phân tích thị trường dược, nhóm mua sắm, quản trị danh mục và nhóm nghiên cứu dữ liệu.')+'</div>'+
      panel('Từ câu hỏi kinh doanh đến KPI có thể đo','Đầu ra thiết kế theo CRISP-DM',table(['Business Question','Metric','Giới hạn'],[
        ['Cơ cấu sản phẩm ra sao?','Số sản phẩm theo hoạt chất/dạng bào chế','Không đại diện doanh số'],
        ['Giá cùng phân khúc phân tán thế nào?','P10, Median, P90, IQR','Phải chuẩn hóa đơn vị giá'],
        ['Mức cạnh tranh danh mục?','Nhà sản xuất trên mỗi hoạt chất','Không phải thị phần'],
        ['Mapping liên kết đáng tin?','Match rate, unlinked, needs review','Không tự suy luận chỉ định'],
        ['Chất lượng dữ liệu đủ tốt?','Completeness, duplicates, provenance','Phụ thuộc nguồn và thời điểm']
      ]))+
      '<div class="cards2">'+panel('Success Criteria','Tiêu chí chấp nhận', '<div class="speaking"><span class="bubble">1</span><div><strong>Tính đúng</strong><p>KPI được đối chiếu bằng SQL; kết quả phân tích có định nghĩa và nguồn rõ ràng.</p></div></div><div class="speaking"><span class="bubble">2</span><div><strong>Tính hữu dụng</strong><p>Người xem lọc được theo hoạt chất, nhà sản xuất, quốc gia, loại giá.</p></div></div><div class="speaking"><span class="bubble">3</span><div><strong>Tính minh bạch</strong><p>Biết dữ liệu là demo, mẫu giới hạn hay tập đầy đủ. Không nhầm số sản phẩm với thị phần.</p></div></div>')+
      panel('Phạm vi nghiên cứu','Phân tích sử dụng dataset hiện có','<div class="speaking"><span class="bubble">A</span><div><strong>Trọng tâm: DAV × Giá</strong><p>Danh mục sản phẩm, hoạt chất, giá công bố/trúng thầu và nhà sản xuất.</p></div></div><div class="speaking"><span class="bubble">B</span><div><strong>Mở rộng: RxNorm, ICD-10, MEDI</strong><p>Chuẩn hóa định danh hoạt chất và đo lường độ phủ liên kết; không dùng để khuyến nghị kê đơn.</p></div></div>')+'</div>';
  }
  function renderWorkflow(){
    var t=(schemaInfo&&schemaInfo.tables)||[],lookup=function(n){return t.find(function(x){return x.name===n;});};
    var tbl=['dav_product','price_record','dav_rxnorm_mapping','rxnorm_concept','rxnorm_scd','disease','medi_relation','rxnorm_scd_component'];
    var tableBoxes=tbl.map(function(n){var x=lookup(n),ok=x&&x.available;return '<div class="status-item"><strong>'+esc(n)+'</strong><small>'+(!schemaInfo?'Ảnh Neon / chưa kết nối':(ok?('Neon ✓ · ~'+(x.estimatedRows===null?'?':fmt(x.estimatedRows))+' dòng'):'Chưa xác định'))+'</small></div>';}).join('');
    return headline('02 / DATA UNDERSTANDING','Hành trình và kiến trúc dữ liệu','Từ hệ quản trị Neon PostgreSQL đến analytical storytelling')+
     panel('Tám bảng nguồn','Ảnh Neon cho thấy các bảng dưới đây; kết quả live được xác minh khi kết nối', '<div class="status-list">'+tableBoxes+'</div>')+
     panel('Data pipeline — ETL / BI','Business-driven analytics architecture',
       '<div class="funnel">'+[
         ['SOURCE','Neon: DAV, MEDI, ICD, RxNorm'],
         ['AUDIT','Profile, nulls, duplicates'],
         ['CLEANING','Chuẩn hóa giá, hàm lượng, tên'],
         ['MAPPING','Kiểm tra join + provenance'],
         ['DATA MART','Facts + dimensions'],
         ['VISUALIZATION','KPI, charts, insights']
       ].map(function(x){return '<div class="funnel-step"><b>'+x[0]+'</b><small>'+x[1]+'</small></div>';}).join('')+'</div>')+
     '<div class="cards2">'+panel('Thiết kế Star Schema','Data mart đề xuất','<div class="speaking"><span class="bubble">F</span><div><strong>fact_drug_price</strong><p>price_record + khóa sản phẩm, loại giá, ngày, giá/đơn vị. Xác định grain trước khi tính KPI.</p></div></div><div class="speaking"><span class="bubble">D</span><div><strong>dim_drug / dim_manufacturer / dim_date</strong><p>Chuẩn hóa hoạt chất, hàm lượng, dạng bào chế, nhà sản xuất và thời điểm.</p></div></div><div class="speaking"><span class="bubble">M</span><div><strong>bridge_rxnorm / disease_relation</strong><p>Lưu quan hệ có trạng thái match và nguồn; không ép unmatched thành mapped.</p></div></div>')+
     panel('Data Governance Checklist','Các lỗi cần xử lý trước khi kết luận','<div class="speaking"><span class="bubble">1</span><div><strong>Giá</strong><p>Phân biệt giá kê khai, trúng thầu và đơn vị đóng gói.</p></div></div><div class="speaking"><span class="bubble">2</span><div><strong>Entity matching</strong><p>Hoạt chất + hàm lượng + dạng bào chế + đường dùng; giữ match status.</p></div></div><div class="speaking"><span class="bubble">3</span><div><strong>Sampling</strong><p>Dashboard mẫu tối đa 2.000 bản ghi; cần SQL aggregation để tính KPI toàn bộ dữ liệu.</p></div></div>')+'</div>';
  }
  function renderEDA(){
    var r=dataRows(),p=pricedRows(),values=p.map(function(x){return Number(x.price_vnd);});
    var byCountry=group(r,'country').sort(function(a,b){return b.items.length-a.items.length;}).slice(0,7).map(function(x){return {name:x.name,value:x.items.length};});
    var ing=group(p,'ingredient').filter(function(x){return x.items.length>=2;}).sort(function(a,b){return b.items.length-a.items.length;}).slice(0,7).map(function(x){return {name:x.name,value:med(x.items.map(function(y){return Number(y.price_vnd);}))};});
    var numericStat=pricesLen=>pricesLen?('Số quan sát có giá: '+fmt(pricesLen)):'Không có giá hợp lệ';
    return headline('03 / EXPLORATORY DATA ANALYSIS','Khám phá phân bố, chênh lệch và cơ cấu','EDA giúp xác định giả thuyết, không chỉ tạo biểu đồ')+
     '<div class="two">'+panel('Price Distribution · Histogram',numericStat(values.length),histogram(p))+
     panel('Country Composition · Donut','Tỷ trọng theo bản ghi sản phẩm',donut(byCountry,'Cơ cấu quốc gia'))+'</div>'+
     panel('Ingredient-level Median · Comparison','Các nhóm nhiều quan sát có giá hợp lệ',lineChart(ing))+
     '<div class="info-band warn"><strong>! Giải thích EDA:</strong> Giá chưa chuẩn hóa theo đơn vị sản phẩm chỉ phản ánh phân bố trong snapshot. Chưa được coi là tương quan giá/giá trị giữa thuốc khác hàm lượng, dạng bào chế.</div>';
  }

  function renderModeling(){
    return headline('06 / MODELING & EVALUATION','Roadmap phân tích dự đoán giá thuốc','Thiết kế thí nghiệm ML trước khi huấn luyện mô hình')+
    '<div class="info-band warn"><strong>Research stage:</strong> Đây là đề xuất mô hình, chưa huấn luyện hoặc công bố chỉ số dự đoán. Chỉ thực hiện sau khi chuẩn hóa giá/đơn vị và nguồn quan sát.</div>'+
    '<div class="cards3">'+card('01 / TARGET','Biến mục tiêu','Giá trên một đơn vị chuẩn hoặc log(price); tách theo loại giá, dạng bào chế, hàm lượng và thời gian.')+
    card('02 / FEATURES','Biến giải thích','Hoạt chất, hàm lượng, dạng bào chế, nhà sản xuất, quốc gia, ngày quan sát và loại giá.')+
    card('03 / BASELINES','Các mô hình','Median baseline → Ridge Regression → Random Forest → Gradient Boosting/XGBoost (nếu dữ liệu đủ).')+'</div>'+
    '<div class="cards2">'+panel('Experimental Design','Tránh leakage và overclaim','<div class="speaking"><span class="bubble">1</span><div><strong>Split</strong><p>Ưu tiên kiểm thử theo thời gian; nhóm cùng số đăng ký không được bị rò giữa train/test.</p></div></div><div class="speaking"><span class="bubble">2</span><div><strong>Evaluation</strong><p>MAE, RMSE, R² trên tập held-out; báo sai số theo nhóm và chênh lệch phân phối.</p></div></div><div class="speaking"><span class="bubble">3</span><div><strong>Explainability</strong><p>Permutation importance/SHAP chỉ phản ánh liên hệ dự báo, không chứng minh quan hệ nhân quả.</p></div></div>')+
    panel('Business Decision Support','Hành động có thể hỗ trợ sau khi mô hình được xác minh','<div class="speaking"><span class="bubble">A</span><div><strong>Price benchmarking</strong><p>Đánh dấu sản phẩm chênh lệch giá trong nhóm thực sự tương đương.</p></div></div><div class="speaking"><span class="bubble">B</span><div><strong>Catalog strategy</strong><p>Nhóm hoạt chất có nhiều nhà cung cấp và phân phối giá rộng để nghiên cứu.</p></div></div><div class="speaking"><span class="bubble">C</span><div><strong>Data monitoring</strong><p>Cảnh báo bản ghi thiếu và bất thường do lỗi chuẩn hóa.</p></div></div>')+'</div>';
  }
  function priceTrend(){
    var dated=pricedRows().filter(function(r){return /^\\d{4}-\\d{2}/.test(String(r.snapshot_date||''));});
    var dict={};dated.forEach(function(r){var key=String(r.snapshot_date).slice(0,7);(dict[key]??=[]).push(Number(r.price_vnd));});
    var arr=Object.keys(dict).sort().slice(-10).map(function(key){return {name:key,value:med(dict[key])};});
    return arr.length<2?'<div class="empty">Chưa đủ chuỗi quan sát giá theo tháng để vẽ biểu đồ. Không nội suy dữ liệu thiếu.</div>':lineChart(arr)+note('Giá trung vị của các quan sát có mốc thời gian trong mẫu. Thay đổi thành phần sản phẩm có thể ảnh hưởng xu hướng; đây không phải chỉ số giá chuẩn hóa.');
  }
  function enrichOverview(){
    var r=dataRows(),p=pricedRows(),groups=group(r,'dosage_form').sort(function(a,b){return b.items.length-a.items.length;}).slice(0,7).map(function(x){return {name:x.name,value:x.items.length};});
    return headline('04 / VISUAL ANALYTICS','Các biểu đồ khám phá bổ sung','Phân phối giá và cơ cấu sản phẩm theo dữ liệu đang được lọc')+
     '<div class="two">'+panel('Distribution of Observed Prices','Phát hiện lệch phải và ngoại lệ tiềm năng',histogram(p))+panel('Dosage Form Mix','Số bản ghi theo dạng bào chế',donut(groups,'Dạng bào chế'))+'</div>';
  }
  function stories(){
    var r=dataRows(),p=pricedRows(),a=group(r,'ingredient').sort(function(x,y){return y.items.length-x.items.length;})[0],vals=p.map(function(x){return Number(x.price_vnd);});
    var insights=[];
    if(a)insights.push({title:'Danh mục tập trung',text:'Nhóm "'+a.name+'" đang có '+fmt(a.items.length)+' bản ghi trong phạm vi lọc. Đây không phải thị phần.'});
    if(vals.length>2)insights.push({title:'Độ phân tán giá',text:'Giá P90/P10 của mẫu là '+(pct(vals,.1)>0?fmt1(pct(vals,.9)/pct(vals,.1))+' lần':'không xác định')+'. Chỉ diễn giải sau khi chuẩn hóa đơn vị.'});
    insights.push({title:'Đặt câu hỏi tiếp theo',text:'Sản phẩm nào có cùng hoạt chất–hàm lượng–dạng bào chế nhưng chênh giá đáng kể, và có bao nhiêu nhà cung cấp?'});
    return '<div class="section-title"><div><span class="eyebrow">DATA STORYTELLING</span><h2>Ba insight để thuyết trình</h2></div></div><div class="cards3">'+insights.map(function(x,i){return card('INSIGHT 0'+(i+1),esc(x.title),esc(x.text));}).join('')+'</div>';
  }
  var origDraw=draw,tableSection=$('table').closest('section'),filterSection=document.querySelector('section.filter');
  var noticeEl=$('notice'),hero=document.createElement('div'),add=document.createElement('div'),story=document.createElement('div');
  hero.id='presentationHero';add.id='visualAddon';story.id='storyFooter';
  noticeEl.insertAdjacentElement('afterend',hero);
  $('visuals').insertAdjacentElement('beforebegin',add);
  $('visuals').insertAdjacentElement('afterend',story);
  draw=function(){
    origDraw();
    var isTheory=view==='business'||view==='workflow'||view==='modeling',eda=view==='eda';
    filterSection.classList.toggle('hide',isTheory);
    tableSection.classList.toggle('hide',isTheory);
    $('stats').classList.toggle('hide',isTheory);
    var live=mode==='database',count=dataRows().length;
    var subtitles={overview:'Vị thế danh mục và các chỉ số toàn cảnh',business:'Bối cảnh, KPI và câu hỏi kinh doanh',workflow:'Nguồn dữ liệu, mô hình và chất lượng',eda:'Khảo sát dữ liệu và giả thuyết',pricing:'Phân khúc giá và độ phân tán',competition:'Cạnh tranh theo nhà sản xuất',portfolio:'Cơ cấu sản phẩm & hoạt chất',quality:'Completeness và dữ liệu thiếu',modeling:'Thiết kế dự báo giá, đánh giá và diễn giải'};
    hero.className='hero-panel';
    hero.innerHTML='<div><div class="hero-tag">✦ PHARMABIZ · DATA-DRIVEN DECISIONS</div><h2>'+esc(view==='business'?'Business Understanding trước khi phân tích':view==='workflow'?'Dữ liệu đáng tin tạo nên quyết định tốt':view==='modeling'?'From business questions to validated models':'Understand the market. Explore the data.')+'</h2><p>'+esc(subtitles[view]||'Vietnam Pharmaceutical Business Intelligence')+'. '+(live?'Đang sử dụng mẫu bản ghi từ Neon.':'Đang trình diễn dữ liệu giả lập, chưa phải thống kê thị trường thực tế.')+'</p><span class="pill '+(live?'':'amber')+'">'+(live?'● NEON CONNECTED':'○ DEMONSTRATION')+'</span></div><div class="hero-metrics"><div class="hero-metric"><strong>'+fmt(count)+'</strong><small>Bản ghi trong bộ lọc</small></div><div class="hero-metric"><strong>'+fmt(new Set(dataRows().map(function(x){return x.ingredient;})).size)+'</strong><small>Nhóm hoạt chất</small></div></div>';
    if(isTheory){add.innerHTML='';$('visuals').innerHTML=view==='business'?renderBusiness():view==='workflow'?renderWorkflow():renderModeling();story.innerHTML='';return;}
    if(eda){add.innerHTML='';$('visuals').innerHTML=renderEDA();story.innerHTML=stories();return;}
    if(mode==='database'&&!pricedRows().length&&view==='pricing'){$('visuals').innerHTML='<div class="info-band warn">Giá chưa được xác thực từ bảng price_record; vui lòng kiểm tra quan hệ khóa và cột giá trong Neon. Không vẽ biểu đồ giá bằng số 0 giả.</div>';}
    add.innerHTML=view==='overview'?enrichOverview():view==='pricing'?panel('Observed Price Timeline','Giá trung vị theo mốc quan sát; cần chú ý sự khác nhau giữa các nhóm',priceTrend()):'';
    story.innerHTML=(view==='overview'||view==='pricing'||view==='competition')?stories():'';
    if(mode==='database'&&!pricedRows().length){var statboxes=$('stats').querySelectorAll('.stat');if(statboxes.length>=4)statboxes[3].querySelector('strong').textContent='Chưa có';}
  };
  draw();
  fetch('/api/insights',{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).then(function(d){if(d&&d.mode==='database'){schemaInfo=d;draw();}}).catch(function(){});
  var oldNav=navigate;
  // Auto-set the speaker's recommended opening slide only if explicitly requested via ?view=business
  try{var requested=new URLSearchParams(location.search).get('view');if(requested&&nav.some(function(n){return n[0]===requested;}))oldNav(requested);}catch(e){}
})();
