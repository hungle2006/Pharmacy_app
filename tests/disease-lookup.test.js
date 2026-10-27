'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {normalize,rankDisease,findDiseases}=require('../api/disease-lookup.js');
test('normalizes Vietnamese diacritics and đ without changing meaning',()=>{
  assert.equal(normalize('Viêm PHẾ quản'), 'viem phe quan');
  assert.equal(normalize('Đái tháo đường'), 'dai thao duong');
  assert.equal(normalize('  hen--suyễn '), 'hen suyen');
});
test('ICD code is a direct exact match',()=>{
  assert.equal(rankDisease({icd_code:'J20.9',icd_code_nodot:'J209'},'J20.9'),100);
  assert.equal(rankDisease({icd_code:'J20.9',icd_code_nodot:'J209'},'j209'),100);
});
test('typo and accentless input rank the right disease above unrelated ones',()=>{
  const target={icd_code:'J20.9',icd_code_nodot:'J209',disease_name_vi:'Viêm phế quản cấp tính, không xác định'};
  const unrelated={icd_code:'E11.9',icd_code_nodot:'E119',disease_name_vi:'Bệnh đái tháo đường típ 2'};
  assert.ok(rankDisease(target,'viem phe quann')>rankDisease(unrelated,'viem phe quann'));
});
test('common language alias hen suyen can find official ICD-10 hen phế quản',async()=>{
  const sample=[
    {icd_code:'E11',icd_code_nodot:'E11',disease_name_vi:'Bệnh đái tháo đường típ 2'},
    {icd_code:'J45',icd_code_nodot:'J45',disease_name_vi:'Hen phế quản [hen suyễn] [hen]',disease_name_vi_norm:'hen phe quan hen suyen hen'}
  ];
  const db={query:async (query,params)=>{assert.match(query,/FROM public\.disease/);assert.ok(params.some(p=>String(p).includes('hen')));return sample;}};
  const results=await findDiseases(db,'hen suyen');
  assert.equal(results[0].icd_code,'J45');
  assert.equal(results[0].disease_name_vi,sample[1].disease_name_vi);
});
