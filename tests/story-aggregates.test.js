'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {PGlite}=require('@electric-sql/pglite');
const {diseaseQuery,mediQuery}=require('../api/story');
test('story counts different grains separately and eligible MEDI requires the complete code chain',async()=>{
 const db=new PGlite();
 try{
  await db.exec(`CREATE TABLE disease(icd_code text,chapter_code text,disease_name_vi text);
  INSERT INTO disease VALUES ('J20','X','Viêm phế quản'),('J45','X','Hen'),('E11',NULL,'  ');
  CREATE TABLE medi_relation(rxcui text,disease_icd_code text,code_system text,icd_match_status text,rxnorm_match_status text);
  INSERT INTO medi_relation VALUES
  ('1','J20','ICD10CM','EXACT_ICD10_CODE','FOUND_IN_RXNORM_SNAPSHOT'),
  ('1','J45','ICD10CM','EXACT_ICD10_CODE','NOT_FOUND'),
  ('2','J20','ICD9CM','EXACT_ICD10_CODE','FOUND_IN_RXNORM_SNAPSHOT'),
  ('3',NULL,'ICD10CM','EXACT_ICD10_CODE','FOUND_IN_RXNORM_SNAPSHOT'),
  ('4','J45','ICD10CM','REVIEW_REQUIRED','FOUND_IN_RXNORM_SNAPSHOT');`);
  const d=(await db.query(diseaseQuery)).rows[0],m=(await db.query(mediQuery)).rows[0];
  assert.equal(Number(d.total),3);assert.equal(Number(d.named_vi),2);
  assert.deepEqual(d.chapters,[{name:'X',value:2},{name:'Chưa phân chương',value:1}]);
  assert.equal(Number(m.total),5);assert.equal(Number(m.concepts),4);assert.equal(Number(m.eligible),1);
  assert.equal(m.systems.reduce((sum,r)=>sum+r.value,0),Number(m.total));
 }finally{await db.close();}
});
