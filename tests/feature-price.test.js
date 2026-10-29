'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const api=require('../api/feature-price');
const res=()=>({code:null,data:null,headers:{},setHeader(k,v){this.headers[k]=v;},status(n){this.code=n;return this;},json(x){this.data=x;return this;}});
const input={price_type:'EXPECTED_WHOLESALE_PRICE_VAT',unit:'viên',ingredient:'Paracetamol',strength:'500 mg'};
test('feature inputs exclude targets and identifiers and reject invalid types or oversized fields',()=>{
 assert.equal(api.validate({...input,price_vnd:5000}),null);assert.equal(api.validate({...input,registration_number:'VN-1'}),null);
 assert.equal(api.validate({...input,ingredient:4}),null);assert.equal(api.validate({...input,strength:'a'.repeat(2049)}),null);
 assert.equal(api.validate({...input,ingredient:'   '}),null);assert.equal(api.validate([]),null);
 assert.equal(api.validate(input).ingredient,'Paracetamol');assert.equal(api.validate(input).manufacturer,'');
});
test('feature proxy validates before forwarding, protects the upstream key, and preserves declared units',async()=>{
 const original={fetch:global.fetch,url:process.env.ML_PRICE_API_URL,key:process.env.ML_API_KEY};
 process.env.ML_PRICE_API_URL='https://pharmabiz-price-ml.onrender.com';process.env.ML_API_KEY='test-key';let calls=0;
 try{
  global.fetch=async(url,options)=>{calls++;assert.equal(new URL(url).pathname,'/feature-price/predict');assert.equal(options.headers['X-API-Key'],'test-key');assert.equal(JSON.parse(options.body).unit,'viên');return {ok:true,json:async()=>({kind:'dav-feature-price',version:'v1',prediction_vnd:1234,status:'experimental',lower_vnd:300,upper_vnd:9000})};};
  let r=res();await api({method:'POST',body:{...input,price_vnd:1000}},r);assert.equal(r.code,400);assert.equal(calls,0);
  r=res();await api({method:'POST',body:input},r);assert.equal(r.code,200);assert.equal(r.data.prediction_vnd,1234);assert.equal(r.headers['Cache-Control'],'no-store');assert.ok(!JSON.stringify(r.data).includes('test-key'));
  global.fetch=async()=>({ok:false,json:async()=>({detail:'UNKNOWN_INGREDIENT'})});r=res();await api({method:'POST',body:input},r);assert.equal(r.code,422);assert.equal(r.data.error,'UNKNOWN_INGREDIENT');
  global.fetch=async()=>({ok:false,json:async()=>({detail:'private internal reason'})});r=res();await api({method:'POST',body:input},r);assert.equal(r.code,503);assert.equal(r.data.error,'FEATURE_SERVICE_UNAVAILABLE');
  process.env.ML_PRICE_API_URL='https://untrusted.example';r=res();await api({method:'GET'},r);assert.equal(r.code,503);
 }finally{global.fetch=original.fetch;for(const [key,value] of [['ML_PRICE_API_URL',original.url],['ML_API_KEY',original.key]]){if(value===undefined)delete process.env[key];else process.env[key]=value;}}
});
test('feature reports reject invalid schema and unsupported methods while retaining unavailable state',async()=>{
 const fetch=global.fetch,url=process.env.ML_PRICE_API_URL;process.env.ML_PRICE_API_URL='https://pharmabiz-price-ml.onrender.com';
 try{let r=res();await api({method:'DELETE'},r);assert.equal(r.code,405);
 global.fetch=async()=>({ok:true,json:async()=>({kind:'wrong',version:'v1',segments:[]})});r=res();await api({method:'GET'},r);assert.equal(r.code,503);
 global.fetch=async()=>{throw Error('upstream unavailable')};r=res();await api({method:'GET'},r);assert.equal(r.code,503);
 }finally{global.fetch=fetch;if(url===undefined)delete process.env.ML_PRICE_API_URL;else process.env.ML_PRICE_API_URL=url;}
});
