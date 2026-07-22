/**
 * canvas_nodes.js — PropFlow Canvas Nodes (v12 - dedup + snapshot refresh)
 * DEBUG: Si ves este mensaje, el JS nuevo está cargado.
 */
console.log('[CanvasNodes] v12 cargado - dedup + snapshot refresh');
/**
 * canvas_nodes.js — PropFlow Canvas Nodes
 *
 * Renderizado y lógica de nodos: Propiedad, Requerimiento, Nota, Archivo, Enlace, Match.
 * Maneja creación, posicionamiento, colapso y eliminación.
 */

/* ═══════════════════════════════════════════════════════════════════════════
 * UTILITIES
 * ═══════════════════════════════════════════════════════════════════════════ */

function formatPrice(val, currency) {
  if (val === null || val === undefined) return '—';
  const num = parseFloat(val);
  if (isNaN(num)) return val;
  const sym = currency === 'PEN' ? 'S/ ' : currency === 'USD' ? '$ ' : '$ ';
  return sym + num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function formatField(val) {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'object') return JSON.stringify(val);
  return String(val);
}

function escHtml(str) {
  if (str === null || str === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

/**
 * Obtiene la URL de imagen de una propiedad.
 * Prioriza la URL calculada por el servidor (`_imagen_url`),
 * que incluye la consulta a property_media para obtener la imagen real.
 * @param {object} data - field_values de la propiedad (incluye _imagen_url)
 * @returns {string|null} URL de imagen o null
 */
function getPropertyImageUrl(data) {
  if (!data) return null;

  // 1. URL calculada por el servidor (consulta property_media + fallback code)
  if (data._imagen_url && typeof data._imagen_url === 'string') {
    return data._imagen_url;
  }

  // 2. Fallback local: construir desde code si _imagen_url no está disponible
  const baseUrl = 'https://propifymedia01.blob.core.windows.net/media';
  if (data.code) {
    const code = String(data.code);
    if (/\.(jpg|jpeg|png|webp|gif)$/i.test(code)) {
      return `${baseUrl}/${code}`;
    }
    return `${baseUrl}/${code}.jpg`;
  }

  return null;
}

/**
 * Formatea el tipo de requerimiento para mostrar en la tarjeta.
 * Traduce valores internos a etiquetas legibles.
 */
function formatTipoRequerimiento(val) {
  if (!val) return '';
  const map = {
    'compra': 'Compra',
    'alquiler': 'Alquiler',
    'anticresis': 'Anticresis',
    'ambos': 'Compra y Alquiler',
    'compartido': 'Compartido',
    'no_especificado': '',
    'REQUERIMIENTO': 'Requerimiento',
    'REQUERIMIENTO COMPRA': 'Req. Compra',
    'REQUERIMIENTO ALQUILER': 'Req. Alquiler',
    'REQUERIMIENTO COMPRA, REQUERIMIENTO ALQUILER': 'Compra + Alquiler',
    'REQUERIMIENTO ALQUILER, REQUERIMIENTO COMPRA': 'Alquiler + Compra',
    'PROPIEDAD VENTA': 'Prop. Venta',
    'MIXTO': 'Mixto',
    'BASURA': '',
    'OTRO': 'Otro',
  };
  return map[val] || val;
}

/* ── window exports: utilities ── */
window.formatPrice = formatPrice;
window.formatField = formatField;
window.escHtml = escHtml;
window.getPropertyImageUrl = getPropertyImageUrl;
window.formatTipoRequerimiento = formatTipoRequerimiento;


/* ═══════════════════════════════════════════════════════════════════════════
 * AUX FUNCTIONS
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Re-renderiza SOLO el body de un nodo propiedad (el contenido entre header y footer).
 * Preserva header (título, botones) y footer (matches).
 */
function reRenderPropBody(id, campos) {
  const nodo = STATE.nodos[id];
  if (!nodo || !nodo.el || !nodo.field_data) return;
  if (nodo.tipo !== 'propiedad') return;

  const data = nodo.field_data;
  const body = nodo.el.querySelector('.cv-node__body');
  if (!body) return;

  const price = formatPrice(data.price, data.currency);
  const district = data.district_name || data.district || '';

  body.innerHTML = `
    <div class="cv-field"><span class="cv-field__key">Precio</span><span class="cv-field__val">${price || '—'}</span></div>
    <div class="cv-field"><span class="cv-field__key">Distrito</span><span class="cv-field__val">${escHtml(district) || '—'}</span></div>
    ${campos && campos.length ? campos.filter(c => !['title','price','district_name','id', 'code', 'file'].includes(c)).map(c => `
      <div class="cv-field"><span class="cv-field__key">${escHtml(c)}</span><span class="cv-field__val">${escHtml(formatField(data[c]))}</span></div>
    `).join('') : ''}
  `;
}

/**
 * Obtiene la lista actual de campos seleccionados en los checkboxes.
 */
function getActiveCampos() {
  return Array.from(document.querySelectorAll('.campo-check:checked')).map(c => c.value);
}

function registerNodeEvents(id, el) {
  const isNota = el.classList.contains('cv-node--nota');

  // Drag: para notas usar .cv-nota__header; para props usar .cv-node__header
  const dragHandle = el.querySelector('.cv-nota__header') || el.querySelector('.cv-node__header');
  if (dragHandle) {
    dragHandle.addEventListener('mousedown', e => {
      if (e.target.closest('input') || e.target.closest('.cv-btn')) return;
      startNodeDrag(e, id);
    });
  }
  // En nodos propiedad, también arrastrar desde el body (no en ports/botones)
  if (!isNota) {
    el.addEventListener('mousedown', e => {
      if (e.target.closest('.cv-node__header') || e.target.closest('.cv-nota__header')) return;
      if (e.target.closest('.cv-btn') || e.target.closest('.cv-port')) return;
      selectNode(id);
      startNodeDrag(e, id);
    });
  }

  // Connection ports — 4 direcciones (top, right, bottom, left)
  el.querySelectorAll('.cv-port').forEach(port => {
    port.addEventListener('mousedown', e => {
      const portDir = port.dataset.port || 'right';
      startConnection(e, id, portDir);
    });
  });

  // Collapse button (solo para nodos propiedad/requerimiento)
  const collapseBtn = el.querySelector('.cv-node__collapse');
  if (collapseBtn) {
    collapseBtn.addEventListener('click', e => {
      e.stopPropagation();
      toggleCollapse(id);
    });
  }

  // Delete button — requerimientos: eliminar directo sin confirmación
  const deleteBtn = el.querySelector('.cv-node__delete');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', e => {
      e.stopPropagation();
      const isReq = el.classList.contains('cv-node--req');
      if (isReq) {
        deleteNode(id);
      } else if (typeof showConfirmModal === 'function') {
        showConfirmModal('¿Eliminar este nodo del lienzo?', () => deleteNode(id));
      } else {
        deleteNode(id);
      }
    });
  }

  // Matches button (solo para nodos propiedad)
  const matchesBtn = el.querySelector('.cv-btn--matches');
  if (matchesBtn) {
    matchesBtn.addEventListener('click', e => {
      e.stopPropagation();
      const propId = matchesBtn.dataset.propId;
      loadMatchesForProp(propId, id);
    });
  }

  // ── NOTA: botón editar título (lápiz) ──
  const editTitleBtn = el.querySelector('.cv-nota__edit-title');
  const titleDisplay = el.querySelector('.cv-nota__title-display');
  const titleInput = el.querySelector('.cv-nota__title-input');
  if (editTitleBtn && titleDisplay && titleInput) {
    editTitleBtn.addEventListener('click', e => {
      e.stopPropagation();
      titleDisplay.style.display = 'none';
      titleInput.style.display = '';
      titleInput.value = titleDisplay.textContent;
      titleInput.focus();
      titleInput.select();
    });
    titleInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        titleInput.blur();
      }
    });
    titleInput.addEventListener('blur', () => {
      titleDisplay.textContent = titleInput.value || 'Nota';
      titleInput.style.display = 'none';
      titleDisplay.style.display = '';
      markDirty();
    });
  }

  // ── NOTA: botón editar contenido (lápiz) ──
  const editBodyBtn = el.querySelector('.cv-nota__edit-body');
  const notaBody = el.querySelector('.cv-nota__body');
  if (editBodyBtn && notaBody) {
    editBodyBtn.addEventListener('click', e => {
      e.stopPropagation();
      const isEditing = notaBody.getAttribute('contenteditable') === 'true';
      if (isEditing) {
        notaBody.setAttribute('contenteditable', 'false');
        editBodyBtn.textContent = '\u270E Editar';
        notaBody.blur();
        markDirty();
      } else {
        notaBody.setAttribute('contenteditable', 'true');
        editBodyBtn.textContent = '\u2714 Listo';
        notaBody.focus();
      }
    });
    notaBody.addEventListener('input', () => { markDirty(); });
  }

  // ── NOTA: resize desde esquina ──
  const resizeHandle = el.querySelector('.cv-nota__resize');
  if (resizeHandle) {
    resizeHandle.addEventListener('mousedown', e => {
      e.stopPropagation();
      e.preventDefault();
      const startX = e.clientX;
      const startY = e.clientY;
      const startW = el.offsetWidth;
      const startH = el.offsetHeight;
      const nodo = STATE.nodos[id];

      const onMouseMove = (ev) => {
        const vp = STATE.viewport;
        const newW = Math.max(160, startW + (ev.clientX - startX) / vp.zoom);
        const newH = Math.max(80, startH + (ev.clientY - startY) / vp.zoom);
        el.style.width = newW + 'px';
        el.style.height = newH + 'px';
        if (nodo) {
          nodo.width = newW;
          nodo.height = newH;
        }
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        updateEdges();
        markDirty();
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });
  } // ← cierre de if(resizeHandle)

  // ── GALERÍA: doble clic en thumbnail abre galería ──
  const thumb = el.querySelector('.cv-node__thumb');
  if (thumb) {
    thumb.addEventListener('dblclick', function(e) {
      e.stopPropagation();
      const img = thumb.querySelector('img');
      const placeholder = thumb.querySelector('.cv-node__thumb-placeholder');
      const propId = (img && img.dataset.propId) || (placeholder && placeholder.dataset.propId);
      if (propId && typeof openPropertyGallery === 'function') {
        openPropertyGallery(parseInt(propId));
      }
    });
  }

  // ── LEAD COUNT: clic abre nodo de análisis de leads ──
  const leadCountEl = el.querySelector('.cv-lead-count');
  if (leadCountEl) {
    leadCountEl.addEventListener('click', function(e) {
      e.stopPropagation();
      const propNode = STATE.nodos[id];
      if (!propNode || !propNode.ref_id) return;
      // Verificar si ya existe un nodo de análisis para esta propiedad
      const existingId = 'lead_analysis_' + propNode.ref_id;
      if (STATE.nodos[existingId]) {
        // Si ya existe, solo centrar la vista
        if (typeof centerOnNode === 'function') {
          centerOnNode(existingId);
        }
        return;
      }
      openLeadAnalysis(propNode.ref_id, id);
    });
  }
}

function positionNode(id, el, x, y) {
  el.style.left = x + 'px';
  el.style.top  = y + 'px';
}

/* ── window exports: aux functions ── */
window.reRenderPropBody = reRenderPropBody;
window.getActiveCampos = getActiveCampos;
window.registerNodeEvents = registerNodeEvents;
window.positionNode = positionNode;


/* ═══════════════════════════════════════════════════════════════════════════
 * CREAR NODOS
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Crea un nodo de tipo Propiedad en el canvas.
 * @param {number} sourceId - source_id del IntelligenceDocument
 * @param {object} data     - { title, price, district_name, ... } campos de field_values
 * @param {number} x, y     - posición inicial
 * @param {string[]} campos - lista de campos a mostrar
 */
