/**
 * canvas_chat.js — Chat IA en la sidebar del Canvas
 *
 * Se conecta al sistema de inteligencia existente (chat-web API)
 * para permitir conversaciones contextuales sobre propiedades,
 * requerimientos y matching desde el lienzo.
 *
 * Dependencias: canvas_engine.js (STATE, CSRF), canvas_save.js (CSRF)
 */

/* ── ESTADO DEL CHAT ── */
let canvasChatState = {
  conversationId: null,
  loading: false,
};

/* ── INICIALIZACIÓN ── */

function initCanvasChat() {
  console.log('[CanvasChat] Inicializando...');
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send');
  const clearBtn = document.getElementById('chat-clear');
  const messages = document.getElementById('chat-messages');

  if (!input || !sendBtn) {
    console.warn('[CanvasChat] No se encontraron elementos del chat');
    return;
  }
  console.log('[CanvasChat] Inicializado correctamente');

  // Enviar con Enter (Shift+Enter para nueva línea)
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  sendBtn.addEventListener('click', sendChatMessage);

  clearBtn.addEventListener('click', function() {
    canvasChatState.conversationId = null;
    messages.innerHTML =
      '<div class="cv-chat-msg cv-chat-msg--system">' +
        'Hola! Soy tu asistente. Pregúntame sobre las propiedades, ' +
        'requerimientos o el mercado inmobiliario.' +
      '</div>';
  });

  // Auto-ajuste de altura del textarea
  input.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 80) + 'px';
  });
}

/* ── CONTEXTO DEL LIENZO ── */

function buildCanvasContext() {
  // NUNCA retornar {} (objeto vacío) porque en el backend Python
  // bool({}) es False y eso impide detectar el contexto del canvas.
  // Siempre retornar al menos {propiedades_count: 0, ...} que es truthy.
  if (typeof STATE === 'undefined' || !STATE.nodos) {
    return {
      propiedades_count: 0,
      requerimientos_count: 0,
      matches_count: 0,
      propiedades: [],
      requerimientos: [],
      matches: [],
    };
  }

  const propiedades = [];
  const requerimientos = [];
  const matches = [];

  Object.values(STATE.nodos).forEach(function(n) {
    if (n.tipo === 'propiedad' && n.field_data) {
      propiedades.push({
        id: n.ref_id,
        titulo: n.field_data.title || n.field_data.direction || '',
        precio: n.field_data.price,
        moneda: n.field_data.currency,
        distrito: n.field_data.district_name || n.field_data.district || '',
        tipo: n.field_data.tipo_propiedad || n.field_data.property_type || '',
        area: n.field_data.area_construida || n.field_data.area || '',
        dormitorios: n.field_data.dormitorios || n.field_data.bedrooms || '',
        direccion: n.field_data.direction || n.field_data.map_address || '',
      });
    } else if (n.tipo === 'requerimiento' && n.field_data) {
      requerimientos.push({
        id: n.ref_id,
        agente: n.field_data.agente || '',
        telefono: n.field_data.agente_telefono || '',
        fecha: n.field_data.fecha || '',
        tipo: n.field_data.tipo_original || '',
        texto: n.field_data.requerimiento || '',
        presupuesto: n.field_data.presupuesto_monto || n.field_data.presupuesto || '',
        moneda: n.field_data.presupuesto_moneda || n.field_data.moneda || '',
        distritos: n.field_data.distritos || '',
        tipo_propiedad: n.field_data.tipo_propiedad || '',
        urbanizacion: n.field_data.urbanizacion || '',
        zona: n.field_data.zona || '',
      });
    }
  });

  // Recopilar aristas (matches) para que el AI entienda conexiones existentes
  Object.values(STATE.aristas).forEach(function(e) {
    if (e.tipo === 'match') {
      matches.push({
        origen: e.origen,
        destino: e.destino,
        score: e.score_total,
        label: e.label,
      });
    }
  });

  return {
    propiedades_count: propiedades.length,
    requerimientos_count: requerimientos.length,
    matches_count: matches.length,
    propiedades: propiedades,
    requerimientos: requerimientos,
    matches: matches,
  };
}

