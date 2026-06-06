# Plan: Pipeline de Vida del Requerimiento en el Calendario de Matching

## Objetivo

Agregar una visualización tipo **pipeline/timeline HORIZONTAL** en el calendario de matching que muestre las 4 etapas del ciclo de vida de un requerimiento en una sola fila:

1. **📝 Requerimiento** — Fecha de creación del requerimiento
2. **🎯 Match** — Fecha del primer matching ejecutado
3. **📤 Propuesta** — Fecha en que se envió la propuesta por WhatsApp
4. **✅ Aceptado / ❌ Rechazado** — Decisión final del cliente

Entre cada etapa, mostrar el **⏱️ lapso de tiempo transcurrido** (días y horas). El pipeline debe ser **horizontal** para ocupar poco espacio dentro del modal.

---

## Arquitectura de Datos

### Fuentes de datos existentes en el modelo actual

| Etapa | Modelo | Campo Fecha | ¿Existe? |
|-------|--------|-------------|----------|
| 1. Requerimiento | [`Requerimiento`](webapp/requerimientos/models.py:73) | `fecha` (DateField) + `hora` (TimeField) o `creado_en` (DateTimeField) | ✅ |
| 2. Match | [`MatchResult`](webapp/matching/models.py:52) | `ejecutado_en` (DateTimeField, auto_now_add) | ✅ |
| 3. Propuesta | [`PropuestaWhatsApp`](webapp/matching/models.py:6) | `enviado_en` (DateTimeField, auto_now_add) | ✅ |
| 4. Aceptado/Rechazado | [`PropuestaWhatsApp`](webapp/matching/models.py:6) | `respondido_en` (DateTimeField, nullable) + `status` | ✅ |

### Relaciones entre modelos

```
Requerimiento (1) ────→ MatchResult (muchos)
                    └──→ PropuestaWhatsApp (muchos)
```

- Un `Requerimiento` puede tener múltiples `MatchResult` (se ejecuta varias veces)
- Un `Requerimiento` puede tener múltiples `PropuestaWhatsApp` (se envían a diferentes propiedades)
- Para el pipeline tomamos el **primer MatchResult** y la **primera PropuestaWhatsApp**

---

## Plan de Implementación

### Paso 1: Nueva función de servicio `pipeline_requerimiento.py`

**Archivo nuevo:** [`webapp/matching/pipeline_requerimiento.py`](webapp/matching/)

Crear función `obtener_pipeline_requerimiento(requerimiento_id)` que:

1. Recibe un `requerimiento_id`
2. Consulta el `Requerimiento` y obtiene `fecha` + `hora` (o `creado_en`)
3. Obtiene el `MatchResult` más antiguo (`ejecutado_en` mínimo) para ese requerimiento
4. Obtiene la `PropuestaWhatsApp` más antigua (`enviado_en` mínimo) para ese requerimiento
5. Si existe propuesta, obtiene `respondido_en` y `status` de la más reciente con respuesta
6. Calcula los **deltas** (diferencia en días+horas) entre cada par de etapas consecutivas
7. Retorna un dict estructurado:

```python
{
    'requerimiento_id': int,
    'etapas': {
        'requerimiento': {
            'fecha': datetime,
            'display': '15/05/2026 14:30',
            'estado': 'ok',
        },
        'match': {
            'fecha': datetime or None,
            'display': '16/05/2026 10:15' or '—',
            'lapso_desde_anterior': {'dias': 0, 'horas': 19, 'minutos': 45, 'display': '19h 45m'},
            'estado': 'ok' | 'pendiente' | 'no_aplica',
        },
        'propuesta': {
            'fecha': datetime or None,
            'display': '18/05/2026 09:00' or '—',
            'lapso_desde_anterior': {'dias': 1, 'horas': 22, 'minutos': 45, 'display': '1d 22h 45m'},
            'estado': 'ok' | 'pendiente' | 'no_aplica',
            'status_propuesta': 'enviada' | 'interesado' | 'rechazado' | None,
        },
        'decision': {
            'fecha': datetime or None,
            'display': '20/05/2026 11:30' or '—',
            'lapso_desde_anterior': {'dias': 2, 'horas': 2, 'minutos': 30, 'display': '2d 2h 30m'},
            'estado': 'aceptado' | 'rechazado' | 'pendiente' | 'no_aplica',
        },
    },
    'lapso_total': {'dias': 5, 'horas': 21, 'display': '5d 21h'},
    'stats_match': {
        'total_ejecuciones': int,
        'total_propuestas_enviadas': int,
        'mejor_score': float,
    }
}
```

