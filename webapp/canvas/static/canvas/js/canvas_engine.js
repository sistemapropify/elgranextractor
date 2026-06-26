/**
 * canvas_engine.js — PropFlow Canvas Engine
 *
 * Motor principal del canvas: grid, pan, zoom, drag de nodos.
 * Gestiona el STATE global y orquesta los submódulos.
 *
 * Dependencias: canvas_nodes.js, canvas_edges.js, canvas_sidebar.js, canvas_save.js
 */

/* ── ESTADO GLOBAL ── */
const STATE = {
  viewport: { x: 0, y: 0, zoom: 1.0 },
  nodos:    {},     // { "prop_123": { id, tipo, ref_id, x, y, width, height, collapsed, color, el } }
  aristas:  {},     // { "e1": { id, origen, destino, tipo, label } }
  selected: null,   // id del nodo seleccionado
  dragging: null,   // { id, startX, startY, offsetX, offsetY }
  connecting: null, // { origen, port: 'out' }
  dirty:    false,  // cambios sin guardar
  edgeIdCounter: 0,
};

/* ── DOM REFS ── */
let dom = {};

function cacheDom() {
  dom.stage    = document.getElementById('cv-stage');
  dom.grid     = document.getElementById('cv-grid');
  dom.edges    = document.getElementById('cv-edges');
  dom.nodes    = document.getElementById('cv-nodes');
  dom.minimap  = document.getElementById('minimap-canvas');
  dom.minimapVp = document.getElementById('minimap-vp');
}

/* ── GRID CANVAS ── */

function resizeGrid() {
  const rect = dom.stage.getBoundingClientRect();
  dom.grid.width  = rect.width;
  dom.grid.height = rect.height;
  dom.minimap.width  = 140;
  dom.minimap.height = 90;
  drawGrid();
}

