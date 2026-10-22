'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const api=require('../api/market-forecast.js');
const legacy=require('../api/forecast-price.js');
const response=()=>({code:null,payload:null,headers:{},
  setHeader(key,value){this.headers[key]=value;return this;},
  status(n){this.code=n;return this;},
  json(data){this.payload=data;return this;}
});

test('Dashboard exposes aggregate trends across 3, 6 and 12 months, not drug-level AI prices',()=>{
  const file=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8');
  const html=file('index.html'),controller=file('assets/presentation.js');
  const ui=file('assets/market-forecast.js'),lookup=file('assets/drug-lookup.js');
  assert.match(html,/id="market-forecast-panel"/);
  assert.match(html,/id="market-horizons"/);
  assert.match(html,/assets\/market-forecast\.js/);
  assert.match(html,/assets\/market-forecast\.css/);
  assert.match(controller,/\['market-forecast'/);
  assert.match(controller,/pharmabiz:market-forecast-view/);
  assert.match(ui,/\[3,6,12\]/);
  assert.match(ui,/historical_change_pct/);
  assert.match(ui,/forecast_change_pct/);
  assert.match(ui,/status==='approved'/);
  assert.match(lookup,/data-view="market-forecast"/);
  assert.doesNotMatch(lookup,/data-forecast-horizon=/);
  assert.doesNotMatch(lookup,/api\/forecast-price/);
});

test('Old per-drug forecast API explicitly returns 410 and never estimates medicine prices',async()=>{
  const res=response();
  await legacy({method:'POST'},res);
  assert.equal(res.code,410);
  assert.equal(res.payload.error,'INDIVIDUAL_DRUG_FORECAST_RETIRED');
});

test('Market dashboard API does not accept individual-drug POST requests',async()=>{
  const res=response();
  await api({method:'POST'},res);
  assert.equal(res.code,405);
});

test('Market dashboard requires trusted Render hostname',async()=>{
  const previous=process.env.ML_PRICE_API_URL;
  process.env.ML_PRICE_API_URL='https://attacker.example.com';
  try{
    const res=response();
    await api({method:'GET'},res);
    assert.equal(res.code,503);
    assert.equal(res.payload.error,'MARKET_API_HOST_NOT_ALLOWED');
  }finally{
    if(previous===undefined)delete process.env.ML_PRICE_API_URL;
    else process.env.ML_PRICE_API_URL=previous;
  }
});
