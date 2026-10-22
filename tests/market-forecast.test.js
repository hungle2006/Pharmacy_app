'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'..',name),'utf8');

test('market forecasting is a dedicated navigation dashboard',()=>{
  const html=read('index.html');
  const app=read('assets/presentation.js');
  const market=read('assets/market-forecast.js');
  assert.match(html,/id="market-forecast-panel"/);
  assert.match(html,/assets\/market-forecast\.js/);
  assert.match(html,/assets\/market-forecast\.css/);
  assert.match(app,/market-forecast','↗','Dự báo xu hướng giá/);
  assert.match(market,/data-mf-horizon/);
  for(const h of ['1','3','6','12'])assert.match(html,new RegExp('data-mf-horizon="'+h+'"'));
});
test('DAV no longer predicts prices for individual medicines',()=>{
  const lookup=read('assets/drug-lookup.js');
  assert.doesNotMatch(lookup,/\/api\/forecast-price/);
  assert.doesNotMatch(lookup,/data-forecast-horizon/);
  assert.match(lookup,/data-view="market-forecast"/);
});
test('legacy per-drug endpoint retires with HTTP 410',async()=>{
  const retired=require('../api/forecast-price.js');
  const r={status(code){this.code=code;return this;},
    setHeader(){},json(payload){this.body=payload;return this;}};
  await retired({method:'POST'},r);
  assert.equal(r.code,410);
  assert.equal(r.body.error,'PER_DRUG_FORECAST_RETIRED');
});
test('market trend proxy rejects mutation methods',async()=>{
  const handler=require('../api/market-forecast.js');
  const r={status(code){this.code=code;return this;},
    setHeader(){},json(payload){this.body=payload;return this;}};
  await handler({method:'POST'},r);
  assert.equal(r.code,405);
});
