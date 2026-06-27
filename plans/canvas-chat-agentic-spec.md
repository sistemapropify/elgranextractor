# Spec: Canvas Chat Agentic — Lenguaje Natural → BD → Agregar Tarjetas al Lienzo

## 1. Resumen

Convertir el chat actual del lienzo (puramente conversacional) en un **asistente agentico** que:
1. Entienda lenguaje natural del usuario
2. Consulte la BD `propiedadespropify` 
3. **Agregue tarjetas de propiedades al canvas** como resultado

Sin romper las funcionalidades existentes de conversación, sidebar drag & drop, checkboxes, autoguardado, undo/redo, ni snapshot.

---

## 2. Estado Actual (qué NO romper)

| Archivo | Función clave | No romper |
|---|---|---|
| [`canvas_chat.js`](webapp/canvas/static/canvas/js/canvas_chat.js) | `sendChatMessage()` — fetch + display text/HTML | Conversación normal debe seguir funcionando |
| [`canvas_sidebar.js:107`](webapp/canvas/static/canvas/js/canvas_sidebar.js:107) | `addPropToCanvas()` — añade desde sidebar | Checkboxes y drag & drop manual |
| [`canvas_nodes.js:17`](webapp/canvas/static/canvas/js/canvas_nodes.js:17) | `createPropNode()` — crea nodo visual | Debe seguir siendo la función central |
| [`canvas_save.js:11`](webapp/canvas/static/canvas/js/canvas_save.js:11) | `markDirty()` — auto-save 2s debounce | Cualquier cambio debe marcarse |
| [`canvas_save.js:20`](webapp/canvas/static/canvas/js/canvas_save.js:20) | `buildSnapshot()` — serializa nodos | Debe incluir nodos agregados por chat |
| [`canvas_history.js:22`](webapp/canvas/static/canvas/js/canvas_history.js:22) | `captureState()` — undo/redo | Cada adición debe capturarse |
| [`chat_processor.py:158`](webapp/intelligence/services/chat_processor.py:158) | `process_message()` — orquestación con DeepSeek | Flujo actual intacto |
| [`chat_processor.py:589`](webapp/intelligence/services/chat_processor.py:589) | `_orquestar()` — decide skill según origen | Routing canvas→BD vs canvas→contexto |
| [`chat_processor.py:795`](webapp/intelligence/services/chat_processor.py:795) | `_generar_respuesta()` — respuesta texto/HTML | Debe poder retornar también acciones |
| [`canvas/models.py:34`](webapp/canvas/models.py:34) | `Lienzo.snapshot` (JSONField) | Guarda estado completo del canvas |
| [`canvas/views.py:224`](webapp/canvas/views.py:224) | `api_propiedades` — consulta `propiedadespropify` | API usada por sidebar y restore |

---

## 3. Arquitectura del Cambio

### Diagrama de flujo: antes vs después

```mermaid
flowchart TD
    subgraph ANTES
        A1[Usuario escribe en chat] --> A2[canvas_chat.js fetch POST]
        A2 --> A3[/api/v1/intelligence/chat-web/api/]
        A3 --> A4[ChatProcessor.orquestar]
        A4 --> A5{¿source=canvas?}
        A5 -->|Sí| A6[usar_contexto_canvas<br/>solo responde con datos del canvas]
        A5 -->|No| A7[busqueda_propiedades en BD]
        A6 --> A8[Devuelve texto/HTML]
        A7 --> A8
        A8 --> A9[canvas_chat.js muestra texto]
    end

    subgraph DESPUES
        B1[Usuario: 'Agrega los depas en Cayma'] --> B2[canvas_chat.js fetch POST<br/>con canvas_context enriquecido]
        B2 --> B3[/api/v1/intelligence/chat-web/api/]
        B3 --> B4[ChatProcessor.orquestar]
        B4 --> B5{¿intención de agregar al canvas?}
        B5 -->|No, solo conversar| B6[Flujo actual: texto/HTML]
        B5 -->|Sí, buscar y agregar| B7[busqueda_propiedades en BD<br/>+ nueva acción de respuesta]
        B7 --> B8[Devuelve: {<br/>  action: add_nodes,<br/>  propiedades: [...],<br/>  mensaje: 'Encontré 3...'<br/>}]
        B8 --> B9[canvas_chat.js detecta action<br/>→ createPropNode para cada una<br/>→ markDirty + captureState<br/>→ muestra confirmación]
        B6 --> B10[canvas_chat.js muestra texto normal]
    end
```

### Protocolo de acción: cómo el backend dice "agrega esto"

