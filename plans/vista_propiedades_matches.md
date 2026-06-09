# Plan: Vista de Matches desde Propiedades (Property-Centric)

## Objetivo

Crear una nueva vista que muestre las **propiedades como entidad principal** y los **requerimientos como ramas en pipeline**, exactamente invertido del [`/matching/matches/`](webapp/matching/views.py:1643) actual.

Los matches con score ya vienen calculados desde la API (`api.propify.pe`). Solo hay que **reagruparlos** por propiedad en vez de por requerimiento.

---

## 1. Estado Actual

### Vista existente: [`MatchesDashboardView`](webapp/matching/views.py:1643)
- URL: `/matching/matches/`
- Template: [`matches_dashboard.html`](webapp/matching/templates/matching/matches_dashboard.html)
- API consumida: `api.propify.pe` via [`PropifyApiClient`](webapp/matching/propify_api.py)
- Agrupación: Por `requirement_id` → cada fila = requerimiento
- Pipeline existente: [`pipeline_matches`](webapp/matching/views.py:213-341) → 📝 Requerimiento como nodo principal, 🏠 Propiedades como ramas

### Datos disponibles en cada match (desde `client.get_matches()`)
Cada objeto en `results` ya incluye:
| Campo | Descripción |
|---|---|
| `id` | ID del match |
| `property` | ID de la propiedad |
| `property_code` | Código de la propiedad |
| `property_title` | Título de la propiedad |
| `property_district_name` | Distrito |
| `property_price` | Precio |
| `property_currency_name` | Moneda |
| `requirement` | ID del requerimiento |
| `score` | Score del match (0-100) |
| `computed_at` | Fecha de cómputo |

No hay que calcular nada. Solo reagrupar.

---

## 2. Archivos a Modificar

### 2.1. [`webapp/matching/propify_api.py`](webapp/matching/propify_api.py)
**Agregar método** para listar propiedades desde la API (opcional, para tener metadata adicional):
```python
def get_properties(self, page: int = 1, page_size: int = 50, **filters) -> Optional[Dict[str, Any]]:
    params = {"page": page, "page_size": page_size}
    params.update(filters)
    return self._request("GET", "/api/crm/properties/", params=params)
```

### 2.2. [`webapp/matching/views.py`](webapp/matching/views.py)
**Agregar:**

**a) Nuevo endpoint API:** `pipeline_requerimientos_por_propiedad`
- Action en [`MatchingViewSet`](webapp/matching/views.py:41)
- Recibe `property_id` (pk)
- Llama a `client.get_matches_by_property(property_id)` para obtener todos los matches de esa propiedad
- Ordena por score descendente
- Opcionalmente enriquece cada match con datos del requerimiento via `client.get_requirement_detail(req_id)`
- Retorna: propiedad como nodo principal, requerimientos como ramas
- Estructura de respuesta similar a [`pipeline_matches`](webapp/matching/views.py:213) pero invertida

**b) Nueva vista:** `PropiedadesMatchesDashboardView(TemplateView)`
- Template: `matches_por_propiedad.html`
- Lógica (idéntica a [`MatchesDashboardView`](webapp/matching/views.py:1643) pero agrupando por property):

```
1. Obtener todos los requerimientos via client.get_requirements() (para autocomplete y filtros)
2. Obtener matches via client.get_matches()
3. Agrupar matches por el campo 'property' (ID de propiedad)
   → prop_groups[property_id] = { property_id, property_code, ..., requirements: [...], best_score, ... }
4. Ordenar grupos por mejor score descendente
5. Pasar a template
```

### 2.3. Nuevo Template: [`webapp/matching/templates/matching/matches_por_propiedad.html`](webapp/matching/templates/matching/matches_por_propiedad.html)
Basado 1:1 en [`matches_dashboard.html`](webapp/matching/templates/matching/matches_dashboard.html) pero adaptado:

**Stats bar:**
- Total propiedades con match
- Total matches
- Total requerimientos únicos
- Página actual / total páginas

