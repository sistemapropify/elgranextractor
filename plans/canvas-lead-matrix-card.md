# Plan: Lead Matrix Card for Canvas

## Overview
Add a new card type "Matriz de Leads" to the Canvas that displays a **pivot table/matrix** where:
- **Columns**: Dates (lead creation dates, sorted ascending)
- **Rows**: Properties that have leads (property title/code + district)
- **Cells**: Count of leads per property per date

Accessible via: **Right-click on canvas background → "📊 Matriz de Leads"**

---

## Architecture

### Data Flow
```
[Azure SQL: lead + lead_properties + property]
        ↓
[Backend: api_lead_matrix endpoint]
        ↓  JSON response
[Frontend: createLeadMatrixNode]
        ↓
[D3.js heatmap grid OR plain HTML table]
```

### API Response Format
```json
{
  "properties": [
    {
      "property_id": 123,
      "title": "Departamento en Cayma",
      "code": "PROP-001",
      "district_name": "Cayma",
      "daily_counts": {
        "2026-07-01": 3,
        "2026-07-02": 1,
        "2026-07-05": 2
      },
      "total": 6
    }
  ],
  "dates": ["2026-07-01", "2026-07-02", "2026-07-05"],
  "total_properties": 15,
  "total_leads": 45
}
```

---

## Implementation Steps

### Step 1: Backend — API Endpoint [`canvas/views.py`](webapp/canvas/views.py)

Add a new view `api_lead_matrix` at line ~1396 (after existing lead analysis views):

```python
def api_lead_matrix(request):
    """
    GET /canvas/api/lead-matrix/
    Retorna matriz de leads: filas = propiedades, columnas = fechas, celdas = conteo.
    """
    user = _get_current_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    try:
        from django.db import connections
        
        # 1. Obtener todas las propiedades que tienen leads, con sus datos
        with connections['propifai'].cursor() as cursor:
            cursor.execute("""
                SELECT 
                    p.id, p.code, p.title, p.district_name,
                    CAST(SWITCHOFFSET(l.created_at, '-05:00') AS DATE) AS lead_date,
                    COUNT(DISTINCT l.id) AS lead_count
                FROM lead l
                INNER JOIN lead_properties lp ON lp.lead_id = l.id
                INNER JOIN property p ON p.id = lp.property_id
                GROUP BY 
                    p.id, p.code, p.title, p.district_name,
                    CAST(SWITCHOFFSET(l.created_at, '-05:00') AS DATE)
                ORDER BY p.title, lead_date
            """)
            
            # Build matrix
            from collections import OrderedDict
            props_map = OrderedDict()  # property_id -> {data, daily_counts: {date: count}}
            dates_set = set()
            
            for row in cursor.fetchall():
                prop_id, code, title, district, lead_date, count = row
                date_str = lead_date.isoformat() if hasattr(lead_date, 'isoformat') else str(lead_date)
                
                if prop_id not in props_map:
                    props_map[prop_id] = {
                        'property_id': prop_id,
                        'code': code or '',
                        'title': title or f'Prop #{prop_id}',
                        'district_name': district or '',
                        'daily_counts': {},
                        'total': 0,
                    }
                props_map[prop_id]['daily_counts'][date_str] = count
                props_map[prop_id]['total'] += count
                dates_set.add(date_str)
        
        dates = sorted(dates_set)
        properties = list(props_map.values())
        total_leads = sum(p['total'] for p in properties)
        
        return JsonResponse({
            'properties': properties,
            'dates': dates,
            'total_properties': len(properties),
            'total_leads': total_leads,
        })
    except Exception as e:
        logger.warning(f"Error en lead matrix: {e}")
        return JsonResponse({'error': str(e)}, status=500)
```

### Step 2: Backend — URL Route [`canvas/urls.py`](webapp/canvas/urls.py)

Add route at line ~32:
```python
path('api/lead-matrix/', views.api_lead_matrix, name='api_lead_matrix'),
```

