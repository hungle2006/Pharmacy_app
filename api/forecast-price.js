'use strict';
// Only the server-to-server proxy carries the private Render API key.
module.exports = async function handler(req,res) {
  res.setHeader('Cache-Control','private, no-store');
  if(req.method!=='POST')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
  const base=process.env.ML_PRICE_API_URL||'',key=process.env.ML_API_KEY||'';
  if(!base||!key)return res.status(503).json({error:'FORECAST_SERVER_NOT_CONFIGURED'});
  let target;try{target=new URL(base)}catch{return res.status(503).json({error:'INVALID_FORECAST_SERVER_URL'})}
  if(target.protocol!=='https:'||!target.hostname.endsWith('.onrender.com'))
    return res.status(503).json({error:'FORECAST_HOST_NOT_ALLOWED'});
  let data;try{data=typeof req.body==='string'?JSON.parse(req.body):req.body}
  catch{return res.status(400).json({error:'INVALID_JSON'})}
  if(!data||Array.isArray(data)||typeof data!=='object'||JSON.stringify(data).length>4000)
    return res.status(400).json({error:'INVALID_INPUT'});
  const names=['ingredient','strength','dosage_form','manufacturer','country','package','price_type','unit'];
  if(names.some(n=>typeof data[n]!=='string'||data[n].length>300))
    return res.status(400).json({error:'INVALID_FEATURES'});
  const ageDate=data.latest_price_date;
  if(typeof ageDate!=='string'||!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(ageDate))
    return res.status(400).json({error:'INVALID_PRICE_DATE'});
  if(typeof data.latest_price_vnd!=='number'||!Number.isFinite(data.latest_price_vnd)
      ||data.latest_price_vnd<=0||data.latest_price_vnd>1e10)
    return res.status(400).json({error:'INVALID_BASE_PRICE'});
  if(![3,6,12].includes(data.horizon_months))return res.status(400).json({error:'INVALID_HORIZON'});
  try{
    const response=await fetch(new URL('/forecast-price',target),{
      method:'POST',signal:AbortSignal.timeout(25000),
      headers:{'Content-Type':'application/json','X-API-Key':key},
      body:JSON.stringify({...Object.fromEntries(names.map(n=>[n,data[n]])),
                            latest_price_vnd:data.latest_price_vnd,
                            latest_price_date:ageDate,horizon_months:data.horizon_months})
    });
    const result=await response.json();
    return res.status(response.status).json(result);
  }catch(e){
    console.error('Forecast proxy unavailable',e?.name||'unknown');
    return res.status(503).json({error:'FORECAST_SERVER_UNAVAILABLE',
      notice:'Máy chủ dự báo chưa sẵn sàng. Vui lòng thử lại sau.'});
  }
};
