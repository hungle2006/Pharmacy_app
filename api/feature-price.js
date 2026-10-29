'use strict';
// Public experiment report; validated small feature requests only. No SQL writes.
const FIELDS=['ingredient','strength','dosage_form','manufacturer','country','package'];
function validate(body){
 if(!body||typeof body!=='object'||Array.isArray(body))return null;
 const keys=['price_type','unit',...FIELDS];
 if(Object.keys(body).some(k=>!keys.includes(k)))return null;
 const data={};for(const key of keys){const value=body[key]??'';if(typeof value!=='string'||value.length>(FIELDS.includes(key)?2048:key==='unit'?100:200))return null;data[key]=value.trim();}
 if(!data.price_type||!data.unit||!data.ingredient)return null;
 return data;
}
async function handler(req,res){
 const posting=req.method==='POST';res.setHeader('Cache-Control',posting?'no-store':'public, max-age=30, s-maxage=60');
 if(!['GET','POST'].includes(req.method))return res.status(405).json({error:'METHOD_NOT_ALLOWED'});
 let base;try{base=new URL(process.env.ML_PRICE_API_URL)}catch{return res.status(503).json({error:'FEATURE_API_NOT_CONFIGURED'});}
 if(base.protocol!=='https:'||!base.hostname.endsWith('.onrender.com'))return res.status(503).json({error:'FEATURE_HOST_NOT_ALLOWED'});
 let payload;if(posting){
  if(Number(req.headers?.['content-length']||0)>65536)return res.status(413).json({error:'INPUT_TOO_LARGE'});
  let body=req.body;try{if(typeof body==='string')body=JSON.parse(body)}catch{return res.status(400).json({error:'INVALID_FEATURES'});}
  payload=validate(body);if(!payload)return res.status(400).json({error:'INVALID_FEATURES'});
  if(!process.env.ML_API_KEY)return res.status(503).json({error:'FEATURE_API_NOT_CONFIGURED'});
 }
 try{
  const upstream=await fetch(new URL(posting?'/feature-price/predict':'/feature-price/report',base),{
   method:posting?'POST':'GET',headers:posting?{'Accept':'application/json','Content-Type':'application/json','X-API-Key':process.env.ML_API_KEY}:{'Accept':'application/json'},
   ...(posting?{body:JSON.stringify(payload)}:{}),signal:AbortSignal.timeout(45000)
  });
  const result=await upstream.json();
  if(!upstream.ok){const known=['UNKNOWN_INGREDIENT','UNSUPPORTED_PRICE_SEGMENT'];const code=typeof result.detail==='string'&&known.includes(result.detail)?result.detail:'FEATURE_SERVICE_UNAVAILABLE';return res.status(known.includes(code)?422:503).json({error:code});}
  if(result.kind!=='dav-feature-price'||!result.version||(!posting&&(!Array.isArray(result.segments)||result.schema_version!==1)))return res.status(503).json({error:'INVALID_FEATURE_REPORT'});
  if(posting&&(!['prediction_vnd','lower_vnd','upper_vnd'].every(k=>Number.isFinite(result[k])&&result[k]>=0)||result.lower_vnd>result.prediction_vnd||result.upper_vnd<result.prediction_vnd||!['approved','experimental'].includes(result.status)))return res.status(503).json({error:'INVALID_FEATURE_RESULT'});
  return res.status(200).json(result);
 }catch(e){console.error('Feature price service unavailable:',e?.name||'unknown');return res.status(503).json({error:'FEATURE_SERVICE_UNAVAILABLE'});}
}
module.exports=handler;module.exports.validate=validate;
