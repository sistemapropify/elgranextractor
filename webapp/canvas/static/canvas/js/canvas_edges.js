/**
 * canvas_edges.js — PropFlow Canvas Edges
 *
 * Renderizado de aristas SVG con curvas Bezier entre nodos.
 * Soporta tipos: match, dependencia, block, nota.
 */

let tempEdgeEl = null;

/* ── EDGE PATH ── */

function edgePath(x1, y1, x2, y2) {
  const dx = Math.abs(x2 - x1) * 0.5;
  return `M${x1},${y1} C${x1+dx},${y1} ${x2-dx},${y2} ${x2},${y2}`;
}

function getNodeCenter(id, portType) {
  const nodo = STATE.nodos[id];
  if (!nodo) return { x: 0, y: 0 };
  const w = nodo.width || 220;
  const h = nodo.height || 160;
  if (portType === 'out') {
    return { x: nodo.x + w, y: nodo.y + h / 2 };
  }
  return { x: nodo.x, y: nodo.y + h / 2 };
}

function getNodePortPos(id, portType) {
  return getNodeCenter(id, portType);
}

/* ── UPDATE ALL EDGES ── */

function updateEdges() {
  // Remove old edges
  dom.edges.querySelectorAll('.cv-edge, .cv-edge__label').forEach(el => {
    if (el !== tempEdgeEl) el.remove();
  });

  Object.values(STATE.aristas).forEach(edge => {
    const from = getNodePortPos(edge.origen, 'out');
    const to   = getNodePortPos(edge.destino, 'in');
    const path = edgePath(from.x, from.y, to.x, to.y);

    const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pathEl.setAttribute('d', path);
    pathEl.classList.add('cv-edge', `cv-edge--${edge.tipo}`);
    if (edge.tipo === 'match') pathEl.setAttribute('marker-end', 'url(#arrow-blue)');
    else if (edge.tipo === 'dep') pathEl.setAttribute('marker-end', 'url(#arrow-green)');
    else if (edge.tipo === 'block') pathEl.setAttribute('marker-end', 'url(#arrow-red)');
    dom.edges.appendChild(pathEl);

    // Label at midpoint
    if (edge.label) {
      const midX = (from.x + to.x) / 2;
      const midY = (from.y + to.y) / 2 - 8;
      const labelEl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      labelEl.setAttribute('x', midX);
      labelEl.setAttribute('y', midY);
      labelEl.setAttribute('text-anchor', 'middle');
      labelEl.classList.add('cv-edge__label');
      labelEl.textContent = edge.label;
      dom.edges.appendChild(labelEl);
    }
  });
}

/* ── TEMPORARY EDGE (durante conexión) ── */

function updateTempEdge(e) {
  if (!tempEdgeEl) {
    tempEdgeEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    tempEdgeEl.classList.add('cv-edge', 'cv-edge--match');
    tempEdgeEl.style.strokeDasharray = '5 3';
    tempEdgeEl.style.opacity = '0.5';
    dom.edges.appendChild(tempEdgeEl);
  }
  const conn = STATE.connecting;
  if (!conn) return;
  const from = getNodePortPos(conn.origen, 'out');
  const rect = dom.stage.getBoundingClientRect();
  const vp = STATE.viewport;
  const mx = (e.clientX - rect.left - vp.x) / vp.zoom;
  const my = (e.clientY - rect.top - vp.y) / vp.zoom;
  const path = edgePath(from.x, from.y, mx, my);
  tempEdgeEl.setAttribute('d', path);
}

function removeTempEdge() {
  if (tempEdgeEl && tempEdgeEl.parentNode) {
    tempEdgeEl.parentNode.removeChild(tempEdgeEl);
  }
  tempEdgeEl = null;
}
