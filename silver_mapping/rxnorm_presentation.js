(() => {
  'use strict';
  const steps = [...document.querySelectorAll('.report-step')];
  const links = [...document.querySelectorAll('[data-step]')];
  const filters = [...document.querySelectorAll('[data-filter]')];
  const titleOf = step => document.querySelector(`[data-step="${step.id}"]`).textContent.trim().replace(/^\d+/, '').trim();
  let filter = 'all';
  let current = steps.find(step => step.id === location.hash.slice(1)) || steps[0];
  let presenting = false;
  let toastTimer;
  const visibleSteps = () => steps.filter(step => filter === 'all' || step.dataset.report === filter);
  function toast(message) {
    const el = document.getElementById('toast');
    el.textContent = message;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 4000);
  }
  function update() {
    const visible = visibleSteps();
    const index = visible.indexOf(current);
    steps.forEach(step => { step.hidden = !visible.includes(step) || (presenting && step !== current); });
    links.forEach(link => {
      if (link.dataset.step === current.id) link.setAttribute('aria-current', 'step');
      else link.removeAttribute('aria-current');
    });
    filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === filter)));
    document.querySelectorAll('.nav-group').forEach(group => { group.hidden = filter !== 'all' && group.dataset.report !== filter; });
    document.getElementById('current-report').textContent = `REPORT ${current.dataset.report}`;
    document.getElementById('current-title').textContent = titleOf(current);
    document.getElementById('step-counter').textContent = `${String(index + 1).padStart(2, '0')} / ${String(visible.length).padStart(2, '0')}`;
    document.getElementById('progress-fill').style.width = `${100 * (index + 1) / visible.length}%`;
    document.getElementById('prev-step').disabled = index === 0;
    document.getElementById('next-step').disabled = index === visible.length - 1;
    document.getElementById('present-toggle').setAttribute('aria-pressed', String(presenting));
    document.getElementById('present-toggle').innerHTML = presenting ? 'Thoát trình chiếu <span>×</span>' : 'Trình chiếu <span>↗</span>';
  }
  function closeMenu() {
    document.body.classList.remove('menu-open');
    document.getElementById('menu-toggle').setAttribute('aria-expanded', 'false');
  }
  function go(step, scroll = true) {
    if (!step) return;
    if (filter !== 'all' && step.dataset.report !== filter) filter = step.dataset.report;
    current = step;
    update();
    history.replaceState(null, '', `#${step.id}`);
    closeMenu();
    if (scroll) {
      if (presenting) window.scrollTo({ top: 0, behavior: 'instant' });
      else step.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
    }
  }
  function advance(delta) {
    const visible = visibleSteps();
    go(visible[visible.indexOf(current) + delta]);
  }
  filters.forEach(button => button.addEventListener('click', () => {
    filter = button.dataset.filter;
    const visible = visibleSteps();
    go(visible.includes(current) ? current : visible[0]);
  }));
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    const target = steps.find(step => `#${step.id}` === link.getAttribute('href'));
    if (target) link.addEventListener('click', event => { event.preventDefault(); go(target); });
  });
  document.getElementById('prev-step').addEventListener('click', () => advance(-1));
  document.getElementById('next-step').addEventListener('click', () => advance(1));
  document.getElementById('present-toggle').addEventListener('click', () => {
    presenting = !presenting;
    document.body.classList.toggle('presenting', presenting);
    go(current);
    if (presenting) toast('Dùng ← → để chuyển chủ đề · Esc để thoát · ⛶ để toàn màn hình');
  });
  document.getElementById('notes-toggle')?.addEventListener('click', event => {
    const hidden = document.body.classList.toggle('hide-notes');
    event.currentTarget.setAttribute('aria-pressed', String(!hidden));
  });
  const fullButton = document.getElementById('fullscreen-toggle');
  fullButton.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch { toast('Trình duyệt chưa cho phép toàn màn hình. Bạn có thể dùng phím F11.'); }
  });
  document.addEventListener('fullscreenchange', () => {
    fullButton.setAttribute('aria-label', document.fullscreenElement ? 'Thoát toàn màn hình' : 'Toàn màn hình');
    fullButton.setAttribute('aria-pressed', String(!!document.fullscreenElement));
  });
  document.getElementById('menu-toggle').addEventListener('click', event => {
    const open = document.body.classList.toggle('menu-open');
    event.currentTarget.setAttribute('aria-expanded', String(open));
  });
  document.querySelector('main').addEventListener('click', closeMenu);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      closeMenu();
      if (presenting) document.getElementById('present-toggle').click();
      return;
    }
    if (event.target.closest('input,textarea,select,summary,[contenteditable=true],.table-wrap,.r3-math')) return;
    if (presenting && ['ArrowRight', 'PageDown', 'ArrowLeft', 'PageUp'].includes(event.key)) {
      event.preventDefault();
      advance(['ArrowRight', 'PageDown'].includes(event.key) ? 1 : -1);
    }
  });
  document.getElementById('print-report').addEventListener('click', () => {
    // Printing includes the full report; expand evidence only for print and restore afterward.
    const closed = [...document.querySelectorAll('details:not([open])')];
    closed.forEach(el => { el.open = true; });
    const restore = () => { closed.forEach(el => { el.open = false; }); window.removeEventListener('afterprint', restore); };
    window.addEventListener('afterprint', restore, { once: true });
    window.print();
  });
  window.addEventListener('hashchange', () => {
    const target = steps.find(step => step.id === location.hash.slice(1));
    if (target) go(target);
  });
  // Scroll tracking in reading mode, throttled to one DOM pass per frame.
  let scheduled = false;
  window.addEventListener('scroll', () => {
    if (presenting || scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      const line = innerWidth <= 850 ? 210 : 150;
      const visible = visibleSteps();
      const active = [...visible].reverse().find(step => step.getBoundingClientRect().top <= line) || visible[0];
      if (active !== current) { current = active; update(); }
    });
  }, { passive: true });
  update();
  if (location.hash) requestAnimationFrame(() => go(current));
})();
