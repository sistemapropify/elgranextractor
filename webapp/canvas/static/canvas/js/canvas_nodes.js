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

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--prop';
  node.dataset.id = id;
  node.style.left = x + 'px';
  node.style.top  = y + 'px';

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

  const imgUrl = getPropertyImageUrl(data);

  // Reconstruir el body manteniendo los campos fijos (Precio, Distrito) + dinámicos
  body.innerHTML = `
    <div class="cv-node__thumb${imgUrl ? '' : ' cv-node__thumb--empty'}">
      ${imgUrl ? `<img src="${escHtml(imgUrl)}" loading="lazy" onerror="this.parentElement.classList.add('cv-node__thumb--empty')" alt="">` : ''}
    </div>
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

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--req';
  node.dataset.id = id;
  node.style.left = x + 'px';
  node.style.top  = y + 'px';

  const titulo   = data.titulo || `Req #${reqId}`;
  const presup   = data.presupuesto ? formatPrice(data.presupuesto, data.moneda) : (data.score_estructural ? '—' : '—');
  const distritos = data.distritos || '—';
  const scoreEstructural = data.score_estructural || 0;
  const scoreSemantico   = data.score_semantico || 0;
  const fecha = data.fecha || '';
  const tipo = data.tipo || 'estructural';

  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--req">REQ</span>
      <span class="cv-node__title">${escHtml(titulo)}</span>
    </div>
    <div class="cv-node__body">
      <div class="cv-field"><span class="cv-field__key">Presup.</span><span class="cv-field__val">${escHtml(presup)}</span></div>
      <div class="cv-field"><span class="cv-field__key">Zona</span><span class="cv-field__val">${escHtml(distritos)}</span></div>
      <div class="cv-field"><span class="cv-field__key">Fecha</span><span class="cv-field__val">${escHtml(fecha)}</span></div>
      <div class="cv-field cv-field--score">
        <span class="cv-field__key">Estructural</span>
        <span class="cv-score" style="background:color-mix(in srgb, var(--cv-done) 15%, transparent);color:var(--cv-done);border:1px solid color-mix(in srgb, var(--cv-done) 30%, transparent);">${scoreEstructural}%</span>
      </div>
      <div class="cv-field cv-field--score">
        <span class="cv-field__key">Semántico</span>
        <span class="cv-score" style="background:color-mix(in srgb, #5c6bc0 15%, transparent);color:#8896f0;border:1px solid color-mix(in srgb, #5c6bc0 30%, transparent);">${scoreSemantico}</span>
      </div>
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
 * Crea un nodo Nota (sticky).
 */