function createPropNode(sourceId, data, x, y, campos) {
  const id = 'prop_' + sourceId;
  if (STATE.nodos[id]) {
    STATE.nodos[id].field_data = data;
    reRenderPropBody(id, campos || getActiveCampos());
    return id;
  }
  if (typeof captureState === 'function') captureState();

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--prop';
  node.dataset.id = id;
  node.style.left = x + 'px';
  node.style.top  = y + 'px';
  node.style.width = '220px';
  node.style.minWidth = '220px';
  node.style.minHeight = '60px';

  const title = data.title || data.direction || `Prop #${sourceId}`;
  const price = formatPrice(data.price, data.currency);
  const district = data.district_name || data.district || '';
  const leadCount = data._lead_count !== undefined ? parseInt(data._lead_count) : 0;

  const imgUrl = getPropertyImageUrl(data);

  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--prop">PROP</span>
      <span class="cv-node__title">${escHtml(title)}</span>
      <button class="cv-node__collapse" title="Colapsar">−</button>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__thumb${imgUrl ? '' : ' cv-node__thumb--empty'}">
      ${imgUrl ? `<img src="${escHtml(imgUrl)}" loading="lazy" onerror="this.parentElement.classList.add('cv-node__thumb--empty')" alt="" data-prop-id="${sourceId}">` : ''}
      ${!imgUrl ? `<div class="cv-node__thumb-placeholder" data-prop-id="${sourceId}" title="Ver galería">📷</div>` : ''}
    </div>
    <div class="cv-node__body">
      <div class="cv-field"><span class="cv-field__key">Precio</span><span class="cv-field__val">${price || '—'}</span></div>
      <div class="cv-field"><span class="cv-field__key">Distrito</span><span class="cv-field__val">${escHtml(district) || '—'}</span></div>
      ${campos && campos.length ? campos.filter(c => !['title','price','district_name','id', 'code', 'file'].includes(c)).map(c => `
        <div class="cv-field"><span class="cv-field__key">${escHtml(c)}</span><span class="cv-field__val">${escHtml(formatField(data[c]))}</span></div>
      `).join('') : ''}
    </div>
    <div class="cv-node__footer">
      <button class="cv-btn--matches" data-prop-id="${sourceId}">Ver matches &rarr;</button>
      <span class="cv-match-count">— reqs</span>
      <span class="cv-lead-count" title="Leads asociados">👤 <span class="cv-lead-count__num">${leadCount}</span></span>
    </div>
    <div class="cv-port cv-port--top"    data-node="${id}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${id}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${id}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${id}" data-port="left"></div>
    <div class="cv-resize-handle" data-node="${id}"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(id, node, x, y);

  const nodoData = {
    id, tipo: 'propiedad', ref_id: sourceId,
    x, y, width: 220, height: node.offsetHeight || 160,
    collapsed: false, color: null, el: node,
    field_data: data,
  };
  STATE.nodos[id] = nodoData;
  registerNodeEvents(id, node);
  markDirty();
  return id;
}

/**
 * Re-renderiza el body de TODOS los nodos propiedad con los campos activos.
 * Se llama cuando el usuario cambia los checkboxes de campos.
 */
function refreshAllPropNodes() {
  const campos = getActiveCampos();
  Object.values(STATE.nodos).forEach(n => {
    if (n.tipo === 'propiedad' && n.field_data && n.el) {
      reRenderPropBody(n.id, campos);
    }
  });
  if (typeof updateEdges === 'function') {
    updateEdges();
  }
}

/**
 * Crea un nodo de tipo Requerimiento.
 */
function createReqNode(reqId, data, x, y) {
  const id = 'req_' + reqId;
  if (STATE.nodos[id]) return id;
  if (typeof captureState === 'function') captureState();

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--req';
  node.dataset.id = id;
  node.style.left = x + 'px';
  node.style.top  = y + 'px';

  const agente      = data.agente || data.titulo || `Req #${reqId}`;
  const telefono    = data.agente_telefono || '';
  const fecha       = data.fecha || '';
  const hora        = data.hora || '';
  const tipoOrig    = data.tipo_original || data.condicion || '';
  const reqTexto    = data.requerimiento || '';

  const tipoProp    = data.tipo_propiedad || '';
  const presupuesto = data.presupuesto_monto != null
    ? formatPrice(data.presupuesto_monto, data.presupuesto_moneda)
    : (data.presupuesto ? formatPrice(data.presupuesto, data.moneda) : '');
  const distritos   = data.distritos || '';
  const urbanizacion = data.urbanizacion || '';
  const zona        = data.zona || '';
  const formaPago   = data.presupuesto_forma_pago || '';

  const tipoLabel = formatTipoRequerimiento(tipoOrig);

  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--req">REQ</span>
      <span class="cv-node__title">${escHtml(agente)}</span>
      <button class="cv-node__delete cv-node__delete--req" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__req-info">
      ${telefono ? `<span class="cv-req-info__item">📞 ${escHtml(telefono)}</span>` : ''}
      ${fecha ? `<span class="cv-req-info__item">📅 ${escHtml(fecha)}${hora ? ' ' + escHtml(hora) : ''}</span>` : ''}
      ${tipoLabel ? `<span class="cv-req-info__item">📋 ${escHtml(tipoLabel)}</span>` : ''}
    </div>
    <div class="cv-node__req-body">
      <div class="cv-req-text">${escHtml(reqTexto)}</div>
    </div>
    <div class="cv-node__req-footer">
      ${tipoProp ? `<div class="cv-field"><span class="cv-field__key">🏠 Tipo</span><span class="cv-field__val">${escHtml(tipoProp)}</span></div>` : ''}
      ${presupuesto ? `<div class="cv-field"><span class="cv-field__key">💰 Presup.</span><span class="cv-field__val">${escHtml(presupuesto)}</span></div>` : ''}
      ${distritos ? `<div class="cv-field"><span class="cv-field__key">📍 Distritos</span><span class="cv-field__val">${escHtml(distritos)}</span></div>` : ''}
      ${urbanizacion ? `<div class="cv-field"><span class="cv-field__key">🏘️ Urb.</span><span class="cv-field__val">${escHtml(urbanizacion)}</span></div>` : ''}
      ${zona ? `<div class="cv-field"><span class="cv-field__key">📌 Zona</span><span class="cv-field__val">${escHtml(zona)}</span></div>` : ''}
      ${formaPago ? `<div class="cv-field"><span class="cv-field__key">💳 Pago</span><span class="cv-field__val">${escHtml(formaPago)}</span></div>` : ''}
    </div>
    <div class="cv-port cv-port--top"    data-node="${id}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${id}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${id}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${id}" data-port="left"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(id, node, x, y);

  STATE.nodos[id] = {
    id, tipo: 'requerimiento', ref_id: reqId,
    x, y, width: 220, height: node.offsetHeight || 200,
    collapsed: false, color: null, el: node,
    field_data: data,
  };
  registerNodeEvents(id, node);
  markDirty();
  return id;
}

/**
 * Crea un nodo Nota (sticky) con título editable + resize + botón lápiz.
 */
