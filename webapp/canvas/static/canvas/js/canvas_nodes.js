/**
 * canvas_nodes.js — PropFlow Canvas Nodes
 *
 * Renderizado y lógica de nodos: Propiedad, Requerimiento, Nota.
 * Maneja creación, posicionamiento, colapso y eliminación.
 */

/* ── CREAR NODOS ── */

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
    // Si ya existe, actualizar field_data y re-renderizar
    STATE.nodos[id].field_data = data;
    reRenderPropBody(id, campos || getActiveCampos());
    return id;
  }
  // Capturar estado antes de crear nuevo nodo
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

  const imgUrl = getPropertyImageUrl(data);

  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--prop">PROP</span>
      <span class="cv-node__title">${escHtml(title)}</span>
      <button class="cv-node__collapse" title="Colapsar">−</button>
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
      <button class="cv-btn--matches" data-prop-id="${sourceId}">Ver matches &rarr;</button>
      <span class="cv-match-count">— reqs</span>
    </div>
    <!-- 4 puertos direccionales -->
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
  // Re-dibujar aristas después de cambiar campos visibles
  if (typeof updateEdges === 'function') {
    updateEdges();
  }
}


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

  // Solo actualizar los campos en el body (el thumbnail está fuera del body en createPropNode / renderPlaceholderNodes)
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

  // ── Extraer datos con fallbacks ──
  const agente      = data.agente || data.titulo || `Req #${reqId}`;
  const telefono    = data.agente_telefono || '';
  const fecha       = data.fecha || '';
  const hora        = data.hora || '';
  const tipoOrig    = data.tipo_original || data.condicion || '';
  const reqTexto    = data.requerimiento || '';

  // Footer fields
  const tipoProp    = data.tipo_propiedad || '';
  const presupuesto = data.presupuesto_monto != null
    ? formatPrice(data.presupuesto_monto, data.presupuesto_moneda)
    : (data.presupuesto ? formatPrice(data.presupuesto, data.moneda) : '');
  const distritos   = data.distritos || '';
  const urbanizacion = data.urbanizacion || '';
  const zona        = data.zona || '';
  const formaPago   = data.presupuesto_forma_pago || '';

  // Formatear tipo_original para mostrar
  const tipoLabel = formatTipoRequerimiento(tipoOrig);

  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--req">REQ</span>
      <span class="cv-node__title">${escHtml(agente)}</span>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
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
    <!-- 4 puertos direccionales -->
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
  };
  registerNodeEvents(id, node);
  markDirty();
  return id;
}

/* ── EVENTOS DE NODO ── */

function registerNodeEvents(id, el) {
  const isNota = el.classList.contains('cv-node--nota');

  // Drag: para notas usar .cv-nota__header; para props usar .cv-node__header
  const dragHandle = el.querySelector('.cv-nota__header') || el.querySelector('.cv-node__header');
  if (dragHandle) {
    dragHandle.addEventListener('mousedown', e => {
      // Si el clic es en un input o botón dentro del header, no arrastrar
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

  // Delete button — con modal de confirmación
  const deleteBtn = el.querySelector('.cv-node__delete');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', e => {
      e.stopPropagation();
      if (typeof showConfirmModal === 'function') {
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
      // Mostrar input, ocultar span
      titleDisplay.style.display = 'none';
      titleInput.style.display = '';
      titleInput.value = titleDisplay.textContent;
      titleInput.focus();
      titleInput.select();
    });
    // Enter en input → guardar
    titleInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        titleInput.blur();
      }
    });
    // Blur → guardar y mostrar span
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
        // Desactivar edición
        notaBody.setAttribute('contenteditable', 'false');
        editBodyBtn.textContent = '\u270E Editar';
        notaBody.blur();
        markDirty();
      } else {
        // Activar edición
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
  }
}

