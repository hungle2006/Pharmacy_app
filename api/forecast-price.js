'use strict';
// Compatibility response. Individual-drug price forecasting has been retired.
module.exports=async function handler(req,res){
  res.setHeader('Cache-Control','no-store');
  return res.status(410).json({
    error:'INDIVIDUAL_DRUG_FORECAST_RETIRED',
    notice:'Tính năng dự báo giá từng thuốc đã ngừng. Sử dụng dashboard Dự báo thị trường thuốc.',
    dashboard:'/ ?view=market-forecast'.replace(' ','')
  });
};