### Paso 2: Nueva API endpoint para pipeline

**Archivo:** [`webapp/matching/views.py`](webapp/matching/views.py)

Agregar en `MatchingViewSet`:

```python
@action(detail=True, methods=['GET'])
def pipeline(self, request, pk=None):
    """
    GET /api/matching/{requerimiento_id}/pipeline/
    Retorna el pipeline de vida del requerimiento con lapsos.
    """
    requerimiento = get_object_or_404(Requerimiento, pk=pk)
    data = obtener_pipeline_requerimiento(requerimiento.id)
    return Response(data)
```

**Archivo:** [`webapp/matching/urls.py`](webapp/matching/urls.py)

Agregar ruta:

```python
path('api/matching/<int:pk>/pipeline/', 
     views.MatchingViewSet.as_view({'get': 'pipeline'}), 
     name='matching-pipeline'),
```

### Paso 3: Agregar pestaña "Pipeline" en el modal de matching

**Archivo:** [`webapp/matching/templates/matching/calendar.html`](webapp/matching/templates/matching/calendar.html)

Modificar el modal existente (líneas ~1442-1460) para agregar **tabs**:

```
┌──────────────────────────────────────────────┐
│ MATCH #123 — Mejor 85% (3 props)             │
│ [🏠 Matches] [📊 Pipeline]                   │
├──────────────────────────────────────────────┤
│  (contenido de la pestaña activa)            │
└──────────────────────────────────────────────┘
```

#### Estructura HTML del pipeline (HORIZONTAL):

```html
<div class="pipeline-timeline-horizontal">
  <!-- Etapa 1: Requerimiento -->
  <div class="pipeline-node completed">
    <div class="pipeline-marker">📝</div>
    <div class="pipeline-content">
      <div class="pipeline-title">Requerimiento</div>
      <div class="pipeline-date">15/05 14:30</div>
    </div>
  </div>

  <!-- Conector con lapso -->
  <div class="pipeline-connector">
    <div class="connector-line"></div>
    <span class="lapso-badge">19h 45m</span>
  </div>

  <!-- Etapa 2: Match -->
  <div class="pipeline-node completed">
    <div class="pipeline-marker">🎯</div>
    <div class="pipeline-content">
      <div class="pipeline-title">Match</div>
      <div class="pipeline-date">16/05 10:15</div>
      <div class="pipeline-score">85%</div>
    </div>
  </div>

  <!-- Conector con lapso -->
  <div class="pipeline-connector">
    <div class="connector-line"></div>
    <span class="lapso-badge">1d 22h</span>
  </div>

  <!-- Etapa 3: Propuesta -->
  <div class="pipeline-node completed">
    <div class="pipeline-marker">📤</div>
    <div class="pipeline-content">
      <div class="pipeline-title">Propuesta</div>
      <div class="pipeline-date">18/05 09:00</div>
      <div class="pipeline-prop-status">⏳ Pendiente</div>
    </div>
  </div>

  <!-- Conector con lapso -->
  <div class="pipeline-connector">
    <div class="connector-line"></div>
    <span class="lapso-badge">2d 2h</span>
  </div>

  <!-- Etapa 4: Decisión -->
  <div class="pipeline-node pending">
    <div class="pipeline-marker">⏳</div>
    <div class="pipeline-content">
      <div class="pipeline-title">Decisión</div>
      <div class="pipeline-date">—</div>
      <div class="pipeline-status-tag">Esperando...</div>
    </div>
  </div>
</div>
```

