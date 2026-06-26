/**
 * canvas_modal.js — PropFlow Canvas Custom Modal
 *
 * Modal de confirmación personalizado (reemplaza confirm() del navegador).
 * Sigue el tema oscuro del canvas.
 */

function showConfirmModal(message, onConfirm) {
  const modal = document.getElementById('cv-modal');
  if (!modal) return;

  const msgEl = modal.querySelector('.cv-modal__msg');
  const confirmBtn = document.getElementById('modal-confirm');
  const cancelBtn = document.getElementById('modal-cancel');
  const overlay = modal.querySelector('.cv-modal__overlay');

  msgEl.textContent = message;
  modal.style.display = 'flex';

  function close() {
    modal.style.display = 'none';
    confirmBtn.onclick = null;
    cancelBtn.onclick = null;
    overlay.onclick = null;
  }

  confirmBtn.onclick = () => { close(); onConfirm(); };
  cancelBtn.onclick = close;
  overlay.onclick = close;

  // Cerrar con Escape
  const escHandler = (e) => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', escHandler); }};
  document.addEventListener('keydown', escHandler);
}


/**
 * Muestra un mensaje informativo (sin botón de confirmación).
 */
function showToastMessage(message, duration) {
  const toast = document.getElementById('cv-toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => {
    toast.classList.remove('visible');
  }, duration || 2500);
}
