'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'..',name),'utf8');
test('workspace shell loads after the existing product and never changes the Start canvas',()=>{
 const html=read('index.html');
 const positions=['assets/scene3d.js','assets/presentation.js','assets/focus-workspace.js','assets/premium-ui.js','assets/workspace-shell.js'].map(t=>html.indexOf(t));
 assert.ok(positions.every(n=>n>=0), 'all live modules exist');
 assert.ok(positions.every((n,i)=>!i||n>positions[i-1]),'shell must run last');
 assert.ok(html.indexOf('assets/workspace-shell.css')>html.indexOf('assets/premium-ui.css'));
 assert.match(html,/<section class="cover start-focus" id="cover"/);
 assert.match(html,/<canvas id="scene"/);
 assert.match(html,/<button id="start" class="start-btn"/);
});
test('task switches restore detail before replacing the rendered page',()=>{
 const presentation=read('assets/presentation.js');
 const shell=read('assets/workspace-shell.js');
 assert.match(presentation,/document\.dispatchEvent\(new CustomEvent\('pharmabiz:workspace-before-view'/);
 assert.match(shell,/document\.addEventListener\('pharmabiz:workspace-before-view'/);
 assert.match(shell,/function closeSheet\(restoreFocus=true\)/);
 assert.match(shell,/marker\.replaceWith\(node\)/);
});
test('mobile lookup opens a detail panel instead of forcing document scrolling',()=>{
 const src=read('assets/drug-lookup.js');
 const shell=read('assets/workspace-shell.js');
 assert.match(src,/pharmabiz:lookup-detail-open/);
 const start=src.indexOf('function bindClose()'),end=src.indexOf('async function selectItem',start);
 assert.ok(start>=0&&end>start);
 assert.doesNotMatch(src.slice(start,end),/scrollIntoView/);
 assert.match(shell,/openSheet\(node,'Chi tiết hồ sơ thuốc',trigger,'lookup'\)/);
 assert.match(shell,/lookupClose\.click\(\)/);
});
test('detail sheet has keyboard closing, focus trapping, and mobile-safe spacing',()=>{
 const script=read('assets/workspace-shell.js');
 const css=read('assets/workspace-shell.css');
 for(const text of ['aria-modal="true"','aria-labelledby="ws-sheet-heading"','Escape','e.shiftKey','document.activeElement===last','role="listbox"','Ctrl K']){
  assert.ok(script.includes(text), 'missing '+text);
 }
 assert.match(css,/@media\(max-width:760px\)/);
 assert.match(css,/@media\(max-width:390px\)/);
 assert.match(css, /env\(safe-area-inset-bottom\)/);
 assert.match(css, /prefers-reduced-motion:reduce/);
 assert.match(css, /\.ws-sheet-body\{[^}]*overflow:auto/);
});
test('workspace keeps source rows accessible and does not substitute fabricated values',()=>{
 const script=read('assets/workspace-shell.js');
 const css=read('assets/workspace-shell.css');
 assert.match(script,/openSheet\(panel,'Bản ghi dữ liệu nguồn'/);
 assert.match(script,/openSheet\(source,'Số liệu và phương pháp'/);
 assert.match(css,/#records-panel:not\(\.ws-in-sheet\)\{display:none!important\}/);
 assert.doesNotMatch(script,/\/api\/|Math\.random|price_vnd|rxcui/);
});
test('button motion remains subtle and cannot conflict with old whole-app WAAPI pointer animation',()=>{
 const motion=read('assets/motion-mobile.js');
 const css=read('assets/workspace-shell.css');
 assert.match(motion,/closest\('#cover button'\)/);
 assert.match(css,/transform:scale\(\.978\)/);
 assert.match(css,/transition-duration:90ms/);
});