Cuando DeepSeek detecte que el usuario quiere **agregar propiedades al canvas**, el backend NO devuelve texto. Devuelve una **estructura JSON de acción** dentro de la respuesta normal:

```json
{
  "success": true,
  "conversation_id": "...",
  "response": "Encontré 3 departamentos en Cayma. Los agregué al lienzo.",
  "action": {
    "type": "add_nodes",
    "nodes": [
      {
        "node_type": "propiedad",
        "source_id": 123,
        "data": {
          "title": "Departamento en Cayma",
          "price": 172900,
          "currency": "USD",
          "district_name": "Cayma",
          "tipo_propiedad": "Departamento",
          "direction": "Av. Ejemplo 123",
          "area_construida": 80,
          "dormitorios": 3,
          "banos": 2
        }
      }
    ],
    "position_strategy": "cascade"
  }
}
```

Si el backend usó el pipeline `busqueda_propiedades → formatear_propiedades`, también puede incluir HTML para mostrar mientras se agregan:

```json
{
  "success": true,
  "response": "Agregué las propiedades al lienzo.",
  "html": "<div class='pf-carousel'>...carrusel de propiedades...</div>",
  "action": {
    "type": "add_nodes",
    "nodes": [...]
  }
}
```

---

## 4. Componentes a Implementar

### A. Backend: Nueva skill virtual `agregar_al_canvas`

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py)

**Cambio en `_orquestar()`:** Detectar intención de agregar al canvas.

Actualmente el método solo verifica `source === 'canvas'`. Se necesita un análisis adicional en el mensaje para detectar frases como:
- "agrega", "añade", "pon", "mételo", "ponlo", "agregar", "añadir"
- "al lienzo", "al canvas", "a mi lienzo", "al tablero"

```python
@classmethod
def _orquestar(cls, ctx: ChatContext) -> OrchestrationDecision:
    canvas_ctx = (ctx.metadata or {}).get('canvas_context', {})
    es_canvas = (ctx.metadata or {}).get('source') == 'canvas'
    mensaje = ctx.message.lower()
    
    # Detectar intención de agregar al canvas
    INTENCION_AGREGAR = ['agrega', 'añade', 'pon', 'mételo', 'ponlo', 
                         'agregar', 'añadir', 'agrega al lienzo']
    quiere_agregar = any(p in mensaje for p in INTENCION_AGREGAR)
    
    if es_canvas and canvas_ctx:
        if quiere_agregar:
            # Buscar en BD y devolver acción
            return OrchestrationDecision(
                skill='busqueda_propiedades',
                params={
                    'semantic_query': ctx.message,
                    'modo_retorno': 'accion_agregar',  # NUEVO: indica que queremos acción
                },
            )
        else:
            # Flujo actual: solo responder con contexto del canvas
            return OrchestrationDecision(
                skill='usar_contexto_canvas',
                params={
                    'canvas_propiedades': props,
                    'canvas_requerimientos': reqs,
                    'semantic_query': ctx.message,
                },
            )
    
    # Flujo normal (no canvas): búsqueda en BD
    return OrchestrationDecision(
        skill='busqueda_propiedades',
        params={'semantic_query': ctx.message},
    )
```

**Cambio en `_ejecutar_skill()`:** Después de ejecutar `busqueda_propiedades`, si `params.get('modo_retorno') == 'accion_agregar'`, estructurar el resultado como acción en lugar de solo HTML.

```python
# Dentro de _ejecutar_skill, después del pipeline busqueda→formatear:
if params.get('modo_retorno') == 'accion_agregar' and skill_result.success:
    propiedades = skill_result.data  # lista de propiedades encontradas
    if propiedades and len(propiedades) > 0:
        # Construir acción
        action_nodes = []
        for prop in propiedades[:10]:  # Máximo 10
            fv = prop.get('field_values', prop)
            action_nodes.append({
                'node_type': 'propiedad',
                'source_id': prop.get('source_id') or fv.get('_source_id'),
                'data': {
                    'title': fv.get('title', ''),
                    'price': fv.get('price'),
                    'currency': fv.get('currency'),
                    'district_name': fv.get('district_name'),
                    'tipo_propiedad': fv.get('property_type_name'),
                    'direction': fv.get('map_address') or fv.get('display_address'),
                    'area_construida': fv.get('area_construida') or fv.get('area'),
                    'dormitorios': fv.get('bedrooms'),
                    'banos': fv.get('bathrooms'),
                }
            })
        
        resultado['action'] = {
            'type': 'add_nodes',
            'nodes': action_nodes,
            'position_strategy': 'cascade',
        }
```