/* ── ENVIAR MENSAJE ── */

async function sendChatMessage() {
  console.log('[CanvasChat] Enviando mensaje...');
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send');
  const messages = document.getElementById('chat-messages');
  const text = input.value.trim();

  if (!text || canvasChatState.loading) {
    console.log('[CanvasChat] No se envia: text=' + !!text + ' loading=' + canvasChatState.loading);
    return;
  }

  // Limpiar input y reset altura
  input.value = '';
  input.style.height = 'auto';

  // Agregar mensaje del usuario
  addChatMessage('user', text);

  // Mostrar indicador de carga
  const loadingId = addChatMessage('loading', 'Escribiendo...');

  canvasChatState.loading = true;
  sendBtn.disabled = true;

  try {
    // Timeout de 45s para evitar que se quede pegado si DeepSeek no responde
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000);

    const res = await fetch('/api/v1/intelligence/chat-web/api/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': typeof CSRF !== 'undefined' ? CSRF : '',
      },
      signal: controller.signal,
      body: JSON.stringify({
        message: text,
        conversation_id: canvasChatState.conversationId,
        user_id: typeof USER_ID !== 'undefined' ? USER_ID : null,
        use_memory: true,
        use_rag: true,
        metadata: {
          source: 'canvas',
          lienzo_id: typeof LIENZO_ID !== 'undefined' ? LIENZO_ID : null,
          canvas_context: buildCanvasContext(),
        },
      }),
    });

    clearTimeout(timeoutId);

    const data = await res.json();

    // Remover indicador de carga
    removeChatMessage(loadingId);

    if (data.success) {
      canvasChatState.conversationId = data.conversation_id;

      // Detectar acción del backend (add_nodes, rearrange_nodes, clear_canvas, etc.)
      if (data.action) {
        if (data.action.type === 'add_nodes') {
          executeAddNodesAction(data.action, data.response || data.html);
        } else if (data.action.type === 'rearrange_nodes') {
          executeRearrangeNodesAction(data.action);
          // Mostrar también el mensaje de respuesta si existe
          if (data.response || data.html) {
            addChatMessage('assistant', data.response || data.html);
          }
        } else if (data.action.type === 'clear_canvas') {
          executeClearCanvasAction(data.action);
          // Mostrar mensaje de confirmación
          addChatMessage('assistant', data.response || data.html || '✅ El lienzo ha sido limpiado exitosamente.');
        } else {
          // Acción desconocida, mostrar mensaje normal
          addChatMessage('assistant', data.response || data.html || '');
        }
      } else {
        // Flujo normal: mostrar como texto/HTML
        addChatMessage('assistant', data.response || data.html || '');
      }
    } else {
      addChatMessage('assistant', 'Error: ' + (data.error || 'No se pudo obtener respuesta'));
    }
  } catch (err) {
    removeChatMessage(loadingId);
    if (err.name === 'AbortError') {
      addChatMessage('assistant', '⏱️ La solicitud tardó demasiado. Intenta con una consulta más simple o vuelve a intentarlo.');
    } else {
      addChatMessage('assistant', 'Error de conexión. Intenta de nuevo.');
    }
    console.error('Canvas chat error:', err);
  } finally {
    canvasChatState.loading = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

/* ── ACCIÓN: AGREGAR NODOS AL LIENZO ── */

/**
 * Calcula una posición para un nodo según la estrategia especificada.
 * Soporta: cascade (default grid), vertical (una columna), grid (N columnas), circle.
 *
 * @param {number} index - Índice dentro del lote actual (0-based)
 * @param {number} totalPrevios - Cantidad de nodos del mismo tipo ya existentes
 * @param {object} options - { strategy, columns, gap, startX, startY }
 * @returns {{ x: number, y: number }}
 */
function calcNodePosition(index, totalPrevios, options) {
  var opts = Object.assign({
    strategy: 'cascade',
    columns: 4,
    gap: 200,
    startX: 50,
    startY: 60,
  }, options || {});

  var vp = STATE.viewport;
  var nodeIndex = totalPrevios + index;
  var cardWidth = 240;
  var cardGap = opts.gap || 200;
  var colGap  = 40;

  var offsetX, offsetY;

  switch (opts.strategy) {
    case 'vertical':
      offsetX = opts.startX;
      offsetY = opts.startY + nodeIndex * cardGap;
      break;

    case 'grid':
      offsetX = opts.startX + (nodeIndex % opts.columns) * (cardWidth + colGap);
      offsetY = opts.startY + Math.floor(nodeIndex / opts.columns) * cardGap;
      break;

    case 'circle':
      {
        var total = totalPrevios + nodeIndex + 1;
        var radius = Math.max(200, total * 25);
        var angle = (2 * Math.PI * nodeIndex) / Math.max(total, 1);
        var cx = opts.startX + radius;
        var cy = opts.startY + radius;
        offsetX = cx + Math.cos(angle) * radius - cardWidth / 2;
        offsetY = cy + Math.sin(angle) * radius - 60;
      }
      break;

    case 'cascade':
    default:
      offsetX = opts.startX + (nodeIndex % opts.columns) * (cardWidth + colGap);
      offsetY = opts.startY + Math.floor(nodeIndex / opts.columns) * cardGap;
      break;
  }

  return {
    x: (offsetX - vp.x) / vp.zoom,
    y: (offsetY - vp.y) / vp.zoom,
  };
}


/**
 * Ejecuta una acción de tipo add_nodes recibida desde el backend.
 * Crea nodos en el canvas usando createPropNode() y marca dirty.
 * No duplica nodos ya existentes.
 * Respeta position_strategy, columns y gap definidos en la acción.
 */
function executeAddNodesAction(action, mensaje) {
  if (!action.nodes || action.nodes.length === 0) {
    addChatMessage('assistant', mensaje || 'No se encontraron propiedades para agregar.');
    return;
  }

  if (typeof captureState === 'function') captureState();

  var campos = (typeof getActiveCampos === 'function') ? getActiveCampos() : [];
  var addedCount = 0;

  var posStrategy = action.position_strategy || 'cascade';
  var posColumns = action.columns || 4;
  var posGap = action.gap || 200;

  var effectiveStrategy = posStrategy;
  var effectiveColumns = posColumns;
  if (posStrategy === 'vertical') {
    effectiveStrategy = 'vertical';
    effectiveColumns = 1;
  } else if (posStrategy === 'cascade') {
    effectiveColumns = 4;
  }

  action.nodes.forEach(function(nodeData, index) {
    if (nodeData.node_type === 'propiedad' && nodeData.source_id) {
      var existingId = 'prop_' + nodeData.source_id;
      if (STATE.nodos[existingId]) return;

      var existingProps = Object.values(STATE.nodos).filter(function(n) { return n.tipo === 'propiedad'; });
      var pos = calcNodePosition(index, existingProps.length, {
        strategy: effectiveStrategy,
        columns: effectiveColumns,
        gap: posGap,
      });

      createPropNode(nodeData.source_id, nodeData.data, pos.x, pos.y, campos);
      addedCount++;
    }
  });

  if (addedCount > 0) {
    if (typeof markDirty === 'function') markDirty();

    if (action.rearrange) {
      setTimeout(function() {
        executeRearrangeNodesAction(action.rearrange);
      }, 100);
    }

    addChatMessage('assistant', '✅ Agregu\u00e9 ' + addedCount + ' propiedad' + (addedCount > 1 ? 'es' : '') + ' al lienzo.');
  } else {
    addChatMessage('assistant', mensaje || 'Todas las propiedades ya est\u00e1n en el lienzo.');
  }
}


/* ── ACCIÓN: REORDENAR NODOS DEL LIENZO ── */

/**
 * Ejecuta una accion de tipo rearrange_nodes.
 * Reordena los nodos existentes segun la estrategia especificada.
 *
 * Estrategias:
 *   - grid: disposicion en grilla con N columnas
 *   - vertical: una sola columna vertical
 *   - sort: ordena y luego dispone en grid
 *   - group: agrupa por campo y dispone en grid
 *   - circle: disposicion circular
 */
function executeRearrangeNodesAction(action) {
  if (!action || action.type !== 'rearrange_nodes') return;

  var strategy = action.strategy || 'grid';
  var columns = action.columns || 4;
  var gap = action.gap || 200;
  var startX = 50;
  var startY = 60;

  var propNodes = Object.values(STATE.nodos).filter(function(n) { return n.tipo === 'propiedad'; });
  var reqNodes = Object.values(STATE.nodos).filter(function(n) { return n.tipo === 'requerimiento'; });

  if (propNodes.length === 0 && reqNodes.length === 0) {
    addChatMessage('assistant', 'No hay nodos en el lienzo para reordenar.');
    return;
  }

  if (typeof captureState === 'function') captureState();

  // ── ORDENAR (sort) ──
  var orderedProps = propNodes.slice();
  if (strategy === 'sort' && action.sort_by) {
    var sortField = action.sort_by;
    var sortOrder = action.sort_order || 'asc';
    orderedProps.sort(function(a, b) {
      var va = a.field_data ? (a.field_data[sortField] || '') : '';
      var vb = b.field_data ? (b.field_data[sortField] || '') : '';
      if (typeof va === 'number' && typeof vb === 'number') {
        return sortOrder === 'asc' ? va - vb : vb - va;
      }
      var sa = String(va).toLowerCase();
      var sb = String(vb).toLowerCase();
      if (sa < sb) return sortOrder === 'asc' ? -1 : 1;
      if (sa > sb) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }

  // ── AGRUPAR (group) ──
  var groupedProps = null;
  if (strategy === 'group' && action.group_by) {
    groupedProps = {};
    orderedProps.forEach(function(n) {
      var val = n.field_data ? (n.field_data[action.group_by] || 'Sin agrupar') : 'Sin agrupar';
      if (!groupedProps[val]) groupedProps[val] = [];
      groupedProps[val].push(n);
    });
  }

  // ── POSICIONAR ──
  var vp = STATE.viewport;

  if (strategy === 'group' && groupedProps) {
    var groupKeys = Object.keys(groupedProps);
    var groupY = startY;
    groupKeys.forEach(function(key) {
      var groupNodes = groupedProps[key];
      groupNodes.forEach(function(n, i) {
        var col = i % columns;
        var row = Math.floor(i / columns);
        var nx = startX + col * 250;
        var ny = groupY + row * gap;
        n.x = (nx - vp.x) / vp.zoom;
        n.y = (ny - vp.y) / vp.zoom;
        if (n.el) {
          n.el.style.left = n.x + 'px';
          n.el.style.top = n.y + 'px';
        }
      });
      groupY += Math.ceil(groupNodes.length / columns) * gap + 40;
    });
  } else if (strategy === 'vertical') {
    orderedProps.forEach(function(n, i) {
      var nx = startX;
      var ny = startY + i * gap;
      n.x = (nx - vp.x) / vp.zoom;
      n.y = (ny - vp.y) / vp.zoom;
      if (n.el) {
        n.el.style.left = n.x + 'px';
        n.el.style.top = n.y + 'px';
      }
    });
  } else if (strategy === 'circle') {
    var total = orderedProps.length;
    var radius = Math.max(200, total * 25);
    var cardWidth = 220;
    orderedProps.forEach(function(n, i) {
      var angle = (2 * Math.PI * i) / Math.max(total, 1);
      var cx = startX + radius;
      var cy = startY + radius;
      var nx = cx + Math.cos(angle) * radius - cardWidth / 2;
      var ny = cy + Math.sin(angle) * radius - 60;
      n.x = (nx - vp.x) / vp.zoom;
      n.y = (ny - vp.y) / vp.zoom;
      if (n.el) {
        n.el.style.left = n.x + 'px';
        n.el.style.top = n.y + 'px';
      }
    });
  } else {
    // grid
    orderedProps.forEach(function(n, i) {
      var col = i % columns;
      var row = Math.floor(i / columns);
      var nx = startX + col * 250;
      var ny = startY + row * gap;
      n.x = (nx - vp.x) / vp.zoom;
      n.y = (ny - vp.y) / vp.zoom;
      if (n.el) {
        n.el.style.left = n.x + 'px';
        n.el.style.top = n.y + 'px';
      }
    });
  }

  // Posicionar requerimientos a la derecha
  var baseX = startX + 800;
  reqNodes.forEach(function(n, i) {
    var nx = baseX;
    var ny = startY + i * gap;
    n.x = (nx - vp.x) / vp.zoom;
    n.y = (ny - vp.y) / vp.zoom;
    if (n.el) {
      n.el.style.left = n.x + 'px';
      n.el.style.top = n.y + 'px';
    }
  });

  if (typeof updateEdges === 'function') updateEdges();
  if (typeof markDirty === 'function') markDirty();
  if (typeof fitToScreen === 'function') fitToScreen();

  var msg = '\ud83d\udd04 Nodos reordenados en ' + strategy;
  if (columns > 1) msg += ' (' + columns + ' columnas)';
  if (action.gap) msg += ', separaci\u00f3n ' + action.gap + 'px';
  msg += '.';
  addChatMessage('assistant', msg);
}


  /* ── ACCIÓN: LIMPIAR LIENZO ── */

/**
 * Limpia completamente el lienzo eliminando todos los nodos y aristas.
 * Deja el canvas vacío como nuevo, listo para empezar de cero.
 * Captura el estado actual en el historial de deshacer antes de limpiar.
 */
function clearCanvas() {
  // Capturar estado para undo antes de la limpieza
  if (typeof captureState === 'function') captureState();

  // Eliminar todos los nodos del DOM
  Object.values(STATE.nodos).forEach(function(n) {
    if (n.el && n.el.parentNode) {
      n.el.parentNode.removeChild(n.el);
    }
  });

  // Limpiar estado
  STATE.nodos = {};
  STATE.aristas = {};

  // Actualizar visualizaciones
  if (typeof updateEdges === 'function') updateEdges();
  if (typeof markDirty === 'function') markDirty();
  if (typeof updateTransform === 'function') updateTransform();

  // Resetear viewport a zoom/default
  if (typeof zoomReset === 'function') zoomReset();

  console.log('[CanvasChat] Lienzo limpiado completamente');
}


/**
 * Ejecuta una acción de tipo clear_canvas recibida desde el backend.
 * Limpia todos los nodos y aristas del lienzo, dejándolo vacío.
 * También resetea el contador de chat para empezar una conversación nueva.
 */
function executeClearCanvasAction(action) {
  // Confirmación si hay nodos para evitar borrado accidental
  var nodeCount = Object.keys(STATE.nodos).length;
  if (nodeCount === 0) {
    // Ya está vacío, solo mostrar mensaje
    return;
  }

  clearCanvas();

  // Opcional: resetear conversación del chat también si el backend lo indica
  if (action.reset_chat !== false) {
    canvasChatState.conversationId = null;
    var messages = document.getElementById('chat-messages');
    if (messages) {
      messages.innerHTML =
        '<div class="cv-chat-msg cv-chat-msg--system">' +
          '¡El lienzo ha sido limpiado exitosamente! Ahora está vacío y listo para ' +
          'que puedas agregar nuevas propiedades o realizar nuevas búsquedas.' +
        '</div>';
    }
  }
}


/* ── UTILIDADES DE MENSAJES ── */

function addChatMessage(role, text) {
  var messages = document.getElementById('chat-messages');
  var div = document.createElement('div');
  div.className = 'cv-chat-msg cv-chat-msg--' + role;
  div.textContent = text;
  var ts = Date.now();
  var rand = Math.random().toString(36).substr(2, 4);
  div.dataset.msgid = 'msg_' + ts + '_' + rand;
  messages.appendChild(div);
  // Auto-scroll al último mensaje
  messages.scrollTop = messages.scrollHeight;
  return div.dataset.msgid;
}

function removeChatMessage(msgId) {
  var el = document.querySelector('[data-msgid="' + msgId + '"]');
  if (el) el.remove();
}
