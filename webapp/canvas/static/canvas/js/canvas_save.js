/**
 * canvas_save.js — PropFlow Canvas Save
 *
 * Autoguardado con debounce, carga, serialización de snapshot.
 */

/* ── DEBOUNCED SAVE ── */

let saveTimer = null;

function markDirty() {
  STATE.dirty = true;
  updateStatus('Sin guardar', true);
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveCanvas, 2000);
}

/* ── BUILD SNAPSHOT ── */

function buildSnapshot() {
  const nodos = Object.values(STATE.nodos).map(n => ({
    id: n.id,
    tipo: n.tipo,
    ref_id: n.ref_id,
    x: Math.round(n.x),
    y: Math.round(n.y),
    width: n.width,
    height: n.height,
    collapsed: n.collapsed || false,
    color: n.color || null,
    field_data: n.field_data || null,
  }));

  const aristas = Object.values(STATE.aristas).map(e => ({
    id: e.id,
    origen: e.origen,
    destino: e.destino,
    tipo: e.tipo,
    label: e.label || '',
  }));

  const agenteSelect = document.getElementById('agente-select');
  return {
    nodos,
    aristas,
    viewport: { ...STATE.viewport },
    // Guardar los campos activos para restaurarlos al recargar
    campos: getActiveCampos(),
    // Guardar el agente seleccionado para restaurarlo al recargar
    agente_id: agenteSelect ? agenteSelect.value : '',
  };
}

/* ── SAVE (forzado, ignora dirty flag) ── */

async function doSave() {
  updateStatus('Guardando...', true);

  const nombre = document.getElementById('cv-lienzo-nombre').value;

  const payload = {
    nombre: nombre,
    snapshot: buildSnapshot(),
  };

  try {
    const res = await fetch(`/canvas/api/lienzo/${LIENZO_ID}/save/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF,
      },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      STATE.dirty = false;
      updateStatus('Guardado', false);
      showToast('Guardado ✓');
      return true;
    } else {
      const errText = await res.text().catch(() => 'Unknown error');
      console.error('Save failed:', res.status, errText);
      updateStatus('Error al guardar (' + res.status + ')', true);
      return false;
    }
  } catch (err) {
    console.error('Save error:', err);
    updateStatus('Error de red', true);
    return false;
  }
}

/* ── SAVE (autoguardado, respeta dirty flag) ── */

async function saveCanvas() {
  if (!STATE.dirty) return;
  return doSave();
}

/* ── LOAD ── */

async function loadCanvas() {
  try {
    const res = await fetch(`/canvas/api/lienzo/${LIENZO_ID}/load/`);
    const data = await res.json();
    if (data.snapshot && data.snapshot.nodos) {
      // Clear existing nodes
      Object.values(STATE.nodos).forEach(n => {
        if (n.el && n.el.parentNode) n.el.parentNode.removeChild(n.el);
      });
      STATE.nodos = {};
      STATE.aristas = {};

      restoreSnapshot(data.snapshot);
    }
    if (data.nombre) {
      document.getElementById('cv-lienzo-nombre').value = data.nombre;
    }
    updateStatus('Cargado', false);
  } catch (err) {
    console.error('Load error:', err);
  }
}

/* ── STATUS UI ── */

function updateStatus(text, dirty) {
  const dot = document.getElementById('status-dot');
  const txt = document.getElementById('status-text');
  if (dot) {
    dot.classList.toggle('cv-status__dot--dirty', dirty);
  }
  if (txt) txt.textContent = text;
}

/* ── TOAST ── */

function showToast(message) {
  const toast = document.getElementById('cv-toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => {
    toast.classList.remove('visible');
  }, 2500);
}

/* ── SAVE BUTTON (siempre guarda, ignora dirty) ── */

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('btn-save');
  if (btn) {
    btn.addEventListener('click', doSave);
  }
});

/* ── BEFOREUNLOAD: guardar si hay cambios pendientes ── */

window.addEventListener('beforeunload', (e) => {
  if (STATE.dirty) {
    // sendBeacon no necesita CSRF porque envía como POST simple;
    // pero el endpoint espera CSRF. Para evitarlo, enviamos síncrono.
    try {
      const nombre = document.getElementById('cv-lienzo-nombre').value;
      const payload = {
        nombre: nombre,
        snapshot: buildSnapshot(),
      };
      navigator.sendBeacon(
        `/canvas/api/lienzo/${LIENZO_ID}/save/`,
        new Blob([JSON.stringify(payload)], { type: 'application/json' })
      );
    } catch (_) {
      // Si falla, mostrar diálogo
    }
    // Siempre mostrar diálogo si hay cambios sin guardar
    e.preventDefault();
    e.returnValue = '';
  }
});