**Cambio en `_generar_respuesta()`:** Si hay `action` en resultados, incluirla en la respuesta final. El mensaje del response_text se genera normalmente por DeepSeek.

La respuesta final se modifica en el view [`chat_web_api`](webapp/intelligence/views.py:1840):

```python
# En chat_web_api, después de process_message:
response_data = {
    'success': True,
    'conversation_id': result.conversation_id,
    'response': response_text,
    'html': html_content,
    'metadata': result.metadata,
}

# Si hay acción, incluirla
if result.metadata.get('action'):
    response_data['action'] = result.metadata['action']
```

---

### B. Frontend: Enriquecer `buildCanvasContext()`

**Archivo:** [`webapp/canvas/static/canvas/js/canvas_chat.js:60`](webapp/canvas/static/canvas/js/canvas_chat.js:60)

Enviar más datos para que DeepSeek pueda entender qué hay en el canvas antes de agregar:

```javascript
function buildCanvasContext() {
  if (typeof STATE === 'undefined' || !STATE.nodos) return {};

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
        tipo_original: n.field_data.tipo_original || '',
        // NUEVO: texto completo del requerimiento
        texto: n.field_data.requerimiento || '',
        presupuesto: n.field_data.presupuesto_monto || n.field_data.presupuesto || '',
        moneda: n.field_data.presupuesto_moneda || n.field_data.moneda || '',
        distritos: n.field_data.distritos || '',
        urbanizacion: n.field_data.urbanizacion || '',
        zona: n.field_data.zona || '',
      });
    }
  });

  // NUEVO: recopilar aristas (matches)
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
```

---

### C. Frontend: Puente Chat → Canvas (nuevo módulo o modificación de `canvas_chat.js`)

**Archivo:** [`webapp/canvas/static/canvas/js/canvas_chat.js`](webapp/canvas/static/canvas/js/canvas_chat.js)

Modificar `sendChatMessage()` para que, después de recibir la respuesta, inspeccione `data.action` y ejecute las acciones:

```javascript
async function sendChatMessage() {
  // ... existing code: validate input, add user message, show loading ...

  try {
    const res = await fetch('/api/v1/intelligence/chat-web/api/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
      body: JSON.stringify({
        message: text,
        conversation_id: canvasChatState.conversationId,
        use_memory: true,
        use_rag: true,
        metadata: {
          source: 'canvas',
          lienzo_id: LIENZO_ID,
          canvas_context: buildCanvasContext(),
        },
      }),
    });

    const data = await res.json();
    removeChatMessage(loadingId);

    // NUEVO: procesar acción si existe
    if (data.action && data.action.type === 'add_nodes') {
      executeAddNodesAction(data.action, data.response);
    } else if (data.success) {
      // Flujo actual: mostrar respuesta como texto
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

/** NUEVO: Ejecuta acción de agregar nodos al canvas */
function executeAddNodesAction(action, mensaje) {
  if (!action.nodes || action.nodes.length === 0) {
    addChatMessage('assistant', mensaje || 'No se encontraron propiedades para agregar.');
    return;
  }

  // Capturar estado para undo antes de agregar
  if (typeof captureState === 'function') captureState();

  const campos = getActiveCampos();
  let addedCount = 0;

  action.nodes.forEach(function(nodeData, index) {
    if (nodeData.node_type === 'propiedad' && nodeData.source_id) {
      // Verificar si ya existe para no duplicar
      const existingId = 'prop_' + nodeData.source_id;
      if (STATE.nodos[existingId]) return; // ya está en el canvas

      // Calcular posición en cascada (misma lógica que sidebar)
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
    const confirmMsg = `✅ Agregué ${addedCount} propiedad${addedCount > 1 ? 'es' : ''} al lienzo. ${mensaje || ''}`;
    addChatMessage('assistant', confirmMsg);
  } else {
    addChatMessage('assistant', mensaje || 'Todas las propiedades ya están en el lienzo.');
  }
}
```

---

### D. Backend: Enriquecer endpoint `api_propiedades` para búsqueda por chat

**Archivo:** [`webapp/canvas/views.py:224`](webapp/canvas/views.py:224)

Actualmente el endpoint solo soporta filtro por `agente_id`. Opcionalmente se puede agregar un parámetro `q` para búsqueda textual que usa la misma lógica híbrida que el skill `busqueda_propiedades`. Esto permitiría al chat hacer consultas rápidas sin pasar por DeepSeek.

