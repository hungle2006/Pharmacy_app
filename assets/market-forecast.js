(() => {
  'use strict';
  const panel=document.getElementById('market-forecast-panel');
  if(!panel)return;
  const output=document.getElementById('mf-report');
  const status=document.getElementById('mf-message');
  const updated=document.getElementById('mf-updated');
  const buttons=document.getElementById('mf-horizons');
  let active=false,loading=false,loaded=null,horizon='6';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','"':'&quot;'}[c]));
  const number=value=>Number(value??0).toLocaleString('vi-VN',{maximumFractionDigits:0});
  const percent=value=>value===null||value===undefined?'—':
    (Number(value)>0?'+':'')+Number(value).toLocaleString('vi-VN',{maximumFractionDigits:2})+'%';
  const valueClass=value=>Number(value)>0?'mf-trend-up':Number(value)<0?'mf-trend-down':'mf-trend-flat';
  function card(title,value,detail,css=''){
    return '<div class="mf-stat"><div class="mf-stat-label">'+esc(title)+'</div>'+
      '<strong class="'+css+'">'+esc(value)+'</strong><p>'+esc(detail)+'</p></div>';
  }
  function distributionBar(label,value,cls){
    const width=Math.max(0,Math.min(100,Number(value)||0));
    return '<div class="mf-bar"><span>'+esc(label)+'</span><div class="mf-track">'+
      '<div class="mf-fill '+(cls||'')+'" style="width:'+width+'%"></div></div>'+
      '<strong>'+esc(width.toLocaleString('vi-VN',{maximumFractionDigits:1}))+'%</strong></div>';
  }
  function draw(){
    if(!active)return;
    [...buttons.querySelectorAll('[data-mf-horizon]')].forEach(btn=>{
      const yes=btn.dataset.mfHorizon===horizon;
      btn.classList.toggle('active',yes);
      btn.setAttribute('aria-pressed',String(yes));
    });
    if(!loaded){
      output.innerHTML='<div class="mf-empty">Chưa tải được báo cáo phân tích biến động giá từ Render. Dữ liệu lịch sử và dự báo không được tự dựng hoặc thay bằng số mô phỏng.</div>';
      return;
    }
    const report=loaded;
    const selected=report.horizons?.[horizon];
    if(!selected){
      output.innerHTML='<div class="mf-empty">Chưa có dữ liệu lịch sử cho khung '+esc(horizon)+' tháng.</div>';
      return;
    }
    const approved=selected.status==='approved'&&
      Number.isFinite(Number(selected.forecast_change_pct))&&
      selected.forecast_change_pct!==null;
    const hist=selected.historical_change_pct;
    const histText=hist===null?'Chưa đủ dữ liệu':percent(hist);
    const forecastText=approved?percent(selected.forecast_change_pct):'Chưa đủ chuẩn';
    const statement=approved?
      'Dự báo thị trường ghép cặp đã cải thiện trên tập kiểm thử theo thời gian. Đây không phải mức tăng bắt buộc của mọi loại thuốc.':
      'Chưa có dự báo tương lai vượt kiểm định độc lập. Số liệu bên cạnh phản ánh biến động đã quan sát trong lịch sử, không phải mức tăng dự báo.';
    const index=approved?(100*(1+Number(selected.forecast_change_pct)/100)).toLocaleString('vi-VN',{maximumFractionDigits:2}):'—';
    const statuses={approved:'Đã đạt kiểm định',rejected_validation:'Không vượt đối chứng ở validation',
      rejected_quality_gate:'Không đạt kiểm định ngoài mẫu',insufficient_history:'Thiếu lịch sử lặp lại'};
    let table='<div class="mf-panel"><h3>So sánh theo khung thời gian</h3>'+
      '<p class="mf-muted">Giá trị phần trăm là chỉ số biến động của giá kê khai ghép cặp, không phải trung bình giá VND từ các đơn vị thuốc khác nhau.</p>'+
      '<div class="mf-table-wrap"><table class="mf-horizon-table"><thead><tr>'+
      '<th>Khung</th><th>Lịch sử (%)</th><th>Dự báo tương lai</th><th>Cặp giá</th><th>Đánh giá</th>'+
      '</tr></thead><tbody>';
    for(const h of ['1','3','6','12']){
      const item=report.horizons?.[h]||{};
      table+='<tr data-mf-row="'+h+'" tabindex="0" role="button" aria-label="Xem '+h+' tháng"'+(h===horizon?' class="selected"':'')+'>'+
        '<td><strong>'+h+' tháng</strong></td>'+
        '<td>'+esc(percent(item.historical_change_pct))+'</td>'+
        '<td>'+esc(item.status==='approved'?percent(item.forecast_change_pct):'Chưa đạt')+'</td>'+
        '<td>'+esc(number(item.n_pairs))+'</td>'+
        '<td><span class="mf-status '+(item.status==='approved'?'approved':'unapproved')+'">'+
           esc(item.status==='approved'?'Đạt':'Chưa đạt')+'</span></td></tr>';
    }
    table+='</tbody></table></div></div>';
    output.innerHTML=
      '<div class="mf-summary">'+
        card('Biến động lịch sử · '+horizon+' tháng',histText,
          'Bình quân log-ratio đã giới hạn ảnh hưởng ngoại lệ; không phải dự báo.',valueClass(hist))+
        card('Xu hướng dự báo · '+horizon+' tháng',forecastText,
          'Chỉ hiển thị % nếu vượt kiểm định so với giả định không đổi.',approved?valueClass(selected.forecast_change_pct):'')+
        card('Độ phủ lịch sử',number(selected.n_pairs)+' cặp',
          number(selected.n_series)+' chuỗi cùng số đăng ký, loại giá và đơn vị.')+
      '</div>'+
      '<div class="mf-panels">'+
        '<section class="mf-panel"><h3>Cơ cấu biến động giá đã quan sát</h3>'+
          '<p class="mf-muted">So sánh chính sản phẩm giữa hai lần kê khai cách nhau xấp xỉ '+horizon+' tháng.</p>'+
          distributionBar('Tăng giá',selected.share_up_pct,'')+
          distributionBar('Giảm giá',selected.share_down_pct,'down')+
          distributionBar('Giữ nguyên',selected.share_unchanged_pct,'flat')+
          '<div class="mf-legend">Phân vị P10 <b>'+esc(percent(selected.p10_change_pct))+
           '</b> · Phân vị P90 <b>'+esc(percent(selected.p90_change_pct))+'</b></div></section>'+
        '<section class="mf-panel"><h3>Chỉ số dự báo thị trường</h3>'+
          '<p class="mf-muted">Chỉ số giá tham chiếu = 100 tại thời điểm hiện tại, chỉ tính khi forecast được phê duyệt.</p>'+
          '<div class="mf-index"><span class="mf-status '+(approved?'approved':'unapproved')+'">'+
            esc(statuses[selected.status]||selected.status||'Chưa đủ dữ liệu')+'</span>'+
            '<strong>'+esc(index)+'</strong>'+
            '<small>'+esc(statement)+'</small></div></section></div>'+
      table+
      '<div class="mf-panel"><h3>Phương pháp và kiểm định</h3>'+
        '<p class="mf-muted">'+esc(report.methodology||'Dữ liệu từ giá kê khai ghép cặp.')+'</p>'+
        '<div class="mf-legend"><span>Cặp giá được xét: <b>'+esc(number(report.paired_observations))+'</b></span>'+
        '<span>Kiểm thử cho mốc này: <b>'+esc(number(selected.n_test))+'</b> mẫu</span>'+
        '<span>Cải thiện test: <b>'+
         esc(selected.test_gain_fraction===null||selected.test_gain_fraction===undefined?'Chưa có':
             percent(Number(selected.test_gain_fraction)*100))+
        '</b></span></div></div>';
  }
  async function fetchReport(force=false){
    if(loading||(!force&&loaded))return;
    loading=true;
    status.textContent='Đang tải báo cáo biến động giá thực tế…';
    try {
      const response=await fetch('/api/market-forecast',{cache:'no-store'});
      const data=await response.json();
      if(!response.ok||data.kind!=='market-declaration-price-trend')throw Error(data.notice||data.detail||'Báo cáo chưa sẵn sàng');
      loaded=data;
      updated.textContent='Báo cáo '+new Date(data.generated_at).toLocaleString('vi-VN');
      const qualified=data.approved_horizons||[];
      status.textContent='Dữ liệu ghép cặp từ Neon Gold · '+number(data.paired_observations)+
        ' cặp giá lịch sử · '+qualified.length+' / 4 khung dự báo đạt kiểm định.';
    } catch(e) {
      loaded=null;
      updated.textContent='Chưa có báo cáo mới';
      status.textContent='Chưa tải được báo cáo thị trường: '+String(e.message||'Không kết nối được Render');
    } finally {loading=false;draw();}
  }
  buttons.addEventListener('click',e=>{
    const btn=e.target.closest('[data-mf-horizon]');
    if(!btn)return;
    horizon=btn.dataset.mfHorizon;draw();
  });
  output.addEventListener('click',e=>{
    const row=e.target.closest('[data-mf-row]');
    if(row){horizon=row.dataset.mfRow;draw();}
  });
  output.addEventListener('keydown',e=>{
    if(e.key!=='Enter'&&e.key!==' ')return;
    const row=e.target.closest('[data-mf-row]');
    if(row){e.preventDefault();horizon=row.dataset.mfRow;draw();}
  });
  document.addEventListener('pharmabiz:market-view',e=>{
    active=!!e.detail?.active;
    if(active){draw();fetchReport();}
  });
  document.addEventListener('pharmabiz:market-refresh',()=>{loaded=null;if(active)fetchReport(true);});
})();
