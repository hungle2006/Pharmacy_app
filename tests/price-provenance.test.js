'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {PGlite}=require('@electric-sql/pglite');
const {buildQuery}=require('../api/data');
const {buildQuery:analytics}=require('../api/analytics');

test('known numeric-ID collisions keep raw history but never serve a foreign legacy price',async()=>{
  const db=new PGlite();
  try {
    await db.exec(`
      CREATE TABLE dav_product(dav_row_id text,registration_number text,drug_name text,
        active_ingredient_raw text,strength_raw text,dosage_form_raw text,
        manufacturer text,country text,unit text,package text,source text,
        catalog_duplicate_status text,catalog_equivalent_to text);
      CREATE TABLE price_record(price_id text,dav_row_id text,price_vnd bigint,currency text,
        price_type text,declaration_date date,unit text,package text,source text);
      INSERT INTO dav_product(dav_row_id,drug_name,source) VALUES
        ('1','Current tablet','SILVER_R2'),('2','Unpriced current product','SILVER_R2');
      INSERT INTO price_record VALUES
        ('current','1',1000,'VND','KK','2025-01-01','tablet','box','SILVER_DAV_PRICE'),
        ('foreign','1',90000,'VND','wholesale','2026-01-01','mCi','vial','DAV_PUBLIC_DRUG_PRICE');
    `);
    const query=buildQuery({mode:'products'});
    const rows=(await db.query(query.rowsSql,query.params)).rows;
    assert.equal(Number(rows.find(r=>r.id==='1').price_vnd),1000);
    assert.equal(rows.find(r=>r.id==='2').price_vnd,null);
    const q=analytics({});
    const result=(await db.query(q.text,q.params)).rows[0];
    assert.equal(Number(result.summary.priced),1);
    assert.equal(Number(result.summary.median),1000);
    assert.equal(Number((await db.query('SELECT COUNT(*) AS n FROM price_record')).rows[0].n),2);
    await db.exec(`ALTER TABLE price_record ADD COLUMN source_observed_at timestamptz;
      INSERT INTO price_record(price_id,dav_row_id,price_vnd,currency,price_type,unit,source,source_observed_at)
      VALUES ('revised','1',1200,'VND','KK','tablet','SILVER_DAV_PRICE','2026-11-13T00:00:00Z');`);
    const revised=(await db.query(query.rowsSql,query.params)).rows.find(r=>r.id==='1');
    assert.equal(Number(revised.price_vnd),1200);
    assert.equal(revised.snapshot_date,null); // Never invent a filing date from observation time.

  } finally {await db.close();}
});
