(() => {
  'use strict';
  const host=document.getElementById('market-forecast-panel');
  if(!host)return;
  const $=id=>document.getElementById(id);
  const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','"':'&quot;'}[c]));
  const integer=x=>Number(x||0).toLocaleString('vi-VN',{maximumFractionDigits:0});
  const pct=x=>!Number.isFinite(Number(x))||x==null?'—':(Number(x)>0?'+':'')+Number(x).toLocaleString('vi-VN',{maximumFractionDigits:2})+'%';
  const sharePct=x=>window.PharmaCharts.percent(x,1);
  const n=x=>typeof x==='number'&&Number.isFinite(x)?x:0;
  let report=null,active=false,horizon=6,loading=false;

  const hasNumber=value=>typeof value==='number'&&Number.isFinite(value);
  function badge(status,experimental) {
    return status==='approved'
      ?'<span class="market-chip market-chip-ok">Đã vượt kiểm định</span>'
      :experimental
        ?'<span class="market-chip market-chip-neutral">Thử nghiệm · Chưa vượt kiểm định</span>'
        :'<span class="market-chip market-chip-neutral">Chỉ có dữ liệu lịch sử</span>';
  }
  const qualityReason=item=>item.status==='approved'?'Dự báo đã vượt kiểm định trên tập test độc lập theo thời gian.':({
    NO_DIRECTIONAL_SIGNAL:'Mô hình chưa tìm được tín hiệu tăng/giảm tốt hơn giả định giá giữ nguyên trên tập xác thực.',
    VALIDATION_NOT_BETTER_THAN_BASELINE:'Tập xác thực chưa cải thiện ít nhất 1% so với giả định giá không đổi.',
    INSUFFICIENT_DISTINCT_TEST_DRUGS:'Tập kiểm định chưa có đủ số đăng ký thuốc phân biệt.',
    TEST_NOT_BETTER_THAN_BASELINE:'Tập kiểm định độc lập chưa cải thiện ít nhất 1% so với giá không đổi.',
    NO_VALIDATION_IMPROVEMENT:'Cả ba mô hình đều không cải thiện tối thiểu 1% so với baseline trên các vòng validation.',
    INSUFFICIENT_CHRONOLOGICAL_HOLDOUT:'Chưa đủ mẫu test độc lập về thời gian và mã thuốc.',
    INSUFFICIENT_WALK_FORWARD_HISTORY:'Không tạo được tối thiểu hai vòng kiểm định cuốn chiếu đạt yêu cầu.',
    INSUFFICIENT_CURRENT_REFERENCE:'Thiếu ít nhất 15 mã thuốc kê khai lặp lại để xuất bản tỷ lệ dự báo chung.'
  }[item.reason]||(item.status==='insufficient_history'
    ?'Chưa có đủ chuỗi giá được tách theo thời gian để huấn luyện và kiểm định cho kỳ hạn này.'
    :'Mô hình chưa vượt kiểm định độc lập; dữ liệu lịch sử vẫn có thể được sử dụng.'));
  const modelNames={time_weighted:'Xu hướng trọng số thời gian',hierarchical:'Mô hình phân cấp nhóm thuốc',temporal_ridge:'Hồi quy có yếu tố thời gian'};
  function validationPanel(item){
    const comparisons=item.model_comparison||[];
    if(!comparisons.length){
      return '<p class="market-muted">'+esc(qualityReason(item))+
        ' Thống kê lịch sử vẫn được hiển thị độc lập.</p>'+
        '<p class="market-footnote">Mẫu train: '+integer(item.n_train)+' · validation: '+integer(item.n_validation)+
        ' · test: '+integer(item.n_test)+' · vòng cuốn chiếu: '+integer(item.n_walkforward_folds)+'</p>';
    }
    const entries=comparisons.map(model=>'<tr><td>'+esc(modelNames[model.name]||model.name)+'</td>'+
      '<td>'+esc(Number(model.validation_log_mae).toFixed(5))+'</td>'+
      '<td>'+pct(model.validation_gain_pct)+'</td></tr>').join('');
    const hasTest=typeof item.test_gain_fraction==='number';
    const ci=item.test_gain_ci95_pct_points;
    const sampleCI=item.forecast_sample_ci90_pct;
    const chosen=item.selected_model?esc(modelNames[item.selected_model]||item.selected_model):'Chưa chọn';
    return '<div class="market-qa-grid">'+
      '<div><span>Validation cuốn chiếu</span><strong>'+integer(item.n_walkforward_folds)+' vòng / '+integer(item.n_validation)+' mẫu</strong></div>'+
      '<div><span>Test độc lập</span><strong>'+integer(item.n_test)+' mẫu</strong></div>'+
      '<div><span>Ứng viên được chọn</span><strong>'+chosen+'</strong></div>'+
      '<div><span>Mức cải thiện trên test</span><strong>'+(hasTest?pct(item.test_gain_fraction*100):'Chưa kiểm định')+'</strong></div>'+
      '</div>'+
      '<div class="market-model-scroll"><table class="market-model-table"><thead><tr>'+
      '<th>Mô hình</th><th>Validation log-MAE</th><th>So với baseline</th></tr></thead><tbody>'+
      '<tr><td>Giữ nguyên giá (baseline)</td><td>'+esc(Number(item.validation_baseline_log_mae||0).toFixed(5))+'</td><td>0%</td></tr>'+
      entries+'</tbody></table></div>'+
      '<p class="market-footnote"><strong>Độ bất định:</strong> '+
      (hasTest&&Array.isArray(ci)?'Khoảng bootstrap 95% cho mức cải thiện MAE trên test: '+pct(ci[0])+' đến '+pct(ci[1])+'. ':'Chưa đủ điều kiện ước lượng khoảng cải thiện trên test. ')+
      (item.status==='approved'&&Array.isArray(sampleCI)?'Khoảng bootstrap 90% của trung bình dự báo trên tập thuốc tham chiếu: '+pct(sampleCI[0])+' đến '+pct(sampleCI[1])+'. ':'')+
      'Đây là độ bất định do lấy mẫu; không phải khoảng dự báo giá cho từng thuốc.</p>'+
      '<p class="market-footnote">'+esc(qualityReason(item))+'</p>';
  }
  function render(){
    if(!active)return;
    if(!report){return;}
    $('market-source').textContent='Neon Gold · '+integer(report.source_records)+' bản ghi giá nguồn · '+
      integer(report.labeled_pairs)+' cặp lịch sử theo thời gian';
    $('market-updated').textContent='Phiên bản dữ liệu: '+esc(report.version||'—');
    const approved=report.approved_horizons||[];
    const indicative=[3,6,12].filter(h=>hasNumber(report.horizons?.[String(h)]?.experimental_change_pct));
    $('market-summary').innerHTML='<article class="market-stat"><span>Khung thời gian phân tích</span><strong>3 · 6 · 12 tháng</strong><small>So sánh cùng thuốc, loại giá và đơn vị</small></article>'+
      '<article class="market-stat"><span>Cặp giá lịch sử</span><strong>'+integer(report.labeled_pairs)+'</strong><small>Chỉ gồm các lần kê khai có thật</small></article>'+
      '<article class="market-stat"><span>Chất lượng mô hình</span><strong>'+approved.length+'/3 đạt chuẩn</strong><small>'+indicative.length+' thời hạn có ước tính thử nghiệm chưa kiểm định đạt</small></article>';
    $('market-horizons').innerHTML=[3,6,12].map(h=>{
      const item=report.horizons?.[String(h)]||{};
      const good=item.status==='approved' && hasNumber(item.forecast_change_pct);
      const experimental=!good && hasNumber(item.experimental_change_pct);
      const shown=good?item.forecast_change_pct:experimental?item.experimental_change_pct:item.historical_change_pct;
      const indicator=good?'Đã kiểm định':experimental?'Thử nghiệm':'Lịch sử';
      const indicatorClass=good?'':experimental?' experimental':'';
      const context=good?'Dự báo đã vượt kiểm định':experimental?'Ước tính chưa đạt kiểm định':'Trung vị biến động lịch sử';
      return '<button type="button" class="market-horizon '+(h===horizon?'is-active':'')+
        '" data-market-horizon="'+h+'" aria-pressed="'+(h===horizon)+'" aria-label="'+h+' tháng: '+esc(context)+', '+pct(shown)+'">'+
        '<span class="market-horizon-top"><span class="market-horizon-icon" aria-hidden="true">▦</span>'+
        '<span class="market-horizon-tag'+indicatorClass+'">'+indicator+'</span></span>'+
        '<span class="market-horizon-name">Xu hướng giá '+h+' tháng</span>'+
        '<strong class="market-horizon-value '+(shown>=0?'up':'down')+'">'+pct(shown)+'</strong>'+
        '<span class="market-horizon-label">'+context+'</span>'+
        '<span class="market-horizon-footer"><span>'+integer(item.n_products)+' mã thuốc trong lịch sử</span><b aria-hidden="true">↗</b></span></button>';
    }).join('');
    const item=report.horizons?.[String(horizon)]||{};
    const valid=item.status==='approved' && hasNumber(item.forecast_change_pct);
    const experimental=!valid&&hasNumber(item.experimental_change_pct);
    $('market-selected-horizon').textContent=horizon+' tháng';
    $('market-model-status').innerHTML=badge(item.status,experimental);
    $('market-main-number').textContent=pct(valid?item.forecast_change_pct:experimental?item.experimental_change_pct:item.historical_change_pct);
    $('market-main-caption').textContent=valid
      ?'Dự báo biến động giá kê khai của tập thuốc tham chiếu — đã vượt kiểm định'
      :experimental
        ?'Ước tính mô hình thử nghiệm trên dữ liệu giá thật — CHƯA VƯỢT KIỂM ĐỊNH'
        :'Trung vị biến động đã ghi nhận trong lịch sử — không phải dự báo';
    $('market-forecast-note').innerHTML=valid
      ?'<strong>Đã vượt ngưỡng kiểm định:</strong> mức cải thiện log-MAE so với giá không đổi là '+pct(n(item.test_gain_fraction)*100)+'. Không phải giá bán lẻ.'
      :experimental
        ?'<strong>⚠ CHƯA VƯỢT KIỂM ĐỊNH — KHÔNG DÙNG ĐỂ QUYẾT ĐỊNH:</strong> Đây là ước tính thử nghiệm, không phải dự báo tương lai đã được chứng minh. '+esc(qualityReason(item))+' Trung vị thay đổi lịch sử của cùng kỳ: <strong>'+pct(item.historical_change_pct)+'</strong>.'
        :'<strong>⚠ Chưa có ước tính dự báo đủ điều kiện:</strong> '+esc(qualityReason(item))+' Số đang hiển thị là trung vị biến động lịch sử, không phải dự báo.';
    $('market-coverage').textContent=integer(item.n_products)+' mã thuốc · '+integer(item.n_pairs)+' cặp giá đã ghi nhận';
    $('market-dates').textContent=(item.observed_from||'—')+' → '+(item.observed_to||'—');
    $('market-band').textContent=pct(item.p10_pct)+' đến '+pct(item.p90_pct);
    const parts=[
      {name:'Tăng > 1%',value:n(item.share_increase_pct),kind:'up'},
      {name:'Gần như giữ nguyên (±1%)',value:n(item.share_stable_pct),kind:'stable'},
      {name:'Giảm > 1%',value:n(item.share_decrease_pct),kind:'down'}
    ];
    const up=Math.min(100,Math.max(0,n(item.share_increase_pct)));
    const stable=Math.min(100,Math.max(0,n(item.share_stable_pct)));
    $('market-distribution').innerHTML=parts.some(part=>part.value>0)?
      '<div class="market-distribution-layout">'+
      '<div class="market-donut" role="img" aria-label="Tỷ lệ tăng '+sharePct(up)+', giữ nguyên '+sharePct(stable)+
      ', giảm '+sharePct(item.share_decrease_pct)+'" style="--market-increase:'+up+'%;--market-stable-end:'+
      Math.min(100,up+stable)+'%"><div class="market-donut-center"><strong>'+
      integer(item.n_products)+'</strong><span>mã thuốc</span></div></div>'+
      '<div class="market-donut-legend">'+parts.map(p=>
        '<div class="market-distribution-line"><div class="market-distribution-title"><span>'+esc(p.name)+
        '</span><strong>'+sharePct(p.value)+'</strong></div>'+
        '<div class="market-track" tabindex="0" data-tip="'+esc(p.name)+'" data-value="'+sharePct(p.value)+' số thuốc trong lịch sử"><div class="market-track-fill '+p.kind+
        '" style="width:'+Math.min(100,Math.max(0,p.value))+'%"></div></div></div>'
      ).join('')+'</div></div>':'<p class="market-muted">Chưa có số cặp giá lịch sử để tính tỷ trọng tăng, giữ nguyên và giảm.</p>';
    const timeline=item.yearly_history||[];
    const max=Math.max(5,...timeline.map(x=>Math.abs(n(x.median_change_pct))));
    $('market-timeline').innerHTML=timeline.length
      ?timeline.map(row=>{
        const amount=n(row.median_change_pct);
        const span=Math.round(Math.abs(amount)/max*48);
        return '<div class="market-timeline-row"><span class="market-year">'+row.year+'</span>'+
          '<div class="market-timeline-track" tabindex="0" data-tip="Năm '+row.year+'" data-value="Trung vị '+pct(amount)+' · '+integer(row.n_products)+' thuốc"><div class="market-axis"></div><span class="market-timebar '+(amount>=0?'up':'down')+
          '" style="width:'+span+'%;'+(amount>=0?'left:50%':'right:50%')+'"></span></div>'+
          '<strong>'+pct(amount)+'</strong><small>'+integer(row.n_products)+' thuốc</small></div>';
      }).join('')
      :'<p class="market-muted">Chưa đủ số cặp kê khai theo từng năm để hiển thị xu hướng dài hạn.</p>';
    $('market-validation').innerHTML=validationPanel(item);
    $('market-method').textContent='Mỗi cặp so sánh cùng số đăng ký, loại giá và đơn vị. '+
      'Các thuốc không có nhiều lần kê khai không được đưa vào chỉ số thay đổi. Mỗi số đăng ký có trọng số ngang nhau trong thống kê hiện tại. '+
      'Khoảng P10–P90 mô tả phân phối thay đổi lịch sử; không phải khoảng tin cậy của dự báo. '+
      'Không phản ánh doanh số, giá bán lẻ hay chỉ số lạm phát chung.';
  }
  async function load(force=false) {
    if(loading||(!force&&report))return;
    loading=true;
    $('market-message').classList.remove('market-error','market-warning');
    $('market-message').textContent='Đang tải báo cáo thị trường từ dữ liệu DAV…';
    try{
      const res=await fetch('/api/market-forecast',{cache:'no-store'});
      const payload=await res.json();
      if(!res.ok||payload.kind!=='dav-market-price-trend')throw Error(payload.notice||'Báo cáo thị trường chưa được công bố');
      report=payload;
      const nExperimental=[3,6,12].filter(h=>hasNumber(report.horizons?.[String(h)]?.experimental_change_pct)).length;
      const nav=document.querySelector('#nav [data-view="market-forecast"]');
      if(nav){
        nav.title=report.historical_only?'Chưa vượt kiểm định: có thể xem lịch sử và ước tính thử nghiệm':'Đã có dự báo vượt kiểm định';
        nav.classList.toggle('market-nav-unvalidated',Boolean(report.historical_only));
        const arrow=nav.querySelector('.nav-arrow');
        if(arrow)arrow.textContent=report.historical_only?'⚠':'↗';
      }
      $('market-message').classList.toggle('market-warning',Boolean(report.historical_only));
      $('market-message').textContent=report.historical_only
        ?(nExperimental
           ?'Đã tải dữ liệu thật: '+nExperimental+' khung thời gian có ước tính thử nghiệm CHƯA vượt kiểm định. Xem cảnh báo ở từng thẻ.'
           :'Đã tải dữ liệu lịch sử; chưa đủ bằng chứng để đưa ra ước tính thử nghiệm đáng dùng. Bạn vẫn xem được thống kê 3/6/12 tháng.')
        :'Đã tải báo cáo giá thuốc; các dự báo đạt chuẩn và ước tính thử nghiệm được phân biệt rõ.';
      render();
    }catch(error){
      $('market-message').classList.add('market-error');
      $('market-message').textContent='Không thể kết nối báo cáo: '+String(error.message||'Lỗi kết nối')+
        '. Mục dự báo vẫn mở; thử bấm “Cập nhật báo cáo” hoặc kiểm tra lại máy chủ Render.';
    }finally{loading=false}
  }
  host.addEventListener('click',e=>{
    const choice=e.target.closest('[data-market-horizon]');
    if(choice){horizon=Number(choice.dataset.marketHorizon);render();}
    if(e.target.closest('[data-market-reload]'))load(true);
  });
  document.addEventListener('pharmabiz:market-forecast-view',event=>{
    active=Boolean(event.detail?.active);
    host.hidden=!active;
    if(active){if(report)render();else load();}
  });
})();
