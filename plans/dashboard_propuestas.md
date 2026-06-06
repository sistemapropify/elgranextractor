# Plan: Dashboard de Propuestas WhatsApp

## 1. Contexto

Existe el modelo `PropuestaWhatsApp` en `matching/models.py` con campos:
- `status`: enviada, respondida, interesado, rechazado, no_interesado, visita_agendada, cerrada
- `enviado_en`, `respondido_en` (fechas)
- `agente_nombre`, `agente_telefono`
- FK a `Requerimiento`

Ya hay endpoints API para guardar/actualizar propuestas, pero **no hay un dashboard visual** para gestionarlas.

## 2. Arquitectura

### Archivos a crear/modificar:

| Archivo | Acción |
|---|---|
| `webapp/matching/views.py` | Agregar `PropuestasDashboardView` |
| `webapp/matching/urls.py` | Agregar ruta `/matching/propuestas/dashboard/` |
| `webapp/matching/templates/matching/propuestas_dashboard.html` | **NUEVO** — Template completo |
| `webapp/templates/base.html` | Agregar items en sidebar bajo Matching |

### Flujo de datos:

```
[Browser] → GET /matching/propuestas/dashboard/
           → PropuestasDashboardView.get_context_data()
               → QuerySet: PropuestaWhatsApp.aggregate stats
               → Generar charts (matplotlib → base64)
               → Retornar contexto
           → Render: propuestas_dashboard.html
```

## 3. Vista: `PropuestasDashboardView`

Clase que hereda de `TemplateView`, template `matching/propuestas_dashboard.html`.

### Stats del contexto:

```python
context['stats'] = {
    'hoy': {
        'enviadas': N,
        'respondidas': N,
        'aceptadas': N,       # interesado + visita_agendada + cerrada
        'rechazadas': N,      # rechazado + no_interesado
        'tasa_respuesta': 'XX%',
        'tasa_aceptacion': 'XX%',
    },
    'semana': { ... mismo esquema ... },
    'mes': { ... mismo esquema ... },
    'total_general': N,
}
```

### Charts (matplotlib → base64):

Basado en el patrón de `market_analysis/charts.py`:
- Usar `matplotlib.use('Agg')`, fondo `#0d1117`, texto claro
- Convertir a base64 con `_fig_to_base64()`

| Chart | Tipo | Descripción |
|---|---|---|
| `chart_evolucion_semanal` | Línea | Últimos 7 días: enviadas vs respondidas |
| `chart_evolucion_mensual` | Línea | Últimos 30 días (agrupado cada 3 días): enviadas vs respondidas |
| `chart_barras_semana` | Barras agrupadas | Enviadas vs Aceptadas vs Rechazadas por día (últimos 7) |
| `chart_distribucion_status` | Donut | Distribución de status actual (enviada, interesado, rechazado, etc.) |

### Datos para charts (desde BD):

```sql
-- Propuestas por día (últimos 7 días)
SELECT DATE(enviado_en) as dia, status, COUNT(*) as total
FROM matching_propuestawhatsapp
WHERE enviado_en >= DATEADD(day, -7, GETDATE())
GROUP BY DATE(enviado_en), status
ORDER BY dia
```

## 4. Template: `propuestas_dashboard.html`

Extiende `base.html` con block `{% block content %}`.

### Secciones:

```
┌─────────────────────────────────────────────────────┐
│ 📊 Dashboard de Propuestas                          │
├─────────────────────────────────────────────────────┤
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐  │
│ │ Hoy  │ │ Sem  │ │ Mes  │ │ Tasa │ │ Aceptac  │  │
│ │ 12   │ │ 45   │ │ 180  │ │ 68%  │ │ 35%      │  │
│ └──────┘ └──────┘ └──────┘ └──────┘ └──────────┘  │
├─────────────────────────────────────────────────────┤
│ ┌──────────────────────┐ ┌──────────────────────┐   │
│ │ Evolución Semanal    │ │ Evolución Mensual    │   │
│ │ (line chart)         │ │ (line chart)         │   │
│ └──────────────────────┘ └──────────────────────┘   │
├─────────────────────────────────────────────────────┤
│ ┌──────────────────────┐ ┌──────────────────────┐   │
│ │ Barras Semana        │ │ Distribución Status  │   │
│ │ (bar chart)          │ │ (donut chart)        │   │
│ └──────────────────────┘ └──────────────────────┘   │
├─────────────────────────────────────────────────────┤
│ Tabla: Últimas 20 propuestas                        │
│ ┌────┬────────┬──────────┬────────┬──────────┐     │
│ │ ID │ Agente │ Status   │ Fecha  │ Respuesta│     │
│ ├────┼────────┼──────────┼────────┼──────────┤     │
│ │ 1  │ Juan   │ enviada  │ 04/06  │ —        │     │
│ │ 2  │ María  │ aceptado │ 03/06  │ ✅       │     │
│ └────┴────────┴──────────┴────────┴──────────┘     │
└─────────────────────────────────────────────────────┘
```

### Colores (tema oscuro existente):
- Fondo: `#0d1117`
- Tarjetas: `#161b22`
- Bordes: `#30363d`
- Texto: `#e6edf3`
- Azul (enviadas): `#58a6ff`
- Verde (aceptadas): `#3fb950`
- Rojo (rechazadas): `#f85149`
- Naranja (pendientes): `#d29922`

## 5. Sidebar (`base.html`)

Agregar bajo el menú Matching existente:

```html
<li class="has-submenu {% if '/matching/' in request.path %}active{% endif %}">
    <a href="#">
        <i class="bi bi-lightning-charge-fill"></i>
        <span>Matching</span>
        <i class="bi bi-chevron-down ms-auto"></i>
    </a>
    <ul class="submenu">
        ... items existentes ...
        <li class="has-submenu {% if '/matching/propuestas/' in request.path %}active{% endif %}">
            <a href="#">
                <i class="bi bi-whatsapp"></i>
                <span>Propuestas</span>
                <i class="bi bi-chevron-down ms-auto"></i>
            </a>
            <ul class="submenu" style="padding-left:30px;">
                <li>
                    <a href="/matching/propuestas/dashboard/" class="{% if '/matching/propuestas/dashboard/' in request.path %}active{% endif %}">
                        <i class="bi bi-speedometer2"></i>
                        <span>Dashboard</span>
                    </a>
                </li>
            </ul>
        </li>
    </ul>
</li>
```

## 6. URL (`urls.py`)

```python
path('propuestas/dashboard/', views.PropuestasDashboardView.as_view(), name='propuestas-dashboard'),
```

## 7. Implementación paso a paso

1. **Crear vista** `PropuestasDashboardView` en `matching/views.py`:
   - Query stats por día/semana/mes
   - Generar charts con matplotlib
   - Retornar contexto con stats + charts base64

2. **Agregar URL** en `matching/urls.py`

3. **Crear template** `propuestas_dashboard.html`:
   - Stats cards (hoy, semana, mes, tasas)
   - Charts grid (2x2)
   - Tabla de últimas propuestas

4. **Modificar sidebar** en `base.html`:
   - Submenú Propuestas → Dashboard bajo Matching
