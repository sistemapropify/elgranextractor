# Plan: Match Badge Circular + Modal Comparativo

## Resumen

Reemplazar el label de texto "XX%" en las aristas match del canvas con un badge circular animado (borde amarillo fosforescente parpadeante) que muestre el score y la fecha del cálculo. Al hacer clic, abrir un modal comparativo propiedad vs requerimiento con ✓/✗ en los 10 campos del matching.

## Archivos a modificar/crear

### 1. Backend: Nueva API `/canvas/api/match-detail/<match_id>/`

**Archivo:** [`webapp/canvas/views.py`](webapp/canvas/views.py)

Nuevo endpoint `api_match_detail` que recibe un `match_id` (ID de `MatchResult`) y retorna:

```json
{
  "match_id": 123,
  "score_total": 85.5,
  "ejecutado_en": "2026-06-26T14:30:00",
  "fase_eliminada": null,
  "campos": [
    {
      "nombre": "condicion",
      "label": "Condición",
      "propiedad": "Venta",
      "requerimiento": "Compra",
      "compatible": true,
      "ponderacion": 15
    },
    {
      "nombre": "tipo_propiedad",
      "label": "Tipo Propiedad",
      "propiedad": "Departamento",
      "requerimiento": "Departamento",
      "compatible": true,
      "ponderacion": 15
    },
    // ... 8 campos más
  ]
}
```

Los campos ordenados por peso/importancia (basado en PESOS de scoring + filtros duros eliminatorios):

| # | Campo | Label | Peso | Propiedad src | Requerimiento src |
|---|-------|-------|------|--------------|-------------------|
| 1 | precio | Presupuesto | 20pts | price | presupuesto_monto |
| 2 | distrito | Distrito | 15pts | district_name | distritos |
| 3 | habitaciones | Habitaciones | 15pts | bedrooms | habitaciones |
| 4 | semantico | Coincidencia | 15pts | description/title | requerimiento |
| 5 | condicion | Condición | 🔴 Filtro | operation_type_name | condicion |
| 6 | tipo_propiedad | Tipo Propiedad | 🔴 Filtro | property_type_name | tipo_propiedad |
| 7 | banos | Baños | 10pts | bathrooms | banos |
| 8 | area | Área m² | 10pts | built_area | area_m2 |
| 9 | amenities | Ascensor+Cochera | 10pts | has_elevator, garage_spaces | ascensor, cochera |
| 10 | antiguedad | Antigüedad | 5pts | year_built / antigüedad | antiguedad_max |
| 11 | forma_pago | Forma Pago | 🔴 Filtro | forma_pago | forma_pago |

**Endpoint adicional REQ:** El endpoint debe también obtener los datos del `Requerimiento` asociado al match para extraer los campos requeridos del requerimiento.

### 2. Frontend: Edge label → Badge circular

**Archivo:** [`webapp/canvas/static/canvas/js/canvas_edges.js`](webapp/canvas/static/canvas/js/canvas_edges.js)

Modificar `updateEdges()`:
- Donde se crea el `<text>` label, reemplazar con un `<g>` (grupo SVG) que contenga:
  - Círculo de fondo (radio ~16px, relleno oscuro)
  - Círculo de borde amarillo `#ffdd00` con animación de parpadeo (stroke-dasharray + CSS animation)
  - Texto del score dentro del círculo
  - Texto de fecha debajo (opcional, tamaño 8px)
- Hacer el `<g>` clickeable con `cursor: pointer`

**Nuevo CSS en:** [`webapp/canvas/static/canvas/css/canvas.css`](webapp/canvas/static/canvas/css/canvas.css)

```css
@keyframes cv-badge-pulse {
  0%, 100% { opacity: 1; stroke-opacity: 0.8; }
  50% { opacity: 0.4; stroke-opacity: 0.3; }
}
.cv-edge__badge-circle {
  fill: #1a1c24;
  stroke: #ffdd00;
  stroke-width: 2.5;
  animation: cv-badge-pulse 1.5s ease-in-out infinite;
  cursor: pointer;
}
.cv-edge__badge-text {
  fill: #ffdd00;
  font-size: 11px;
  font-weight: 700;
  text-anchor: middle;
  dominant-baseline: central;
  cursor: pointer;
}
.cv-edge__badge-date {
  fill: #8b90a7;
  font-size: 7px;
  text-anchor: middle;
}
```

### 3. Frontend: Modal comparativo

**Nuevo archivo (o añadir en HTML existente):** El modal en el HTML template

**Archivo template:** Buscar el HTML del canvas para agregar el modal

O crear inline via JS en un nuevo archivo:

**Nuevo archivo:** [`webapp/canvas/static/canvas/js/canvas_match_modal.js`](webapp/canvas/static/canvas/js/canvas_match_modal.js)

Contenido:
- Función `showMatchModal(matchId, propX, propY)`:
  1. Fetch `/canvas/api/match-detail/{matchId}/`
  2. Renderizar modal flotante con:
     - Header: "Comparación Match - XX%" + score badge + botón cerrar
     - Tabla/Grid de 3 columnas: Propiedad | Requerimiento | Compatible
     - Cada fila: campo específico
     - Compatible: ✓ verde o ✗ rojo
     - Footer: botón "Cerrar"

**Estructura del modal:**

```
┌────────────────────────────────────────────┐
│  🎯 Match: 85%  [2026-06-26 14:30]    [✕] │
├──────────────┬──────────────────┬──────────┤
│  PROPIEDAD   │  REQUERIMIENTO   │  ✓/✗    │
├──────────────┼──────────────────┼──────────┤
│ Condición    │ Condición        │          │
│  Venta       │  Compra          │    ✓     │
├──────────────┼──────────────────┼──────────┤
│ Tipo Prop.   │ Tipo Prop.       │          │
│  Depto.      │  Depto.          │    ✓     │
├──────────────┼──────────────────┼──────────┤
│ ...          │ ...              │  ...     │
└──────────────┴──────────────────┴──────────┘
```

### 4. Frontend: Click handler en badge

**Archivo:** [`webapp/canvas/static/canvas/js/canvas_edges.js`](webapp/canvas/static/canvas/js/canvas_edges.js)

En `updateEdges()`, al crear el badge circular, agregar:
```javascript
badgeGroup.addEventListener('click', () => {
  // Buscar match_id desde el edge
  showMatchModal(matchId, midX, midY);
});
```

### 5. Conexión: Almacenar match_id en edge data

**Archivo:** [`webapp/canvas/static/canvas/js/canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js)

En `loadMatchesForProp()`, al crear el edge, almacenar el match_id real:
```javascript
STATE.aristas[edgeId] = {
  id: edgeId,
  origen: nodeId,
  destino: reqNodeId,
  tipo: 'match',
  match_id: req.match_id, // ← NUEVO: ID del MatchResult
  label: (req.score_estructural || 0) + '%',
  ejecutado_en: req.ejecutado_en || null,
};
```

**Backend:** En `api_reqs_match()` de [`canvas/views.py`](webapp/canvas/views.py), añadir `match_id` al response de cada match, obtenido del `mr.id`.

## Orden de implementación

1. Backend: Añadir `match_id` y `ejecutado_en` a `api_reqs_match` response
2. Backend: Nueva API `api_match_detail` con datos comparativos
3. Frontend: Almacenar match_id en edge data en `canvas_nodes.js`
4. Frontend: Reemplazar label SVG por badge circular en `canvas_edges.js`
5. CSS: Animación de parpadeo y estilos del badge
6. Frontend: Modal comparativo (HTML + JS)
7. Probar: Flujo completo matches → badge → click → modal
