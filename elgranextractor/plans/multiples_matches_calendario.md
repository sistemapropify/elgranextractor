# Plan: Múltiples Matches en Calendario

---

## 1. Problema

Actualmente en el calendario de matching:
- Las tarjetas solo muestran **1 match** (el mejor porcentaje)
- El modal solo compara **1 propiedad** (la mejor)
- El botón WhatsApp solo envía **1 propiedad** (la mejor)

Si un requerimiento tiene 3 propiedades compatibles, solo se ve la #1.

---

## 2. Análisis del Código Actual

### `_obtener_resumen_calendario()` (views.py:562)
```python
# LÍNEA 598-600 — Solo guarda el PRIMER match por req_id
mejores_por_req = {}
for m in mejores:
    if m.requerimiento_id not in mejores_por_req:
        mejores_por_req[m.requerimiento_id] = m
```
Devuelve un dict por req_id con UNA sola propiedad. Se pierden los matches #2, #3, etc.

### Week view (views.py:823-842)
Serializa `porcentaje_match` y `mejor_propiedad_*` como campos sueltos. No hay una lista de matches.

### Modal (calendar.html:2075-2210)
La API `ejecutar` YA devuelve todos los resultados, pero el modal solo usa `resultados[0]`:
```javascript
const topResult = resultados[0];    // solo el primero
const prop = topResult.propiedad || {};
```

### WhatsApp (calendar.html:1843-1993)
`ultimaPropiedadTop = resultados[0].propiedad` — solo la primera propiedad.

---

## 3. Cambios Necesarios

### 3.1 Backend: Modificar `_obtener_resumen_calendario`

**Archivo:** `webapp/matching/views.py`

Cambiar para que retorne TODOS los matches por requerimiento, no solo el mejor:

```python
def _obtener_multiples_matches_calendario(limite=500, umbral_minimo=60.0):
    """
    Retorna hasta 3 MatchResult por requerimiento con score >= 60%.
    Ordenados por score descendente.
    """
    resultados = MatchResult.objects.filter(
        fase_eliminada__isnull=True,
        score_total__gte=umbral_minimo
    ).order_by('requerimiento_id', '-score_total')

    # Agrupar y limitar a 3 por req en Python
    resumen = []
    count_por_req = {}
    for m in resultados:
        rid = m.requerimiento_id
        if count_por_req.get(rid, 0) >= 3:
            continue
        count_por_req[rid] = count_por_req.get(rid, 0) + 1
        # ... append ...
    
    return resumen[:limite]

    resumen = []
    for m in resultados:
        resumen.append({
            'requerimiento_id': m.requerimiento_id,
            'porcentaje_match': float(m.score_total),
            'propiedad_id': m.propiedad_id,
            'propiedad_codigo': m.propiedad_code,
            'propiedad_titulo': m.propiedad_title,
            'propiedad_precio': float(m.propiedad_price) if m.propiedad_price else None,
            'propiedad_moneda_id': m.propiedad_currency_id,
            'propiedad_distrito': m.propiedad_district_id,
        })
    return resumen
```

### 3.2 Week/Day view: Incluir matches múltiples

**Archivo:** `webapp/matching/views.py`

En la serialización de req para semana/día, agregar `matches_list`:

```python
# En lugar de info.get('porcentaje_match', 0) etc:
matches_del_req = [m for m in resumen if m['requerimiento_id'] == r.id]
mejor_match = matches_del_req[0] if matches_del_req else {}

req_data = {
    # ... campos existentes ...
    'porcentaje_match': mejor_match.get('porcentaje_match', 0) if matches_del_req else 0,
    'mejor_propiedad_codigo': mejor_match.get('propiedad_codigo'),
    'mejor_propiedad_precio': mejor_match.get('propiedad_precio'),
    'mejor_propiedad_moneda_id': mejor_match.get('propiedad_moneda_id'),
    # NUEVO: lista completa de matches
    'matches': matches_del_req,  # lista de dicts
}
```

### 3.3 Card rendering: Múltiples badges

**Archivo:** `webapp/matching/templates/matching/calendar.html`

En el render de `week-req-item` (línea ~1597), reemplazar el badge único por múltiples badges:

```javascript
// ANTES (un solo badge):
`<span class="match-badge ${badgeClass}">${badgeText}</span>`

// DESPUÉS (múltiples badges verticales):
var badgesHtml = '';
req.matches.forEach(function(m, idx) {
    var cls = getMatchBadgeClass(m.porcentaje_match);
    var txt = getMatchBadgeText(m.porcentaje_match);
    badgesHtml += `<span class="match-badge ${cls}" style="display:block;margin-bottom:1px;">${txt}</span>`;
});
// En el HTML:
`<span class="req-matches" style="display:flex;flex-direction:column;gap:1px;flex-shrink:0;">${badgesHtml}</span>`
```

