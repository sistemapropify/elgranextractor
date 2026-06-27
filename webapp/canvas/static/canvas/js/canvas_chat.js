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
    const res = await fetch('/api/v1/intelligence/chat-web/api/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': typeof CSRF !== 'undefined' ? CSRF : '',
      },
      body: JSON.stringify({
        message: text,
        conversation_id: canvasChatState.conversationId,
        use_memory: true,
        use_rag: true,
        metadata: {
          source: 'canvas',
          lienzo_id: typeof LIENZO_ID !== 'undefined' ? LIENZO_ID : null,
          canvas_context: buildCanvasContext(),
        },
      }),
    });

    const data = await res.json();

    // Remover indicador de carga
    removeChatMessage(loadingId);

    if (data.success) {
      canvasChatState.conversationId = data.conversation_id;

      // NUEVO: detectar acción de agregar nodos al canvas
      if (data.action && data.action.type === 'add_nodes') {
        executeAddNodesAction(data.action, data.response || data.html);
      } else {
        // Flujo normal: mostrar como texto/HTML
        addChatMessage('assistant', data.response || data.html || '');
      }
    } else {
      addChatMessage('assistant', 'Error: ' + (data.error || 'No se pudo obtener respuesta'));
    }
  } catch (err) {
    removeChatMessage(loadingId);
    addChatMessage('assistant', 'Error de conexión. Intenta de nuevo.');
    console.error('Canvas chat error:', err);
  } finally {
    canvasChatState.loading = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

/* ── ACCIÓN: AGREGAR NODOS AL LIENZO ── */

/**
 * Ejecuta una acción de tipo add_nodes recibida desde el backend.
 * Crea nodos en el canvas usando createPropNode() y marca dirty.
 * No duplica nodos ya existentes. Respeta la plantilla de campos activa.
 */
function executeAddNodesAction(action, mensaje) {
  if (!action.nodes || action.nodes.length === 0) {
    addChatMessage('assistant', mensaje || 'No se encontraron propiedades para agregar.');
    return;
  }

  // Capturar estado para undo antes de modificar
  if (typeof captureState === 'function') captureState();

  const campos = (typeof getActiveCampos === 'function') ? getActiveCampos() : [];
  let addedCount = 0;

  action.nodes.forEach(function(nodeData, index) {
    if (nodeData.node_type === 'propiedad' && nodeData.source_id) {
      const existingId = 'prop_' + nodeData.source_id;
      if (STATE.nodos[existingId]) return; // ya está en el canvas, no duplicar

      // Posición en cascada (misma lógica que sidebar.js:addPropToCanvas)
      const vp = STATE.viewport;
      const existingProps = Object.values(STATE.nodos).filter(n => n.tipo === 'propiedad');
      const offsetX = 50 + (existingProps.length + addedCount) % 4 * 240;
      const offsetY = 60 + Math.floor((existingProps.length + addedCount) / 4) * 200;
      const x = (offsetX - vp.x) / vp.zoom;
      const y = (offsetY - vp.y) / vp.zoom;

      createPropNode(nodeData.source_id, nodeData.data, x, y, campos);
      addedCount++;
    }
  });

  if (addedCount > 0) {
    if (typeof markDirty === 'function') markDirty();
    const confirmMsg = '✅ Agregué ' + addedCount + ' propiedad' + (addedCount > 1 ? 'es' : '') + ' al lienzo. ' + (mensaje || '');
    addChatMessage('assistant', confirmMsg);
  } else {
    addChatMessage('assistant', mensaje || 'Todas las propiedades ya están en el lienzo.');
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
  div.dataset.msgId = 'msg_' + ts + '_' + rand;
  messages.appendChild(div);
  // Auto-scroll al último mensaje
  messages.scrollTop = messages.scrollHeight;
  return div.dataset.msgId;
}

function removeChatMessage(msgId) {
  var el = document.querySelector('[data-msgid="' + msgId + '"]');
  if (el) el.remove();
}
