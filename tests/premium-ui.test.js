'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {buildQuery}=require('../api/data');
const read=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8');

test('lookup filters use parameterized product conditions rather than cosmetic select boxes',()=>{
 const q=buildQuery({mode:'products',q:'ALAXAN',ingredient:'Acetaminophen',country:'Việt Nam',kind:'PRICE',unit:'viên',currentOnly:'true',page:1,pageSize:8});
 assert.equal(q.pageSize,8);
 assert.match(q.countSql,/d\.active_ingredient_raw = \$\d+/);
 assert.match(q.countSql,/d\.country = \$\d+/);
 assert.match(q.countSql,/p\.price_type = \$\d+/);
 assert.match(q.countSql,/COALESCE\(NULLIF\(p\.unit,''\),NULLIF\(d\.unit,''\)\) = \$\d+/);
 assert.match(q.countSql,/d\.source = 'SILVER_R2'/);
 assert.deepEqual(q.countParams.filter(v=>!String(v).startsWith('%')),['Acetaminophen','Việt Nam','PRICE','viên']);
});
test('Start and pill scene remain untouched with the same IDs and original JS bundle',()=>{
 const html=read('index.html');
 assert.match(html,/<section class="cover start-focus" id="cover"/);
 assert.match(html,/<canvas id="scene"/);
 assert.match(html,/<button id="start" class="start-btn"/);
 assert.match(html,/assets\/scene3d\.js/);
 assert.match(html,/assets\/premium-ui\.css/);
 assert.match(html,/assets\/premium-ui\.js/);
});
test('searchable ingredient dropdown has bounded options, accessible keyboard and filter synchronization',()=>{
 const ui=read('assets/premium-ui.js');
 assert.match(ui,/slice\(0,60\)/);
 assert.match(ui,/role="listbox"/);
 assert.match(ui,/aria-expanded/);
 assert.match(ui,/ArrowDown/);
 assert.match(ui,/pharmabiz:lookup-filters/); // In integration across files below
 const presentation=read('assets/presentation.js');
 const lookup=read('assets/drug-lookup.js');
 assert.match(presentation,/pharmabiz:lookup-filters/);
 assert.match(lookup,/for\(const key of \['ingredient','country','kind','unit'\]\)/);
 assert.match(lookup,/lookup-filters/);
 const css=read('assets/premium-ui.css');
 assert.match(css,/max-height:245px/);
 assert.match(css,/@media\(max-width:760px\)/);
});
test('DAV detail tabs reparent real API fields instead of copying fabricated values',()=>{
 const ui=read('assets/premium-ui.js');
 assert.match(ui,/fieldList\.children/);
 assert.match(ui,/pane\.append\(dl\)/);
 assert.match(ui,/mapping\)panes\[2\]\.append\(mapping\)/);
 assert.match(ui,/role','tabpanel/);
 assert.match(ui,/role','tab'/);
 const lookup=read('assets/drug-lookup.js');
 assert.match(lookup,/pharmabiz:lookup-detail-render/);
});
test('discrete monthly dashboard distinguishes partial-month observation counts and readable ticks',()=>{
 const depth=read('assets/task-depth.js');
 assert.match(depth,/nice=\[1,2,2\.5,5,10\]/);
 assert.match(depth,/is-partial/);
 assert.match(depth,/Tháng .+ chưa kết thúc/);
 const css=read('assets/premium-ui.css');
 assert.match(css,/depth-mark\.is-partial/);
});
