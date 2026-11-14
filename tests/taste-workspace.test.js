'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {priceBandSeries,groupOther}=require('../assets/task-depth');

const read=relative=>fs.readFileSync(path.join(__dirname,'..',relative),'utf8');

test('price band dot chart preserves irregular-bin counts without pretending equal-width density',()=>{
 const input=[{bucket:0,value:11},{bucket:2,value:5},{bucket:5,value:3}];
 const original=JSON.stringify(input);
 const rows=priceBandSeries(input);
 assert.equal(rows.length,6);
 assert.deepEqual(rows.map(row=>row.value),[11,0,5,0,0,3]);
 assert.equal(rows.reduce((total,row)=>total+row.value,0),19);
 assert.match(rows[0].name,/1\.000/);
 assert.match(rows[5].name,/100\.000/);
 assert.equal(JSON.stringify(input),original);
});

test('price bands reject unrelated buckets and keep zero observations separate from missing chart',()=>{
 const rows=priceBandSeries([{bucket:-1,value:12},{bucket:8,value:99},{bucket:3,value:-9},{bucket:4,value:2}]);
 assert.deepEqual(rows.map(row=>row.value),[0,0,0,0,2,0]);
});

test('proportional category grouping keeps every observation in a mutually-exclusive remainder',()=>{
 const rows=Array.from({length:7},(_,i)=>({name:'Category '+i,value:10+i}));
 const grouped=groupOther(rows,6);
 assert.equal(grouped.length,6);
 assert.equal(grouped.reduce((sum,row)=>sum+row.value,0),rows.reduce((sum,row)=>sum+row.value,0));
 assert.equal(grouped.at(-1).other,true);
});

test('all task views load the new chart and workspace styling after the earlier styles',()=>{
 const html=read('index.html');
 const base=html.indexOf('assets/workspace-a.css');
 const focus=html.indexOf('assets/focus-workspace.css');
 const newSheet=html.indexOf('assets/taste-workspace.css');
 assert.ok(base>=0&&focus>base&&newSheet>focus);
 const css=read('assets/taste-workspace.css');
 for(const name of ['taste-mosaic','taste-lollipop','taste-time-stem','taste-funnel','taste-price-interval']){
  assert.ok(css.includes(name),'missing visual family: '+name);
 }
 assert.match(css,/@media\(max-width:375px\)/);
});

test('new chart families are rendered from real data and an uncertainty interval',()=>{
 const depth=read('assets/task-depth.js');
 const explore=read('assets/data-exploration.js');
 const feature=read('assets/feature-price.js');
 assert.match(depth,/priceBandSeries\(d\.bins\)/);
 assert.match(depth,/function mix\(rows,total\)/);
 assert.match(explore,/function funnel\(rows,total,unit/);
 assert.match(explore,/values\.some\(\(v,i\)=>i>0&&v>values\[i-1\]\)/);
 assert.match(feature,/intervalVisual\(d\)/);
});
