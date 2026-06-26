/**
 * canvas_history.js — PropFlow Canvas Undo/Redo
 *
 * Sistema de historial para deshacer/rehacer cambios en el canvas.
 * Almacena snapshots del STATE antes de cada modificación.
 * Límite: 50 niveles de deshacer.
 */

const HISTORY = {
  undoStack: [],
  redoStack: [],
  maxLen: 50,
  /** Bandera para evitar capturar durante una restauración */
  _restoring: false,
};


/**
 * Captura el estado actual del canvas en el historial de deshacer.
 * Debe llamarse ANTES de hacer un cambio.
 */
function captureState() {
  if (HISTORY._restoring) return;

  // Tomar snapshot profundo solo de nodos y aristas
  const snap = {
    nodos: {},
    aristas: {},
    viewport: { ...STATE.viewport },
  };

  Object.values(STATE.nodos).forEach(n => {
    snap.nodos[n.id] = {
      id: n.id,
      tipo: n.tipo,
      ref_id: n.ref_id,
      x: n.x,
      y: n.y,
      width: n.width,
      height: n.height,
      collapsed: n.collapsed || false,
      color: n.color || null,
      field_data: n.field_data ? JSON.parse(JSON.stringify(n.field_data)) : null,
    };
  });

  Object.values(STATE.aristas).forEach(e => {
    snap.aristas[e.id] = { ...e };
  });

  HISTORY.undoStack.push(snap);
  if (HISTORY.undoStack.length > HISTORY.maxLen) {
    HISTORY.undoStack.shift();
  }
  // Al hacer un nuevo cambio, el redo se limpia
  HISTORY.redoStack = [];
  updateUndoButtons();
}


/**
 * Deshace el último cambio.
 */
function undo() {
  if (HISTORY.undoStack.length === 0) return;

  // Guardar estado actual en redo
  const currentSnap = captureCurrentState();
  HISTORY.redoStack.push(currentSnap);

  // Restaurar último estado guardado
  const snap = HISTORY.undoStack.pop();
  HISTORY._restoring = true;
  restoreStateFromHistory(snap);
  HISTORY._restoring = false;

  updateUndoButtons();
  markDirty();
  showToast('Deshecho ↩');
}


/**
 * Rehace el último cambio deshecho.
 */
function redo() {
  if (HISTORY.redoStack.length === 0) return;

  // Guardar estado actual en undo
  const currentSnap = captureCurrentState();
  HISTORY.undoStack.push(currentSnap);

  // Restaurar siguiente estado
  const snap = HISTORY.redoStack.pop();
  HISTORY._restoring = true;
  restoreStateFromHistory(snap);
  HISTORY._restoring = false;

  updateUndoButtons();
  markDirty();
  showToast('Rehecho ↪');
}


/**
 * Captura el estado actual como snapshot para el historial.
 */
function captureCurrentState() {
  const snap = {
    nodos: {},
    aristas: {},
    viewport: { ...STATE.viewport },
  };

  Object.values(STATE.nodos).forEach(n => {
    snap.nodos[n.id] = {
      id: n.id,
      tipo: n.tipo,
      ref_id: n.ref_id,
      x: n.x,
      y: n.y,
      width: n.width,
      height: n.height,
      collapsed: n.collapsed || false,
      color: n.color || null,
      field_data: n.field_data ? JSON.parse(JSON.stringify(n.field_data)) : null,
    };
  });

  Object.values(STATE.aristas).forEach(e => {
    snap.aristas[e.id] = { ...e };
  });

  return snap;
}


/**
 * Restaura el canvas desde un snapshot del historial.
 * Reconstruye todos los nodos y aristas.
 */