```python
def api_propiedades(request):
    # ... existing code ...
    
    # NUEVO: filtro por búsqueda textual
    query = request.GET.get('q')
    if query:
        # Usar RAG o filtro simple por field_values
        from django.db.models import Q
        q_filter = Q()
        for term in query.split():
            q_filter |= Q(field_values__title__icontains=term)
            q_filter |= Q(field_values__direction__icontains=term)
            q_filter |= Q(field_values__district_name__icontains=term)
        qs = qs.filter(q_filter)
    
    # ... rest of existing code ...
```

---

### E. Manejo de errores y edge cases

1. **Máximo de nodos:** Limitar a 10 propiedades por acción para no saturar el canvas.
2. **Detección de duplicados:** Usar `STATE.nodos[existingId]` para no duplicar propiedades ya en el canvas.
3. **Sin resultados:** Si la búsqueda no encuentra propiedades, el action tendrá `nodes: []` y el chat mostrará el mensaje de DeepSeek.
4. **Canvas no cargado:** Si `LIENZO_ID` o `STATE.nodos` no están definidos, la acción se ignora y se muestra solo el texto.
5. **Fallback de posición:** Si no hay viewport, usar posición default (100, 100).
6. **Conservar conversación:** Siempre actualizar `conversation_id` aunque haya acción.
7. **Prioridad de campos:** Usar `getActiveCampos()` que respeta la plantilla de campos seleccionada.

---

## 5. Plan de Implementación (Orden de Ejecución)

### Paso 1: Enriquecer `buildCanvasContext()` (frontend, sin riesgo)
- Modificar [`canvas_chat.js:60`](webapp/canvas/static/canvas/js/canvas_chat.js:60)
- Agregar: texto de requerimientos, matches, direcciones
- **No rompe nada** — solo agrega más datos al metadata

### Paso 2: Crear `executeAddNodesAction()` en frontend
- Agregar función en [`canvas_chat.js`](webapp/canvas/static/canvas/js/canvas_chat.js)
- Modificar `sendChatMessage()` para detectar `data.action`
- **No rompe nada** — si no hay action, funciona igual que antes

### Paso 3: Modificar backend `chat_processor.py` — detección de intención
- Modificar `_orquestar()` para detectar frases como "agrega al lienzo"
- **No rompe nada** — solo agrega una rama condicional

### Paso 4: Modificar backend `chat_processor.py` — acción en resultados
- Modificar `_ejecutar_skill()` para construir estructura `action` cuando `modo_retorno == 'accion_agregar'`
- **No rompe nada** — solo agrega un campo `action` al resultado

### Paso 5: Modificar `chat_web_api` view — incluir action en response
- Modificar [`intelligence/views.py:1840`](webapp/intelligence/views.py:1840) para propagar `action` a la respuesta JSON
- **No rompe nada** — campo extra que los clientes existentes ignoran

### Paso 6 (Opcional): Búsqueda textual en `api_propiedades`
- Agregar parámetro `q` en [`canvas/views.py:224`](webapp/canvas/views.py:224)
- Útil para consultas rápidas sin pasar por DeepSeek

---

## 6. Matriz de Riesgos

| Cambio | Riesgo | Mitigación |
|---|---|---|
| `buildCanvasContext()` enriquecido | Bajo — solo agrega campos al JSON | No afecta parsing del backend |
| `executeAddNodesAction()` | Medio — nuevo código en frontend | No interfiere con flujo existente (solo se ejecuta si hay `data.action`) |
| `_orquestar()` detección de intención | Bajo — rama condicional nueva | Fallback: si detecta mal, solo devuelve texto como siempre |
| `_ejecutar_skill()` con action | Medio — modifica respuesta | Solo afecta cuando `modo_retorno='accion_agregar'` |
| `chat_web_api` view | Bajo — campo extra en JSON | Clientes existentes ignoran campos desconocidos |

---

## 7. Pruebas de Regresión

Después de implementar, verificar que lo siguiente SIGA funcionando:

1. **Chat conversacional normal:** "¿qué propiedades hay en Cayma?" → texto/HTML
2. **Sidebar checkbox:** seleccionar/deseleccionar propiedades desde la lista
3. **Drag & drop:** arrastrar chip al canvas
4. **Autoguardado:** mover nodos → markDirty → save a los 2s
5. **Undo/Redo:** Ctrl+Z después de agregar/eliminar nodos
6. **Snapshot:** recargar página → propiedades persistidas correctamente
7. **Chat desde fuera del canvas:** el chat general no debe verse afectado