#### Estados visuales de cada nodo:

| Estado | Clase CSS | Descripción |
|--------|-----------|-------------|
| ✅ Completado | `.completed` | Etapa alcanzada con fecha |
| ⏳ Pendiente | `.pending` | Etapa no alcanzada aún, pero factible |
| ➖ No aplica | `.na` | Etapa que nunca ocurrirá (ej: decisión si no hay propuesta) |

#### CSS para el timeline HORIZONTAL (dark theme existente):

```css
.pipeline-timeline-horizontal {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 0;
    padding: 16px 8px;
    width: 100%;
    overflow-x: auto;
}
.pipeline-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 8px 12px;
    min-width: 100px;
    text-align: center;
    flex-shrink: 0;
}
.pipeline-node.completed {
    border-color: var(--accent-green);
    box-shadow: 0 0 8px rgba(63, 185, 80, 0.15);
}
.pipeline-node.pending {
    border-color: var(--accent-orange);
    opacity: 0.75;
}
.pipeline-node.na {
    border-color: var(--text-muted);
    opacity: 0.5;
}
.pipeline-marker {
    font-size: 20px;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--bg-secondary);
    border: 2px solid var(--border-color);
    flex-shrink: 0;
    margin-bottom: 2px;
}
.pipeline-node.completed .pipeline-marker {
    border-color: var(--accent-green);
}
.pipeline-title {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
}
.pipeline-node.completed .pipeline-title {
    color: var(--accent-green);
}
.pipeline-date {
    font-size: 11px;
    color: var(--text-primary);
    font-weight: 500;
}
.pipeline-score {
    font-size: 10px;
    color: var(--accent-blue);
    font-weight: 600;
}
.pipeline-prop-status {
    font-size: 9px;
    color: var(--accent-orange);
}
.pipeline-status-tag {
    font-size: 9px;
    color: var(--text-muted);
    font-style: italic;
}
.pipeline-connector {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    min-width: 50px;
    flex-shrink: 0;
    position: relative;
}
.connector-line {
    width: 100%;
    height: 2px;
    background: var(--border-color);
    position: relative;
}
.pipeline-node.completed + .pipeline-connector .connector-line {
    background: var(--accent-green);
    opacity: 0.5;
}
.lapso-badge {
    background: var(--bg-secondary);
    border: 1px solid var(--accent-blue);
    color: var(--accent-blue);
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
    white-space: nowrap;
}
```

### Paso 4: Agregar vista de pipeline en el modal (JavaScript)

**Archivo:** [`webapp/matching/templates/matching/calendar.html`](webapp/matching/templates/matching/calendar.html)

Modificar `renderMatchModal()` para:

1. Después de cargar los resultados de matching (`fetch` a `/api/matching/{id}/guardados/`), también hacer fetch a `/api/matching/{id}/pipeline/`
2. Agregar tabs en el header del modal: "🏠 Matches" (default) y "📊 Pipeline"
3. Al hacer click en "📊 Pipeline", mostrar la visualización del pipeline
4. Al hacer click en "🏠 Matches", mostrar las propiedades compatibles (vista actual)

### Paso 5: Pipeline Dashboard (vista agregada opcional)

**Opcional pero recomendado:** Nueva vista `/matching/pipeline/` que muestre:

- **Resumen general**: Cuántos requerimientos han llegado a cada etapa
- **Cuellos de botella**: Promedio de tiempo entre cada etapa
- **Tasa de conversión**: Requerimiento → Match → Propuesta → Aceptado
- **Distribución de tiempos**: Histograma de lapsos entre etapas

---

## Diagrama de Flujo

