'use strict';
// This read-only route exposes only public aggregate data and validated
// percentage forecasts. It never accepts product identifiers or prices.
module.exports=async function handler(req,res){
  res.setHeader('Cache-Control','public, max-age=60, s-maxage=180');
  if(req.method!=='GET')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
  const base=process.env.ML_PRICE_API_URL;
  if(!base)return res.status(503).json({error:'MARKET_API_NOT_CONFIGURED'});
  let upstream;try{upstream=new URL(base)}
  catch{return res.status(503).json({error:'INVALID_MARKET_API_URL'})}
  if(upstream.protocol!=='https:'||!upstream.hostname.endsWith('.onrender.com'))
    return res.status(503).json({error:'MARKET_API_HOST_NOT_ALLOWED'});
  try{
    const response=await fetch(new URL('/market-forecast',upstream),{
      method:'GET',headers:{'Accept':'application/json'},
      signal:AbortSignal.timeout(25000),
    });
    const report=await response.json();
    if(!response.ok)return res.status(503).json({
      error:'MARKET_REPORT_NOT_READY',
      notice:'Báo cáo thị trường chưa sẵn sàng; vui lòng thử lại.'
    });
    if(report?.schema_version!==1||report?.kind!=='dav-market-price-trend'
      ||typeof report.horizons!=='object'||!report.horizons)
      return res.status(503).json({error:'INVALID_MARKET_REPORT'});
    return res.status(200).json(report);
  }catch(e){
    console.error('Market report proxy unavailable:',e?.name||'unknown');
    return res.status(503).json({
      error:'MARKET_SERVER_UNAVAILABLE',
      notice:'Chưa kết nối được báo cáo xu hướng giá thuốc.'
    });
  }
};
