/**
 * canvas_match_modal.js — Match Comparison Modal
 *
 * Modal comparativo propiedad vs requerimiento con ✓/✗ en 11 campos.
 * Se abre al hacer clic en el badge circular de las aristas match.
 *
 * Dependencias: canvas_engine.js, canvas_edges.js
 */

/* ── MOSTRAR MODAL COMPARATIVO ── */

async function showMatchModal(matchId, badgeX, badgeY) {
  // Verificar si ya existe un modal abierto
  const existing = document.querySelector('.cv-match-modal');
  if (existing) existing.remove();

  try {
    const res = await fetch(`/canvas/api/match-detail/${matchId}/`);
    if (!res.ok) {
      showToast('Error al cargar detalle del match');
      return;
    }
    const data = await res.json();

    renderMatchModal(data);
  } catch (err) {
    console.error('Error fetching match detail:', err);
    showToast('Error de conexión al cargar detalle');
  }
}


/* ── RENDER MODAL ── */

function renderMatchModal(data) {
  const score = Math.round(parseFloat(data.score_total) || 0);
  const fecha = data.ejecutado_en || '';
  const faseElim = data.fase_eliminada || '';
  const campos = data.campos || [];

  // Crear backdrop + panel
  const modal = document.createElement('div');
  modal.className = 'cv-match-modal';

  modal.innerHTML = `
    <div class="cv-match-modal__panel">
      <div class="cv-match-modal__header">
        <div class="cv-match-modal__title">
          🎯 Match
          <span class="cv-match-modal__score">${score}%</span>
          ${fecha ? `<span style="font-size:11px;color:#4a4e62;font-weight:400;">${fecha}</span>` : ''}
          ${faseElim ? `<span style="font-size:10px;color:#a32d2d;font-weight:400;background:rgba(163,45,45,0.12);padding:2px 8px;border-radius:4px;">Eliminado: ${faseElim}</span>` : ''}
        </div>
        <button class="cv-match-modal__close" title="Cerrar">&times;</button>
      </div>
      <div class="cv-match-modal__body">
        <table class="cv-match-modal__table">
          <thead>
            <tr>
              <th>Campo</th>
              <th>Propiedad</th>
              <th>Requerimiento</th>
              <th style="text-align:center;">Estado</th>
            </tr>
          </thead>
          <tbody>
            ${campos.map(c => renderCampoRow(c)).join('')}
          </tbody>
        </table>
      </div>
      <div class="cv-match-modal__footer">
        <button class="cv-btn" id="cv-mm-close">Cerrar</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  // ── Eventos ──
  const closeBtn = modal.querySelector('.cv-match-modal__close');
  const closeFooter = modal.querySelector('#cv-mm-close');

  function closeModal() {
    modal.remove();
  }

  closeBtn.addEventListener('click', closeModal);
  closeFooter.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  // Escape key
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      closeModal();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
}


/* ── RENDER FILA DE CAMPO ── */

function renderCampoRow(campo) {
  const nombre = campo.label || campo.nombre || '—';
  const propVal = campo.propiedad || '—';
  const reqVal = campo.requerimiento || '—';

  // Determinar ícono de compatibilidad
  let icono = '';
  let cls = '';
  if (campo.compatible === true) {
    icono = '✓';
    cls = 'cv-mm-ok';
  } else if (campo.compatible === false) {
    icono = '✗';
    cls = 'cv-mm-fail';
  } else {
    icono = '—';
    cls = 'cv-mm-neutral';
  }

  // Si es filtro duro (peso -1), resaltar
  const isHardFilter = campo.peso === -1;

  return `
    <tr${isHardFilter ? ' style="background:rgba(163,45,45,0.04);"' : ''}>
      <td class="cv-mm-label">
        ${nombre}
        ${campo.detalle ? `<br><span style="font-size:9px;color:#4a4e62;">${escHtml(campo.detalle)}</span>` : ''}
      </td>
      <td class="cv-mm-prop">${escHtml(propVal.length > 80 ? propVal.substring(0, 77) + '...' : propVal)}</td>
      <td class="cv-mm-req">${escHtml(reqVal.length > 80 ? reqVal.substring(0, 77) + '...' : reqVal)}</td>
      <td class="cv-mm-status"><span class="${cls}">${icono}</span></td>
    </tr>
  `;
}


/* ── SHOW TOAST (si no existe en el contexto) ── */

if (typeof showToast !== 'function') {
  function showToast(msg) {
    const existing = document.querySelector('.cv-toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = 'cv-toast';
    toast.textContent = msg;
    toast.style.cssText = `
      position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
      background:#1a1c24;border:1px solid #2e3044;color:#e8eaf0;
      padding:8px 18px;border-radius:8px;font-size:12px;z-index:99999;
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }
}
