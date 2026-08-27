(function () {
  'use strict';
  const resolve = value => typeof value === 'string' ? document.querySelector(value) : value;
  class ToggleSurface {
    constructor(element) { this.element = resolve(element); if (this.element) this.element.__propifaiInstance = this; }
    show() { if (!this.element) return; this.element.classList.add('show'); this.element.setAttribute('aria-hidden', 'false'); document.body.classList.add('surface-open'); }
    hide() { if (!this.element) return; this.element.classList.remove('show'); this.element.setAttribute('aria-hidden', 'true'); document.body.classList.remove('surface-open'); }
    toggle() { this.element && this.element.classList.contains('show') ? this.hide() : this.show(); }
    static getInstance(element) { element = resolve(element); return element ? element.__propifaiInstance || new this(element) : null; }
  }
  class Modal extends ToggleSurface {}
  class Offcanvas extends ToggleSurface {}
  class Toast extends ToggleSurface { constructor(element, options) { super(element); this.options = options || {}; } show() { super.show(); window.setTimeout(() => this.hide(), this.options.delay || 3000); } }
  class Tooltip { constructor(element) { this.element = resolve(element); } }
  window.PropifaiUI = { Modal, Offcanvas, Toast, Tooltip };
  document.addEventListener('click', event => {
    const opener = event.target.closest('[data-bs-toggle="modal"],[data-ui-toggle="modal"]');
    if (opener) { event.preventDefault(); new Modal(opener.getAttribute('data-bs-target') || opener.getAttribute('data-ui-target')).show(); return; }
    const closer = event.target.closest('[data-bs-dismiss="modal"],[data-bs-dismiss="offcanvas"],[data-ui-dismiss]');
    if (closer) { event.preventDefault(); const surface = closer.closest('.modal,.offcanvas'); ToggleSurface.getInstance(surface)?.hide(); }
  });
})();
