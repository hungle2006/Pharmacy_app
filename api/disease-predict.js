'use strict';
// Server-only proxy. Never expose Render credentials or forward raw upstream errors.
function validate(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body) || Object.keys(body).some(k=>!['text','top_k'].includes(k))) return null;
  if (typeof body.text !== 'string') return null;
  const text=body.text.trim(), top_k=body.top_k??5;
  if (text.length<5 || text.length>4000 || !Number.isInteger(top_k) || top_k<1 || top_k>10) return null;
  return {text,top_k};
}
function cleanPredictions(data) {
  if (!data || data.score_type!=='uncalibrated_softmax' || typeof data.model_run!=='string' || !Array.isArray(data.predictions) || !data.predictions.length || data.predictions.length>10) return null;
  const predictions=[];
  for (const p of data.predictions) {
    if(typeof p.label!=='string' || !p.label.trim() || p.label.length>500 || typeof p.score!=='number' || !Number.isFinite(p.score) || p.score<0 || p.score>1) return null;
    predictions.push({label:p.label,score:p.score});
  }
  return {model_run:data.model_run.slice(0,200),predictions:predictions.sort((a,b)=>b.score-a.score),score_type:'uncalibrated_softmax',scope:'research_only'};
}
function cleanReport(d) {
  if(!d || !['ready','not_trained'].includes(d.status))return null;
  if(d.status==='not_trained')return {status:d.status};
  if(typeof d.model_run!=='string'||!d.metrics||typeof d.metrics!=='object')return null;
  const metrics={};
  for(const split of ['validation','test']) {
    metrics[split]={};
    for(const metric of ['accuracy','macro_f1','balanced_accuracy','top3_accuracy','top5_accuracy']) {
      const v=d.metrics[split]?.[metric];
      if(typeof v==='number' && Number.isFinite(v) && v>=0 && v<=1)metrics[split][metric]=v;
    }
  }
  return {status:'ready',model_run:d.model_run.slice(0,200),dataset_revision:String(d.dataset_revision||'').slice(0,100),benchmark_sha256:String(d.benchmark_sha256||'').slice(0,100),metrics};
}
async function handler(req,res) {
  res.setHeader('Cache-Control','private, no-store');res.setHeader('X-Content-Type-Options','nosniff');
  if(!['GET','POST'].includes(req.method)){res.setHeader('Allow','GET, POST');return res.status(405).json({error:'METHOD_NOT_ALLOWED'});}
  let payload;
  if(req.method==='POST') {
    if(Number(req.headers?.['content-length']||0)>24000)return res.status(413).json({error:'INPUT_TOO_LARGE'});
    let body=req.body;try{if(typeof body==='string')body=JSON.parse(body);}catch{return res.status(400).json({error:'INVALID_INPUT'});}
    payload=validate(body);if(!payload)return res.status(400).json({error:'INVALID_INPUT'});
  }
  let base;try{base=new URL(process.env.DISEASE_API_URL);}catch{return res.status(503).json({error:'DISEASE_API_NOT_CONFIGURED'});}
  if(base.protocol!=='https:' || !base.hostname.endsWith('.onrender.com') || base.username || base.password || base.port || !process.env.DISEASE_API_KEY)return res.status(503).json({error:'DISEASE_API_NOT_CONFIGURED'});
  try {
    const upstream=await fetch(new URL(payload?'/predict':'/report',base),{method:payload?'POST':'GET',headers:{Accept:'application/json','X-API-Key':process.env.DISEASE_API_KEY,...(payload?{'Content-Type':'application/json'}:{})},...(payload?{body:JSON.stringify(payload)}:{}),redirect:'error',signal:AbortSignal.timeout(50000)});
    if(!upstream.ok)return res.status(503).json({error:'DISEASE_SERVICE_UNAVAILABLE'});
    const data=await upstream.json(),result=payload?cleanPredictions(data):cleanReport(data);
    if(!result)return res.status(502).json({error:'INVALID_MODEL_RESPONSE'});
    return res.status(200).json(result);
  }catch(e){return res.status(e?.name==='TimeoutError'?504:503).json({error:e?.name==='TimeoutError'?'MODEL_TIMEOUT':'DISEASE_SERVICE_UNAVAILABLE'});}
}
module.exports=handler;module.exports.validate=validate;module.exports.cleanPredictions=cleanPredictions;module.exports.cleanReport=cleanReport;
