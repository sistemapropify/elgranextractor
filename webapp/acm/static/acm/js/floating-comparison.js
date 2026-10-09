(() => {
  'use strict';
  const host = document.getElementById('map-container');
  function initialize(id, label, anchor, updateEvent) {
  const card = document.getElementById(id);
  const handle = document.getElementById(id + '-handle');
  const content = document.getElementById(id + '-content');
  const toggle = document.getElementById(id + '-toggle');
  if (!host || !card || !handle || !content || !toggle) return;
  let position = null, drag = null, frame = 0;
  const margin = 8;
  function move(x, y) {
    const maxX = Math.max(margin, host.clientWidth - card.offsetWidth - margin);
    const maxY = Math.max(margin, host.clientHeight - card.offsetHeight - margin);
    position = {x: Math.round(Math.max(margin, Math.min(maxX, x))), y: Math.round(Math.max(margin, Math.min(maxY, y)))};
    card.style.left = position.x + 'px';
    card.style.top = position.y + 'px';
  }
  function fit() {
    if (card.hidden) return;
    move(position ? position.x : anchor === 'bottom-left' ? margin : host.clientWidth - card.offsetWidth - margin,
         position ? position.y : anchor.startsWith('bottom') ? host.clientHeight - card.offsetHeight - 32 : margin);
  }
  function schedule() {
    if (frame) return;
    frame = requestAnimationFrame(() => { frame = 0; fit(); });
  }
  function stop(event) {
    if (!drag) return;
    drag = null;
    card.classList.remove('cmp-floating-dragging');
    if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
  }
  handle.addEventListener('pointerdown', event => {
    if (event.button !== 0 || event.target.closest('button')) return;
    event.preventDefault();
    event.stopPropagation();
    fit();
    drag = {x: event.clientX, y: event.clientY, left: position.x, top: position.y};
    handle.focus();
    handle.setPointerCapture(event.pointerId);
    card.classList.add('cmp-floating-dragging');
  });
  handle.addEventListener('pointermove', event => {
    if (drag) move(drag.left + event.clientX - drag.x, drag.top + event.clientY - drag.y);
  });
  handle.addEventListener('pointerup', stop);
  handle.addEventListener('pointercancel', stop);
  handle.addEventListener('lostpointercapture', stop);
  handle.addEventListener('keydown', event => {
    if (event.target !== handle) return;
    const step = event.shiftKey ? 40 : 10;
    const deltas = {ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step]};
    if (!deltas[event.key]) return;
    event.preventDefault();
    fit();
    move(position.x + deltas[event.key][0], position.y + deltas[event.key][1]);
  });
  toggle.addEventListener('click', () => {
    content.hidden = !content.hidden;
    card.classList.toggle('cmp-floating-minimized', content.hidden);
    toggle.setAttribute('aria-expanded', String(!content.hidden));
    toggle.setAttribute('aria-label', (content.hidden ? 'Expandir ' : 'Minimizar ') + label);
    toggle.textContent = content.hidden ? '+' : '−';
    schedule();
  });
  if (updateEvent) document.addEventListener(updateEvent, event => {
    if (event.detail?.reposition) position = null;
    content.hidden = false;
    card.classList.remove('cmp-floating-minimized');
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-label', 'Minimizar ' + label);
    toggle.textContent = '−';
    schedule();
  });
  document.addEventListener('acm:workspace-resize', schedule);
  const observer = new ResizeObserver(schedule);
  observer.observe(host);
  observer.observe(card);
  schedule();
  }
  initialize('cmp-comparison', 'comparación', 'top-right', 'acm:comparison-updated');
  initialize('cmp-plan-layers', 'capas del plano', 'bottom-left');
  initialize('cmp-pdm-zone', 'zona de uso', 'bottom-right');
})();
