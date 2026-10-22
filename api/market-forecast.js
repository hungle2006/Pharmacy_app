'use strict';
// Aggregate public market statistics; no individual drug/price details or secrets.
module.exports=async function marketForecast(req,res){
  res.setHeader('Cache-Control','public, max-age=120, stale-while-revalidate=180');
  if(req.method!=='GET')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
  const base=process.env.ML_PRICE_API_URL||'';
  let url;
  try{url=new URL(base)}
  catch{return res.status(503).json({error:'MARKET_SERVICE_NOT_CONFIGURED'})}
  if(url.protocol!=='https:'||!url.hostname.endsWith('.onrender.com'))
    return res.status(503).json({error:'MARKET_SERVICE_HOST_INVALID'});
  try{
    const response=await fetch(new URL('/market-forecast',url),{
      signal:AbortSignal.timeout(25000),
      headers:{'Accept':'application/json'}});
    const result=await response.json();
    if(response.ok&&result.kind!=='market-declaration-price-trend')
      return res.status(502).json({error:'MARKET_REPORT_FORMAT_INVALID'});
    return res.status(response.status).json(result);
  }catch(e){
    console.error('Market trend service unreachable',e?.name||'unknown');
    return res.status(503).json({error:'MARKET_REPORT_UNAVAILABLE',
      notice:'Báo cáo thị trường chưa sẵn sàng.'});
  }
};