function positionNode(id, el, x, y) {
  el.style.left = x + 'px';
  el.style.top  = y + 'px';
}

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
  // Remove connected edges
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

  // Icono según tipo
  const iconMap = { excel: '📊', word: '📝', pdf: '📄', image: '🖼️', other: '📎' };
  const icon = iconMap[data.tipo] || '📎';
  const badgeClass = 'cv-badge--' + (data.tipo || 'other');
  const tipoLabel = { excel: 'EXCEL', word: 'WORD', pdf: 'PDF', image: 'IMG', other: 'ARCHIVO' };
  const label = tipoLabel[data.tipo] || 'ARCHIVO';

  // Tamaño formateado
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
  
  // Renderizar preview PDF si aplica
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
  if (STATE.nodos[id]) return id; // ya existe
  if (typeof captureState === 'function') captureState();

  // Crear nodo placeholder inmediatamente
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

  // Cargar datos de la API
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

  // Actualizar título
  const titleEl = nodo.el.querySelector('.cv-node__title');
  if (titleEl) {
    titleEl.textContent = `Match ${score}%`;
  }

  // Construir body
  let html = `<div class="cv-match-table">`;

  // Cabecera compacta: score + fecha
  html += `<div class="cv-match-table__header">
    <span class="cv-match-table__score" style="color:#ffdd00;font-weight:700;">${score}%</span>
    ${fecha ? `<span style="color:var(--cv-text-muted);font-size:10px;">${fecha}</span>` : ''}
  </div>`;

  // Tabla de comparación
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
    // Actualizar altura en state
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

    // ── Limpiar aristas match PREVIAS desde este nodo propiedad ──
    const prevEdgeIds = Object.keys(STATE.aristas).filter(
      eid => STATE.aristas[eid].origen === nodeId && STATE.aristas[eid].tipo === 'match'
    );
    prevEdgeIds.forEach(eid => delete STATE.aristas[eid]);

    // ── Crear nodos req y aristas match ──
    if (data.matches && data.matches.length > 0) {
      const prop = STATE.nodos[nodeId];
      const baseX = prop.x + 280;
      const baseY = prop.y;
      data.matches.forEach((req, i) => {
        const reqId = req.id;
        const reqNodeId = createReqNode(reqId, req, baseX, baseY + i * 220);
        // Solo crear arista si no existe ya una entre origen y destino
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

  // Restaurar campos guardados en el snapshot
  if (snapshot.campos && snapshot.campos.length > 0) {
    document.querySelectorAll('.campo-check').forEach(c => {
      c.checked = snapshot.campos.includes(c.value);
    });
  }

  // Guardar agente_id para restaurarlo después de cargar agentes
  STATE._restoreAgenteId = snapshot.agente_id || '';

  snapshot.nodos.forEach(n => {
    if (n.tipo === 'propiedad') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'propiedad', ref_id: n.ref_id,
        x: n.x, y: n.y, width: n.width || 220, height: n.height || 160,
        collapsed: n.collapsed || false, color: n.color || null, el: null,
        field_data: n.field_data || null, // snapshot guardado; populatePlaceholderProps lo refresca si puede
      };
    } else if (n.tipo === 'requerimiento') {
      STATE.nodos[n.id] = {
        id: n.id, tipo: 'requerimiento', ref_id: n.ref_id,
        x: n.x, y: n.y, width: n.width || 220, height: n.height || 200,
        collapsed: n.collapsed || false, color: n.color || null, el: null,
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
    }
  });

  // Renderizar placeholders hasta que se carguen datos
  renderPlaceholderNodes(snapshot.nodos);

  // Restore edges
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
  // Máximo 3 intentos con retry
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch('/canvas/api/propiedades/');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.propiedades) return;

      // Indexar propiedades por source_id
      const propsBySourceId = {};
      data.propiedades.forEach(p => {
        propsBySourceId[p._source_id] = p;
      });

      // Refrescar field_data desde la API (sobrescribe datos del snapshot con datos frescos)
      Object.values(STATE.nodos).forEach(n => {
        if (n.tipo === 'propiedad' && n.ref_id) {
          const propData = propsBySourceId[n.ref_id];
          if (propData) {
            n.field_data = propData;
          }
          // Si no se encuentra en la API, conserva el field_data del snapshot (no se pierde el título)
        }
      });

      // Re-renderizar placeholders con datos reales
      const campos = getActiveCampos();
      Object.values(STATE.nodos).forEach(n => {
        if (n.tipo === 'propiedad' && n.field_data && n.el) {
          // Actualizar título
          const titleEl = n.el.querySelector('.cv-node__title');
          if (titleEl) {
            const title = n.field_data.title || n.field_data.direction || `Prop #${n.ref_id}`;
            titleEl.textContent = title;
          }
          // Re-renderizar body
          reRenderPropBody(n.id, campos);
        }
      });

      // Re-dibujar aristas después de re-renderizar nodos
      if (typeof updateEdges === 'function') {
        updateEdges();
      }
      return; // Éxito, salir del bucle
    } catch (err) {
      console.warn(`Error populating placeholder props (intento ${attempt}/3):`, err);
      if (attempt < 3) {
        await new Promise(r => setTimeout(r, 1000 * attempt)); // Esperar 1s, 2s, ...
      } else {
        console.error('Error definitivo al poblar propiedades:', err);
      }
    }
  }
}

