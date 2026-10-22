'use strict';
// Per-drug forecasts have been retired. Use the market outlook dashboard.
module.exports=async function retired(req,res){
  res.setHeader('Cache-Control','no-store');
  return res.status(410).json({error:'PER_DRUG_FORECAST_RETIRED',
    notice:'Dự báo theo từng thuốc đã được thay bằng dashboard xu hướng giá chung.'});
};
