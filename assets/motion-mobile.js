/* Small compositor animations, with a single reduced-motion switch. */
(() => {
'use strict';
const reduced=matchMedia('(prefers-reduced-motion:reduce)');let pageAnimation;
function page(update){pageAnimation?.cancel();update();if(reduced.matches||document.getElementById('app').hidden)return;const content=document.getElementById('content');pageAnimation=content.animate([{opacity:.3,transform:'translateY(9px)'},{opacity:1,transform:'translateY(0)'}],{duration:240,easing:'cubic-bezier(.22,1,.36,1)'});}
function intro(){if(!reduced.matches)document.getElementById('cover').animate([{opacity:.2,transform:'scale(1.02)'},{opacity:1,transform:'scale(1)'}],{duration:360,easing:'cubic-bezier(.22,1,.36,1)'});}
document.addEventListener('pointerdown',event=>{const button=event.target.closest('button');if(!button||button.disabled||reduced.matches||event.button!==0)return;button.animate([{transform:'scale(1)'},{transform:'scale(.97)'},{transform:'scale(1)'}],{duration:210,easing:'ease-out'});});
document.addEventListener('click',event=>{const more=event.target.closest('[data-mobile-menu]');if(more)document.getElementById('menu').click();});
window.PharmaMotion=Object.freeze({page,intro});
})();
