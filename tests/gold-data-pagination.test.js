'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const { PGlite }=require('@electric-sql/pglite');
const data=require('../api/data');
const rxnorm=require('../api/rxnorm');

test('Gold records are paginated across row 2000 without global truncation',async()=>{
  const db=new PGlite();
  try {
    await db.exec([
      "CREATE TABLE dav_product (dav_row_id text primary key,drug_name text,",
      "active_ingredient_raw text,strength_raw text,dosage_form_raw text,",
      "manufacturer text,country text,registration_number text,",
      "source text,catalog_duplicate_status text,catalog_equivalent_to text,",
      "unit text,package text);",
      "CREATE TABLE price_record (price_id text primary key,dav_row_id text,",
      "price_vnd bigint,currency text,price_type text,declaration_date date,",
      "unit text,package text);",
      "INSERT INTO dav_product ",
      "(dav_row_id,drug_name,active_ingredient_raw,strength_raw,dosage_form_raw,",
      "manufacturer,country,registration_number,source,unit,package)",
      "SELECT 'P'||LPAD(i::text,5,'0'),'Drug '||i,'test ingredient','500 MG',",
      "'Oral Tablet','Test manufacturer','Việt Nam','VD'||i,'SILVER_R2',",
      "'tablet','box' FROM generate_series(1,2105) i;",
      "INSERT INTO price_record",
      "(price_id,dav_row_id,price_vnd,currency,price_type,declaration_date)",
      "SELECT 'price'||i,'P'||LPAD(i::text,5,'0'),i,'VND','KKL','2026-10-20'",
      "FROM generate_series(1,2105) i;"
    ].join(' '));
    const get=async (page)=>{
      const query=data.buildQuery({page:String(page),pageSize:'100'});
      const count=await db.query(query.countSql,query.countParams);
      const rows=await db.query(query.rowsSql,query.params);
      return {query,total:Number(count.rows[0].total_rows),records:rows.rows};
    };
    const first=await get(1),twenty=await get(20),twentyOne=await get(21),last=await get(22);
    assert.equal(first.total,2105);
    assert.equal(first.records.length,100);
    assert.equal(twenty.records.length,100);
    assert.equal(twentyOne.records.length,100);
    assert.equal(twentyOne.records[0].id,'P02001');
    assert.equal(last.records.length,5);
    assert.equal(last.records.at(-1).id,'P02105');
    const any=await db.query(data.buildQuery({q:'Drug 210',pageSize:100}).countSql,
      data.buildQuery({q:'Drug 210',pageSize:100}).countParams);
    assert.equal(Number(any.rows[0].total_rows),6);
  } finally { await db.close(); }
});

test('Data pagination bounds inputs and uses parameters instead of interpolation',()=>{
  const injected="x%' OR 1=1 --";
  const built=data.buildQuery({page:'2;DROP TABLE dav_product',pageSize:'50000',q:injected,
    ingredient:'Amoxicillin',currentOnly:'true'});
  assert.equal(built.page,1);
  assert.equal(built.pageSize,200);
  assert(!built.rowsSql.includes(injected));
  assert(built.rowsSql.includes('LIMIT $3 OFFSET $4'));
  assert(!built.rowsSql.includes('LIMIT 2000'));
  assert.deepEqual(built.countParams,['%'+injected.replace(/[\\%_]/g,'\\$&')+'%','Amoxicillin']);
  assert.equal(built.params.at(-2),200);
  assert.equal(built.params.at(-1),0);
  assert.match(built.countSql,/COUNT\(\*\)::bigint AS total_rows/);
  assert.match(built.rowsSql,/catalog_duplicate_status/);
});

test('RxNorm search is also parameterized and can reach any page',async()=>{
  const q=rxnorm.buildConceptQuery({q:"acetaminophen%' OR true --",page:'5',pageSize:'9999'});
  assert(!q.rowsSql.includes("OR true --"));
  assert.equal(q.page,5);
  assert.equal(q.pageSize,100);
  assert.equal(q.params[3],400);
  assert.equal(rxnorm.buildConceptQuery({q:'  '}),null);
  const db=new PGlite();
  try {
    await db.exec([
      "CREATE TABLE rxnorm_concept (rxcui text primary key,canonical_name text,",
      "canonical_tty text, canonical_sab text,tty_set text,sab_set text,",
      "is_ingredient integer,is_scd integer);",
      "CREATE TABLE rxnorm_scd (scd_rxcui text primary key,scd_name text,",
      "component_count integer,component_status text,dose_form_name text);",
      "INSERT INTO rxnorm_concept VALUES",
      "('161','acetaminophen','IN','RXNORM','IN','RXNORM',1,0),",
      "('162','acetaminophen 500 MG Oral Tablet','SCD','RXNORM','SCD','RXNORM',0,1);",
      "INSERT INTO rxnorm_scd VALUES ('162','acetaminophen 500 MG Oral Tablet',1,",
      "'TEXT_INFERRED_REVIEW','Oral Tablet');"
    ].join(' '));
    const find=rxnorm.buildConceptQuery({q:'acetaminophen'});
    const c=await db.query(find.countSql,find.countParams);
    const result=await db.query(find.rowsSql,find.params);
    assert.equal(Number(c.rows[0].total_rows),2);
    assert.equal(result.rows.length,2);
    assert(result.rows.some(x=>x.rxcui==='162'&&x.scd_name.includes('Oral Tablet')));
  } finally {await db.close();}
});

test('both APIs fail closed without Neon connection credentials',async()=>{
  const prior=process.env.DATABASE_URL;
  delete process.env.DATABASE_URL;
  const res=()=>({setHeader(){},status(code){this.code=code;return this;},
    json(payload){this.payload=payload;return this;}});
  try {
    for(const handler of [data,rxnorm]) {
      const r=res();
      await handler({method:'GET',query:{}},r);
      assert.equal(r.code,503);
      assert.equal(r.payload.reason,'DATABASE_URL_MISSING');
      const other=res();
      await handler({method:'POST',query:{}},other);
      assert.equal(other.code,405);
    }
  } finally {
    if(prior===undefined)delete process.env.DATABASE_URL;
    else process.env.DATABASE_URL=prior;
  }
});
