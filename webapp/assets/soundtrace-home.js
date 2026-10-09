(() => {
  const art = document.querySelector('.moment-art');
  if (!art) return;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let visible = true;
  const render = () => {
    art.dataset.motion = !reducedMotion.matches && visible && !document.hidden ? 'playing' : 'paused';
  };
  reducedMotion.addEventListener('change', render);
  document.addEventListener('visibilitychange', render);
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      render();
    }).observe(art);
  }
  render();
})();