function createNotaNode(x, y, contenido, color, titulo) {
  const id = 'nota_' + Date.now();
  if (typeof captureState === 'function') captureState();
  const node = document.createElement('div');
  node.className = 'cv-node cv-node--nota';
  node.dataset.id = id;
  node.style.left = (x || 150) + 'px';
  node.style.top  = (y || 150) + 'px';
  if (color) node.style.setProperty('--nota-color', color);

  node.innerHTML = `
    <div class="cv-nota__header">
      <span class="cv-nota__icon">&#10022;</span>
      <span class="cv-nota__title-display">${escHtml(titulo || 'Nota')}</span>
      <input class="cv-nota__title-input" value="${escHtml(titulo || 'Nota')}" style="display:none">
      <button class="cv-nota__edit-title" title="Editar título">&#9998;</button>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-nota__body" contenteditable="false">${escHtml(contenido || '')}</div>
    <button class="cv-nota__edit-body" title="Editar contenido">&#9998; Editar</button>
    <div class="cv-nota__resize" title="Redimensionar"></div>
    <div class="cv-port cv-port--top"    data-node="${id}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${id}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${id}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${id}" data-port="left"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(id, node, x || 150, y || 150);

  STATE.nodos[id] = {
    id, tipo: 'nota', ref_id: null,
    x: x || 150, y: y || 150, width: 200, height: node.offsetHeight || 120,
    collapsed: false, color: color || null, el: node,
    field_data: { titulo: titulo || 'Nota', contenido: contenido || '' },
  };
  registerNodeEvents(id, node);
  markDirty();
  return id;
}


/* ═══════════════════════════════════════════════════════════════════════════
 * REST OF FUNCTIONS
 * ═══════════════════════════════════════════════════════════════════════════ */

function toggleCollapse(id) {
  const nodo = STATE.nodos[id];
  if (!nodo || !nodo.el) return;
  if (typeof captureState === 'function') captureState();
  nodo.collapsed = !nodo.collapsed;
  nodo.el.classList.toggle('collapsed', nodo.collapsed);
  const btn = nodo.el.querySelector('.cv-node__collapse');
  if (btn) btn.textContent = nodo.collapsed ? '+' : '−';
  markDirty();
}

function deleteNode(id) {
  const nodo = STATE.nodos[id];
  if (!nodo) return;
  if (typeof captureState === 'function') captureState();
  if (nodo.el && nodo.el.parentNode) nodo.el.parentNode.removeChild(nodo.el);
  delete STATE.nodos[id];
  Object.keys(STATE.aristas).forEach(eid => {
    const e = STATE.aristas[eid];
    if (e.origen === id || e.destino === id) {
      delete STATE.aristas[eid];
    }
  });
  updateEdges();
  markDirty();
}

/* ── NODO ARCHIVO (Excel, Word, PDF, Imagen) ── */

/**
 * Crea un nodo de tipo Archivo en el canvas.
 * @param {object} data - { id, nombre, tipo, blob_url, tamano }
 * @param {number} x, y - posición inicial
 */
function createArchivoNode(data, x, y) {
  const id = 'archivo_' + data.id;
  if (STATE.nodos[id]) return id;
  if (typeof captureState === 'function') captureState();

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--archivo';
  node.dataset.id = id;
  node.style.left = (x || 100) + 'px';
  node.style.top  = (y || 100) + 'px';

  const iconMap = { excel: '📊', word: '📝', pdf: '📄', image: '🖼️', other: '📎' };
  const icon = iconMap[data.tipo] || '📎';
  const badgeClass = 'cv-badge--' + (data.tipo || 'other');
  const tipoLabel = { excel: 'EXCEL', word: 'WORD', pdf: 'PDF', image: 'IMG', other: 'ARCHIVO' };
  const label = tipoLabel[data.tipo] || 'ARCHIVO';

  const tamanoStr = formatFileSize(data.tamano);

  const officeEmbedUrl = ['excel','word'].includes(data.tipo)
    ? `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(data.blob_url)}`
    : '';

  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--archivo ${badgeClass}">${icon} ${label}</span>
      <span class="cv-node__title">${escHtml(data.nombre)}</span>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__body">
      ${data.tipo === 'image' ? `<img class="cv-archivo-img" src="/canvas/api/media/${data.id}/" ondblclick="window.open('/canvas/api/media/${data.id}/','_blank')" onerror="this.style.display='none'">` : ''}
      ${data.tipo === 'pdf' ? `<div class="cv-pdf-preview" data-pdf-id="${data.id}"><span>Cargando PDF...</span></div>` : ''}
      ${officeEmbedUrl ? `<iframe class="cv-office-preview" src="${officeEmbedUrl}" loading="lazy"></iframe>` : ''}
      <div class="cv-file-info">
        <span class="cv-file-info__size">${tamanoStr}</span>
        <div style="display:flex;gap:6px;margin-top:4px;">
          <a class="cv-file-info__link" href="${escHtml(data.blob_url)}" download="${escHtml(data.nombre)}" style="font-size:11px;">⬇ Descargar</a>
          ${['excel','word'].includes(data.tipo) ? `<a class="cv-file-info__link" href="https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(data.blob_url)}" target="_blank" rel="noopener" style="font-size:11px;">👁 Abrir en grande</a>` : ''}
        </div>
      </div>
    </div>
    <div class="cv-port cv-port--top"    data-node="${id}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${id}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${id}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${id}" data-port="left"></div>
    <div class="cv-resize-handle" data-node="${id}"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(id, node, x || 100, y || 100);

  if (data.tipo === 'pdf' && data.id) {
    renderPdfPreview(data.id, `/canvas/api/media/${data.id}/`);
  }

  STATE.nodos[id] = {
    id, tipo: 'archivo', ref_id: data.id,
    x: x || 100, y: y || 100, width: 220, height: node.offsetHeight || 90,
    collapsed: false, color: null, el: node,
    field_data: {
      file_url: data.blob_url,
      file_name: data.nombre,
      file_type: data.tipo,
      file_size: data.tamano,
    },
  };
  registerNodeEvents(id, node);
  markDirty();
  return id;
}

/* ── NODO ENLACE (URL) ── */

/**
 * Crea un nodo de tipo Enlace (URL) en el canvas.
 * @param {string} url - URL del enlace
 * @param {string} titulo - Título mostrado
 * @param {number} x, y - posición inicial
 */
function createEnlaceNode(url, titulo, x, y) {
  const id = 'enlace_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4);
  if (STATE.nodos[id]) return id;
  if (typeof captureState === 'function') captureState();

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--enlace';
  node.dataset.id = id;
  node.style.left = (x || 100) + 'px';
  node.style.top  = (y || 100) + 'px';

  const displayTitle = titulo || url;
  const displayUrl = url.length > 50 ? url.substring(0, 47) + '...' : url;

  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--enlace">🔗 ENLACE</span>
      <span class="cv-node__title">${escHtml(displayTitle)}</span>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__body">
      <a class="cv-link-display" href="${escHtml(url)}" target="_blank" rel="noopener" title="${escHtml(url)}">
        ${escHtml(displayUrl)} ↗
      </a>
    </div>
    <div class="cv-port cv-port--top"    data-node="${id}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${id}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${id}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${id}" data-port="left"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(id, node, x || 100, y || 100);

  STATE.nodos[id] = {
    id, tipo: 'enlace', ref_id: null,
    x: x || 100, y: y || 100, width: 220, height: node.offsetHeight || 80,
    collapsed: false, color: null, el: node,
    field_data: {
      url: url,
      url_title: titulo || url,
    },
  };
  registerNodeEvents(id, node);
  markDirty();
  return id;
}

/* ── NODO MATCH COMPARATIVO ── */

/**
 * Crea un nodo de tipo Match (comparativo) en el canvas.
 * Al hacer clic en el badge circular de una arista match, se consulta
 * la API y se crea este nodo con tabla comparativa propiedad vs requerimiento.
 * @param {number} matchId - ID del MatchResult
 * @param {number} x, y - posición inicial
 */
async function createMatchNode(matchId, x, y) {
  const id = 'match_' + matchId;
  if (STATE.nodos[id]) return id;
  if (typeof captureState === 'function') captureState();

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--match';
  node.dataset.id = id;
  node.style.left = (x || 100) + 'px';
  node.style.top  = (y || 100) + 'px';
  node.style.width = '380px';
  node.style.minWidth = '300px';

  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--match">MATCH</span>
      <span class="cv-node__title">Cargando...</span>
      <button class="cv-node__collapse" title="Colapsar">−</button>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__body" style="text-align:center;padding:16px;color:var(--cv-text-muted);">
      Cargando comparativa...
    </div>
    <div class="cv-port cv-port--top"    data-node="${id}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${id}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${id}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${id}" data-port="left"></div>
    <div class="cv-resize-handle" data-node="${id}"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(id, node, x || 100, y || 100);

  STATE.nodos[id] = {
    id, tipo: 'match', ref_id: matchId,
    x: x || 100, y: y || 100, width: 380, height: node.offsetHeight || 300,
    collapsed: false, color: null, el: node,
    field_data: { match_id: matchId },
  };
  registerNodeEvents(id, node);
  markDirty();

  try {
    const res = await fetch(`/canvas/api/match-detail/${matchId}/`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderMatchNodeBody(id, data);
  } catch (err) {
    console.error('Error loading match detail:', err);
    const body = node.querySelector('.cv-node__body');
    if (body) body.innerHTML = '<div style="color:var(--cv-block);padding:12px;text-align:center;">Error al cargar comparativa</div>';
  }

  return id;
}

/**
 * Renderiza el body de un nodo match con los datos comparativos.
 */
function renderMatchNodeBody(nodeId, data) {
  const nodo = STATE.nodos[nodeId];
  if (!nodo || !nodo.el) return;

  const score = Math.round(parseFloat(data.score_total) || 0);
  const fecha = data.ejecutado_en || '';
  const campos = data.campos || [];

  const titleEl = nodo.el.querySelector('.cv-node__title');
  if (titleEl) {
    titleEl.textContent = `Match ${score}%`;
  }

  let html = `<div class="cv-match-table">`;

  html += `<div class="cv-match-table__header">
    <span class="cv-match-table__score" style="color:#ffdd00;font-weight:700;">${score}%</span>
    ${fecha ? `<span style="color:var(--cv-text-muted);font-size:10px;">${fecha}</span>` : ''}
  </div>`;

  html += `<table class="cv-match-table__grid">
    <thead><tr>
      <th>Campo</th><th>Propiedad</th><th>Requerimiento</th><th style="text-align:center;">Ok</th>
    </tr></thead><tbody>`;

  campos.forEach(c => {
    const propVal = escHtml(String(c.propiedad || '—').substring(0, 60));
    const reqVal = escHtml(String(c.requerimiento || '—').substring(0, 60));
    let icono, cls;
    if (c.compatible === true) { icono = '✓'; cls = 'cv-mm-ok'; }
    else if (c.compatible === false) { icono = '✗'; cls = 'cv-mm-fail'; }
    else { icono = '—'; cls = 'cv-mm-neutral'; }
    const isFilter = c.peso === -1;
    html += `<tr${isFilter ? ' class="cv-match-tr-filter"' : ''}>
      <td class="cv-match-td-label">${escHtml(c.label || c.nombre || '')}</td>
      <td class="cv-match-td-prop">${propVal || '—'}</td>
      <td class="cv-match-td-req">${reqVal || '—'}</td>
      <td class="cv-match-td-status"><span class="${cls}">${icono}</span></td>
    </tr>`;
  });

  html += `</tbody></table></div>`;

  const body = nodo.el.querySelector('.cv-node__body');
  if (body) {
    body.innerHTML = html;
    nodo.height = nodo.el.offsetHeight || 300;
  }
  markDirty();
}

/* ── FORMAT FILE SIZE ── */

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024;
    i++;
  }
  return size.toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}

/* ── MATCHES ── */

async function loadMatchesForProp(propId, nodeId) {
  const btn = STATE.nodos[nodeId]?.el?.querySelector('.cv-btn--matches');
  const cnt = STATE.nodos[nodeId]?.el?.querySelector('.cv-match-count');
  if (btn) btn.textContent = 'Cargando...';

  try {
    const res = await fetch(`/canvas/api/reqs/${propId}/`);
    const data = await res.json();
    if (cnt) cnt.textContent = data.total + ' reqs';

    const prevEdgeIds = Object.keys(STATE.aristas).filter(
      eid => STATE.aristas[eid].origen === nodeId && STATE.aristas[eid].tipo === 'match'
    );
    prevEdgeIds.forEach(eid => delete STATE.aristas[eid]);

    if (data.matches && data.matches.length > 0) {
      const prop = STATE.nodos[nodeId];
      const baseX = prop.x + 280;
      const baseY = prop.y;
      data.matches.forEach((req, i) => {
        const reqId = req.id;
        const reqNodeId = createReqNode(reqId, req, baseX, baseY + i * 220);
        const edgeExists = Object.values(STATE.aristas).some(
          e => e.origen === nodeId && e.destino === reqNodeId
        );
        if (!edgeExists) {
          const edgeId = 'e' + (++STATE.edgeIdCounter);
          STATE.aristas[edgeId] = {
            id: edgeId,
            origen: nodeId,
            destino: reqNodeId,
            tipo: 'match',
            match_id: req.match_id || null,
            score_total: req.score_total || req.score_estructural || 0,
            ejecutado_en: req.ejecutado_en || '',
            label: (req.score_estructural || 0) + '%',
          };
        }
      });
      updateEdges();
      markDirty();
    }
  } catch (err) {
    console.error('Error loading matches:', err);
  } finally {
    if (btn) btn.textContent = 'Ver matches →';
  }
}

/* ── SNAPSHOT RESTORE ── */

function restoreSnapshot(snapshot) {
  if (!snapshot || !snapshot.nodos) return;
  const vp = snapshot.viewport || { x: 0, y: 0, zoom: 1.0 };
  STATE.viewport = vp;

  if (snapshot.campos && snapshot.campos.length > 0) {
    document.querySelectorAll('.campo-check').forEach(c => {
      c.checked = snapshot.campos.includes(c.value);
    });
  }

  STATE._restoreAgenteId = snapshot.agente_id || '';

  snapshot.nodos.forEach(n => {
    if (n.tipo === 'match_badge') return;

    if (n.tipo === 'propiedad') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'propiedad', ref_id: n.ref_id,
        x: n.x, y: n.y, width: n.width || 220, height: n.height || 160,
        collapsed: n.collapsed || false, color: n.color || null, el: null,
        field_data: n.field_data || null,
      };
    } else if (n.tipo === 'requerimiento') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'requerimiento', ref_id: n.ref_id,
        x: n.x, y: n.y, width: n.width || 220, height: n.height || 200,
        collapsed: n.collapsed || false, color: n.color || null, el: null,
        field_data: n.field_data || null,
      };
    } else if (n.tipo === 'nota') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'nota', ref_id: null,
        x: n.x, y: n.y, width: n.width || 200, height: n.height || 100,
        collapsed: false, color: n.color || null, el: null,
      };
    } else if (n.tipo === 'archivo') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'archivo', ref_id: n.ref_id,
        x: n.x, y: n.y, width: n.width || 220, height: n.height || 90,
        collapsed: false, color: null, el: null,
        field_data: n.field_data || null,
      };
    } else if (n.tipo === 'enlace') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'enlace', ref_id: null,
        x: n.x, y: n.y, width: n.width || 220, height: n.height || 80,
        collapsed: false, color: null, el: null,
        field_data: n.field_data || null,
      };
    } else if (n.tipo === 'match') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'match', ref_id: n.ref_id,
        x: n.x, y: n.y, width: n.width || 380, height: n.height || 300,
        collapsed: n.collapsed || false, color: null, el: null,
      };
    } else if (n.tipo === 'lead_analysis') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'lead_analysis', ref_id: n.ref_id,
        x: n.x, y: n.y, width: n.width || 340, height: n.height || 280,
        collapsed: false, color: null, el: null,
        field_data: n.field_data || null,
      };
    } else if (n.tipo === 'lead_nodo') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'lead_nodo', ref_id: n.ref_id,
        x: n.x, y: n.y, width: n.width || 260, height: n.height || 160,
        collapsed: false, color: null, el: null,
        field_data: n.field_data || null,
      };
    } else if (n.tipo === 'lead_global') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'lead_global', ref_id: null,
        x: n.x, y: n.y, width: n.width || 340, height: n.height || 280,
        collapsed: false, color: null, el: null,
        field_data: n.field_data || null,
      };
    } else if (n.tipo === 'lead_matrix') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'lead_matrix', ref_id: null,
        x: n.x, y: n.y, width: n.width || 560, height: n.height || 360,
        collapsed: false, color: null, el: null,
        field_data: n.field_data || null,
      };
    }
  });

  renderPlaceholderNodes(snapshot.nodos.filter(n => n.tipo !== 'match_badge'));

  if (snapshot.aristas) {
    snapshot.aristas.forEach(e => {
      STATE.aristas[e.id] = { ...e };
    });
    const maxId = snapshot.aristas.reduce((m, e) => {
      const num = parseInt(e.id.replace('e', '')) || 0;
      return num > m ? num : m;
    }, 0);
    STATE.edgeIdCounter = maxId;
  }

  updateTransform();
  updateEdges();
}

/**
 * Puebla los nodos placeholder con datos reales desde la API.
 * Busca todas las propiedades visibles y asigna field_data a los nodos
 * cuyo ref_id coincida con el source_id de la propiedad.
 */
async function populatePlaceholderProps() {
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch('/canvas/api/propiedades/');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.propiedades) return;

      const propsBySourceId = {};
      data.propiedades.forEach(p => {
        propsBySourceId[p._source_id] = p;
      });

      Object.values(STATE.nodos).forEach(n => {
        if (n.tipo === 'propiedad' && n.ref_id) {
          const propData = propsBySourceId[n.ref_id];
          if (propData) {
            n.field_data = propData;
          }
        }
      });

      const campos = getActiveCampos();
      Object.values(STATE.nodos).forEach(n => {
        if (n.tipo === 'propiedad' && n.field_data && n.el) {
          const titleEl = n.el.querySelector('.cv-node__title');
          if (titleEl) {
            const title = n.field_data.title || n.field_data.direction || `Prop #${n.ref_id}`;
            titleEl.textContent = title;
          }
          // Actualizar thumbnail si hay nueva URL de imagen
          const thumb = n.el.querySelector('.cv-node__thumb');
          if (thumb) {
            const newImgUrl = getPropertyImageUrl(n.field_data);
            const existingImg = thumb.querySelector('img');
            if (newImgUrl && (!existingImg || existingImg.src !== newImgUrl)) {
              thumb.classList.remove('cv-node__thumb--empty');
              thumb.innerHTML = `<img src="${escHtml(newImgUrl)}" loading="lazy" onerror="this.parentElement.classList.add('cv-node__thumb--empty')" alt="" data-prop-id="${n.ref_id}">`;
            } else if (!newImgUrl && !existingImg) {
              thumb.classList.add('cv-node__thumb--empty');
              thumb.innerHTML = `<div class="cv-node__thumb-placeholder" data-prop-id="${n.ref_id}" title="Ver galería">📷</div>`;
            }
          }
          // Actualizar conteo de leads
          const leadCountEl = n.el.querySelector('.cv-lead-count__num');
          if (leadCountEl && n.field_data._lead_count !== undefined) {
            leadCountEl.textContent = n.field_data._lead_count;
          }
          reRenderPropBody(n.id, campos);
        }
      });

      if (typeof updateEdges === 'function') {
        updateEdges();
      }
      return;
    } catch (err) {
      console.warn(`Error populating placeholder props (intento ${attempt}/3):`, err);
      if (attempt < 3) {
        await new Promise(r => setTimeout(r, 1000 * attempt));
      } else {
        console.error('Error definitivo al poblar propiedades:', err);
      }
    }
  }
}