function createNotaNode(x, y, contenido, color) {
  const id = 'nota_' + Date.now();
  const node = document.createElement('div');
  node.className = 'cv-node cv-node--nota';
  node.dataset.id = id;
  node.style.left = (x || 150) + 'px';
  node.style.top  = (y || 150) + 'px';
  if (color) node.style.setProperty('--nota-color', color);

  node.innerHTML = `
    <div class="cv-nota__handle">&#10022; nota</div>
    <div class="cv-nota__body" contenteditable="true">${escHtml(contenido || 'Escribe aquí...')}</div>
    <div class="cv-port cv-port--out" data-node="${id}"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(id, node, x || 150, y || 150);

  STATE.nodos[id] = {
    id, tipo: 'nota', ref_id: null,
    x: x || 150, y: y || 150, width: 200, height: node.offsetHeight || 100,
    collapsed: false, color: color || null, el: node,
  };
  registerNodeEvents(id, node);
  markDirty();
  return id;
}

/* ── EVENTOS DE NODO ── */

function registerNodeEvents(id, el) {
  // Drag
  el.querySelector('.cv-node__header, .cv-nota__handle').addEventListener('mousedown', e => {
    startNodeDrag(e, id);
  });
  // In prop nodes, also drag on the whole node body (but not on buttons/ports)
  el.addEventListener('mousedown', e => {
    if (e.target.closest('.cv-node__header') || e.target.closest('.cv-nota__handle')) return;
    if (e.target.closest('.cv-btn') || e.target.closest('.cv-port')) return;
    selectNode(id);
    startNodeDrag(e, id);
  });

  // Connection ports — ahora 4 direcciones (top, right, bottom, left)
  el.querySelectorAll('.cv-port').forEach(port => {
    port.addEventListener('mousedown', e => {
      const portDir = port.dataset.port || 'right';
      startConnection(e, id, portDir);
    });
  });

  // Collapse button
  const collapseBtn = el.querySelector('.cv-node__collapse');
  if (collapseBtn) {
    collapseBtn.addEventListener('click', e => {
      e.stopPropagation();
      toggleCollapse(id);
    });
  }

  // Delete button
  const deleteBtn = el.querySelector('.cv-node__delete');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', e => {
      e.stopPropagation();
      deleteNode(id);
    });
  }

  // Matches button
  const matchesBtn = el.querySelector('.cv-btn--matches');
  if (matchesBtn) {
    matchesBtn.addEventListener('click', e => {
      e.stopPropagation();
      const propId = matchesBtn.dataset.propId;
      loadMatchesForProp(propId, id);
    });
  }

  // Nota content editable
  const notaBody = el.querySelector('.cv-nota__body');
  if (notaBody) {
    notaBody.addEventListener('input', () => { markDirty(); });
  }
}

function positionNode(id, el, x, y) {
  el.style.left = x + 'px';
  el.style.top  = y + 'px';
}

function toggleCollapse(id) {
  const nodo = STATE.nodos[id];
  if (!nodo || !nodo.el) return;
  nodo.collapsed = !nodo.collapsed;
  nodo.el.classList.toggle('collapsed', nodo.collapsed);
  const btn = nodo.el.querySelector('.cv-node__collapse');
  if (btn) btn.textContent = nodo.collapsed ? '+' : '−';
  markDirty();
}

function deleteNode(id) {
  const nodo = STATE.nodos[id];
  if (!nodo) return;
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

/* ── MATCHES ── */

async function loadMatchesForProp(propId, nodeId) {
  const btn = STATE.nodos[nodeId]?.el?.querySelector('.cv-btn--matches');
  const cnt = STATE.nodos[nodeId]?.el?.querySelector('.cv-match-count');
  if (btn) btn.textContent = 'Cargando...';

  try {
    const res = await fetch(`/canvas/api/reqs/${propId}/`);
    const data = await res.json();
    if (cnt) cnt.textContent = data.total + ' reqs';

    // Create req nodes connected to this property
    if (data.matches && data.matches.length > 0) {
      const prop = STATE.nodos[nodeId];
      const baseX = prop.x + 280;
      const baseY = prop.y;
      data.matches.forEach((req, i) => {
        const reqId = req.id;
        const reqNodeId = createReqNode(reqId, req, baseX, baseY + i * 220);
        // Create edge
        const edgeId = 'e' + (++STATE.edgeIdCounter);
        STATE.aristas[edgeId] = {
          id: edgeId,
          origen: nodeId,
          destino: reqNodeId,
          tipo: 'match',
          label: (req.score_estructural || 0) + '%',
        };
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
        field_data: null, // se llenará cuando se carguen propiedades
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
  try {
    const res = await fetch('/canvas/api/propiedades/');
    const data = await res.json();
    if (!data.propiedades) return;

    // Indexar propiedades por source_id
    const propsBySourceId = {};
    data.propiedades.forEach(p => {
      propsBySourceId[p._source_id] = p;
    });

    // Asignar field_data a nodos placeholder
    Object.values(STATE.nodos).forEach(n => {
      if (n.tipo === 'propiedad' && !n.field_data && n.ref_id) {
        const propData = propsBySourceId[n.ref_id];
        if (propData) {
          n.field_data = propData;
        }
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
  } catch (err) {
    console.error('Error populating placeholder props:', err);
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
