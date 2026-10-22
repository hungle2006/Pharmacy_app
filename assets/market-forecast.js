(() => {
  'use strict';
  const host=document.getElementById('market-forecast-panel');
  if(!host)return;
  const $=id=>document.getElementById(id);
  const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','"':'&quot;'}[c]));
  const integer=x=>Number(x||0).toLocaleString('vi-VN',{maximumFractionDigits:0});
  const pct=x=>!Number.isFinite(Number(x))||x==null?'—':(Number(x)>0?'+':'')+Number(x).toLocaleString('vi-VN',{maximumFractionDigits:2})+'%';
  const n=x=>typeof x==='number'&&Number.isFinite(x)?x:0;
  let report=null,active=false,horizon=6,loading=false;

  function badge(status) {
    return status==='approved'
      ?'<span class="market-chip market-chip-ok">Đã vượt kiểm định</span>'
      :'<span class="market-chip market-chip-neutral">Chưa có dự báo đạt chuẩn</span>';
  }
  const qualityReason=item=>({
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
    $('market-summary').innerHTML='<article class="market-stat"><span>Khung thời gian phân tích</span><strong>3 · 6 · 12 tháng</strong><small>So sánh cùng thuốc, loại giá và đơn vị</small></article>'+
      '<article class="market-stat"><span>Cặp giá lịch sử</span><strong>'+integer(report.labeled_pairs)+'</strong><small>Chỉ gồm các lần kê khai có thật</small></article>'+
      '<article class="market-stat"><span>Thời hạn đạt chuẩn dự báo</span><strong>'+approved.length+'/3</strong><small>Đối chiếu với giả định giá không đổi</small></article>';
    $('market-horizons').innerHTML=[3,6,12].map(h=>{
      const item=report.horizons?.[String(h)]||{};
      const good=item.status==='approved' && typeof item.forecast_change_pct==='number';
      return '<button type="button" class="market-horizon '+(h===horizon?'is-active':'')+
        '" data-market-horizon="'+h+'" aria-pressed="'+(h===horizon)+'">'+
        '<span class="market-horizon-head"><span>0'+([3,6,12].indexOf(h)+1)+' / '+h+' THÁNG</span><span aria-hidden="true">↗</span></span>'+
        '<strong class="market-horizon-value '+(good?(item.forecast_change_pct>=0?'up':'down'):'')+'">'+
        (good?pct(item.forecast_change_pct):pct(item.historical_change_pct))+'</strong>'+
        '<span class="market-horizon-label">'+(good?'Dự báo tỷ lệ biến động toàn thị trường':'Trung vị thay đổi trong lịch sử')+'</span>'+
        '<span class="market-horizon-footer">'+integer(item.n_products)+' mã thuốc tham chiếu · '+
        (good?'Dự báo đã kiểm định':'Chỉ số lịch sử, không phải dự báo')+'</span></button>';
    }).join('');
    const item=report.horizons?.[String(horizon)]||{};
    const valid=item.status==='approved' && typeof item.forecast_change_pct==='number';
    $('market-selected-horizon').textContent=horizon+' tháng';
    $('market-model-status').innerHTML=badge(item.status);
    $('market-main-number').textContent=valid?pct(item.forecast_change_pct):pct(item.historical_change_pct);
    $('market-main-caption').textContent=valid
      ?'Dự báo thay đổi giá kê khai trung bình cho nhóm thuốc có lịch sử lặp lại'
      :'Trung vị biến động đã ghi nhận trong lịch sử — không phải tỷ lệ tăng giá được dự báo';
    $('market-forecast-note').innerHTML=valid
      ?'<strong>Dự báo thử nghiệm đã đạt ngưỡng:</strong> MAE trên biến động log tốt hơn giữ nguyên giá '+pct(n(item.test_gain_fraction)*100)+'. Kết quả không đại diện giá bán lẻ hay mọi thuốc.'
      :'<strong>Chưa có dự báo tương lai đáng tin cậy:</strong> '+esc(qualityReason(item))+' Các con số đang hiển thị chỉ là thống kê lịch sử.';
    $('market-coverage').textContent=integer(item.n_products)+' mã thuốc · '+integer(item.n_pairs)+' cặp giá đã ghi nhận';
    $('market-dates').textContent=(item.observed_from||'—')+' → '+(item.observed_to||'—');
    $('market-band').textContent=pct(item.p10_pct)+' đến '+pct(item.p90_pct);
    const parts=[
      {name:'Tăng > 1%',value:n(item.share_increase_pct),kind:'up'},
      {name:'Gần như giữ nguyên (±1%)',value:n(item.share_stable_pct),kind:'stable'},
      {name:'Giảm > 1%',value:n(item.share_decrease_pct),kind:'down'}
    ];
    $('market-distribution').innerHTML=parts.map(p=>
      '<div class="market-distribution-line"><div class="market-distribution-title"><span>'+esc(p.name)+'</span><strong>'+pct(p.value)+'</strong></div>'+
      '<div class="market-track"><div class="market-track-fill '+p.kind+'" style="width:'+Math.min(100,Math.max(0,p.value))+'%"></div></div></div>'
    ).join('');
    const timeline=item.yearly_history||[];
    const max=Math.max(5,...timeline.map(x=>Math.abs(n(x.median_change_pct))));
    $('market-timeline').innerHTML=timeline.length
      ?timeline.map(row=>{
        const amount=n(row.median_change_pct);
        const span=Math.round(Math.abs(amount)/max*48);
        return '<div class="market-timeline-row"><span class="market-year">'+row.year+'</span>'+
          '<div class="market-timeline-track"><div class="market-axis"></div><span class="market-timebar '+(amount>=0?'up':'down')+
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
    $('market-message').textContent='Đang tải báo cáo xu hướng thị trường từ Render / Cloudflare R2…';
    try{
      const res=await fetch('/api/market-forecast',{cache:'no-store'});
      const payload=await res.json();
      if(!res.ok||payload.kind!=='dav-market-price-trend')throw Error(payload.notice||'Báo cáo thị trường chưa được công bố');
      report=payload;
      $('market-message').textContent=report.historical_only
        ?'Đã tải số liệu lịch sử. Chưa có thời hạn dự báo nào vượt kiểm định.'
        :'Đã tải báo cáo thị trường; chỉ các dự báo đạt chuẩn được hiển thị là dự báo tương lai.';
      render();
    }catch(error){
      $('market-message').textContent='Chưa tải được báo cáo: '+String(error.message||'Lỗi kết nối')+'. Dữ liệu sẽ hiển thị khi GitHub xuất bản báo cáo lên R2.';
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