### Step 3: Frontend — New Node Creation [`canvas/static/canvas/js/canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js)

Add at the end (before `initCanvasContextMenu`, around line ~2082):

```javascript
/**
 * Crea un nodo de Matriz de Leads en el canvas.
 * Muestra una tabla/heatmap con propiedades como filas, fechas como columnas.
 */
async function createLeadMatrixNode(x, y) {
  if (typeof captureState === 'function') captureState();

  const nodeId = 'lead_matrix_' + Date.now();
  if (STATE.nodos[nodeId]) return;

  const node = document.createElement('div');
  node.className = 'cv-node cv-node--lead-matrix';
  node.dataset.id = nodeId;
  node.style.left = x + 'px';
  node.style.top = y + 'px';
  node.style.width = '560px';
  node.style.minWidth = '400px';
  node.innerHTML = `
    <div class="cv-node__header">
      <span class="cv-node__badge cv-badge--lead-matrix">📊 MATRIZ</span>
      <span class="cv-node__title">Matriz de Leads</span>
      <span class="cv-lead-gran-label">👤 <span id="matrix-total">—</span></span>
      <button class="cv-node__delete" title="Eliminar">&#x2715;</button>
    </div>
    <div class="cv-node__body" style="padding:8px;overflow:auto;max-height:400px;">
      <div style="text-align:center;padding:20px;color:var(--cv-text-muted);">
        Cargando datos...
      </div>
    </div>
    <div class="cv-port cv-port--top"    data-node="${nodeId}" data-port="top"></div>
    <div class="cv-port cv-port--right"  data-node="${nodeId}" data-port="right"></div>
    <div class="cv-port cv-port--bottom" data-node="${nodeId}" data-port="bottom"></div>
    <div class="cv-port cv-port--left"   data-node="${nodeId}" data-port="left"></div>
    <div class="cv-resize-handle" data-node="${nodeId}"></div>
  `;

  dom.nodes.appendChild(node);
  positionNode(nodeId, node, x, y);

  STATE.nodos[nodeId] = {
    id: nodeId, tipo: 'lead_matrix', ref_id: null,
    x: x, y: y, width: 560, height: node.offsetHeight || 340,
    collapsed: false, color: null, el: node,
    field_data: {},
  };
  registerNodeEvents(nodeId, node);
  markDirty();

  try {
    const res = await fetch('/canvas/api/lead-matrix/');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    renderLeadMatrixBody(nodeId, await res.json());
  } catch (err) {
    console.error('Error loading lead matrix:', err);
    const body = node.querySelector('.cv-node__body');
    if (body) body.innerHTML = '<div style="color:var(--cv-block);padding:12px;text-align:center;">Error al cargar matriz</div>';
  }
}

/**
 * Renderiza el body con la tabla/matriz de leads.
 */
function renderLeadMatrixBody(nodeId, data) {
  const nodo = STATE.nodos[nodeId];
  if (!nodo || !nodo.el) return;
  const body = nodo.el.querySelector('.cv-node__body');
  if (!body) return;

  const properties = data.properties || [];
  const dates = data.dates || [];
  const totalLeads = data.total_leads || 0;
  const totalProps = data.total_properties || 0;

  // Update header total
  const totalEl = nodo.el.querySelector('#matrix-total');
  if (totalEl) totalEl.textContent = totalLeads + ' leads / ' + totalProps + ' props';

  if (properties.length === 0 || dates.length === 0) {
    body.innerHTML = '<div style="text-align:center;padding:30px;color:var(--cv-text-muted);font-size:13px;">Sin datos de leads</div>';
    return;
  }

  const maxCount = Math.max.apply(null, properties.map(function(p) {
    return Math.max.apply(null, Object.values(p.daily_counts));
  }));

  // Helper: color intensity based on count
  function cellColor(count) {
    if (!count || count === 0) return 'transparent';
    const intensity = Math.min(1, count / maxCount);
    const r = Math.round(92 + (92 - 92) * intensity);
    const g = Math.round(107 + (192 - 107) * intensity);
    const b = Math.round(192 + (192 - 192) * intensity);
    const alpha = 0.15 + intensity * 0.65;
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  }

  function formatDateCol(dateStr) {
    if (!dateStr) return '';
    var parts = dateStr.split('-');
    if (parts.length === 3) return parts[2] + '/' + parts[1];
    return dateStr;
  }

  var html = '<div class="cv-matrix-wrap" style="overflow-x:auto;">';
  html += '<table class="cv-matrix-table" style="width:100%;border-collapse:collapse;font-size:11px;">';

  // Header row
  html += '<thead><tr>';
  html += '<th style="text-align:left;padding:4px 8px;position:sticky;left:0;background:var(--cv-bg);z-index:2;border-bottom:1px solid var(--cv-border);color:var(--cv-text-sec);font-weight:600;min-width:160px;">Propiedad</th>';
  html += '<th style="text-align:right;padding:4px 8px;border-bottom:1px solid var(--cv-border);color:var(--cv-text-sec);font-weight:600;min-width:40px;">Total</th>';
  dates.forEach(function(d) {
    html += '<th style="text-align:center;padding:4px 2px;border-bottom:1px solid var(--cv-border);color:var(--cv-text-muted);font-weight:500;font-size:10px;min-width:36px;writing-mode:vertical-lr;transform:rotate(180deg);">' + escHtml(formatDateCol(d)) + '</th>';
  });
  html += '</tr></thead>';

  // Body rows
  html += '<tbody>';
  properties.forEach(function(prop) {
    var propLabel = prop.title || prop.code || 'Prop #' + prop.property_id;
    if (prop.district_name) propLabel += ' — ' + prop.district_name;
    if (propLabel.length > 50) propLabel = propLabel.substring(0, 47) + '...';

    html += '<tr>';
    html += '<td style="text-align:left;padding:3px 8px;border-bottom:1px solid var(--cv-border);color:var(--cv-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px;position:sticky;left:0;background:var(--cv-bg);z-index:1;" title="' + escHtml(prop.title || '') + '">' + escHtml(propLabel) + '</td>';
    html += '<td style="text-align:right;padding:3px 8px;border-bottom:1px solid var(--cv-border);color:var(--cv-text-pri);font-weight:600;">' + prop.total + '</td>';

    dates.forEach(function(d) {
      var count = prop.daily_counts[d] || 0;
      var color = cellColor(count);
      html += '<td style="text-align:center;padding:3px 2px;border-bottom:1px solid var(--cv-border);background:' + color + ';color:' + (count > 0 ? 'var(--cv-text-pri)' : 'var(--cv-text-muted)') + ';font-size:11px;font-weight:' + (count > 0 ? '600' : '400') + ';">';
      html += count > 0 ? count : '—';
      html += '</td>';
    });

    html += '</tr>';
  });
  html += '</tbody></table>';
  html += '</div>';

  // Summary footer
  html += '<div style="display:flex;justify-content:space-between;padding:6px 10px;border-top:1px solid var(--cv-border);margin-top:4px;font-size:11px;color:var(--cv-text-muted);">';
  html += '<span>Total: <strong style="color:#5c6bc0;">' + totalLeads + '</strong> leads</span>';
  html += '<span>Propiedades: <strong style="color:var(--cv-text-sec);">' + totalProps + '</strong></span>';
  html += '<span>Período: <strong style="color:var(--cv-text-sec);">' + formatDateCol(dates[0]) + ' — ' + formatDateCol(dates[dates.length-1]) + '</strong></span>';
  html += '</div>';

  body.innerHTML = html;
  nodo.height = nodo.el.offsetHeight || 340;
  markDirty();
}

// Export functions
window.createLeadMatrixNode = createLeadMatrixNode;
window.renderLeadMatrixBody = renderLeadMatrixBody;
```

