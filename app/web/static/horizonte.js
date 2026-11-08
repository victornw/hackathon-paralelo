/* A process advances only when its server-rendered current step changes. */
(() => {
  const rail = document.querySelector('.trilho[data-processo]');
  if (!rail) return;
  const steps = Array.from(rail.children);
  const current = steps.findIndex(step => step.getAttribute('aria-current') === 'step');
  if (current < 0) return;
  const key = `dia:etapa:${rail.dataset.processo}`;
  let previous;
  try {
    const saved = sessionStorage.getItem(key);
    previous = saved === null ? null : Number(saved);
    sessionStorage.setItem(key, String(current));
  } catch { return; }
  if (previous === null || !Number.isInteger(previous) || previous < 0 || previous >= current ||
      matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  // One brief progression, even if several stages passed between visits.
  const interval = 180 / (current - previous);
  steps.slice(previous, current).forEach((step, offset) => {
    step.style.setProperty('--passage-delay', `${offset * interval}ms`);
    step.classList.add('passagem');
  });
  steps[current].style.setProperty('--passage-delay', '180ms');
  steps[current].classList.add('chegada');
  setTimeout(() => {
    steps.forEach(step => {
      step.classList.remove('passagem', 'chegada');
      step.style.removeProperty('--passage-delay');
    });
  }, 500);
})();
