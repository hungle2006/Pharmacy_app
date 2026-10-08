const test = require('node:test');
const assert = require('node:assert/strict');
const {buildQuery} = require('../api/analytics');
test('filters remain parameters and product counts stay distinct',()=>{
 const malicious="x'); DROP TABLE dav_product; --";
 const q=buildQuery({q:malicious,ingredient:'Amoxicillin',country:'Việt Nam',kind:'declared',unit:'Viên',page:'2'});
 assert(!q.text.includes(malicious));assert.equal(q.params[0], '%' + malicious.replace(/[\\%_]/g, '\\$&') + '%');assert.equal(q.params.length,5);
 assert.match(q.text,/COUNT\(DISTINCT id\) AS products/);assert.match(q.text,/OFFSET 12/);
 assert.match(q.text,/declaration_date AS snapshot_date/);
 assert.match(q.text,/GROUP BY ingredient,strength,dosage_form,unit,price_type/);
});
test('unsafe or negative pages cannot inject into SQL',()=>{
 for(const page of ['-1','NaN','1;DROP TABLE foo','0','Infinity'])assert.equal(buildQuery({page}).page,1);
 assert.equal(buildQuery({page:'99999999'}).page,100000);
});
test('missing credentials and unsupported methods have explicit states',async()=>{
 const handler=require('../api/analytics');const prior=process.env.DATABASE_URL;delete process.env.DATABASE_URL;
 function response(){return {setHeader(){},status(code){this.code=code;return this;},json(value){this.value=value;return this;}};}
 try{let r=response();await handler({method:'GET',query:{}},r);assert.equal(r.code,503);assert.equal(r.value.reason,'DATABASE_URL_MISSING');r=response();await handler({method:'POST',query:{}},r);assert.equal(r.code,405);}finally{if(prior!==undefined)process.env.DATABASE_URL=prior;}
});
