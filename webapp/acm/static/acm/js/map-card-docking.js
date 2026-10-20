/* Keep minimized map panels in two shared rails, restoring their original DOM on expand. */
(() => {
  'use strict';
  const host = document.getElementById('map-container');
  const top = document.getElementById('cmp-card-dock-top');
  const bottom = document.getElementById('cmp-card-dock-bottom');
  if (!host || !top || !bottom) return;
  const root = host.closest('.components-acm') || host;
  const panels = [
    ['cmp-controls', 'cmp-form-toggle'],
    ['cmp-comparison', 'cmp-comparison-toggle'],
    ['cmp-plan-layers', 'cmp-plan-layers-toggle'],
    ['cmp-pdm-zone', 'cmp-pdm-zone-toggle'],
    ['cmp-cadastral', 'cmp-cadastral-toggle'],
    ['cmp-selected-card', 'cmp-selected-toggle'],
  ];
  const entries = new Map(), docked = [];
  let frame = 0, clearance = {top: 8, bottom: 8};
  const gap = 8;
  function schedule() {
    if (!frame) frame = requestAnimationFrame(() => { frame = 0; layout(); });
  }
  function restore(entry) {
    if (!entry.placeholder) return;
    entry.placeholder.replaceWith(entry.card);
    entry.placeholder = null;
    entry.card.classList.remove('cmp-map-docked');
    docked.splice(docked.indexOf(entry), 1);
  }
  function layout() {
    if (!host.clientWidth) return;
    const focused = document.activeElement;
    let movedFocus = false;
    for (const [id, toggleId] of panels) {
      const card = document.getElementById(id), toggle = document.getElementById(toggleId);
      if (!card || !toggle) continue;
      let entry = entries.get(id);
      if (!entry) {
        entry = {card, placeholder: null}; entries.set(id, entry);
        observer.observe(card);
      }
      const collapsed = !card.hidden && toggle.getAttribute('aria-expanded') === 'false';
      if (collapsed && !entry.placeholder) {
        entry.placeholder = document.createComment(id + ' expanded position');
        card.before(entry.placeholder);
        card.classList.add('cmp-map-docked');
        movedFocus ||= card.contains(focused);
        top.append(card);
        docked.push(entry);
      } else if (!collapsed && entry.placeholder) {
        movedFocus ||= card.contains(focused);
        restore(entry);
      }
    }
    const available = Math.max(0, host.clientWidth - 2 * gap);
    let used = 0, overflow = false, topIndex = 0, bottomIndex = 0;
    for (const entry of docked) {
      const width = entry.card.getBoundingClientRect().width;
      if (used && used + gap + width > available) overflow = true;
      const rail = overflow ? bottom : top;
      const index = overflow ? bottomIndex++ : topIndex++;
      if (rail.children[index] !== entry.card) {
        movedFocus ||= entry.card.contains(focused);
        rail.insertBefore(entry.card, rail.children[index] || null);
      }
      if (!overflow) used += (used ? gap : 0) + width;
    }
    // A narrow map may need several lower rows; scroll them instead of overlapping.
    const limit = Math.max(0, host.clientHeight - top.offsetHeight - 3 * gap) + 'px';
    if (bottom.style.maxHeight !== limit) bottom.style.maxHeight = limit;
    const next = {top: top.children.length ? top.offsetHeight + 2 * gap : gap,
                  bottom: bottom.children.length ? bottom.offsetHeight + 2 * gap : gap};
    if (next.top !== clearance.top || next.bottom !== clearance.bottom) {
      clearance = next;
      host.style.setProperty('--cmp-dock-top', next.top + 'px');
      host.style.setProperty('--cmp-dock-bottom', next.bottom + 'px');
      document.dispatchEvent(new CustomEvent('acm:card-dock-layout'));
    }
    if (movedFocus && focused?.isConnected && focused !== document.body) focused.focus({preventScroll: true});
  }
  const observer = new ResizeObserver(schedule);
  observer.observe(host);
  new MutationObserver(schedule).observe(root, {
    subtree: true, childList: true, attributes: true,
    attributeFilter: ['hidden', 'aria-expanded', 'class'],
  });
  document.addEventListener('acm:workspace-resize', schedule);
  window.addEventListener('resize', schedule);
  window.ACMCardDock = {bounds: () => clearance};
  schedule();
})();