### 3.4 Modal: Mostrar TODOS los matches con botones individuales

**Archivo:** `webapp/matching/templates/matching/calendar.html`

Reemplazar el panel lateral del modal (que muestra 1 propiedad) por una **lista de propiedades** con sus propios botones:

```javascript
// En renderMatchModal, en lugar de usar solo resultados[0]:
var propiedadesHtml = '';
resultados.forEach(function(r, idx) {
    var prop = r.propiedad || {};
    var score = parseFloat(r.score_total || 0);
    var scoreClass = score >= 90 ? 'high' : (score >= 50 ? 'medium' : 'low');
    
    propiedadesHtml += `
        <div class="modal-prop-card" style="border:1px solid var(--border-color);border-radius:8px;padding:10px;margin-bottom:8px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="font-weight:600;color:var(--accent-blue);font-size:12px;">#${idx+1}</span>
                <span class="score-num ${scoreClass}" style="font-size:18px;">${Math.round(score)}%</span>
            </div>
            <div style="font-size:12px;font-weight:500;">${prop.title || '—'}</div>
            <div style="font-size:11px;color:var(--text-secondary);">${prop.code || ''} · ${getDistritoName(prop.district)}</div>
            <div style="font-size:13px;font-weight:600;color:var(--accent-green);margin:4px 0;">${formatPrice(prop.price, prop.currency_id)}</div>
            <button onclick="enviarPropuestaWhatsAppPropiedad(${idx})" class="btn-whatsapp" style="width:100%;font-size:12px;padding:6px;">
                📤 Enviar propuesta
            </button>
        </div>
    `;
});
```

La tabla comparativa (Req vs Prop #1) se mantiene, pero ahora el panel lateral muestra todas las propiedades.

### 3.5 WhatsApp: Función para enviar propiedad específica

**Archivo:** `webapp/matching/templates/matching/calendar.html`

Crear `enviarPropuestaWhatsAppPropiedad(index)` que seleccione `resultados[index].propiedad`:

```javascript
function enviarPropuestaWhatsAppPropiedad(index) {
    // Obtener resultados del modal actual
    var resultados = ultimosResultadosModal;  // variable global nueva
    if (!resultados || !resultados[index]) return;
    
    ultimaPropiedadTop = resultados[index].propiedad;
    enviarPropuestaWhatsApp();
}
```

---

## 4. Resumen de Archivos a Modificar

| Archivo | Cambios |
|---------|---------|
| `webapp/matching/views.py` | `_obtener_resumen_calendario()` → retorna todos los matches |
| `webapp/matching/views.py` | Week/day view: serializar `matches` list en req_data |
| `webapp/matching/templates/matching/calendar.html` | Week card: badges múltiples verticales |
| `webapp/matching/templates/matching/calendar.html` | Modal: renderizar lista de propiedades en vez de 1 |
| `webapp/matching/templates/matching/calendar.html` | Modal: botones WhatsApp individuales |
| `webapp/matching/templates/matching/calendar.html` | Nueva función `enviarPropuestaWhatsAppPropiedad(index)` |

---

## 5. Flujo Actualizado

```mermaid
graph TD
    A[CalendarView carga reqs de semana] --> B[_obtener_multiples_matches_calendario]
    B --> C[Retorna TODOS los MatchResult > 70%]
    C --> D[Agrupa por req_id en Python]
    D --> E[Serializa req con lista matches]
    E --> F[Render week view: badges múltiples]
    F --> G[Usuario ve N badges por req]
    G --> H[Click en tarjeta abre modal]
    H --> I[API ejecutar matching]
    I --> J[Misma API, ya retorna todos]
    J --> K[Modal renderiza LISTA de propiedades]
    K --> L[Usuario elige y click en Enviar]
    L --> M[enviarPropuestaWhatsAppPropiedad(idx)]
    M --> N[Selecciona propiedad específica]
    N --> O[Abre WhatsApp con esa propiedad]
```

---

## 6. Notas Técnicas

1. **API no cambia** — `MatchingViewSet.ejecutar` ya retorna todos los resultados. Solo cambia el frontend.
2. **`_obtener_resumen_calendario`** se modifica para no dedup por req_id. El mes view contará reqs con match > 0, que seguirá funcionando.
3. **Sin migraciones** — No se toca el modelo.
4. **La tabla comparativa** del modal se mantiene (Req vs Prop #1), pero se agrega la lista de propiedades debajo.