function renderPlaceholderNodes(nodos) {
  nodos.forEach(n => {
    if (STATE.nodos[n.id] && STATE.nodos[n.id].el) return; // already rendered
    const node = document.createElement('div');
    node.className = `cv-node cv-node--${n.tipo}`;
    node.dataset.id = n.id;
    node.style.left = n.x + 'px';
    node.style.top  = n.y + 'px';

    if (n.tipo === 'propiedad') {
      // Usar título guardado en field_data si existe (fallback a "Prop #id")
      const savedFd = n.field_data || {};
      const savedTitle = savedFd.title || savedFd.direction || `Prop #${n.ref_id}`;
      const savedImgUrl = getPropertyImageUrl(savedFd);
      node.innerHTML = `
        <div class="cv-node__header">
          <span class="cv-node__badge cv-badge--prop">PROP</span>
          <span class="cv-node__title">${escHtml(savedTitle)}</span>
          <button class="cv-node__collapse">${n.collapsed ? '+' : '−'}</button>
          <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
        </div>
        <div class="cv-node__thumb${savedImgUrl ? '' : ' cv-node__thumb--empty'}">
          ${savedImgUrl ? `<img src="${escHtml(savedImgUrl)}" loading="lazy" onerror="this.parentElement.classList.add('cv-node__thumb--empty')" alt="">` : ''}
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
        <div class="cv-resize-handle" data-node="${n.id}"></div>
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
    // Restaurar ancho guardado; NO restaurar altura fija (que el contenido determine la altura)
    if (n.width) node.style.width = n.width + 'px';
    registerNodeEvents(n.id, node);
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
}

/* ── IMAGE HELPER ── */

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

/* ── UTILITIES ── */

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

/* ── PDF PREVIEW ── */

/**
 * Renderiza la primera página de un PDF como thumbnail usando PDF.js.
 * @param {number|string} archivoId - ID del ArchivoLienzo
 * @param {string} pdfUrl - URL del PDF (proxy /canvas/api/media/{id}/)
 */
function renderPdfPreview(archivoId, pdfUrl) {
  const container = document.querySelector(`.cv-pdf-preview[data-pdf-id="${archivoId}"]`);
  if (!container) return;

  // Cargar PDF.js desde CDN si no está disponible
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
    // No setear inline width/height — el CSS con max-width/max-height lo contiene
    container.innerHTML = '';
    container.appendChild(canvas);
    return page.render({ canvasContext: canvas.getContext('2d'), viewport: viewport }).promise;
  }).catch(function() {
    container.innerHTML = '<span style="font-size:10px;color:var(--cv-text-muted);">Vista previa no disponible</span>';
  });
}