function renderPlaceholderNodes(nodos) {
  nodos.forEach(n => {
    if (n.tipo === 'match_badge') return;
    if (STATE.nodos[n.id] && STATE.nodos[n.id].el) return;
    const node = document.createElement('div');
    node.className = `cv-node cv-node--${n.tipo}`;
    node.dataset.id = n.id;
    node.style.left = n.x + 'px';
    node.style.top  = n.y + 'px';

    if (n.tipo === 'propiedad') {
      const savedFd = n.field_data || {};
      const savedTitle = savedFd.title || savedFd.direction || `Prop #${n.ref_id}`;
      const savedImgUrl = getPropertyImageUrl(savedFd);
      const savedLeadCount = savedFd._lead_count !== undefined ? parseInt(savedFd._lead_count) : 0;
      node.innerHTML = `
        <div class="cv-node__header">
          <span class="cv-node__badge cv-badge--prop">PROP</span>
          <span class="cv-node__title">${escHtml(savedTitle)}</span>
          <button class="cv-node__collapse">${n.collapsed ? '+' : '−'}</button>
          <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-node__thumb${savedImgUrl ? '' : ' cv-node__thumb--empty'}">
          ${savedImgUrl ? `<img src="${escHtml(savedImgUrl)}" loading="lazy" onerror="this.parentElement.classList.add('cv-node__thumb--empty')" alt="" data-prop-id="${n.ref_id}">` : ''}
          ${!savedImgUrl ? `<div class="cv-node__thumb-placeholder" data-prop-id="${n.ref_id}" title="Ver galería">📷</div>` : ''}
        </div>
        <div class="cv-node__body"><div style="color:var(--cv-text-muted);font-size:11px;text-align:center;padding:8px">Cargando datos...</div></div>
        <div class="cv-node__footer">
          <button class="cv-btn--matches" data-prop-id="${n.ref_id}">Ver matches &rarr;</button>
          <span class="cv-match-count">— reqs</span>
          <span class="cv-lead-count" title="Leads asociados">👤 <span class="cv-lead-count__num">${savedLeadCount}</span></span>
        </div>
        <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
        <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
        <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
        <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
        <div class="cv-resize-handle" data-node="${n.id}"></div>
      `;
    } else if (n.tipo === 'requerimiento') {
      const fd = n.field_data || {};
      const agente      = fd.agente || fd.titulo || `Req #${n.ref_id}`;
      const telefono    = fd.agente_telefono || '';
      const fecha       = fd.fecha || '';
      const hora        = fd.hora || '';
      const tipoOrig    = fd.tipo_original || fd.condicion || '';
      const reqTexto    = fd.requerimiento || '';
      const tipoProp    = fd.tipo_propiedad || '';
      const presupuesto = fd.presupuesto_monto != null
        ? formatPrice(fd.presupuesto_monto, fd.presupuesto_moneda)
        : (fd.presupuesto ? formatPrice(fd.presupuesto, fd.moneda) : '');
      const distritos   = fd.distritos || '';
      const urbanizacion = fd.urbanizacion || '';
      const zona        = fd.zona || '';
      const formaPago   = fd.presupuesto_forma_pago || '';
      const tipoLabel   = formatTipoRequerimiento(tipoOrig);
      node.innerHTML = `
        <div class="cv-node__header">
          <span class="cv-node__badge cv-badge--req">REQ</span>
          <span class="cv-node__title">${escHtml(agente)}</span>
          <button class="cv-node__delete cv-node__delete--req" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-node__req-info">
          ${telefono ? `<span class="cv-req-info__item">📞 ${escHtml(telefono)}</span>` : ''}
          ${fecha ? `<span class="cv-req-info__item">📅 ${escHtml(fecha)}${hora ? ' ' + escHtml(hora) : ''}</span>` : ''}
          ${tipoLabel ? `<span class="cv-req-info__item">📋 ${escHtml(tipoLabel)}</span>` : ''}
        </div>
        <div class="cv-node__req-body">
          <div class="cv-req-text">${escHtml(reqTexto)}</div>
        </div>
        <div class="cv-node__req-footer">
          ${tipoProp ? `<div class="cv-field"><span class="cv-field__key">🏠 Tipo</span><span class="cv-field__val">${escHtml(tipoProp)}</span></div>` : ''}
          ${presupuesto ? `<div class="cv-field"><span class="cv-field__key">💰 Presup.</span><span class="cv-field__val">${escHtml(presupuesto)}</span></div>` : ''}
          ${distritos ? `<div class="cv-field"><span class="cv-field__key">📍 Distritos</span><span class="cv-field__val">${escHtml(distritos)}</span></div>` : ''}
          ${urbanizacion ? `<div class="cv-field"><span class="cv-field__key">🏘️ Urb.</span><span class="cv-field__val">${escHtml(urbanizacion)}</span></div>` : ''}
          ${zona ? `<div class="cv-field"><span class="cv-field__key">📌 Zona</span><span class="cv-field__val">${escHtml(zona)}</span></div>` : ''}
          ${formaPago ? `<div class="cv-field"><span class="cv-field__key">💳 Pago</span><span class="cv-field__val">${escHtml(formaPago)}</span></div>` : ''}
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
      const tamanoStr = formatFileSize(fd.file_size);
      const officeEmbedUrl = ['excel','word'].includes(fd.file_type)
        ? `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(fd.file_url)}`
        : '';
      node.innerHTML = `
        <div class="cv-node__header">
          <span class="cv-node__badge cv-badge--archivo ${badgeClass}">${icon} ${label}</span>
          <span class="cv-node__title">${escHtml(fd.file_name || 'Archivo')}</span>
          <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-node__body">
          ${fd.file_type === 'image' && n.ref_id ? `<img class="cv-archivo-img" src="/canvas/api/media/${n.ref_id}/" ondblclick="window.open('/canvas/api/media/${n.ref_id}/','_blank')" onerror="this.style.display='none'">` : fd.file_type === 'image' ? `<img class="cv-archivo-img" src="${escHtml(fd.file_url)}" ondblclick="window.open('${escHtml(fd.file_url)}','_blank')" onerror="this.style.display='none'">` : ''}
          ${fd.file_type === 'pdf' && n.ref_id ? `<div class="cv-pdf-preview" data-pdf-id="${n.ref_id}"><span>Cargando PDF...</span></div>` : ''}
          ${officeEmbedUrl ? `<iframe class="cv-office-preview" src="${officeEmbedUrl}" loading="lazy"></iframe>` : ''}
          <div class="cv-file-info">
            <span class="cv-file-info__size">${tamanoStr}</span>
            <div style="display:flex;gap:6px;margin-top:4px;">
              <a class="cv-file-info__link" href="${escHtml(fd.file_url)}" download="${escHtml(fd.file_name || 'archivo')}" style="font-size:11px;">⬇ Descargar</a>
              ${['excel','word'].includes(fd.file_type) ? `<a class="cv-file-info__link" href="https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(fd.file_url)}" target="_blank" rel="noopener" style="font-size:11px;">👁 Abrir en grande</a>` : ''}
            </div>
          </div>
        </div>
        <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
        <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
        <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
        <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
        <div class="cv-resize-handle" data-node="${n.id}"></div>
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
    } else if (n.tipo === 'match') {
      node.innerHTML = `
        <div class="cv-node__header">
          <span class="cv-node__badge cv-badge--match">MATCH</span>
          <span class="cv-node__title">Match #${n.ref_id || ''}</span>
          <button class="cv-node__collapse" title="Colapsar">−</button>
          <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-node__body"><div style="color:var(--cv-text-muted);font-size:11px;text-align:center;padding:16px">Cargando comparativa...</div></div>
        <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
        <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
        <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
        <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
        <div class="cv-resize-handle" data-node="${n.id}"></div>
      `;
    } else if (n.tipo === 'lead_analysis') {
      var savedGran = (n.field_data && n.field_data._granularity) || 'day';
      var savedGranLabel = { day: 'Día', week: 'Semana', month: 'Mes' }[savedGran] || 'Día';
      node.innerHTML = `
        <div class="cv-node__header">
          <span class="cv-node__badge cv-badge--lead-analysis">📊 LEAD</span>
          <span class="cv-node__title">Análisis de Leads</span>
          <span class="cv-lead-gran-label" title="Click derecho → cambiar vista">📅 ${savedGranLabel}</span>
          <button class="cv-btn-clear-leads" title="Limpiar leads conectados">🧹</button>
          <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-node__body"><div style="color:var(--cv-text-muted);font-size:11px;text-align:center;padding:16px">Cargando datos...</div></div>
        <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
        <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
        <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
        <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
        <div class="cv-resize-handle" data-node="${n.id}"></div>
      `;
    } else if (n.tipo === 'lead_global') {
      var savedGran = (n.field_data && n.field_data._granularity) || 'day';
      var savedGranLabel = { day: 'Día', week: 'Semana', month: 'Mes' }[savedGran] || 'Día';
      node.innerHTML = `
        <div class="cv-node__header">
          <span class="cv-node__badge cv-badge--lead-analysis">📊 GLOBAL</span>
          <span class="cv-node__title">Todos los Leads</span>
          <span class="cv-lead-gran-label" title="Click derecho → cambiar vista">📅 ${savedGranLabel}</span>
          <button class="cv-btn-clear-leads" title="Limpiar leads conectados">🧹</button>
          <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-node__body"><div style="color:var(--cv-text-muted);font-size:11px;text-align:center;padding:16px">Cargando datos...</div></div>
        <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
        <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
        <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
        <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
        <div class="cv-resize-handle" data-node="${n.id}"></div>
      `;
    } else if (n.tipo === 'nota') {
      const fd = n.field_data || {};
      const savedContent = fd.contenido || fd.content || '';
      const savedTitle = fd.titulo || fd.title || 'Nota';
      if (n.color) node.style.setProperty('--nota-color', n.color);
      node.innerHTML = `
        <div class="cv-nota__header">
          <span class="cv-nota__icon">&#10022;</span>
          <span class="cv-nota__title-display">${escHtml(savedTitle)}</span>
          <input class="cv-nota__title-input" value="${escHtml(savedTitle)}" style="display:none">
          <button class="cv-nota__edit-title" title="Editar título">&#9998;</button>
          <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-nota__body" contenteditable="false">${escHtml(savedContent)}</div>
        <button class="cv-nota__edit-body" title="Editar contenido">&#9998; Editar</button>
        <div class="cv-nota__resize" title="Redimensionar"></div>
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
      // ── FIX: Restaurar fecha/hora del lead desde field_data ──
      var createdAt = fd.created_at || '';
      var fechaStr = '';
      if (createdAt) {
        var dateMatch = createdAt.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
        if (dateMatch) {
          fechaStr = dateMatch[3] + '/' + dateMatch[2] + '/' + dateMatch[1] + ' ' + dateMatch[4] + ':' + dateMatch[5];
        } else {
          fechaStr = createdAt;
        }
      }
      // Propiedad vinculada guardada en snapshot (via field_data.propiedades)
      var propiedades = fd.propiedades || [];
      var prop = propiedades.length > 0 ? propiedades[0] : null;
      var propHtml = '';
      if (prop) {
        var propTitle = prop.title || prop.code || ('Prop #' + prop.id);
        var propPrice = (prop.price != null)
          ? formatPrice(prop.price, prop.currency)
          : '';
        var propDistrict = prop.district_name || '';
        var propTitleShort = propTitle.length > 60 ? propTitle.substring(0, 57) + '...' : propTitle;
        var propDetail = propTitleShort;
        if (propDistrict) propDetail += ' — ' + propDistrict;
        if (propPrice) propDetail += ' (' + propPrice + ')';
        propHtml = '<span class="cv-req-info__item" style="color:#66bb6a;">🏠 ' + escHtml(propDetail) + '</span>';
      }
      node.innerHTML = `
        <div class="cv-node__header" style="cursor:pointer;" title="Doble click para abrir CRM" ondblclick="window.open('https://app.propify.pe/crm/lead/${n.ref_id || ''}','_blank')">
          <span class="cv-node__badge cv-badge--lead-analysis">👤 LEAD</span>
          <span class="cv-node__title">${escHtml(contactName)}</span>
          <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-node__req-info">
          ${propHtml}
          ${fechaStr ? '<span class="cv-req-info__item">🕐 ' + escHtml(fechaStr) + '</span>' : ''}
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
    } else if (n.tipo === 'lead_matrix') {
      node.innerHTML = `
        <div class="cv-node__header">
          <span class="cv-node__badge cv-badge--lead-matrix">MATRIZ</span>
          <span class="cv-node__title">Matriz de Leads</span>
          <span class="cv-lead-gran-label" id="matrix-total-label-${n.id}">-</span>
          <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-node__body" style="padding:0;overflow:auto;max-height:420px;">
          <div style="text-align:center;padding:30px;color:var(--cv-text-muted);font-size:13px;">
            Cargando datos...
          </div>
        </div>
        <div class="cv-port cv-port--top"    data-node="${n.id}" data-port="top"></div>
        <div class="cv-port cv-port--right"  data-node="${n.id}" data-port="right"></div>
        <div class="cv-port cv-port--bottom" data-node="${n.id}" data-port="bottom"></div>
        <div class="cv-port cv-port--left"   data-node="${n.id}" data-port="left"></div>
        <div class="cv-resize-handle" data-node="${n.id}"></div>
      `;
      // Refrescar datos al restaurar
      setTimeout(function(id) {
        fetch('/canvas/api/lead-matrix/?t=' + Date.now())
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (typeof renderLeadMatrixBody === 'function') {
              renderLeadMatrixBody(id, data);
            }
          })
          .catch(function() {});
      }, 500, n.id);
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
    // Seguridad: si el nodo no se registró en STATE (tipo desconocido en restoreSnapshot), salir
    if (!STATE.nodos[n.id]) {
      console.warn(`[Canvas] renderPlaceholderNodes: nodo ${n.id} (tipo: ${n.tipo}) no registrado en STATE, saltando`);
      return;
    }
    STATE.nodos[n.id].el = node;
    if (n.collapsed) node.classList.add('collapsed');
    if (n.width) node.style.width = n.width + 'px';
    if (n.height) node.style.minHeight = n.height + 'px';
    registerNodeEvents(n.id, node);
    // Adjuntar menú contextual de granularidad y botón limpiar leads
    if (n.tipo === 'lead_analysis' || n.tipo === 'lead_global') {
      node.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        e.stopPropagation();
        showLeadContextMenu(n.id, e);
      });
      var ccBtn = node.querySelector('.cv-btn-clear-leads');
      if (ccBtn) {
        ccBtn.addEventListener('click', function(e) {
          e.stopPropagation();
          clearConnectedLeads(n.id);
        });
      }
    }
  });
  // Renderizar PDFs después de restaurar todos los nodos
  Object.values(STATE.nodos).forEach(function(n) {
    if (n.tipo === 'archivo' && n.field_data && n.field_data.file_type === 'pdf' && n.ref_id) {
      setTimeout(function(id){ renderPdfPreview(id, '/canvas/api/media/'+id+'/'); }, 200, n.ref_id);
    }
  });
  // Refrescar nodos match (cargar datos desde API)
  Object.values(STATE.nodos).forEach(function(n) {
    if (n.tipo === 'match' && n.ref_id && n.el) {
      setTimeout(function(matchId, nodeId) {
        fetch('/canvas/api/match-detail/' + matchId + '/')
          .then(function(r) { return r.json(); })
          .then(function(data) { renderMatchNodeBody(nodeId, data); })
          .catch(function() {});
      }, 300, n.ref_id, n.id);
    }
  });
  // Refrescar nodos lead_analysis desde la API al cargar snapshot
  Object.values(STATE.nodos).forEach(function(n) {
    if (n.tipo === 'lead_analysis' && n.el) {
      var propId = n.ref_id || (n.field_data && n.field_data.prop_id);
      if (!propId) {
        console.warn('[LeadAnalysis] snapshot lead_analysis node sin prop_id, reintentando con field_data', n.field_data);
        return;
      }
      var gran = (n.field_data && n.field_data._granularity) || 'day';
      console.log('[LeadAnalysis] refrescando nodo', n.id, 'propId=', propId, 'gran=', gran);
      setTimeout(function(pid, nodeId, g) {
        fetch('/canvas/api/lead-analysis/' + pid + '/?granularity=' + g)
          .then(function(r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
          })
          .then(function(data) {
            console.log('[LeadAnalysis] datos recibidos para', nodeId, data.total_leads, 'leads');
            renderLeadAnalysisBody(nodeId, data);
          })
          .catch(function(err) {
            console.error('[LeadAnalysis] error al refrescar:', err);
          });
      }, 800, propId, n.id, gran);
    }
  });
  // Refrescar nodos lead_global desde la API al cargar snapshot
  Object.values(STATE.nodos).forEach(function(n) {
    if (n.tipo === 'lead_global' && n.el) {
      var gran = (n.field_data && n.field_data._granularity) || 'day';
      setTimeout(function(nodeId, g) {
        fetch('/canvas/api/lead-analysis-global/?granularity=' + g)
          .then(function(r) { return r.json(); })
          .then(function(data) { renderLeadAnalysisBody(nodeId, data); })
          .catch(function() {});
      }, 800, n.id, gran);
    }
  });

  // Refrescar nodos lead_matrix desde la API al cargar snapshot
  Object.values(STATE.nodos).forEach(function(n) {
    if (n.tipo === 'lead_matrix' && n.el) {
      setTimeout(function(nodeId) {
        fetch('/canvas/api/lead-matrix/')
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (typeof renderLeadMatrixBody === 'function') {
              renderLeadMatrixBody(nodeId, data);
            }
          })
          .catch(function() {});
      }, 800, n.id);
    }
  });
}


