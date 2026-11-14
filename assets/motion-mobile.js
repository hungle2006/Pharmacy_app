/* Small compositor animations, with a single reduced-motion switch. */
(() => {
'use strict';
const reduced=matchMedia('(prefers-reduced-motion:reduce)');let pageAnimation;
const ease='cubic-bezier(.22,1,.36,1)';
function reveal(){
  if(reduced.matches||document.getElementById('app').hidden)return;
  const content=document.getElementById('content');pageAnimation?.cancel();
  pageAnimation=content.animate([{opacity:.78,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],{duration:210,easing:ease});
}
function page(update){
  pageAnimation?.cancel();update();
  if(reduced.matches||document.getElementById('app').hidden)return;
  const content=document.getElementById('content');
  pageAnimation=content.animate([{opacity:.72,transform:'translateY(4px)'},{opacity:1,transform:'translateY(0)'}],{duration:190,easing:ease});
}
function intro(){
  const cover=document.getElementById('cover');
  if(!reduced.matches)cover.animate([{opacity:.72},{opacity:1}],{duration:210,easing:ease});
}
// CSS owns Start press/hover feedback; avoid competing WAAPI and transform animations.
document.addEventListener('click',event=>{const more=event.target.closest('[data-mobile-menu]');if(more)document.getElementById('menu').click();});
window.PharmaMotion=Object.freeze({page,intro,reveal});
})();
