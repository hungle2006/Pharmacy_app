'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {PGlite}=require('@electric-sql/pglite');
const handler=require('../api/report-data');
const {catalog,buildProfileQuery}=handler;
test('report profiles restrict tables and identifiers to the declared public data catalog',()=>{
 assert.equal(Object.keys(catalog).length,9);
 for(const name of ['dav_product; DROP TABLE disease','__proto__','users','constructor'])assert.throws(()=>buildProfileQuery(name,[]),/INVALID_TABLE/);
 const built=buildProfileQuery('disease',[{name:'icd_code',type:'text'},{name:'chapter_code',type:'text'}]);
 assert.doesNotMatch(built.text,/AVG\(/);assert.match(built.text,/COUNT\(DISTINCT/);
});
test('report statistics preserve all rows while numeric price statistics exclude non-VND, negative and missing prices',async()=>{
 const db=new PGlite();try{
  await db.exec(`CREATE TABLE price_record(price_vnd numeric,currency text,unit text,price_type text,declaration_date date);
 INSERT INTO price_record VALUES (1000,'VND','viên','A','2026-01-01'),(3000,'VND','viên','A','2026-02-01'),(0,NULL,'ống','B',NULL),(-1,'VND','viên','A',NULL),(50,'USD','hộp','B',NULL),(NULL,'VND','  ','B',NULL);`);
  const cols=['price_vnd','currency','unit','price_type','declaration_date'].map(name=>({name,type:name==='price_vnd'?'numeric':'text'}));
  const {text,params}=buildProfileQuery('price_record',cols);const r=(await db.query(text,params)).rows[0];
  assert.equal(Number(r.summary.total),6);assert.equal(Number(r.summary.n),3);assert.equal(Number(r.summary.mean),4000/3);assert.equal(Number(r.summary.p2),1000);assert.equal(Number(r.summary.m2),1);
  assert.equal(r.distribution.reduce((s,r)=>s+Number(r.value),0),6);assert.equal(r.bins.reduce((s,r)=>s+Number(r.value),0),3);assert.equal(r.timeline.reduce((s,r)=>s+Number(r.value),0),2);
 }finally{await db.close();}
});
test('empty table has zero counts and unavailable numeric statistics, never fabricated zero prices',async()=>{
 const db=new PGlite();try{
 await db.exec('CREATE TABLE price_record(price_vnd numeric,currency text);');
 const q=buildProfileQuery('price_record',[{name:'price_vnd',type:'numeric'},{name:'currency',type:'text'}]);const r=(await db.query(q.text,q.params)).rows[0];
 assert.equal(Number(r.summary.total),0);assert.equal(Number(r.summary.n),0);assert.equal(r.summary.mean,null);assert.deepEqual(r.bins,[]);
 }finally{await db.close();}
});
test('report endpoints reject writes and unknown table names before any database operation',async()=>{
 const response=()=>({setHeader(){},status(n){this.code=n;return this;},json(v){this.value=v;return this;}});
 let r=response();await handler({method:'POST',query:{table:'dav_product'}},r);assert.equal(r.code,405);
 r=response();await handler({method:'GET',query:{table:'secret'}},r);assert.equal(r.code,400);
});
