'use strict';
// Secrets remain on Vercel; no Render API key is sent to the browser.
module.exports = async function handler(req,res) {
  res.setHeader('Cache-Control','private, no-store');
  if(req.method!=='POST')return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
  const base=process.env.ML_PRICE_API_URL||'',key=process.env.ML_API_KEY||'';
  if(!base||!key)return res.status(503).json({error:'ML_SERVER_NOT_CONFIGURED',notice:'Render ML API chưa được kết nối.'});
  let u;try{u=new URL(base)}catch{return res.status(503).json({error:'INVALID_ML_SERVER_URL'})}
  if(u.protocol!=='https:'||!u.hostname.endsWith('.onrender.com'))
    return res.status(503).json({error:'ML_SERVER_HOST_NOT_ALLOWED'});
  let body;try{body=typeof req.body==='string'?JSON.parse(req.body):req.body}
  catch{return res.status(400).json({error:'INVALID_JSON'})}
  if(!body||typeof body!=='object'||Array.isArray(body)||JSON.stringify(body).length>4000)
    return res.status(400).json({error:'INVALID_INPUT'});
  const names=['ingredient','strength','dosage_form','manufacturer','country','package','price_type','unit'];
  if(names.some(n=>typeof body[n]!=='string'||body[n].length>300))
    return res.status(400).json({error:'INVALID_FEATURES'});
  try {
    const response=await fetch(new URL('/predict-price',u),{
      method:'POST',signal:AbortSignal.timeout(25000),
      headers:{'Content-Type':'application/json','X-API-Key':key},
      body:JSON.stringify(Object.fromEntries(names.map(n=>[n,body[n]])))
    });
    const result=await response.json();
    return res.status(response.status).json(result);
  }catch(e) {
    console.error('ML proxy unavailable',e?.name||'unknown');
    return res.status(503).json({error:'ML_SERVER_UNAVAILABLE',notice:'Render có thể đang khởi động. Vui lòng thử lại.'});
  }
};
