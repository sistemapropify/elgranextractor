/**
 * canvas_edges.js — PropFlow Canvas Edges
 *
 * Renderizado de aristas SVG con curvas Bezier entre nodos.
 * Soporta 4 puertos direccionales: top, right, bottom, left.
 * La curva se adapta según la dirección de los puertos de origen y destino.
 */

let tempEdgeEl = null;

/* ── EDGE PATH con curvas adaptativas ── */

function edgePath(x1, y1, x2, y2, portFrom, portTo) {
  // Calcular puntos de control según direcciones de los puertos
  const dx = Math.abs(x2 - x1);
  const dy = Math.abs(y2 - y1);
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  
  // Control point offset: usar distancia proporcional para curvas suaves
  const cpx1 = portFrom === 'right' ? x1 + dx * 0.5
             : portFrom === 'left'  ? x1 - dx * 0.5
             : portFrom === 'top'   ? x1
             : portFrom === 'bottom'? x1
             : x1 + dx * 0.5;
  
  const cpy1 = portFrom === 'right' ? y1
             : portFrom === 'left'  ? y1
             : portFrom === 'top'   ? y1 - dy * 0.5
             : portFrom === 'bottom'? y1 + dy * 0.5
             : y1;
  
  const cpx2 = portTo === 'right' ? x2 + dx * 0.5
             : portTo === 'left'  ? x2 - dx * 0.5
             : portTo === 'top'   ? x2
             : portTo === 'bottom'? x2
             : x2 - dx * 0.5;
  
  const cpy2 = portTo === 'right' ? y2
             : portTo === 'left'  ? y2
             : portTo === 'top'   ? y2 - dy * 0.5
             : portTo === 'bottom'? y2 + dy * 0.5
             : y2;
  
  return `M${x1},${y1} C${cpx1},${cpy1} ${cpx2},${cpy2} ${x2},${y2}`;
}


/**
 * Obtiene la posición de un puerto específico en un nodo.
 * @param {string} id - ID del nodo
 * @param {string} portDir - dirección: 'top'|'right'|'bottom'|'left'
 * @returns {{x, y}}
 */
function getNodePortPos(id, portDir) {
  const nodo = STATE.nodos[id];
  if (!nodo) return { x: 0, y: 0 };
  const w = nodo.width || 220;
  const h = nodo.height || 160;
  
  switch (portDir) {
    case 'top':    return { x: nodo.x + w / 2, y: nodo.y };
    case 'right':  return { x: nodo.x + w,     y: nodo.y + h / 2 };
    case 'bottom': return { x: nodo.x + w / 2, y: nodo.y + h };
    case 'left':   return { x: nodo.x,         y: nodo.y + h / 2 };
    default:       return { x: nodo.x + w,     y: nodo.y + h / 2 }; // fallback a right
  }
}


/* ── UPDATE ALL EDGES ── */

