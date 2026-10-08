const test=require('node:test');
const assert=require('node:assert/strict');
const {PGlite}=require('@electric-sql/pglite');
const {buildQuery}=require('../api/analytics');
test('PostgreSQL aggregation handles multiple prices, missing prices, filters and equivalent groups',async()=>{
 const db=new PGlite();
 try{
  await db.exec(`CREATE TABLE dav_product(dav_row_id text,registration_number text,drug_name text,active_ingredient_raw text,strength_raw text,dosage_form_raw text,manufacturer text,country text,unit text,package text);
  CREATE TABLE price_record(price_id text,dav_row_id text,price_vnd bigint,currency text,price_type text,declaration_date date,unit text,package text);
  INSERT INTO dav_product VALUES ('d1','r1','Drug A','Ingredient A','500mg','Tablet','Maker A','Việt Nam','Tablet','10 tablets'),('d2','r2','Drug B','Ingredient A','500mg','Tablet','Maker B','Việt Nam','Tablet','10 tablets'),('d3','r3','Drug C','Ingredient C',NULL,NULL,'Maker C','France',NULL,NULL);
  INSERT INTO price_record VALUES ('p1','d1',1000,'VND','declared','2026-01-02','Tablet','10 tablets'),('p2','d1',2000,'VND','declared','2026-02-02','Tablet','10 tablets'),('p3','d2',3000,'VND','declared','2026-02-05','Tablet','10 tablets'),('p4','d2',99,'USD','declared','2026-03-05','Tablet','10 tablets');`);
  let q=buildQuery({});let r=(await db.query(q.text,q.params)).rows[0];
  assert.equal(Number(r.summary.products),3);assert.equal(Number(r.summary.observations),5);assert.equal(Number(r.summary.priced),3);assert.equal(Number(r.summary.median),2000);
  assert.equal(Number(r.countries.find(x=>x.name==='Việt Nam').value),2);assert.equal(r.comparable.length,1);assert.equal(Number(r.comparable[0].products),2);assert.equal(Number(r.comparable[0].observations),3);
  const missing=r.records.find(x=>x.id==='d3');assert.equal(missing.price_vnd,null);
  q=buildQuery({country:'France'});r=(await db.query(q.text,q.params)).rows[0];assert.equal(Number(r.summary.products),1);assert.equal(r.summary.median,null);assert.equal(r.bins.length,0);
  q=buildQuery({country:'Unknown'});r=(await db.query(q.text,q.params)).rows[0];assert.equal(Number(r.summary.products),0);assert.equal(r.records.length,0);
  q=buildQuery({q:"'); DROP TABLE dav_product; --"});r=(await db.query(q.text,q.params)).rows[0];assert.equal(Number(r.summary.products),0);assert.equal(Number((await db.query('SELECT COUNT(*) AS n FROM dav_product')).rows[0].n),3);
  q=buildQuery({page:2});r=(await db.query(q.text,q.params)).rows[0];assert.equal(r.records.length,0);assert.equal(Number(r.summary.products),3);
  q=buildQuery({unit:'Tablet',kind:'declared'});r=(await db.query(q.text,q.params)).rows[0];assert.equal(Number(r.summary.products),2);
 }finally{await db.close();}
});
