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
 for(const text of ['aria-modal="true"','aria-labelledby="ws-sheet-heading"','Escape','e.shiftKey','document.activeElement===last','role="listbox"','e.ctrlKey||e.metaKey']){
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
 assert.doesNotMatch(motion,/\.animate\(\[\{transform:'scale\(1\)'/);
 assert.match(css,/transform:scale\(\.978\)/);
 assert.match(css,/transition-duration:90ms/);
});


test('direct lookup URL reattaches its filter row after deferred UI initializes',()=>{
 const premium=read('assets/premium-ui.js');
 assert.match(premium,/requestAnimationFrame\(\(\)=>\{if\(document\.body\.dataset\.activeView==='lookup'\)/);
 assert.match(premium,/pharmabiz:lookup-view/);
 assert.match(premium,/form\.after\(filters\)/);
});
test('record detail sheet does not get wrapped inside a new collapsed details container',()=>{
 const focus=read('assets/focus-workspace.js');
 const css=read('assets/workspace-shell.css');
 assert.match(focus,/records\?\.closest\('\.ws-sheet-body'\)\?null:fold\(records/);
 assert.match(css,/#records-disclosure:not\(\.ws-in-sheet\)\{display:none!important\}/);
});

test('header omits the redundant task-selection CTA while keeping existing navigation',()=>{
 const shell=read('assets/workspace-shell.js');
 const html=read('index.html');
 assert.doesNotMatch(shell,/createElement\('button'\);taskAction/);
 assert.doesNotMatch(shell,/<span>Chọn tác vụ<\/span>/);
 assert.match(shell,/actions\.append\(sourceAction\)/);
 assert.match(html,/<nav id="mobile-taskbar"/);
 assert.match(html,/<nav id="nav"/);
});
test('focus chapters use an accessible bounded custom popover rather than native select UI',()=>{
 const focus=read('assets/focus-workspace.js');
 const css=read('assets/workspace-shell.css');
 assert.match(focus,/const trigger=document\.createElement\('button'\)/);
 assert.match(focus,/trigger\.setAttribute\('aria-haspopup','menu'\)/);
 assert.match(focus,/menuSearch\.addEventListener\('input',drawMenu\)/);
 assert.match(focus,/select\.dispatchEvent\(new Event\('change'/);
 assert.match(focus,/trigger\.setAttribute\('aria-expanded','false'\)/);
 assert.match(focus,/e\.key==='Escape'/);
 assert.match(css,/select\.focus-native-select/);
 assert.match(css,/\.focus-menu-list\{[^}]*overflow-y:auto/s);
 assert.match(css,/@media\(max-width:490px\)/);
});


test('mobile popover opening upwards measures available space from entire picker, not trigger',()=>{
 const src=read('assets/focus-workspace.js');
 const css=read('assets/workspace-shell.css');
 assert.match(src,/const above=Math\.max\(0,picker\.getBoundingClientRect\(\)\.top-18\)/);
 assert.match(src,/menu\.classList\.toggle\('focus-menu-up',openUp\)/);
 assert.match(src,/menu\.style\.maxHeight=Math\.max\(118,Math\.min\(440,room-8\)\)\+'px'/);
 assert.match(css,/\.focus-menu\.focus-menu-up/);
});

test('Start motion has synchronized 440ms exit, app reveal and optional reduced motion',()=>{
 const presentation=read('assets/presentation.js');
 const motion=read('assets/motion-mobile.js');
 const css=read('assets/responsive-polish.css');
 assert.match(presentation,/button\.classList\.add\('is-entering'\)/);
 assert.match(presentation,/button\.setAttribute\('aria-busy','true'\)/);
 assert.match(presentation,/PharmaMotion\.reveal\(\)/);
 assert.match(presentation,/matches\?0:440/);
 assert.match(motion,/function reveal\(\)/);
 assert.match(css, /animation:pb-start-exit 440ms/);
 assert.ok(css.includes('.start-btn:active:not(:disabled)'));
 assert.ok(css.includes('@media(prefers-reduced-motion:reduce)'));
});
test('responsive element spacing covers compact phone heights without replacing Blender scene',()=>{
 const css=read('assets/responsive-polish.css');
 const html=read('index.html');
 assert.ok(css.includes('@media(max-width:760px) and (max-height:690px)'));
 assert.match(css,/height:100dvh/);
 assert.match(css,/min-height:48px/);
 assert.ok(css.includes('@media(max-width:370px)'));
 assert.match(css,/#mobile-taskbar button/);
 assert.ok(html.indexOf('assets/responsive-polish.css')>html.indexOf('assets/workspace-shell.css'));
 assert.match(html,/<canvas id="scene"/);
});


test('mobile lookup collapsed filter has one full-width row and no tiny 40px retry control',()=>{
 const css=read('assets/responsive-polish.css');
 const content=read('assets/presentation.js');
 assert.ok(css.includes('grid-template-columns:minmax(0,1fr)!important'));
 assert.ok(css.includes('#filter-toggle'));
 assert.ok(css.includes('max-height:46px!important'));
 assert.ok(css.includes('.lookup-retry'));
 assert.ok(css.includes('min-height:44px'));
 assert.ok(content.includes('title="Hồ sơ → Cấu hình → Giá → Bằng chứng">Cách đọc kết quả</summary>'));
});
test('primary desktop quick search submit exposes a proper 44px touch target',()=>{
 const css=read('assets/responsive-polish.css');
 assert.ok(css.includes('.workspace-search button[type="submit"]'));
 assert.ok(css.includes('min-width:44px;width:44px'));
 assert.ok(css.includes('min-height:44px;height:44px'));
});