function updateEdges() {
  // Remove old edges and badges
  dom.edges.querySelectorAll('.cv-edge, .cv-edge__label, .cv-edge__badge-group').forEach(el => {
    if (el !== tempEdgeEl) el.remove();
  });

  Object.values(STATE.aristas).forEach(edge => {
    const from     = getNodePortPos(edge.origen, edge.port_from || 'right');
    const to       = getNodePortPos(edge.destino, edge.port_to || 'left');
    const path     = edgePath(from.x, from.y, to.x, to.y, edge.port_from || 'right', edge.port_to || 'left');

    const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pathEl.setAttribute('d', path);
    pathEl.classList.add('cv-edge', `cv-edge--${edge.tipo}`);
    if (edge.tipo === 'match') pathEl.setAttribute('marker-end', 'url(#arrow-blue)');
    else if (edge.tipo === 'dep') pathEl.setAttribute('marker-end', 'url(#arrow-green)');
    else if (edge.tipo === 'block') pathEl.setAttribute('marker-end', 'url(#arrow-red)');
    dom.edges.appendChild(pathEl);

    // ── BADGE CIRCULAR AMARILLO (solo para edges match) ──
    if (edge.tipo === 'match') {
      const midX = (from.x + to.x) / 2;
      const midY = (from.y + to.y) / 2;

      // Obtener score
      let scoreVal = edge.score_total;
      if (scoreVal == null && edge.label) {
        scoreVal = parseFloat(edge.label);
      }
      const score = !isNaN(scoreVal) ? Math.round(parseFloat(scoreVal)) : 0;

      // Grupo SVG contenedor
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.classList.add('cv-edge__badge-group');
      g.style.cssText = 'cursor:pointer;pointer-events:all;';
      if (edge.match_id) g.dataset.matchId = edge.match_id;

      // Círculo de fondo más grande
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', midX);
      circle.setAttribute('cy', midY);
      circle.setAttribute('r', '26');
      circle.classList.add('cv-edge__badge-circle');
      g.appendChild(circle);

      // Texto "MATCH" arriba
      const labelText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      labelText.setAttribute('x', midX);
      labelText.setAttribute('y', midY - 5);
      labelText.setAttribute('text-anchor', 'middle');
      labelText.classList.add('cv-edge__badge-label');
      labelText.textContent = 'MATCH';
      g.appendChild(labelText);

      // Texto del score abajo
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', midX);
      text.setAttribute('y', midY + 11);
      text.setAttribute('text-anchor', 'middle');
      text.classList.add('cv-edge__badge-text');
      text.textContent = score + '%';
      g.appendChild(text);

      // Click en badge → crear nodo match
      g.addEventListener('click', function(e) {
        e.stopPropagation();
        if (edge.match_id && typeof createMatchNode === 'function') {
          createMatchNode(edge.match_id, midX - 140, midY - 80);
        }
      });

      dom.edges.appendChild(g);

      // ── PUERTOS HTML ENCIMA DEL BADGE (para que no se corten) ──
      var virtualId = 'match_badge_' + (edge.match_id || Math.random().toString(36).substr(2,6));
      var portSize = 14;
      var offset = 32;
      var portPositions = [
        { dir:'top',    l:midX - portSize/2, t:midY - offset - portSize/2 },
        { dir:'right',  l:midX + offset - portSize/2, t:midY - portSize/2 },
        { dir:'bottom', l:midX - portSize/2, t:midY + offset - portSize/2 },
        { dir:'left',   l:midX - offset - portSize/2, t:midY - portSize/2 },
      ];
      portPositions.forEach(function(p) {
        var portEl = document.createElement('div');
        portEl.className = 'cv-badge-port';
        portEl.style.cssText = 'position:absolute;left:' + p.l + 'px;top:' + p.t + 'px;' +
          'width:' + portSize + 'px;height:' + portSize + 'px;border-radius:50%;' +
          'background:#3a3e58;border:2px solid #ffdd00;cursor:crosshair;' +
          'z-index:10;pointer-events:all;';
        portEl.dataset.portDir = p.dir;
        portEl.dataset.virtualNode = virtualId;
        portEl.dataset.matchId = edge.match_id || '';
        // Mousedown en puerto → iniciar conexión
        portEl.addEventListener('mousedown', function(ev) {
          ev.stopPropagation();
          ev.preventDefault();
          // Registrar nodo virtual
          if (!STATE.nodos[virtualId]) {
            STATE.nodos[virtualId] = {
              id: virtualId, tipo: 'match_badge',
              ref_id: edge.match_id || null,
              x: midX - 26, y: midY - 26, width: 52, height: 52,
              collapsed: false, color: null, el: null, _virtual: true,
            };
          }
          if (typeof startConnection === 'function') {
            startConnection(ev, virtualId, p.dir);
          }
        });
        dom.nodes.appendChild(portEl);
      });
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
  const from = getNodePortPos(conn.origen, conn.port_dir || 'right');
  const rect = dom.stage.getBoundingClientRect();
  const vp = STATE.viewport;
  const mx = (e.clientX - rect.left - vp.x) / vp.zoom;
  const my = (e.clientY - rect.top - vp.y) / vp.zoom;
  const path = edgePath(from.x, from.y, mx, my, conn.port_dir || 'right', 'left');
  tempEdgeEl.setAttribute('d', path);
}

function removeTempEdge() {
  if (tempEdgeEl && tempEdgeEl.parentNode) {
    tempEdgeEl.parentNode.removeChild(tempEdgeEl);
  }
  tempEdgeEl = null;
}
