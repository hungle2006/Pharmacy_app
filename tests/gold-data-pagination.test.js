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
    assert.equal(Number(any.rows[0].total_rows),7);
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
  // PostgreSQL HTTP drivers may decode raw DATE as JavaScript Date.
  // Explicit ISO formatting prevents values like 'Thu Aug 27' with no year.
  assert(built.rowsSql.includes("TO_CHAR(p.declaration_date::date, 'YYYY-MM-DD') AS snapshot_date"));
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

test('Drug lookup returns one product per card with the newest price, while preserving observation mode',async()=>{
  const db=new PGlite();
  try{
    await db.exec([
      "CREATE TABLE dav_product (dav_row_id text primary key,drug_name text,",
      "active_ingredient_raw text,strength_raw text,dosage_form_raw text,manufacturer text,",
      "country text,registration_number text,source text,catalog_duplicate_status text,",
      "catalog_equivalent_to text,unit text,package text);",
      "CREATE TABLE price_record (price_id text primary key,dav_row_id text,price_vnd bigint,",
      "currency text,price_type text,declaration_date date,unit text,package text);",
      "INSERT INTO dav_product (dav_row_id,drug_name,source) VALUES",
      "('A','Drug A','SILVER_R2'),('B','Drug B','SILVER_R2');",
      "INSERT INTO price_record (price_id,dav_row_id,price_vnd,currency,declaration_date)",
      "VALUES ('old','A',1000,'VND','2024-01-01'),",
      "('new','A',2000,'VND','2026-10-21');"
    ].join(' '));
    const obs=data.buildQuery({pageSize:'10'});
    const product=data.buildQuery({mode:'products',pageSize:'10',currentOnly:'true'});
    const observationCount=await db.query(obs.countSql,obs.countParams);
    const productCount=await db.query(product.countSql,product.countParams);
    assert.equal(Number(observationCount.rows[0].total_rows),3);
    assert.equal(Number(productCount.rows[0].total_rows),2);
    const onePerDrug=await db.query(product.rowsSql,product.params);
    assert.equal(onePerDrug.rows.length,2);
    assert.equal(onePerDrug.rows[0].id,'A');
    assert.equal(onePerDrug.rows[0].price_id,'new');
    assert.equal(onePerDrug.rows[0].snapshot_date,'2026-10-21');
    assert.equal(onePerDrug.rows[0].snapshot_date.length,10);
    assert.equal(onePerDrug.rows[1].id,'B');
    assert.equal(onePerDrug.rows[1].price_vnd,null);
  }finally{await db.close();}
});

