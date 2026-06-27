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
  if (typeof STATE === 'undefined' || !STATE.nodos) return {};

  const propiedades = [];
  const requerimientos = [];

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
      });
    } else if (n.tipo === 'requerimiento' && n.field_data) {
      requerimientos.push({
        id: n.ref_id,
        agente: n.field_data.agente || '',
        tipo: n.field_data.tipo_original || '',
        presupuesto: n.field_data.presupuesto_monto || n.field_data.presupuesto || '',
        moneda: n.field_data.presupuesto_moneda || n.field_data.moneda || '',
        distritos: n.field_data.distritos || '',
        tipo_propiedad: n.field_data.tipo_propiedad || '',
      });
    }
  });

  return {
    propiedades_count: propiedades.length,
    requerimientos_count: requerimientos.length,
    propiedades: propiedades,
    requerimientos: requerimientos,
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
      addChatMessage('assistant', data.response || data.html || '');
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
