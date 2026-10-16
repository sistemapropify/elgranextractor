(() => {
  'use strict';
  const form = document.getElementById('acm-login-form');
  if (!form) return;
  const button = form.querySelector('button[type="submit"]');
  const label = button.textContent;
  let submitting = false;
  form.addEventListener('submit', event => {
    if (submitting) {
      event.preventDefault();
      return;
    }
    submitting = true;
    button.disabled = true;
    button.textContent = 'Ingresando…';
    form.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', () => {
    submitting = false;
    button.disabled = false;
    button.textContent = label;
    form.removeAttribute('aria-busy');
  });
})();