/* ═══════════════════════════════════════════════════════════════════════════
 * LEAD ANALYSIS NODE
 * ═══════════════════════════════════════════════════════════════════════════ */

/* ── CONTEXT MENU ── */
var _leadContext = null;
var LEAD_CONTEXT_MENU_ID = 'cv-lead-granularity-menu';

function createLeadContextMenu() {
  // Evitar duplicados: si ya existe, retornarlo
  var existing = document.getElementById(LEAD_CONTEXT_MENU_ID);
  if (existing) return existing;

  var menu = document.createElement('div');
  menu.id = LEAD_CONTEXT_MENU_ID;
  menu.className = 'cv-lead-context-menu';
  menu.style.display = 'none';
  menu.innerHTML = `
    <div class="cv-lead-context-menu__header">📊 Ver por</div>
    <div class="cv-lead-context-menu__item" data-granularity="day">📅 Día</div>
    <div class="cv-lead-context-menu__item" data-granularity="week">📆 Semana</div>
    <div class="cv-lead-context-menu__item" data-granularity="month">📅 Mes</div>
  `;
  document.body.appendChild(menu);

  menu.addEventListener('click', function(e) {
    var item = e.target.closest('.cv-lead-context-menu__item');
    if (!item) return;
    var gran = item.dataset.granularity;
    if (_leadContext) reloadLeadGranularity(_leadContext.nodeId, gran);
    hideLeadContextMenu();
  });

  return menu;
}

function getLeadContextMenu() {
  var menu = document.getElementById(LEAD_CONTEXT_MENU_ID);
  if (!menu) menu = createLeadContextMenu();
  return menu;
}

function showLeadContextMenu(nodeId, e) {
  e.preventDefault();
  e.stopPropagation();
  var menu = getLeadContextMenu();
  var nodo = STATE.nodos[nodeId];
  var currentGran = (nodo && nodo.field_data && nodo.field_data._granularity) || 'day';
  menu.querySelectorAll('.cv-lead-context-menu__item').forEach(function(el) {
    el.classList.toggle('active', el.dataset.granularity === currentGran);
  });
  menu.style.left = e.clientX + 'px';
  menu.style.top = e.clientY + 'px';
  menu.style.display = 'block';
  _leadContext = { nodeId: nodeId };
  setTimeout(function() { document.addEventListener('click', hideLeadContextMenu, { once: true }); }, 0);
}

function hideLeadContextMenu() {
  var menu = getLeadContextMenu();
  menu.style.display = 'none';
  _leadContext = null;
}

function granularityLabel(gran) {
  return { day: 'Día', week: 'Semana', month: 'Mes' }[gran] || 'Día';
}

function formatLeadDate(dateStr, granularity) {
  if (!dateStr) return '';
  // Extraer año, mes, día del string ISO (ej: "2026-07-01" o "2026-07-01T00:00:00")
  // Usamos string parsing para EVITAR timezone shifts de Date()
  var isoParts = dateStr.split('T')[0].split('-');
  if (isoParts.length < 3) return dateStr;
  var year = parseInt(isoParts[0], 10);
  var month = parseInt(isoParts[1], 10); // 1-12
  var day = parseInt(isoParts[2], 10);

  if (granularity === 'month') {
    var months = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
    return months[month - 1] + ' ' + year;
  }
  if (granularity === 'week') {
    // Calcular lunes y domingo usando UTC para evitar timezone
    var d = new Date(Date.UTC(year, month - 1, day));
    var dow = d.getUTCDay(); // 0=Sun
    var diff = dow === 0 ? -6 : 1 - dow;
    var mon = new Date(Date.UTC(year, month - 1, day + diff));
    var sun = new Date(Date.UTC(year, month - 1, day + diff + 6));
    var fmt = function(dd) {
      return String(dd.getUTCDate()).padStart(2,'0')+'/'+String(dd.getUTCMonth()+1).padStart(2,'0');
    };
    return fmt(mon) + '-' + fmt(sun);
  }
  // day: DD/MM
  return String(day).padStart(2,'0') + '/' + String(month).padStart(2,'0');
}

/**
 * Abre un nodo de análisis de leads para una propiedad.
 * Consulta la API y crea un nodo con gráfico de barras.
 */
async function openLeadAnalysis(propId, propNodeId) {
  if (!propId) return;
  if (typeof captureState === 'function') captureState();

  const nodeId = 'lead_analysis_' + propId;
  if (STATE.nodos[nodeId]) return;

  const propNode = STATE.nodos[propNodeId];
  if (!propNode) return;

  const vp = STATE.viewport;
  const x = (propNode.x * vp.zoom + 280) / vp.zoom;
  const y = propNode.y;

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--lead-analysis';
  node.dataset.id = nodeId;
  node.style.left = x + 'px';
  node.style.top = y + 'px';
  node.style.width = '340px';
  node.style.minWidth = '280px';
  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--lead-analysis">📊 LEAD</span>
      <span class="cv-node__title">Análisis de Leads</span>
      <span class="cv-lead-gran-label" title="Click derecho → cambiar vista">📅 Día</span>
      <button class="cv-btn-clear-leads" title="Limpiar leads conectados">🧹</button>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__body" style="text-align:center;padding:20px;color:var(--cv-text-muted);">
      Cargando datos...
    </div>
    <div class="cv-port cv-port--top"    data-node="${nodeId}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${nodeId}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${nodeId}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${nodeId}" data-port="left"></div>
    <div class="cv-resize-handle" data-node="${nodeId}"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(nodeId, node, x, y);

  STATE.nodos[nodeId] = {
    id: nodeId, tipo: 'lead_analysis', ref_id: propId,
    x: x, y: y, width: 340, height: node.offsetHeight || 280,
    collapsed: false, color: null, el: node,
    field_data: { prop_id: propId, _granularity: 'day' },
  };
  registerNodeEvents(nodeId, node);
  markDirty();

  // Context menu on right-click
  node.addEventListener('contextmenu', function(e) { showLeadContextMenu(nodeId, e); });

  // Boton limpiar leads conectados
  var clearBtn = node.querySelector('.cv-btn-clear-leads');
  if (clearBtn) {
    clearBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      clearConnectedLeads(nodeId);
    });
  }

  createLeadAnalysisEdge(propNodeId, nodeId);

  try {
    const res = await fetch('/canvas/api/lead-analysis/' + propId + '/');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    renderLeadAnalysisBody(nodeId, await res.json());
  } catch (err) {
    console.error('Error loading lead analysis:', err);
    const body = node.querySelector('.cv-node__body');
    if (body) body.innerHTML = '<div style="color:var(--cv-block);padding:12px;text-align:center;">Error al cargar datos</div>';
  }
}

/**
 * Recarga el nodo con una granularidad diferente.
 */