```mermaid
graph TD
    A[Usuario navega al calendario] --> B[Hace clic en tarjeta de requerimiento]
    B --> C[Modal existente: Match Results]
    C --> D[Modal ahora tiene tabs: Matches | Pipeline]
    D --> E{Usuario selecciona pestaña}
    E -->|Matches| F[Muestra propiedades compatibles - existente]
    E -->|Pipeline| G[Fetch GET /api/matching/id/pipeline/]
    G --> H[JSON con etapas y lapsos]
    H --> I[Renderiza timeline visual]
    
    I --> J{Nodos del pipeline}
    J --> K[📝 Requerimiento - siempre visible]
    J --> L[🎯 Match - si existe MatchResult]
    J --> M[📤 Propuesta - si existe PropuestaWhatsApp]
    J --> N[✅ Decisión - si respondido_en no es null]
    
    K --> O[Lapso: Requerimiento → Match]
    L --> P[Lapso: Match → Propuesta]
    M --> Q[Lapso: Propuesta → Decisión]
```

---

## Archivos a Modificar/Crear

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| [`webapp/matching/pipeline_requerimiento.py`](webapp/matching/) | **CREAR** | Función `obtener_pipeline_requerimiento()` + helpers de cálculo de lapsos |
| [`webapp/matching/views.py`](webapp/matching/views.py:46) | Modificar | Agregar action `pipeline` en `MatchingViewSet` |
| [`webapp/matching/urls.py`](webapp/matching/urls.py:17) | Modificar | Agregar ruta `/api/matching/<pk>/pipeline/` |
| [`webapp/matching/templates/matching/calendar.html`](webapp/matching/templates/matching/calendar.html:1442) | Modificar | Agregar tabs en modal + contenido pipeline + CSS |
| [`webapp/matching/templates/matching/calendar.html`](webapp/matching/templates/matching/calendar.html:2176) | Modificar | Modificar `renderMatchModal()` para soportar tabs y fetch de pipeline |

---

## Notas Técnicas

1. **Cálculo de lapsos**: Usar `django.utils.timezone` para manejar timezone-aware datetimes. Mostrar en formato humano: "X días, Y horas" si es >24h, "X horas, Y minutos" si es <24h, "X minutos" si es <1h.

2. **PropuestaWhatsApp no tiene migración** (solo está en `models.py`). Si la tabla no existe en BD, podría fallar la consulta. Usar `try/except` o verificar existencia de tabla antes de consultar.

3. **MatchResult puede tener múltiples ejecuciones** para el mismo requerimiento. Tomar el `ejecutado_en` mínimo como primer match.

4. **PropuestaWhatsApp puede tener múltiples envíos** para el mismo requerimiento (distintas propiedades). Tomar el `enviado_en` mínimo como primera propuesta. Para la decisión, tomar la última propuesta que tenga `respondido_en` no nulo.

5. **EL requerimiento puede que no tenga match, propuesta o decisión.** El pipeline debe mostrar las etapas como "Pendiente" o "No aplica" según corresponda.

6. **Dark theme**: Mantener consistencia visual con el resto del calendario (`#0d1117` background, `#e6edf3` texto).

---

## Mockup Visual HORIZONTAL

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  📝 Requerimiento #123             15/05/2026                                   │
│  [🏠 Matches] [📊 Pipeline]                                                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────┐   ⏱️19h45m  ┌──────────┐   ⏱️1d22h  ┌──────────┐  ⏱️2d2h  ┌──────────┐ │
│  │  📝      │ ─────────→ │  🎯      │ ────────→ │  📤      │ ──────→ │  ⏳      │ │
│  │Requerim. │            │  Match   │           │Propuesta │         │Decisión  │ │
│  │15/05 14:30│           │16/05 10:15│          │18/05 09:00│        │   —     │ │
│  │          │            │  85%     │           │⏳Pendiente│         │Esperando │ │
│  └──────────┘            └──────────┘           └──────────┘         └──────────┘ │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```
