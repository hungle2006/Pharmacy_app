/* Animate the visible surfaces, leaving the app scroller and overlays stationary. */
(() => {
  'use strict';
  const reduced = matchMedia('(prefers-reduced-motion:reduce)');
  const app = document.getElementById('app');
  const content = document.getElementById('content');
  const cover = document.getElementById('cover');
  const ease = 'cubic-bezier(.22,1,.36,1)';
  const animations = new Set();

  function stop() {
    for (const animation of animations) animation.cancel();
    animations.clear();
  }

  function play(element, keyframes, timing) {
    if (!element?.animate || reduced.matches) return;
    const animation = element.animate(keyframes, { easing: ease, fill: 'backwards', ...timing });
    animations.add(animation);
    animation.onfinish = animation.oncancel = () => animations.delete(animation);
  }

  function animateWorkspace() {
    if (app.hidden || reduced.matches) return;
    play(content.querySelector('.task-heading'), [
      { opacity: .5, transform: 'translateY(8px)' },
      { opacity: 1, transform: 'translateY(0)' },
    ], { duration: 270 });
    const metrics = document.getElementById('metrics');
    if (!metrics.hidden) {
      play(metrics, [{ opacity: .55 }, { opacity: 1 }], { duration: 210, delay: 45 });
      return;
    }
    const panel = content.querySelector(':scope > :is(#lookup-panel,#market-forecast-panel,#disease-predict-panel,#feature-price-panel):not([hidden])');
    if (panel) {
      play(panel, [{ opacity: .68 }, { opacity: 1 }], { duration: 210, delay: 35 });
    }
  }

  function reveal() {
    stop();
    animateWorkspace();
  }

  function page(update) {
    stop();
    update();
    animateWorkspace();
  }

  function intro() {
    stop();
    play(cover.querySelector('.start-copy'), [
      { opacity: .45, transform: 'translateY(9px)' },
      { opacity: 1, transform: 'translateY(0)' },
    ], { duration: 300 });
  }

  reduced.addEventListener('change', stop);
  document.addEventListener('click', event => {
    if (event.target.closest('[data-mobile-menu]')) document.getElementById('menu').click();
  });
  window.PharmaMotion = Object.freeze({ page, intro, reveal });
})();
