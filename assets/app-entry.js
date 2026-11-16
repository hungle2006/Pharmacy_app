(() => {
  'use strict';
  const sceneSource = document.currentScript.dataset.sceneSrc;
  const cover = document.getElementById('cover');
  const stage = cover.querySelector('.start-art');

  function whenVisible(element, load, options) {
    if (!('IntersectionObserver' in window)) {
      load();
      return;
    }
    const observer = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return;
      observer.disconnect();
      load();
    }, options);
    observer.observe(element);
  }

  whenVisible(stage, () => {
    const script = document.createElement('script');
    script.src = sceneSource;
    document.head.append(script);
  });

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
})();
