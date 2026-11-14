'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {groupOther,monthIndex,recent,spreads,completeness,niceMonthlyScale,monthInVietnam}=require('../assets/task-depth');
test('composition grouping reconciles the whole population without mutating the source',()=>{
 const rows=Array.from({length:12},(_,i)=>({name:'Group '+i,value:i+1})),copy=JSON.stringify(rows);
 const grouped=groupOther(rows,5);
 assert.equal(grouped.length,5);assert.equal(grouped.reduce((s,r)=>s+r.value,0),78);
 assert.equal(grouped.at(-1).other,true);assert.equal(JSON.stringify(rows),copy);
});
test('monthly windows use elapsed calendar time and preserve gaps across years',()=>{
 assert.equal(monthIndex('2026-01')-monthIndex('2025-12'),1);
 const rows=[{name:'2025-12'},{name:'2026-01'},{name:'2026-04'}];
 assert.deepEqual(recent(rows,3),[{name:'2026-04'}]);assert.equal(recent(rows,'all').length,3);
});
test('normalized price intervals exclude unusable denominators and preserve asymmetric bounds',()=>{
 const rows=spreads([{median:0,p10:0,p90:3},{median:null,p10:1,p90:3},{median:10,p10:5,p90:30}]);
 assert.equal(rows.length,1);assert.equal(rows[0].low,50);assert.equal(rows[0].high,300);
});
test('missing field priorities preserve overlapping denominators instead of summing failed products',()=>{
 const q={total:10,drug_name:10,ingredient:9,strength:6,dosage_form:3,manufacturer:10,country:7,unit:10};
 const rows=completeness(q);assert.equal(rows[0].key,'dosage_form');assert.equal(rows[0].missing,7);
 assert.equal(rows.find(r=>r.key==='strength').missing,4);assert.equal(q.total,10);
});

test('monthly Y axis uses readable increments and keeps every bar clear of the Y labels',()=>{
 assert.deepEqual(niceMonthlyScale(2500),{step:500,ticks:5,max:2500});
 assert.deepEqual(niceMonthlyScale(2514),{step:500,ticks:6,max:3000});
 assert.deepEqual(niceMonthlyScale(1160),{step:250,ticks:5,max:1250});
 const src=require('node:fs').readFileSync(require('node:path').join(__dirname,'../assets/task-depth.js'),'utf8');
 assert.match(src,/left=166,right=1046/);
 assert.match(src,/monthIndex\(r\.name\)-minMonth\+\.5/);
 assert.match(src,/depth-monthly-current-tag/);
 assert.match(src,/height="'\+Math\.max\(0,bottom-yy\)\+'/);
 assert.match(src,/Đang cập nhật/);
});
test('partial month is evaluated in Vietnam local time, not browser locale',()=>{
 assert.equal(monthInVietnam(new Date('2026-10-31T18:30:00Z')),'2026-11');
 assert.equal(monthInVietnam(new Date('2026-11-30T16:00:00Z')),'2026-11');
 assert.equal(monthInVietnam(new Date('2026-11-30T17:00:00Z')),'2026-12');
});