### Step 4: Frontend — Context Menu Update [`canvas/static/canvas/js/canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js)

In `initCanvasContextMenu()` (~line 2085), update the menu HTML to add:

```javascript
menu.innerHTML = 
  '<div class="cv-lead-context-menu__header">📊 Lienzo</div>' +
  '<div class="cv-lead-context-menu__item" data-action="create-global-leads">📊 Crear tarjeta de leads</div>' +
  '<div class="cv-lead-context-menu__item" data-action="create-lead-matrix">📋 Matriz de Leads</div>';
```

And in the click handler add:
```javascript
if (action === 'create-lead-matrix') {
  if (typeof createLeadMatrixNode === 'function') {
    createLeadMatrixNode(x, y);
  }
}
```

### Step 5: Frontend — Snapshot Restore Logic [`canvas/static/canvas/js/canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js)

In the snapshot restore section (around line ~1408), after the `lead_global` refresh block:

```javascript
// Refrescar nodos lead_matrix desde la API al cargar snapshot
Object.values(STATE.nodos).forEach(function(n) {
  if (n.tipo === 'lead_matrix' && n.el) {
    setTimeout(function(nodeId) {
      fetch('/canvas/api/lead-matrix/')
        .then(function(r) { return r.json(); })
        .then(function(data) { renderLeadMatrixBody(nodeId, data); })
        .catch(function() {});
    }, 800, n.id);
  }
});
```