**Filtros:**
- Vista (all/day/week/month)
- Fecha
- Código de propiedad (input text)
- Responsable (autocomplete)

**Tabla (filas = propiedades):**
| Columna | Contenido |
|---|---|
| 🔽 | Botón expandir pipeline (llama a `/matching/api/matching/{prop_id}/pipeline-requerimientos/`) |
| Propiedad | `property_code` + `property_title` |
| Distrito | `property_district_name` |
| Precio | `property_price` + `property_currency_name` |
| Responsable | Desde `get_property_detail()` o vacío |
| Requerimientos | Total + "+ N más" |
| Mejor Score | Badge color según score (≥80 verde, ≥50 naranja, <50 rojo) |
| Computado | `computed_at` del mejor match |

**Pipeline expandible** (invertido respecto al actual):
```
🏠 PROP-001 (nodo principal)
  ├── 📝 Req #123 (score: 45%)
  ├── 📝 Req #456 (score: 82%)
  └── 📝 Req #789 (score: 91%)
```

### 2.4. [`webapp/matching/urls.py`](webapp/matching/urls.py)
**Agregar rutas:**
```python
path('matches-por-propiedad/', views.PropiedadesMatchesDashboardView.as_view(), name='matches-por-propiedad'),
path('api/matching/<int:pk>/pipeline-requerimientos/', 
     views.MatchingViewSet.as_view({'get': 'pipeline_requerimientos'}), 
     name='matching-pipeline-requerimientos'),
```

---

## 3. Diagrama de Flujo

```mermaid
flowchart TD
    A[GET /matching/matches-por-propiedad/] --> B[client.get_matches page=1 page_size=50 con filtros]
    B --> C[Agrupar results por campo property]
    C --> D[Para cada grupo:\ncalcular best_score, total_requirements, ordenar reqs por score]
    D --> E[Renderizar tabla:\n1 fila = 1 propiedad]
    E --> F{Usuario expande?}
    F -->|Sí| G[GET /matching/api/matching/{prop_id}/pipeline-requerimientos/]
    G --> H[client.get_matches_by_property prop_id]
    H --> I[Ordenar por score descendente]
    I --> J[Renderizar pipeline:\n🏠→📝→📝→📝]
    F -->|No| K[Esperar]
```

---

## 4. Especificación del Pipeline Property→Requirements

Endpoint: `GET /matching/api/matching/{property_id}/pipeline-requerimientos/`

Respuesta:
```json
{
    "property_id": 123,
    "property_code": "PROP-001",
    "property_title": "Departamento en Cayma",
    "property_district": "Cayma",
    "property_price": 120000.00,
    "property_currency_name": "USD",
    "property_created_at": "2026-01-15T10:00:00Z",
    "property_responsable": "Juan Pérez",
    "property_image_url": "https://...",
    "etapa_propiedad": {
        "tipo": "propiedad",
        "label": "PROP-001",
        "icono": "🏠",
        "fecha_display": "15/01",
        "estado": "ok"
    },
    "ramas": [
        {
            "match_id": 456,
            "requirement_id": 789,
            "requirement_code": "REQ-789",
            "requirement_assigned": "María López",
            "requirement_operation": "Venta",
            "requirement_property_type": "Departamento",
            "requirement_created_at": "2026-02-01T14:30:00Z",
            "score": 91.0,
            "computed_at": "2026-02-02T08:00:00Z"
        }
    ],
    "total_ramas": 3
}
```

---

## 5. Orden de Implementación

1. Agregar [`get_properties()`](webapp/matching/propify_api.py) a `PropifyApiClient`
2. Agregar action [`pipeline_requerimientos`](webapp/matching/views.py) a `MatchingViewSet`
3. Crear vista [`PropiedadesMatchesDashboardView`](webapp/matching/views.py)
4. Crear template [`matches_por_propiedad.html`](webapp/matching/templates/matching/matches_por_propiedad.html)
5. Registrar rutas en [`matching/urls.py`](webapp/matching/urls.py)
6. Verificar que la vista funciona y los pipelines se renderizan correctamente
