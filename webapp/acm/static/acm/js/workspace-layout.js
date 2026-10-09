(() => {
  'use strict';
  const layout = document.querySelector('.components-acm .map-layout');
  const handle = document.getElementById('cmp-resizer');
  if (!layout || !handle) return;
  const key = 'acm-results-width-v1';
  let preferred = 280, frame = 0, dragging = false;
  try {
    const saved = Number(localStorage.getItem(key));
    if (Number.isFinite(saved) && saved >= 280) preferred = saved;
  } catch (_) { /* Private browsers can disable storage. */ }
  const limits = () => {
    const width = layout.getBoundingClientRect().width;
    const max = Math.min(520, Math.floor(width * .4) - 8);
    return {min: Math.min(280, max), max};
  };
  function notify() {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      document.dispatchEvent(new CustomEvent('acm:workspace-resize'));
    });
  }
  function apply(value, remember = false) {
    const {min, max} = limits();
    const width = Math.round(Math.max(min, Math.min(max, value)));
    layout.style.setProperty('--cmp-sidebar-width', width + 'px');
    handle.setAttribute('aria-valuemin', min);
    handle.setAttribute('aria-valuemax', max);
    handle.setAttribute('aria-valuenow', width);
    handle.setAttribute('aria-valuetext', width + ' píxeles');
    if (remember) {
      preferred = width;
      try { localStorage.setItem(key, String(width)); } catch (_) {}
    }
    notify();
  }
  function fit() {
    const stacked = window.innerWidth <= 768 || layout.getBoundingClientRect().width < 700;
    layout.classList.toggle('cmp-stack-layout', stacked);
    if (!stacked) apply(preferred);
    notify();
  }
  function stop(event) {
    if (!dragging) return;
    dragging = false;
    layout.classList.remove('cmp-resizing');
    if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
    apply(parseFloat(layout.style.getPropertyValue('--cmp-sidebar-width')), true);
  }
  handle.addEventListener('pointerdown', event => {
    if (event.button !== 0 || layout.classList.contains('cmp-stack-layout')) return;
    event.preventDefault();
    dragging = true;
    handle.focus();
    handle.setPointerCapture(event.pointerId);
    layout.classList.add('cmp-resizing');
  });
  handle.addEventListener('pointermove', event => {
    if (dragging) apply(layout.getBoundingClientRect().right - event.clientX);
  });
  handle.addEventListener('pointerup', stop);
  handle.addEventListener('pointercancel', stop);
  handle.addEventListener('lostpointercapture', event => { if (dragging) stop(event); });
  handle.addEventListener('keydown', event => {
    if (layout.classList.contains('cmp-stack-layout')) return;
    const current = Number(handle.getAttribute('aria-valuenow'));
    const {min, max} = limits();
    const step = event.shiftKey ? 40 : 16;
    const changes = {ArrowLeft: current + step, ArrowRight: current - step, Home: min, End: max};
    if (!(event.key in changes)) return;
    event.preventDefault();
    apply(changes[event.key], true);
  });
  handle.addEventListener('dblclick', () => apply(280, true));
  new ResizeObserver(fit).observe(layout);
  fit();
})();