### Step 6: Frontend — CSS Styling [`canvas/static/canvas/css/canvas.css`](webapp/canvas/static/canvas/css/canvas.css)

Add at the end of the CSS file:

```css
/* ── LEAD MATRIX NODE ── */
.cv-node--lead-matrix {
  background: var(--cv-surface);
  border: 1px solid var(--cv-border);
  border-radius: var(--cv-radius);
  box-shadow: var(--cv-shadow);
  overflow: hidden;
}

.cv-badge--lead-matrix {
  background: #4527a0;
  color: #d1c4e9;
}

.cv-matrix-table {
  font-size: 11px;
}

.cv-matrix-table th {
  user-select: none;
}

.cv-matrix-table td {
  transition: background 0.2s;
}

.cv-matrix-table tr:hover td {
  filter: brightness(1.2);
}

.cv-matrix-wrap::-webkit-scrollbar {
  height: 6px;
  width: 6px;
}

.cv-matrix-wrap::-webkit-scrollbar-track {
  background: var(--cv-bg);
}

.cv-matrix-wrap::-webkit-scrollbar-thumb {
  background: var(--cv-border);
  border-radius: 3px;
}

.cv-matrix-wrap::-webkit-scrollbar-thumb:hover {
  background: var(--cv-text-muted);
}
```

---

## Files to Modify (Summary)

| File | Change |
|------|--------|
| [`webapp/canvas/views.py`](webapp/canvas/views.py) | Add `api_lead_matrix` view |
| [`webapp/canvas/urls.py`](webapp/canvas/urls.py) | Add URL route for `api_lead_matrix` |
| [`webapp/canvas/static/canvas/js/canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js) | Add 3 functions + update context menu + snapshot restore |
| [`webapp/canvas/static/canvas/css/canvas.css`](webapp/canvas/static/canvas/css/canvas.css) | Add matrix node and table styles |

## Not Modified
- No new models needed (uses existing `lead`, `lead_properties`, `property` tables)
- No new templates needed (rendered entirely via JS)
- No migrations needed

## Visual Design

The matrix card will have:
- **Header**: Purple badge "MATRIZ", title "Matriz de Leads", total count badge
- **Body**: Scrollable HTML table with sticky first column (property name)
  - Column headers: Date labels (DD/MM), vertical text, with "Total" column
  - Row cells: Color-coded by intensity (light purple → dark purple based on count)
  - Empty cells show "—"
  - Hover highlights the row
- **Footer**: Summary with total leads, properties, and date range