function restoreStateFromHistory(snap) {
  // Limpiar DOM
  Object.values(STATE.nodos).forEach(n => {
    if (n.el && n.el.parentNode) {
      n.el.parentNode.removeChild(n.el);
    }
  });

  // Restaurar nodos
  STATE.nodos = {};
  Object.values(snap.nodos).forEach(n => {
    STATE.nodos[n.id] = {
      id: n.id,
      tipo: n.tipo,
      ref_id: n.ref_id,
      x: n.x,
      y: n.y,
      width: n.width || 220,
      height: n.height || 160,
      collapsed: n.collapsed || false,
      color: n.color || null,
      el: null,
      field_data: n.field_data || null,
    };
  });

  // Restaurar aristas
  STATE.aristas = {};
  Object.values(snap.aristas).forEach(e => {
    STATE.aristas[e.id] = { ...e };
  });

  // Re-renderizar todos los nodos
  const nodosList = Object.values(snap.nodos);
  const campos = getActiveCampos();

  // Si hay field_data, render con datos completos; si no, placeholder
  const hasData = nodosList.some(n => n.tipo === 'propiedad' && n.field_data);
  if (hasData) {
    nodosList.forEach(n => {
      if (n.tipo === 'propiedad' && n.field_data) {
        const data = n.field_data;
        const node = document.createElement('div');
        node.className = 'cv-node cv-node--prop';
        node.dataset.id = n.id;
        node.style.left = n.x + 'px';
        node.style.top  = n.y + 'px';

        const title = data.title || data.direction || `Prop #${n.ref_id}`;
        const price = formatPrice(data.price, data.currency);
        const district = data.district_name || data.district || '';
        const imgUrl = getPropertyImageUrl(data);

        node.innerHTML = `
          <div class="cv-node__header">
            <span class="cv-node__badge cv-badge--prop">PROP</span>
            <span class="cv-node__title">${escHtml(title)}</span>
            <button class="cv-node__collapse">${n.collapsed ? '+' : '−'}</button>
            <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
          </div>
          <div class="cv-node__thumb${imgUrl ? '' : ' cv-node__thumb--empty'}">
            ${imgUrl ? `<img src="${escHtml(imgUrl)}" loading="lazy" onerror="this.parentElement.classList.add('cv-node__thumb--empty')" alt="">` : ''}
          </div>
          <div class="cv-node__body">
            <div class="cv-field"><span class="cv-field__key">Precio</span><span class="cv-field__val">${price || '—'}</span></div>
            <div class="cv-field"><span class="cv-field__key">Distrito</span><span class="cv-field__val">${escHtml(district) || '—'}</span></div>
            ${campos && campos.length ? campos.filter(c => !['title','price','district_name','id', 'code', 'file'].includes(c)).map(c => `
              <div class="cv-field"><span class="cv-field__key">${escHtml(c)}</span><span class="cv-field__val">${escHtml(formatField(data[c]))}</span></div>
            `).join('') : ''}
          </div>
          <div class="cv-node__footer">
            <button class="cv-btn--matches" data-prop-id="${n.ref_id}">Ver matches &rarr;</button>
            <span class="cv-match-count">— reqs</span>
          </div>
          <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
          <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
          <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
          <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
        `;

        dom.nodes.appendChild(node);
        STATE.nodos[n.id].el = node;
        if (n.collapsed) node.classList.add('collapsed');
        registerNodeEvents(n.id, node);
      } else {
        renderSinglePlaceholder(n);
      }
    });
  } else {
    nodosList.forEach(n => renderSinglePlaceholder(n));
  }

  // Restaurar viewport
  if (snap.viewport) {
    STATE.viewport = { ...snap.viewport };
  }

  updateTransform();
  updateEdges();
}


/**
 * Renderiza un nodo placeholder individual.
 */
function renderSinglePlaceholder(n) {
  const node = document.createElement('div');
  node.className = `cv-node cv-node--${n.tipo}`;
  node.dataset.id = n.id;
  node.style.left = n.x + 'px';
  node.style.top  = n.y + 'px';

  if (n.tipo === 'propiedad') {
    node.innerHTML = `
      <div class="cv-node__header">
        <span class="cv-node__badge cv-badge--prop">PROP</span>
        <span class="cv-node__title">Prop #${n.ref_id}</span>
        <button class="cv-node__collapse">${n.collapsed ? '+' : '−'}</button>
        <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
      </div>
      <div class="cv-node__body"><div style="color:var(--cv-text-muted);font-size:11px;text-align:center;padding:8px">Cargando datos...</div></div>
      <div class="cv-node__footer">
        <button class="cv-btn--matches" data-prop-id="${n.ref_id}">Ver matches &rarr;</button>
        <span class="cv-match-count">— reqs</span>
      </div>
      <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
      <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
      <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
      <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
    `;
  } else if (n.tipo === 'requerimiento') {
    node.innerHTML = `
      <div class="cv-node__header">
        <span class="cv-node__badge cv-badge--req">REQ</span>
        <span class="cv-node__title">Req #${n.ref_id}</span>
      </div>
      <div class="cv-node__body"><div style="color:var(--cv-text-muted);font-size:11px;text-align:center;padding:8px">Cargando...</div></div>
      <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
      <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
      <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
      <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
    `;
  } else {
    node.innerHTML = `
      <div class="cv-nota__handle">&#10022; nota</div>
      <div class="cv-nota__body" contenteditable="true">Nota</div>
      <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
      <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
      <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
      <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
    `;
  }

  dom.nodes.appendChild(node);
  STATE.nodos[n.id].el = node;
  if (n.collapsed) node.classList.add('collapsed');
  registerNodeEvents(n.id, node);
}


/**
 * Actualiza el estado visual de los botones Undo/Redo.
 */
function updateUndoButtons() {
  const btnUndo = document.getElementById('btn-undo');
  const btnRedo = document.getElementById('btn-redo');
  if (btnUndo) btnUndo.disabled = HISTORY.undoStack.length === 0;
  if (btnRedo) btnRedo.disabled = HISTORY.redoStack.length === 0;
}


/* ── KEYBOARD SHORTCUTS ── */

function initHistoryKeyboard() {
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
      e.preventDefault();
      undo();
    }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
      e.preventDefault();
      redo();
    }
  });
}


/* ── INIT ── */

document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    const btnUndo = document.getElementById('btn-undo');
    const btnRedo = document.getElementById('btn-redo');
    if (btnUndo) btnUndo.addEventListener('click', undo);
    if (btnRedo) btnRedo.addEventListener('click', redo);
    updateUndoButtons();
    initHistoryKeyboard();
  }, 150);
});