function drawGrid() {
  const ctx = dom.grid.getContext('2d');
  if (!ctx) return;
  const W = dom.grid.width;
  const H = dom.grid.height;
  const vp = STATE.viewport;
  const CELL  = 24 * vp.zoom;
  const MAJOR = 5;
  const ox    = ((vp.x % (CELL * MAJOR)) + CELL * MAJOR) % (CELL * MAJOR);
  const oy    = ((vp.y % (CELL * MAJOR)) + CELL * MAJOR) % (CELL * MAJOR);

  ctx.clearRect(0, 0, W, H);

  for (let x = ox - CELL * MAJOR; x < W + CELL; x += CELL) {
    const isMajor = Math.round((x - ox) / CELL) % MAJOR === 0;
    ctx.strokeStyle = isMajor ? '#282c3e' : '#1e2130';
    ctx.lineWidth   = isMajor ? 0.8 : 0.5;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  for (let y = oy - CELL * MAJOR; y < H + CELL; y += CELL) {
    const isMajor = Math.round((y - oy) / CELL) % MAJOR === 0;
    ctx.strokeStyle = isMajor ? '#282c3e' : '#1e2130';
    ctx.lineWidth   = isMajor ? 0.8 : 0.5;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
}

/* ── PAN / ZOOM ── */

let isPanning = false;
let panStart = { x: 0, y: 0 };
let panViewport = { x: 0, y: 0 };

function startPan(e) {
  // Pan con botón izquierdo (0) en espacio vacío, o botón derecho (2) / medio (1)
  // No hacer pan si el click es sobre un nodo
  if (e.target.closest('.cv-node')) return;
  if (e.button !== 0 && e.button !== 2 && e.button !== 1) return;
  e.preventDefault();
  isPanning = true;
  panStart = { x: e.clientX, y: e.clientY };
  panViewport = { x: STATE.viewport.x, y: STATE.viewport.y };
  dom.stage.classList.add('cv-stage--panning');
}

function doPan(e) {
  if (!isPanning) return;
  STATE.viewport.x = panViewport.x + (e.clientX - panStart.x);
  STATE.viewport.y = panViewport.y + (e.clientY - panStart.y);
  updateTransform();
}

function endPan() {
  if (!isPanning) return;
  isPanning = false;
  dom.stage.classList.remove('cv-stage--panning');
}

function doZoom(e) {
  e.preventDefault();
  const delta = e.deltaY > 0 ? -0.08 : 0.08;
  const newZoom = Math.max(0.2, Math.min(3, STATE.viewport.zoom + delta));
  const rect = dom.stage.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  // Zoom hacia el cursor
  STATE.viewport.x = mx - (mx - STATE.viewport.x) * (newZoom / STATE.viewport.zoom);
  STATE.viewport.y = my - (my - STATE.viewport.y) * (newZoom / STATE.viewport.zoom);
  STATE.viewport.zoom = newZoom;
  updateTransform();
}

function zoomIn() {
  const rect = dom.stage.getBoundingClientRect();
  const newZoom = Math.min(3, STATE.viewport.zoom + 0.15);
  STATE.viewport.x = rect.width/2 - (rect.width/2 - STATE.viewport.x) * (newZoom / STATE.viewport.zoom);
  STATE.viewport.y = rect.height/2 - (rect.height/2 - STATE.viewport.y) * (newZoom / STATE.viewport.zoom);
  STATE.viewport.zoom = newZoom;
  updateTransform();
}

function zoomOut() {
  const newZoom = Math.max(0.2, STATE.viewport.zoom - 0.15);
  const rect = dom.stage.getBoundingClientRect();
  STATE.viewport.x = rect.width/2 - (rect.width/2 - STATE.viewport.x) * (newZoom / STATE.viewport.zoom);
  STATE.viewport.y = rect.height/2 - (rect.height/2 - STATE.viewport.y) * (newZoom / STATE.viewport.zoom);
  STATE.viewport.zoom = newZoom;
  updateTransform();
}

function zoomReset() {
  STATE.viewport = { x: 0, y: 0, zoom: 1.0 };
  updateTransform();
}

function updateTransform() {
  const vp = STATE.viewport;
  dom.nodes.style.transform = `translate(${vp.x}px, ${vp.y}px) scale(${vp.zoom})`;
  dom.edges.style.transform = `translate(${vp.x}px, ${vp.y}px) scale(${vp.zoom})`;
  dom.nodes.style.transformOrigin = '0 0';
  dom.edges.style.transformOrigin = '0 0';
  drawGrid();
  drawMinimap();
}

/* ── NODE DRAG ── */

function startNodeDrag(e, nodeId) {
  if (e.button !== 0) return;
  if (e.target.closest('.cv-port') || e.target.closest('.cv-btn--matches') || e.target.closest('.cv-node__collapse')) return;
  e.preventDefault();
  const nodo = STATE.nodos[nodeId];
  if (!nodo || !nodo.el) return;
  STATE.selected = nodeId;
  selectNode(nodeId);
  STATE.dragging = {
    id: nodeId,
    startX: e.clientX,
    startY: e.clientY,
    offsetX: nodo.x,
    offsetY: nodo.y,
  };
}

function doNodeDrag(e) {
  if (!STATE.dragging) return;
  const d = STATE.dragging;
  const vp = STATE.viewport;
  const dx = (e.clientX - d.startX) / vp.zoom;
  const dy = (e.clientY - d.startY) / vp.zoom;
  const nodo = STATE.nodos[d.id];
  if (nodo) {
    nodo.x = d.offsetX + dx;
    nodo.y = d.offsetY + dy;
    if (nodo.el) {
      nodo.el.style.left = nodo.x + 'px';
      nodo.el.style.top  = nodo.y + 'px';
    }
  }
  updateEdges();
  markDirty();
}

function endNodeDrag() {
  if (!STATE.dragging) return;
  // Capturar estado después del drag (la posición ya se actualizó en doNodeDrag)
  if (typeof captureState === 'function') captureState();
  STATE.dragging = null;
}

/* ── CONNECTION DRAG ── */

function startConnection(e, nodeId, portDir) {
  e.preventDefault();
  e.stopPropagation();
  STATE.connecting = { origen: nodeId, port_dir: portDir || 'right' };
  dom.stage.style.cursor = 'crosshair';
}

function doConnectionMove(e) {
  if (!STATE.connecting) return;
  // Draw temporary edge (handled in edges module)
  updateTempEdge(e);
}

function endConnection(e) {
  if (!STATE.connecting) return;
  const targetPort = e.target.closest('.cv-port');
  if (targetPort && targetPort.dataset.node) {
    const targetId = targetPort.dataset.node;
    const targetPortDir = targetPort.dataset.port || 'left';
    if (targetId !== STATE.connecting.origen) {
      if (typeof captureState === 'function') captureState();
      const edgeId = 'e' + (++STATE.edgeIdCounter);
      STATE.aristas[edgeId] = {
        id: edgeId,
        origen: STATE.connecting.origen,
        port_from: STATE.connecting.port_dir || 'right',
        destino: targetId,
        port_to: targetPortDir,
        tipo: 'match',
        label: '',
      };
      updateEdges();
      markDirty();
    }
  }
  STATE.connecting = null;
  dom.stage.style.cursor = 'default';
  removeTempEdge();
}

/* ── NODE SELECTION ── */

function selectNode(nodeId) {
  Object.values(STATE.nodos).forEach(n => {
    if (n.el) n.el.classList.remove('selected');
  });
  if (nodeId && STATE.nodos[nodeId] && STATE.nodos[nodeId].el) {
    STATE.nodos[nodeId].el.classList.add('selected');
  }
  STATE.selected = nodeId;
}

function deselectAll(e) {
  if (e && e.target.closest('.cv-node')) return;
  STATE.selected = null;
  Object.values(STATE.nodos).forEach(n => {
    if (n.el) n.el.classList.remove('selected');
  });
}

/* ── MINIMAP ── */

function drawMinimap() {
  const ctx = dom.minimap.getContext('2d');
  if (!ctx) return;
  const W = 140, H = 90;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#13151d';
  ctx.fillRect(0, 0, W, H);

  const stageRect = dom.stage.getBoundingClientRect();
  const scaleX = W / stageRect.width;
  const scaleY = H / stageRect.height;

  // Draw nodes as small dots
  ctx.fillStyle = '#5c6bc0';
  Object.values(STATE.nodos).forEach(n => {
    if (n.tipo === 'propiedad') ctx.fillStyle = '#1d9e75';
    else if (n.tipo === 'requerimiento') ctx.fillStyle = '#8896f0';
    else ctx.fillStyle = '#c9b44a';
    ctx.beginPath();
    ctx.arc(n.x * scaleX, n.y * scaleY, 2, 0, Math.PI * 2);
    ctx.fill();
  });

  // Viewport rect
  const vp = STATE.viewport;
  dom.minimapVp.style.left   = (-vp.x / vp.zoom) * scaleX + 'px';
  dom.minimapVp.style.top    = (-vp.y / vp.zoom) * scaleY + 'px';
  dom.minimapVp.style.width  = (stageRect.width / vp.zoom) * scaleX + 'px';
  dom.minimapVp.style.height = (stageRect.height / vp.zoom) * scaleY + 'px';
}

/* ── FIT TO SCREEN ── */

function fitToScreen() {
  const nodos = Object.values(STATE.nodos);
  if (nodos.length === 0) return;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  nodos.forEach(n => {
    if (n.x < minX) minX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.x + (n.width || 220) > maxX) maxX = n.x + (n.width || 220);
    if (n.y + (n.height || 100) > maxY) maxY = n.y + (n.height || 100);
  });
  const w = maxX - minX + 80;
  const h = maxY - minY + 80;
  const rect = dom.stage.getBoundingClientRect();
  const zoom = Math.min(rect.width / w, rect.height / h, 1.5);
  STATE.viewport = {
    x: (rect.width - w * zoom) / 2 - minX * zoom,
    y: (rect.height - h * zoom) / 2 - minY * zoom,
    zoom: zoom,
  };
  updateTransform();
}

/* ── RESIZE ── */

var _resize = null; // { nodeId, startX, startY, startW, startH }

function startResize(e, handle) {
  var nodeId = handle.dataset.node;
  var nodo = STATE.nodos[nodeId];
  if (!nodo) return;
  e.preventDefault();
  e.stopPropagation();
  _resize = {
    nodeId: nodeId,
    startX: e.clientX,
    startY: e.clientY,
    startW: nodo.width || 220,
    startH: nodo.height || 100,
  };
}

function doResize(e) {
  if (!_resize) return;
  var dx = (e.clientX - _resize.startX) / STATE.viewport.zoom;
  var dy = (e.clientY - _resize.startY) / STATE.viewport.zoom;
  var newW = Math.max(180, _resize.startW + dx);
  var newH = Math.max(60, _resize.startH + dy);
  var nodo = STATE.nodos[_resize.nodeId];
  if (!nodo || !nodo.el) return;
  nodo.width = newW;
  nodo.height = newH;
  nodo.el.style.width = newW + 'px';
  nodo.el.style.height = newH + 'px';
  markDirty();
  if (typeof drawEdges === 'function') drawEdges();
}

function endResize() {
  if (_resize) {
    _resize = null;
  }
}

/* ── INIT ── */

function initCanvas() {
  cacheDom();
  resizeGrid();
  window.addEventListener('resize', () => { resizeGrid(); drawMinimap(); });

  // Stage events
  dom.stage.addEventListener('contextmenu', e => e.preventDefault());
  dom.stage.addEventListener('mousedown', function(e) {
    var handle = e.target.closest('.cv-resize-handle');
    if (handle) {
      startResize(e, handle);
      return;
    }
    startPan(e);
  });
  dom.stage.addEventListener('mousemove', e => { doPan(e); doNodeDrag(e); doConnectionMove(e); doResize(e); });
  dom.stage.addEventListener('mouseup', e => { endPan(); endNodeDrag(); endConnection(e); endResize(); });
  dom.stage.addEventListener('mouseleave', () => { endPan(); endNodeDrag(); endConnection({ target: null }); endResize(); });
  dom.stage.addEventListener('wheel', doZoom, { passive: false });
  dom.stage.addEventListener('click', deselectAll);

  // Zoom buttons
  document.getElementById('btn-zoom-in').addEventListener('click', zoomIn);
  document.getElementById('btn-zoom-out').addEventListener('click', zoomOut);
  document.getElementById('btn-zoom-reset').addEventListener('click', zoomReset);

  // Fit button
  document.getElementById('btn-fit').addEventListener('click', fitToScreen);

  // Restore snapshot if exists
  if (SNAPSHOT && SNAPSHOT.nodos && SNAPSHOT.nodos.length > 0) {
    restoreSnapshot(SNAPSHOT);
  }
  
  // Restaurar agente_id y campos del snapshot aunque no haya nodos
  // (necesario cuando el usuario solo seleccionó agente pero no arrastró tarjetas)
  if (SNAPSHOT) {
    if (SNAPSHOT.agente_id) {
      STATE._restoreAgenteId = SNAPSHOT.agente_id;
    }
    if (SNAPSHOT.campos && SNAPSHOT.campos.length > 0) {
      document.querySelectorAll('.campo-check').forEach(c => {
        c.checked = SNAPSHOT.campos.includes(c.value);
      });
    }
  }

  // Init minimap
  requestAnimationFrame(function renderLoop() {
    drawMinimap();
    requestAnimationFrame(renderLoop);
  });
}

// Called after DOM ready
document.addEventListener('DOMContentLoaded', initCanvas);