test('Drug Lookup workspace is wired into navigation and usable on phones',()=>{
  const fs=require('node:fs');
  const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
  const app=fs.readFileSync(require('node:path').join(__dirname,'../assets/presentation.js'),'utf8');
  const lookup=fs.readFileSync(require('node:path').join(__dirname,'../assets/drug-lookup.js'),'utf8');
  const css=fs.readFileSync(require('node:path').join(__dirname,'../assets/drug-lookup.css'),'utf8');
  for(const id of ['start-lookup','lookup-panel','lookup-form','lookup-search','lookup-results',
    'lookup-details','lookup-tab-dav','lookup-tab-rx','lookup-prev','lookup-next'])
    assert.match(html,new RegExp('id="'+id+'"'));
  assert.match(app,/\['lookup','⌕','Tra cứu thuốc'/);
  assert.match(app,/pharmabiz:lookup-view/);
  assert.match(app,/if\(views\.some\(v=>v\[0\]===requested\)\)/);
  assert.match(lookup,/mode','products'/);
  assert.match(lookup,/\/api\/rxnorm\?/);
  assert.match(css,/@media\(max-width:760px\)/);
  assert.match(html,/assets\/drug-lookup\.css/);
  assert.match(html,/assets\/drug-lookup\.js/);
});


test('RxNorm SCD reverse lookup separates accepted mapping and candidate DAV products',async()=>{
  const db=new PGlite();
  try{
    await db.exec([
      "CREATE TABLE dav_product (dav_row_id text primary key,drug_name text,",
      "registration_number text,active_ingredient_raw text,strength_raw text,",
      "dosage_form_raw text,manufacturer text,source text,unit text,",
      "catalog_duplicate_status text);",
      "CREATE TABLE dav_rxnorm_mapping (dav_row_id text primary key,selected_scd_rxcui text,",
      "suggested_scd_rxcui text,accepted_for_serving integer,mapping_status text);",
      "CREATE TABLE dav_rxnorm_evidence (dav_row_id text,component_order integer,",
      "ingredient_candidate_rxcui text);",
      "CREATE TABLE price_record (price_id text,dav_row_id text,price_vnd bigint,",
      "price_type text,declaration_date date,unit text);",
      "INSERT INTO dav_product (dav_row_id,drug_name,source,registration_number) VALUES",
      "('A','Losartan A','DAV_PUBLIC_DRUG_PRICE','VD1'),",
      "('B','Losartan B','SILVER_R2','VD2'),",
      "('C','Acetaminophen C','SILVER_R2','VD3'),",
      "('D','Losartan D','SILVER_R2','VD4');",
      "INSERT INTO dav_rxnorm_mapping VALUES",
      "('A','979492',NULL,1,'VERIFIED_SCD'),",
      "('B',NULL,'979492',0,'CANDIDATE_REVIEW'),",
      "('C',NULL,NULL,0,'UNMATCHED_REVIEW'),",
      "('D','999999','979492',1,'VERIFIED_SCD');",
      "INSERT INTO dav_rxnorm_evidence VALUES",
      "('C',1,'161'),('C',2,'161'),('B',1,'161');",
      "INSERT INTO price_record VALUES",
      "('old','A',1000,'KKL','2024-01-01','vien'),",
      "('new','A',3000,'KKL','2026-10-21','vien');"
    ].join(' '));
    const q=rxnorm.buildDavReverseQuery({rxcui:'979492',kind:'scd',page:1,pageSize:10});
    assert.equal(Number((await db.query(q.countSql,q.countParams)).rows[0].total_rows),2);
    const rows=(await db.query(q.rowsSql,q.params)).rows;
    assert.deepEqual(rows.map(x=>[x.id,x.match_type]),[['A','ACCEPTED_SCD'],['B','CANDIDATE_SCD']]);
    assert.equal(Number(rows[0].price_vnd),3000);
    const accepted=rxnorm.buildDavReverseQuery({rxcui:'979492',kind:'scd',review:'accepted'});
    assert.deepEqual((await db.query(accepted.rowsSql,accepted.params)).rows.map(x=>x.id),['A']);
    const review=rxnorm.buildDavReverseQuery({rxcui:'979492',kind:'scd',review:'review'});
    assert.deepEqual((await db.query(review.rowsSql,review.params)).rows.map(x=>x.id),['B']);
    const ingredient=rxnorm.buildDavReverseQuery({rxcui:'161',kind:'ingredient',pageSize:1,page:2});
    assert.equal(Number((await db.query(ingredient.countSql,ingredient.countParams)).rows[0].total_rows),2);
    assert.equal((await db.query(ingredient.rowsSql,ingredient.params)).rows.length,1);
    const ingAll=rxnorm.buildDavReverseQuery({rxcui:'161',kind:'ingredient'});
    assert.deepEqual((await db.query(ingAll.rowsSql,ingAll.params)).rows.map(x=>x.match_type),
      ['INGREDIENT_EVIDENCE','INGREDIENT_EVIDENCE']);
    assert.equal(Number((await db.query(
      rxnorm.buildDavReverseQuery({rxcui:'161',kind:'ingredient',review:'accepted'}).countSql,
      ['161','ingredient','accepted'])).rows[0].total_rows),0);
    assert.equal(rxnorm.buildDavReverseQuery({rxcui:"161 OR 1=1"}),null);
    const unsupported=rxnorm.buildDavReverseQuery({rxcui:'161',kind:'unsupported'});
    assert.equal(Number((await db.query(unsupported.countSql,unsupported.countParams)).rows[0].total_rows),0);
  }finally{await db.close();}
});
test('RxNorm UI includes reverse-DAV drill-down and separate pagination controls',()=>{
  const fs=require('node:fs');
  const js=fs.readFileSync(require('node:path').join(__dirname,'../assets/drug-lookup.js'),'utf8');
  const css=fs.readFileSync(require('node:path').join(__dirname,'../assets/drug-lookup.css'),'utf8');
  assert.match(js,/dav_for_rxcui/);
  assert.match(js,/lookup-reverse-dav/);
  assert.match(js,/data-reverse-filter/);
  assert.match(js,/data-reverse-page/);
  assert.match(js,/INGREDIENT_EVIDENCE/);
  assert.match(js,/data-back-rx/);
  assert.match(css,/lookup-reverse-item/);
});