async function reloadLeadGranularity(nodeId, granularity) {
  const nodo = STATE.nodos[nodeId];
  if (!nodo || !nodo.el) return;
  const body = nodo.el.querySelector('.cv-node__body');
  if (body) body.innerHTML = '<div style="text-align:center;padding:20px;color:var(--cv-text-muted);">Cargando...</div>';
  try {
    var url;
    if (nodo.tipo === 'lead_global') {
      url = '/canvas/api/lead-analysis-global/?granularity=' + granularity;
    } else {
      const propId = nodo.ref_id || (nodo.field_data && nodo.field_data.prop_id);
      if (!propId) throw new Error('Sin propId');
      url = '/canvas/api/lead-analysis/' + propId + '/?granularity=' + granularity;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    nodo.field_data = nodo.field_data || {};
    nodo.field_data._granularity = granularity;
    renderLeadAnalysisBody(nodeId, await res.json());
    markDirty(); // Persistir el cambio de granularidad en el snapshot del servidor
  } catch (err) {
    console.error('Error reloading lead analysis:', err);
    if (body) body.innerHTML = '<div style="color:var(--cv-block);padding:12px;text-align:center;">Error al cargar</div>';
  }
}

function createLeadAnalysisEdge(propNodeId, analysisNodeId) {
  const edgeId = 'e_la_' + propNodeId + '_' + analysisNodeId;
  if (STATE.aristas[edgeId]) return;
  STATE.aristas[edgeId] = {
    id: edgeId, origen: propNodeId, destino: analysisNodeId,
    tipo: 'lead_analysis', label: 'leads',
  };
  if (typeof updateEdges === 'function') updateEdges();
}

/**
 * Renderiza el body con gráfico de barras.
 */
function renderLeadAnalysisBody(nodeId, data) {
  const nodo = STATE.nodos[nodeId];
  if (!nodo || !nodo.el) return;
  const body = nodo.el.querySelector('.cv-node__body');
  if (!body) return;

  const granularity = (nodo.field_data && nodo.field_data._granularity) || 'day';
  // Deduplicar por fecha: si hay entradas con la misma fecha (ej: por timezone en datetimeoffset),
  // sumamos sus conteos para evitar columnas duplicadas en el gráfico.
  var rawCounts = data.daily_counts || [];
  var dateMap = {};
  rawCounts.forEach(function(d) {
    var dateKey = d.date ? d.date.split('T')[0] : '';
    if (!dateKey) return;
    if (dateMap[dateKey]) {
      dateMap[dateKey].count += (d.count || 0);
    } else {
      dateMap[dateKey] = { date: dateKey, count: d.count || 0 };
    }
  });
  const daily = Object.keys(dateMap).sort().map(function(k) { return dateMap[k]; });
  const total = data.total_leads || 0;
  const firstDate = data.first_lead_date || '—';
  const maxCount = daily.length > 0 ? Math.max.apply(null, daily.map(function(d) { return d.count; })) : 1;

  var granLabel = nodo.el.querySelector('.cv-lead-gran-label');
  if (granLabel) granLabel.textContent = '📅 ' + granularityLabel(granularity);

  var html = '';
  html += '<div style="display:flex;justify-content:space-between;padding:6px 10px;border-bottom:1px solid var(--cv-border);font-size:11px;">';
  html += '<span style="color:var(--cv-text-muted);">Total: <strong style="color:#5c6bc0;">' + total + '</strong></span>';
  html += '<span style="color:var(--cv-text-muted);">Desde: <strong style="color:var(--cv-text-sec);">' + escHtml(firstDate) + '</strong></span>';
  html += '</div>';

  if (daily.length > 0) {
    html += '<div style="padding:10px;display:flex;align-items:flex-end;gap:3px;height:110px;overflow-x:auto;overflow-y:hidden;">';
    daily.forEach(function(d) {
      var barH = Math.max(4, (d.count / maxCount) * 80);
      var label = formatLeadDate(d.date, granularity);
      var dateKey = d.date ? d.date.split('T')[0] : '';
      var propAttr = nodo.ref_id ? ' data-prop-id="' + nodo.ref_id + '"' : '';
      html += '<div class="cv-lead-bar"' + propAttr + ' data-date="' + escHtml(dateKey) + '" style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;width:28px;cursor:pointer;" title="' + escHtml(d.date) + ': ' + d.count + ' leads — Click para ver leads">';
      html += '<span style="font-size:9px;color:var(--cv-text-muted);margin-bottom:2px;">' + d.count + '</span>';
      html += '<div style="width:20px;height:' + barH + 'px;background:#5c6bc0;border-radius:3px 3px 0 0;opacity:0.8;transition:opacity 0.15s;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.8"></div>';
      html += '<span style="font-size:7px;color:var(--cv-text-muted);margin-top:3px;writing-mode:vertical-lr;transform:rotate(180deg);">' + escHtml(label) + '</span>';
      html += '</div>';
    });
    html += '</div>';
  } else {
    html += '<div style="text-align:center;padding:20px;color:var(--cv-text-muted);font-size:12px;">Sin datos de leads</div>';
  }

  body.innerHTML = html;

  // Handler de clic en columnas del grafico (despues de innerHTML para que persista)
  body.removeEventListener('click', body._leadBarClick);
  body._leadBarClick = function(e) {
    var bar = e.target.closest('.cv-lead-bar');
    if (!bar) return;
    var propId = bar.getAttribute('data-prop-id');
    var date = bar.getAttribute('data-date');
    if (date) loadLeadNodes(propId, date, nodeId);
  };
  body.addEventListener('click', body._leadBarClick);
  nodo.height = nodo.el.offsetHeight || 280;
  markDirty();
}


/**
 * Carga los leads de una propiedad en una fecha y crea nodos en el canvas.
 */
async function loadLeadNodes(propId, dateStr, analysisNodeId) {
  if (!dateStr) return;
  if (typeof captureState === 'function') captureState();

  try {
    var url = propId
      ? '/canvas/api/lead-analysis/' + propId + '/leads/?date=' + dateStr
      : '/canvas/api/leads-by-date/?date=' + dateStr;
    const res = await fetch(url);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    const leads = data.leads || [];
    if (leads.length === 0) {
      showToast('Sin leads para esta fecha');
      return;
    }

    const analysisNode = STATE.nodos[analysisNodeId];
    if (!analysisNode) return;

    // Centrar los lead nodes verticalmente respecto al nodo de analisis
    var nodeHeight = 180; // altura por nodo lead
    var spacing = 250;    // separacion entre nodos (mas separados)
    var totalVisualHeight = (leads.length - 1) * spacing + nodeHeight;
    var startX = analysisNode.x + analysisNode.width + 80;
    var startY = analysisNode.y + (analysisNode.height || 280) / 2 - totalVisualHeight / 2;
    if (startY < 50) startY = 50;

    // Intentar obtener datos de la propiedad desde el nodo de análisis padre
    // (para inyectarla en los leads aunque la BD lead_properties no tenga el vínculo)
    var parentPropInfo = null;
    if (propId && analysisNode.field_data) {
      parentPropInfo = {
        id: parseInt(propId),
        code: analysisNode.field_data._prop_code || '',
        title: analysisNode.field_data._prop_title || '',
        district_name: analysisNode.field_data._prop_district || '',
        price: analysisNode.field_data._prop_price || null,
        currency: analysisNode.field_data._prop_currency || '',
      };
    }

    leads.forEach(function(lead, idx) {
      var leadId = 'lead_' + lead.id;
      if (STATE.nodos[leadId]) return; // ya existe

      // Si el lead no tiene propiedades vinculadas pero el nodo padre sí,
      // inyectar la propiedad del padre
      if ((!lead.propiedades || lead.propiedades.length === 0) && parentPropInfo) {
        lead.propiedades = [parentPropInfo];
      }

      var x = startX;
      var y = startY + idx * spacing;
      createLeadNode(leadId, lead, x, y);

      // Crear arista desde el nodo de analisis al nodo lead
      var edgeId = 'e_la_' + analysisNodeId + '_' + leadId;
      if (!STATE.aristas[edgeId]) {
        STATE.aristas[edgeId] = {
          id: edgeId, origen: analysisNodeId, destino: leadId,
          tipo: 'lead', label: lead.contact_name || lead.username || 'lead',
        };
      }
    });

    // Hacer scroll suave hasta los nuevos nodos
    setTimeout(function() {
      var firstNode = STATE.nodos[Object.keys(STATE.nodos).find(function(k) {
        return k.startsWith('lead_');
      })];
      if (firstNode && firstNode.el) {
        firstNode.el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }, 300);

    if (typeof updateEdges === 'function') updateEdges();
    markDirty();
    showToast(leads.length + ' lead' + (leads.length > 1 ? 's' : '') + ' agregado' + (leads.length > 1 ? 's' : '') + ' al lienzo');
  } catch (err) {
    console.error('Error loading lead nodes:', err);
    showToast('Error al cargar leads');
  }
}


/**
 * Crea un nodo lead en el canvas.
 * Muestra los datos del lead e incluye la propiedad vinculada (si existe).
 */
function createLeadNode(nodeId, lead, x, y) {
  if (STATE.nodos[nodeId]) return nodeId;
  // NOTA: captureState NO se llama aquí porque loadLeadNodes ya captura
  // el estado ANTES de agregar leads en lote. Si cada lead creara su propia
  // entrada en el historial, el deshacer solo removería un lead a la vez.

  var node = document.createElement('div');
  node.className = 'cv-node cv-node--lead';
  node.dataset.id = nodeId;
  node.style.left = x + 'px';
  node.style.top = y + 'px';
  node.style.width = '260px';

  var contactName = lead.contact_name || lead.username || 'Lead #' + lead.id;
  var phone = lead.phone || '';
  var email = lead.email || '';
  var source = lead.source || '';
  var lastMsg = lead.last_message_text || '';
  var notes = lead.notes || '';
  var score = lead.score != null ? lead.score : '';
  var createdAt = lead.created_at || '';
  // La API ya devuelve la hora en Peru (UTC-5), solo formateamos
  var fechaStr = '';
  if (createdAt) {
    var dateMatch = createdAt.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (dateMatch) {
      fechaStr = dateMatch[3] + '/' + dateMatch[2] + '/' + dateMatch[1] + ' ' + dateMatch[4] + ':' + dateMatch[5];
    } else {
      fechaStr = createdAt;
    }
  }

  // Propiedad vinculada: tomar la primera del array 'propiedades'
  var propiedades = lead.propiedades || [];
  var prop = propiedades.length > 0 ? propiedades[0] : null;
  // DEBUG: Verificar que propiedades llega desde la API
  if (propiedades.length === 0) {
    console.log('[LeadNode] lead #' + lead.id + ' sin propiedades vinculadas en lead_properties');
  } else {
    console.log('[LeadNode] lead #' + lead.id + ' propiedad:', prop.title || prop.code || prop.id);
  }
  var propHtml = '';
  if (prop) {
    var propTitle = prop.title || prop.code || ('Prop #' + prop.id);
    var propPrice = (prop.price != null)
      ? formatPrice(prop.price, prop.currency)
      : '';
    var propDistrict = prop.district_name || '';
    var propTitleShort = propTitle.length > 60 ? propTitle.substring(0, 57) + '...' : propTitle;
    var propDetail = propTitleShort;
    if (propDistrict) propDetail += ' — ' + propDistrict;
    if (propPrice) propDetail += ' (' + propPrice + ')';
    propHtml = '<span class="cv-req-info__item" style="color:#66bb6a;">🏠 ' + escHtml(propDetail) + '</span>';
  }

  node.innerHTML = `
    <div class="cv-node__header" style="cursor:pointer;" title="Doble click para abrir CRM" ondblclick="window.open('https://app.propify.pe/crm/lead/${lead.id}','_blank')">
      <span class="cv-node__badge cv-badge--lead-analysis">👤 LEAD</span>
      <span class="cv-node__title">${escHtml(contactName)}</span>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__req-info">
      ${propHtml}
      ${fechaStr ? '<span class="cv-req-info__item">🕐 ' + escHtml(fechaStr) + '</span>' : ''}
      ${phone ? '<span class="cv-req-info__item">📞 ' + escHtml(phone) + '</span>' : ''}
      ${email ? '<span class="cv-req-info__item">✉ ' + escHtml(email) + '</span>' : ''}
    </div>
    <div class="cv-node__req-body" style="font-size:11px;max-height:200px;overflow-y:auto;">
      ${source ? '<div style="color:var(--cv-text-muted);margin-bottom:4px;">📡 ' + escHtml(source) + '</div>' : ''}
      ${lastMsg ? '<div style="background:rgba(92,156,230,0.08);border-radius:6px;padding:6px;margin-bottom:4px;border-left:2px solid #5c9ce6;"><strong style="font-size:10px;color:#5c9ce6;">💬 Conversaci\u00f3n</strong><div style="color:var(--cv-text);margin-top:2px;white-space:pre-wrap;">' + escHtml(lastMsg) + '</div></div>' : ''}
      ${notes ? '<div style="background:rgba(255,221,0,0.06);border-radius:6px;padding:6px;border-left:2px solid #ffdd00;"><strong style="font-size:10px;color:#ffdd00;">📝 Notas</strong><div style="color:var(--cv-text-muted);margin-top:2px;white-space:pre-wrap;">' + escHtml(notes) + '</div></div>' : ''}
    </div>
    <div class="cv-port cv-port--top"    data-node="${nodeId}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${nodeId}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${nodeId}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${nodeId}" data-port="left"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(nodeId, node, x, y);

  STATE.nodos[nodeId] = {
    id: nodeId, tipo: 'lead_nodo', ref_id: lead.id,
    x: x, y: y, width: 220, height: node.offsetHeight || 160,
    collapsed: false, color: null, el: node,
    field_data: lead,
  };
  registerNodeEvents(nodeId, node);
  return nodeId;
}

/**
 * Elimina todos los nodos lead_nodo conectados a un nodo lead_analysis/lead_global.
 * Busca aristas de tipo 'lead' desde/hacia el nodo y remueve los leads y aristas.
 */
function clearConnectedLeads(nodeId) {
  const nodo = STATE.nodos[nodeId];
  if (!nodo) return;

  // Identificar aristas conectadas a este nodo
  const edgeIds = Object.keys(STATE.aristas).filter(function(eid) {
    var e = STATE.aristas[eid];
    return (e.origen === nodeId || e.destino === nodeId) && e.tipo === 'lead';
  });

  // Identificar los lead_nodo a remover
  var leadIds = [];
  edgeIds.forEach(function(eid) {
    var e = STATE.aristas[eid];
    var leadId = e.origen === nodeId ? e.destino : e.origen;
    if (STATE.nodos[leadId] && STATE.nodos[leadId].tipo === 'lead_nodo') {
      if (leadIds.indexOf(leadId) === -1) leadIds.push(leadId);
    }
  });

  if (leadIds.length === 0) {
    showToast('No hay leads conectados');
    return;
  }

  if (typeof captureState === 'function') captureState();

  // Remover nodos lead_nodo del DOM y STATE
  leadIds.forEach(function(leadId) {
    var ln = STATE.nodos[leadId];
    if (ln && ln.el && ln.el.parentNode) {
      ln.el.parentNode.removeChild(ln.el);
    }
    delete STATE.nodos[leadId];
  });

  // Remover aristas
  edgeIds.forEach(function(eid) {
    delete STATE.aristas[eid];
  });

  if (typeof updateEdges === 'function') updateEdges();
  markDirty();
  showToast(leadIds.length + ' lead' + (leadIds.length > 1 ? 's' : '') + ' eliminado' + (leadIds.length > 1 ? 's' : '') + ' del lienzo');
}

/* ── window export ── */
window.clearConnectedLeads = clearConnectedLeads;

/**
 * Formatea fecha ISO a DD/MM.
 */
function formatDateShort(dateStr) {
  if (!dateStr) return '';
  var parts = dateStr.split('-');
  if (parts.length === 3) return parts[2] + '/' + parts[1];
  return dateStr;
}


/* ═══════════════════════════════════════════════════════════════════════════
 * PDF PREVIEW
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Renderiza la primera página de un PDF como thumbnail usando PDF.js.
 * @param {number|string} archivoId - ID del ArchivoLienzo
 * @param {string} pdfUrl - URL del PDF (proxy /canvas/api/media/{id}/)
 */
function renderPdfPreview(archivoId, pdfUrl) {
  const container = document.querySelector(`.cv-pdf-preview[data-pdf-id="${archivoId}"]`);
  if (!container) return;

  if (typeof pdfjsLib === 'undefined') {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
    script.onload = function() {
      pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
      doRenderPdf(container, pdfUrl);
    };
    script.onerror = function() {
      container.innerHTML = '<span style="font-size:10px;color:var(--cv-text-muted);">PDF no disponible</span>';
    };
    document.head.appendChild(script);
  } else {
    doRenderPdf(container, pdfUrl);
  }
}

function doRenderPdf(container, pdfUrl) {
  pdfjsLib.getDocument(pdfUrl).promise.then(function(pdf) {
    return pdf.getPage(1);
  }).then(function(page) {
    const scale = 0.5;
    const viewport = page.getViewport({ scale: scale });
    const canvas = document.createElement('canvas');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    container.innerHTML = '';
    container.appendChild(canvas);
    return page.render({ canvasContext: canvas.getContext('2d'), viewport: viewport }).promise;
  }).catch(function() {
    container.innerHTML = '<span style="font-size:10px;color:var(--cv-text-muted);">Vista previa no disponible</span>';
  });
}


/* ═══════════════════════════════════════════════════════════════════════════
 * GLOBAL LEAD ANALYSIS NODE (todos los leads)
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Crea un nodo de analisis global de leads (todos los leads, sin filtro por propiedad).
 * Se invoca desde el menu contextual del canvas.
 */
async function createGlobalLeadNode(x, y) {
  if (typeof captureState === 'function') captureState();

  const nodeId = 'lead_global_' + Date.now();
  if (STATE.nodos[nodeId]) return;

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--lead-analysis';
  node.dataset.id = nodeId;
  node.style.left = x + 'px';
  node.style.top = y + 'px';
  node.style.width = '340px';
  node.style.minWidth = '280px';
  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--lead-analysis">📊 GLOBAL</span>
      <span class="cv-node__title">Todos los Leads</span>
      <span class="cv-lead-gran-label" title="Click derecho \u2192 cambiar vista">📅 D\u00eda</span>
      <button class="cv-btn-clear-leads" title="Limpiar leads conectados">🧹</button>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__body" style="text-align:center;padding:20px;color:var(--cv-text-muted);">
      Cargando datos...
    </div>
    <div class="cv-port cv-port--top"    data-node="${nodeId}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${nodeId}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${nodeId}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${nodeId}" data-port="left"></div>
    <div class="cv-resize-handle" data-node="${nodeId}"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(nodeId, node, x, y);

  STATE.nodos[nodeId] = {
    id: nodeId, tipo: 'lead_global', ref_id: null,
    x: x, y: y, width: 340, height: node.offsetHeight || 280,
    collapsed: false, color: null, el: node,
    field_data: { _granularity: 'day' },
  };
  registerNodeEvents(nodeId, node);
  markDirty();

  // Context menu on right-click
  node.addEventListener('contextmenu', function(e) { showLeadContextMenu(nodeId, e); });

  // Boton limpiar leads conectados
  var clearBtn = node.querySelector('.cv-btn-clear-leads');
  if (clearBtn) {
    clearBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      clearConnectedLeads(nodeId);
    });
  }

  try {
    const res = await fetch('/canvas/api/lead-analysis-global/?granularity=day');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    renderLeadAnalysisBody(nodeId, await res.json());
  } catch (err) {
    console.error('Error loading global lead analysis:', err);
    const body = node.querySelector('.cv-node__body');
    if (body) body.innerHTML = '<div style="color:var(--cv-block);padding:12px;text-align:center;">Error al cargar datos</div>';
  }
}


/**
 * Crea un nodo de Matriz de Leads en el canvas.
 * Muestra tabla con propiedades como filas, fechas como columnas,
 * y el conteo de leads en cada celda con color por intensidad.
 */
async function createLeadMatrixNode(x, y) {
  if (typeof captureState === 'function') captureState();

  const nodeId = 'lead_matrix_' + Date.now();
  if (STATE.nodos[nodeId]) return;

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--lead-matrix';
  node.dataset.id = nodeId;
  node.style.left = (x || 200) + 'px';
  node.style.top = (y || 200) + 'px';
  node.style.width = '560px';
  node.style.minWidth = '400px';
  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--lead-matrix">MATRIZ</span>
      <span class="cv-node__title">Matriz de Leads</span>
      <span class="cv-lead-gran-label" id="matrix-total-label">-</span>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__body" style="padding:0;overflow:auto;max-height:420px;">
      <div style="text-align:center;padding:30px;color:var(--cv-text-muted);font-size:13px;">
        Cargando datos...
      </div>
    </div>
    <div class="cv-port cv-port--top"    data-node="${nodeId}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${nodeId}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${nodeId}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${nodeId}" data-port="left"></div>
    <div class="cv-resize-handle" data-node="${nodeId}"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(nodeId, node, x || 200, y || 200);

  STATE.nodos[nodeId] = {
    id: nodeId, tipo: 'lead_matrix', ref_id: null,
    x: x || 200, y: y || 200, width: 560, height: node.offsetHeight || 360,
    collapsed: false, color: null, el: node,
    field_data: {},
  };
  registerNodeEvents(nodeId, node);
  markDirty();

  try {
    const res = await fetch('/canvas/api/lead-matrix/?t=' + Date.now());
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    renderLeadMatrixBody(nodeId, data);
  } catch (err) {
    console.error('Error loading lead matrix:', err);
    const body = node.querySelector('.cv-node__body');
    if (body) body.innerHTML = '<div style="color:var(--cv-block);padding:20px;text-align:center;">Error al cargar matriz</div>';
  }
}

function renderLeadMatrixBody(nodeId, data) {
  const nodo = STATE.nodos[nodeId];
  if (!nodo || !nodo.el) return;
  const body = nodo.el.querySelector('.cv-node__body');
  if (!body) return;

  const properties = data.properties || [];
  const dates = data.dates || [];
  const totalLeads = data.total_leads || 0;
  const totalProps = data.total_properties || 0;
  
  // Guardar datos para exportar
  nodo._matrixData = data;

  const totalLabel = nodo.el.querySelector('#matrix-total-label');
  if (totalLabel) {
    totalLabel.textContent = totalLeads + ' leads / ' + totalProps + ' props';
  }

  if (properties.length === 0 || dates.length === 0) {
    body.innerHTML = '<div style="text-align:center;padding:30px;color:var(--cv-text-muted);font-size:13px;">Sin datos de leads</div>';
    return;
  }

  var maxCount = 1;
  properties.forEach(function(p) {
    Object.keys(p.daily_counts).forEach(function(k) {
      if (p.daily_counts[k] > maxCount) maxCount = p.daily_counts[k];
    });
  });

  function cellColor(count) {
    if (!count || count === 0) return 'transparent';
    var intensity = Math.min(1, count / maxCount);
    var alpha = 0.12 + intensity * 0.68;
    return 'rgba(92,107,192,' + alpha + ')';
  }

  function fmtDate(dateStr) {
    if (!dateStr) return '';
    var parts = dateStr.split('-');
    if (parts.length === 3) return parts[2] + '/' + parts[1];
    return dateStr;
  }

  var html = '<div class="cv-matrix-wrap" style="overflow-x:auto;overflow-y:auto;max-height:400px;width:100%;">';
  html += '<table class="cv-matrix-table" style="width:' + Math.max(800, dates.length * 70 + 350) + 'px;border-collapse:collapse;font-size:12px;table-layout:fixed;">';

  html += '<thead><tr>';
  html += '<th class="cv-matrix-th cv-matrix-th--prop" style="text-align:left;padding:8px 12px;position:sticky;top:0;left:0;z-index:3;background:#16213e;border-bottom:2px solid #5c6bc0;color:#e0e0e0;font-weight:700;width:350px;min-width:250px;cursor:col-resize;">Propiedad</th>';
  dates.forEach(function(d) {
    html += '<th class="cv-matrix-th" style="text-align:center;padding:8px 4px;position:sticky;top:0;z-index:2;background:#16213e;border-bottom:2px solid #5c6bc0;color:#9e9e9e;font-weight:500;font-size:11px;width:70px;min-width:50px;" title="' + escHtml(d) + '">' + escHtml(fmtDate(d)) + '</th>';
  });
  html += '<th class="cv-matrix-th" style="text-align:center;padding:8px 12px;position:sticky;top:0;z-index:2;background:#16213e;border-bottom:2px solid #ffdd00;color:#ffdd00;font-weight:700;font-size:12px;width:70px;min-width:50px;">Total</th>';
  html += '</tr></thead>';

  html += '<tbody>';
  properties.forEach(function(prop) {
    var propLabel = prop.title || prop.code || 'Prop #' + prop.property_id;
    if (prop.district_name) propLabel += ' - ' + prop.district_name;
    // Sin truncado

    html += '<tr class="cv-matrix-row" style="transition:background 0.2s;">';
    html += '<td class="cv-matrix-td cv-matrix-td--prop" style="text-align:left;padding:8px 12px;border-bottom:1px solid #1e3a5f;color:#e0e0e0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:350px;min-width:250px;position:sticky;left:0;z-index:1;background:#0d1117;cursor:col-resize;" title="' + escHtml(prop.title || prop.code || '') + ' - ' + escHtml(prop.district_name || '') + '"><strong style="color:#ffffff;">' + escHtml(propLabel) + '</strong></td>';

    dates.forEach(function(d) {
      var count = prop.daily_counts[d] || 0;
      var color = cellColor(count);
      html += '<td class="cv-matrix-td" style="text-align:center;padding:8px 4px;border-bottom:1px solid #1e3a5f;background:' + color + ';color:' + (count > 0 ? '#ffffff' : '#555555') + ';font-size:12px;font-weight:' + (count > 0 ? '700' : '400') + ';min-width:50px;cursor:' + (count > 0 ? 'pointer' : 'default') + ';"';
      html += ' title="' + escHtml(prop.title || prop.code || 'Prop') + ' - ' + fmtDate(d) + ': ' + count + ' leads"';
      html += '>';
      html += count > 0 ? count : '-';
      html += '</td>';
    });

    html += '<td class="cv-matrix-td" style="text-align:center;padding:8px 12px;border-bottom:1px solid #1e3a5f;color:#ffdd00;font-weight:800;font-size:14px;background:#0d1117;min-width:50px;border-left:1px solid #ffdd00;">' + prop.total + '</td>';
    html += '</tr>';
  });
  // Fila de totales por día
  html += '<tr style="background:#16213e;border-top:2px solid #5c6bc0;">';
  html += '<td class="cv-matrix-td" style="text-align:right;padding:8px 12px;color:#ffdd00;font-weight:700;font-size:13px;background:#16213e;position:sticky;left:0;z-index:1;">TOTAL</td>';
  dates.forEach(function(d) {
    var dayTotal = 0;
    properties.forEach(function(prop) {
      dayTotal += prop.daily_counts[d] || 0;
    });
    html += '<td class="cv-matrix-td" style="text-align:center;padding:8px 4px;color:#ffdd00;font-weight:800;font-size:14px;background:#16213e;border-top:2px solid #5c6bc0;">' + dayTotal + '</td>';
  });
  html += '<td class="cv-matrix-td" style="text-align:center;padding:8px 12px;color:#ffdd00;font-weight:800;font-size:16px;background:#16213e;border-top:2px solid #ffdd00;border-left:1px solid #ffdd00;">' + totalLeads + '</td>';
  html += '</tr>';
  html += '</tbody></table>';
  html += '</div>';

  // Botón exportar Excel
  html += '<div style="text-align:center;padding:6px;border-top:1px solid #1e3a5f;background:#0d1117;">';
  html += '<button class="cv-btn-export-excel" data-node="' + nodeId + '" style="background:#5c6bc0;color:white;border:none;border-radius:4px;padding:6px 16px;cursor:pointer;font-size:11px;font-weight:600;">📥 Exportar Excel</button>';
  html += '</div>';

  body.innerHTML = html;

  var exportBtn = body.querySelector('.cv-btn-export-excel');
  if (exportBtn) {
    exportBtn.addEventListener('click', function() {
      exportMatrixToExcel(nodeId);
    });
  }

  body.querySelectorAll('.cv-matrix-row').forEach(function(tr) {
    tr.addEventListener('mouseenter', function() {
      this.style.background = 'rgba(92,107,192,0.06)';
    });
    tr.addEventListener('mouseleave', function() {
      this.style.background = '';
    });
  });

  nodo.height = nodo.el.offsetHeight || 360;
  markDirty();
}

function exportMatrixToExcel(nodeId) {
  const nodo = STATE.nodos[nodeId];
  if (!nodo || !nodo._matrixData) return;
  const data = nodo._matrixData;
  const properties = data.properties || [];
  const dates = data.dates || [];
  
  // Calcular totales por día
  var dateTotals = {};
  dates.forEach(function(d) {
    var total = 0;
    properties.forEach(function(p) { total += p.daily_counts[d] || 0; });
    dateTotals[d] = total;
  });
  var totalLeads = data.total_leads || 0;

  // Encontrar máximo para escala de color
  var maxCount = 1;
  properties.forEach(function(p) {
    Object.keys(p.daily_counts).forEach(function(k) {
      if (p.daily_counts[k] > maxCount) maxCount = p.daily_counts[k];
    });
  });

  function cellBg(count) {
    if (!count || count === 0) return '#1a1a2e';
    var intensity = Math.min(1, count / maxCount);
    var alpha = 0.12 + intensity * 0.68;
    // Convertir rgba a hex aproximado sobre fondo oscuro
    var r = Math.round(92 * alpha + 13 * (1 - alpha));
    var g = Math.round(107 * alpha + 26 * (1 - alpha));
    var b = Math.round(192 * alpha + 46 * (1 - alpha));
    return '#' + [r,g,b].map(function(x) { return x.toString(16).padStart(2,'0'); }).join('');
  }

  var html = '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">';
  html += '<head><meta charset="UTF-8"><!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>Matriz de Leads</x:Name></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->';
  html += '<style>td{border:1px solid #1e3a5f;padding:6px 10px;font-size:11px;} th{background:#16213e;color:#e0e0e0;padding:8px 12px;font-size:11px;font-weight:700;border:1px solid #5c6bc0;}</style></head><body>';
  html += '<table>';
  
  // Header
  html += '<tr><th>Propiedad</th>';
  dates.forEach(function(d) {
    var parts = d.split('-');
    var label = parts.length === 3 ? parts[2] + '/' + parts[1] : d;
    html += '<th>' + label + '</th>';
  });
  html += '<th style="border-color:#ffdd00;color:#ffdd00;">Total</th></tr>';
  
  // Data rows
  properties.forEach(function(p) {
    var title = p.title || p.code || 'Prop #' + p.property_id;
    html += '<tr><td style="background:#0d1117;color:#ffffff;font-weight:600;">' + title + '</td>';
    dates.forEach(function(d) {
      var count = p.daily_counts[d] || 0;
      html += '<td style="text-align:center;background:' + cellBg(count) + ';color:' + (count > 0 ? '#ffffff' : '#555555') + ';font-weight:' + (count > 0 ? '700' : '400') + ';">' + (count > 0 ? count : '-') + '</td>';
    });
    html += '<td style="text-align:center;background:#0d1117;color:#ffdd00;font-weight:800;border-left:2px solid #ffdd00;">' + p.total + '</td>';
    html += '</tr>';
  });
  
  // Totals row
  html += '<tr><td style="background:#16213e;color:#ffdd00;font-weight:700;">TOTAL</td>';
  dates.forEach(function(d) {
    html += '<td style="text-align:center;background:#16213e;color:#ffdd00;font-weight:800;">' + (dateTotals[d] || 0) + '</td>';
  });
  html += '<td style="text-align:center;background:#16213e;color:#ffdd00;font-weight:900;font-size:14px;border-left:2px solid #ffdd00;">' + totalLeads + '</td></tr>';
  
  html += '</table></body></html>';

  var blob = new Blob([html], { type: 'application/vnd.ms-excel' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'Matriz_Leads_' + new Date().toISOString().slice(0,10) + '.xls';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function exportMatrixToExcel(nodeId) {
  var nodo = STATE.nodos[nodeId];
  if (!nodo || !nodo._matrixData) return;
  var data = nodo._matrixData;
  var properties = data.properties || [];
  var dates = data.dates || [];
  
  var dateTotals = {};
  dates.forEach(function(d) {
    var t = 0;
    properties.forEach(function(p) { t += p.daily_counts[d] || 0; });
    dateTotals[d] = t;
  });
  var totalLeads = data.total_leads || 0;
  
  var maxCount = 1;
  properties.forEach(function(p) {
    Object.keys(p.daily_counts).forEach(function(k) { if (p.daily_counts[k] > maxCount) maxCount = p.daily_counts[k]; });
  });
  
  function cellBg(count) {
    if (!count || count === 0) return '#1a1a2e';
    var intensity = Math.min(1, count / maxCount);
    var alpha = 0.12 + intensity * 0.68;
    var r = Math.round(92 * alpha + 13 * (1 - alpha));
    var g = Math.round(107 * alpha + 26 * (1 - alpha));
    var b = Math.round(192 * alpha + 46 * (1 - alpha));
    return '#' + [r,g,b].map(function(x) { return x.toString(16).padStart(2,'0'); }).join('');
  }
  
  var html = '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">';
  html += '<head><meta charset="UTF-8"><!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>Matriz</x:Name></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->';
  html += '<style>td{border:1px solid #1e3a5f;padding:6px 10px;font-size:11px;font-family:Arial;} th{background:#16213e;color:#e0e0e0;padding:8px 12px;font-size:11px;font-weight:700;border:1px solid #5c6bc0;font-family:Arial;}</style></head><body><table>';
  
  html += '<tr><th>Propiedad</th>';
  dates.forEach(function(d) {
    var parts = d.split('-');
    html += '<th>' + (parts.length === 3 ? parts[2] + '/' + parts[1] : d) + '</th>';
  });
  html += '<th style="border-color:#ffdd00;color:#ffdd00;">Total</th></tr>';
  
  properties.forEach(function(p) {
    var title = p.title || p.code || 'Prop #' + p.property_id;
    html += '<tr><td style="background:#0d1117;color:#ffffff;font-weight:600;">' + title + '</td>';
    dates.forEach(function(d) {
      var count = p.daily_counts[d] || 0;
      html += '<td style="text-align:center;background:' + cellBg(count) + ';color:' + (count > 0 ? '#ffffff' : '#555555') + ';font-weight:' + (count > 0 ? '700' : '400') + ';">' + (count > 0 ? count : '-') + '</td>';
    });
    html += '<td style="text-align:center;background:#0d1117;color:#ffdd00;font-weight:800;border-left:2px solid #ffdd00;">' + p.total + '</td></tr>';
  });
  
  html += '<tr><td style="background:#16213e;color:#ffdd00;font-weight:700;">TOTAL</td>';
  dates.forEach(function(d) {
    html += '<td style="text-align:center;background:#16213e;color:#ffdd00;font-weight:800;">' + (dateTotals[d] || 0) + '</td>';
  });
  html += '<td style="text-align:center;background:#16213e;color:#ffdd00;font-weight:900;font-size:14px;border-left:2px solid #ffdd00;">' + totalLeads + '</td></tr>';
  html += '</table></body></html>';
  
  var blob = new Blob([html], { type: 'text/html' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'Matriz_Leads_' + new Date().toISOString().slice(0,10) + '.htm';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

window.createLeadMatrixNode = createLeadMatrixNode;
window.renderLeadMatrixBody = renderLeadMatrixBody;
window.exportMatrixToExcel = exportMatrixToExcel;


/**
 * Inicializa el menu contextual del canvas (click derecho en el fondo).
 */
function initCanvasContextMenu() {
  var menu = document.getElementById('cv-canvas-context-menu');
  if (!menu) {
    menu = document.createElement('div');
    menu.id = 'cv-canvas-context-menu';
    menu.className = 'cv-lead-context-menu';
    menu.style.display = 'none';
    document.body.appendChild(menu);
  }

  // Siempre actualizar el contenido (incluso si ya existe)
  menu.innerHTML =
    '<div class="cv-lead-context-menu__header">Lienzo</div>' +
    '<div class="cv-lead-context-menu__item" data-action="create-global-leads">Crear tarjeta de leads</div>' +
    '<div class="cv-lead-context-menu__item" data-action="create-lead-matrix">Matriz de Leads</div>';

  // Solo adjuntar eventos globales una vez
  if (menu.dataset._initialized) return;
  menu.dataset._initialized = '1';

  menu.addEventListener('click', function(e) {
    var item = e.target.closest('.cv-lead-context-menu__item');
    if (!item) return;
    var action = item.getAttribute('data-action');
    var x = parseFloat(menu.dataset.x || 200);
    var y = parseFloat(menu.dataset.y || 200);
    menu.style.display = 'none';
    if (action === 'create-global-leads') {
      if (typeof createGlobalLeadNode === 'function') {
        createGlobalLeadNode(x, y);
      }
    } else if (action === 'create-lead-matrix') {
      if (typeof createLeadMatrixNode === 'function') {
        createLeadMatrixNode(x, y);
      }
    }
  });

  // Mostrar menu en click derecho sobre el stage
  document.addEventListener('contextmenu', function(e) {
    var target = e.target.closest('.cv-node, .cv-port');
    if (target) return;
    e.preventDefault();
    menu.style.left = e.clientX + 'px';
    menu.style.top = e.clientY + 'px';
    menu.dataset.x = e.clientX;
    menu.dataset.y = e.clientY;
    menu.style.display = 'block';
  });

  // Ocultar al hacer click
  document.addEventListener('click', function() {
    menu.style.display = 'none';
  });
}

// Inicializar cuando el DOM este listo
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCanvasContextMenu);
} else {
  initCanvasContextMenu();
}
