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
  const hasData = nodosList.some(n =>
    (n.tipo === 'propiedad' && n.field_data) ||
    n.tipo === 'archivo' ||
    n.tipo === 'enlace'
  );
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

  // Refrescar nodos lead_analysis y lead_global despues de undo/redo
  setTimeout(function() {
    Object.values(STATE.nodos).forEach(function(n) {
      if (n.tipo === 'lead_analysis' && n.el) {
        var propId = n.ref_id || (n.field_data && n.field_data.prop_id);
        if (!propId) return;
        var gran = (n.field_data && n.field_data._granularity) || 'day';
        fetch('/canvas/api/lead-analysis/' + propId + '/?granularity=' + gran)
          .then(function(r) { return r.json(); })
          .then(function(data) { renderLeadAnalysisBody(n.id, data); })
          .catch(function() {});
      }
      if (n.tipo === 'lead_global' && n.el) {
        var gran = (n.field_data && n.field_data._granularity) || 'day';
        fetch('/canvas/api/lead-analysis-global/?granularity=' + gran)
          .then(function(r) { return r.json(); })
          .then(function(data) { renderLeadAnalysisBody(n.id, data); })
          .catch(function() {});
      }
    });
  }, 300);
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
        <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
      </div>
      <div class="cv-node__req-info">
        <span class="cv-req-info__item" style="color:var(--cv-text-muted);font-size:10px;">Cargando datos...</span>
      </div>
      <div class="cv-node__req-body">
        <div class="cv-req-text" style="color:var(--cv-text-muted);font-size:10px;text-align:center;padding:4px">Cargando...</div>
      </div>
      <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
      <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
      <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
      <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
    `;
  } else if (n.tipo === 'archivo') {
    const fd = n.field_data || {};
    const iconMap = { excel: '📊', word: '📝', pdf: '📄', image: '🖼️', other: '📎' };
    const icon = iconMap[fd.file_type] || '📎';
    const tipoLabel = { excel: 'EXCEL', word: 'WORD', pdf: 'PDF', image: 'IMG', other: 'ARCHIVO' };
    const label = tipoLabel[fd.file_type] || 'ARCHIVO';
    const badgeClass = 'cv-badge--' + (fd.file_type || 'other');
    const tamanoStr = typeof formatFileSize === 'function' ? formatFileSize(fd.file_size) : (fd.file_size || '—');
    node.innerHTML = `
      <div class="cv-node__header">
        <span class="cv-node__badge cv-badge--archivo ${badgeClass}">${icon} ${label}</span>
        <span class="cv-node__title">${escHtml(fd.file_name || 'Archivo')}</span>
        <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
      </div>
      <div class="cv-node__body">
        ${fd.file_type === 'image' ? `<img src="/canvas/api/media/${n.ref_id}/" style="width:100%;max-height:180px;object-fit:cover;border-radius:4px;margin-bottom:6px;cursor:pointer;" onclick="window.open('/canvas/api/media/${n.ref_id}/','_blank')" onerror="this.style.display='none'">` : ''}
        ${fd.file_type === 'pdf' && n.ref_id ? `<div class="cv-pdf-preview" data-pdf-id="${n.ref_id}" style="width:100%;height:120px;background:var(--cv-surface-2);border-radius:4px;margin-bottom:6px;display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--cv-text-muted);overflow:hidden;"><span>Cargando PDF...</span></div>` : ''}
        <div class="cv-file-info">
          <span class="cv-file-info__size">${tamanoStr}</span>
          <div style="display:flex;gap:6px;margin-top:4px;">
            <a class="cv-file-info__link" href="${escHtml(fd.file_url)}" download="${escHtml(fd.file_name || 'archivo')}" style="font-size:11px;">⬇ Descargar</a>
            ${['excel','word'].includes(fd.file_type) ? `<a class="cv-file-info__link" href="https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(fd.file_url)}" target="_blank" rel="noopener" style="font-size:11px;">👁 Ver online</a>` : ''}
          </div>
        </div>
      </div>
      <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
      <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
      <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
      <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
    `;
  } else if (n.tipo === 'enlace') {
    const fd = n.field_data || {};
    const displayUrl = (fd.url || '').length > 50 ? (fd.url || '').substring(0, 47) + '...' : (fd.url || '');
    node.innerHTML = `
      <div class="cv-node__header">
        <span class="cv-node__badge cv-badge--enlace">🔗 ENLACE</span>
        <span class="cv-node__title">${escHtml(fd.url_title || fd.url || 'Enlace')}</span>
        <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
      </div>
      <div class="cv-node__body">
        <a class="cv-link-display" href="${escHtml(fd.url)}" target="_blank" rel="noopener" title="${escHtml(fd.url)}">
          ${escHtml(displayUrl)} ↗
        </a>
      </div>
      <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
      <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
      <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
      <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
    `;
  } else if (n.tipo === 'lead_analysis') {
    var savedGran = (n.field_data && n.field_data._granularity) || 'day';
    var savedGranLabel = { day: 'Día', week: 'Semana', month: 'Mes' }[savedGran] || 'Día';
    node.innerHTML = `
      <div class="cv-node__header">
        <span class="cv-node__badge cv-badge--lead-analysis">📊 LEAD</span>
        <span class="cv-node__title">An\u00e1lisis de Leads</span>
        <span class="cv-lead-gran-label" title="Click derecho \u2192 cambiar vista">📅 ${savedGranLabel}</span>
        <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
      </div>
      <div class="cv-node__body"><div style="color:var(--cv-text-muted);font-size:11px;text-align:center;padding:16px">Cargando datos...</div></div>
      <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
      <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
      <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
      <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
    `;
  } else if (n.tipo === 'lead_nodo') {
    const fd = n.field_data || {};
    var contactName = fd.contact_name || fd.username || 'Lead #' + (n.ref_id || '');
    var phone = fd.phone || '';
    var email = fd.email || '';
    var source = fd.source || '';
    var lastMsg = fd.last_message_text || '';
    var notes = fd.notes || '';
    node.innerHTML = `
      <div class="cv-node__header" style="cursor:pointer;" title="Click para abrir CRM" onclick="window.open('https://app.propify.pe/crm/lead/${n.ref_id || ''}','_blank')">
        <span class="cv-node__badge cv-badge--lead-analysis">👤 LEAD</span>
        <span class="cv-node__title">${escHtml(contactName)}</span>
        <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
      </div>
      <div class="cv-node__req-info">
        ${phone ? '<span class="cv-req-info__item">📞 ' + escHtml(phone) + '</span>' : ''}
        ${email ? '<span class="cv-req-info__item">✉ ' + escHtml(email) + '</span>' : ''}
      </div>
      <div class="cv-node__req-body" style="font-size:11px;max-height:200px;overflow-y:auto;">
        ${source ? '<div style="color:var(--cv-text-muted);margin-bottom:4px;">📡 ' + escHtml(source) + '</div>' : ''}
        ${lastMsg ? '<div style="background:rgba(92,156,230,0.08);border-radius:6px;padding:6px;margin-bottom:4px;border-left:2px solid #5c9ce6;"><strong style="font-size:10px;color:#5c9ce6;">💬 Conversaci\u00f3n</strong><div style="color:var(--cv-text);margin-top:2px;white-space:pre-wrap;">' + escHtml(lastMsg) + '</div></div>' : ''}
        ${notes ? '<div style="background:rgba(255,221,0,0.06);border-radius:6px;padding:6px;border-left:2px solid #ffdd00;"><strong style="font-size:10px;color:#ffdd00;">📝 Notas</strong><div style="color:var(--cv-text-muted);margin-top:2px;white-space:pre-wrap;">' + escHtml(notes) + '</div></div>' : ''}
      </div>
      <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
      <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
      <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
      <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
    `;
  } else if (n.tipo === 'lead_global') {
    var savedGran = (n.field_data && n.field_data._granularity) || 'day';
    var savedGranLabel = { day: 'Día', week: 'Semana', month: 'Mes' }[savedGran] || 'Día';
    node.innerHTML = `
      <div class="cv-node__header">
        <span class="cv-node__badge cv-badge--lead-analysis">📊 GLOBAL</span>
        <span class="cv-node__title">Todos los Leads</span>
        <span class="cv-lead-gran-label" title="Click derecho \u2192 cambiar vista">📅 ${savedGranLabel}</span>
        <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
      </div>
      <div class="cv-node__body"><div style="color:var(--cv-text-muted);font-size:11px;text-align:center;padding:16px">Cargando datos...</div></div>
      <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
      <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
      <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
      <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
    `;
  } else {
    // NOTA: nueva estructura con header, título editable y botón lápiz
    node.innerHTML = `
      <div class="cv-nota__header">
        <span class="cv-nota__icon">&#10022;</span>
        <span class="cv-nota__title-display">Nota</span>
        <input class="cv-nota__title-input" value="Nota" style="display:none">
        <button class="cv-nota__edit-title" title="Editar título">&#9998;</button>
        <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
      </div>
      <div class="cv-nota__body" contenteditable="false">Nota</div>
      <button class="cv-nota__edit-body" title="Editar contenido">&#9998; Editar</button>
      <div class="cv-nota__resize" title="Redimensionar"></div>
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
  // Adjuntar menú contextual de granularidad para nodos lead_analysis y lead_global
  if (n.tipo === 'lead_analysis' || n.tipo === 'lead_global') {
    node.addEventListener('contextmenu', function(e) {
      e.preventDefault();
      e.stopPropagation();
      if (typeof showLeadContextMenu === 'function') {
        showLeadContextMenu(n.id, e);
      }
    });
  }
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
