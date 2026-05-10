# Plan: Unificación de Menú Lateral — Migrar todos los sidebars a submenús en propifai_base.html

## Problema

Actualmente existen **múltiples barras laterales** independientes en el proyecto:

1. **`propifai_base.html`** — El nuevo base template unificado (sidebar principal)
2. **`intelligence/base/base.html`** — Sidebar propio de Intelligence Layer (7 ítems: Dashboard, Skills, Colecciones, Evaluación, Config, Errores, Tests)
3. **`base.html`** — Sidebar antiguo (usado por templates legacy como index.html, matching, etc.)
4. **`acm_dashboard.html`** — Sidebar propio (independiente, no hereda de propifai_base)
5. **`acm_base.html`** — Ya migrado a heredar de propifai_base.html
6. **Archivos HTML sueltos en raíz** — `test.html`, `dashboard_output.html`, etc. (legacy, no tocar)

## Objetivo

Que **TODAS** las apps usen `propifai_base.html` como único base, y sus menús específicos se conviertan en **submenús** dentro del sidebar principal.

---

## Fase 1: Migrar Intelligence Layer + WhatsApp Extractor

### 1.1. Agregar submenú "Inteligencia Artificial" en propifai_base.html

Los ítems actuales del sidebar de `intelligence/base/base.html` deben convertirse en submenús:

```
Inteligencia Artificial (expansible)
├── Dashboard General      → /intelligence/dashboard/
├── Skills                 → /intelligence/skills/
├── Colecciones            → /intelligence/collections/
├── Evaluación Intenciones → /intelligence/intent-evaluation/
├── Configuraciones        → /intelligence/config/
├── Errores                → /intelligence/errors/
├── Tests                  → /intelligence/tests/
```

### 1.2. Modificar intelligence/base/base.html

- Cambiar `{% extends ... %}` para heredar de `propifai_base.html` en vez de ser un template completo
- Eliminar su sidebar propio
- Usar blocks de `propifai_base.html` (`{% block content %}`, `{% block extra_css %}`, etc.)

### 1.3. Modificar WhatsApp Extractor templates

Actualmente los 9 templates del WhatsApp Extractor heredan de `intelligence/base/base.html`. Al migrar ese base, automáticamente heredarán de `propifai_base.html`.

El submenú "WhatsApp Extractor" ya está agregado dentro de "Requerimientos" (Fase 0).

---

## Fase 2: Migrar templates que usan base.html

### 2.1. Identificar templates que extienden base.html

```python
# Templates que extienden base.html:
- templates/index.html
- matching/templates/matching/dashboard.html
- matching/templates/matching/masivo.html
```

### 2.2. Migrar cada template

- Cambiar `{% extends "base.html" %}` → `{% extends "propifai_base.html" %}`
- Ajustar blocks según la estructura de propifai_base.html

---

## Fase 3: Migrar acm_dashboard.html

- `acm/templates/acm/acm_dashboard.html` es un template completo (no hereda de nada)
- Debe modificarse para heredar de `propifai_base.html` y usar `{% block content %}`
- Su sidebar propio debe eliminarse

---

## Fase 4: Agregar submenús faltantes en propifai_base.html

### 4.1. Submenú "Propiedades" (agrupar Propify + Externas)

```
Gestión Inmobiliaria
├── Propiedades Propify    → /propifai/propiedades/
├── Propiedades Externas   → /ingestas/propiedades/
├── Requerimientos (expansible)
│   ├── Lista              → /requerimientos/lista/
│   ├── Dashboard Análisis → /requerimientos/dashboard-analisis/
│   └── WhatsApp Extractor → /whatsapp-extractor/
├── Matching               → /matching/masivo/
```

### 4.2. Submenú "Análisis de Mercado"

```
Análisis & Mercado
├── ACM                    → /acm/analisis/
├── Heatmap                → /market-analysis/heatmap/
├── Dashboard Calidad      → /market-analysis/dashboard/
├── Cuadrantización        → /cuadrantizacion/mapa/
├── Mapa de POIs           → /api/pois/mapa/
```

### 4.3. Submenú "Marketing"

```
Marketing & Prospección
├── Prospección            → /prospects/capture/
├── Meta Ads               → /meta-ads/dashboard/exacto/
├── Leads CRM              → /analisis-crm/
```

### 4.4. Submenú "Sistema"

```
Sistema
├── Fuentes Web            → /fuentes-web/
├── Capturas               → /capturas/
├── Eventos                → /eventos/
├── Admin Django           → /admin/
```

---

## Resumen de archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `webapp/templates/propifai_base.html` | Agregar submenús de Intelligence, expandir estructura |
| `webapp/intelligence/templates/intelligence/base/base.html` | Convertir en extensión de propifai_base.html, eliminar sidebar |
| `webapp/intelligence/static/intelligence/css/intelligence_base.css` | Eliminar o reducir (estilos del sidebar ya no necesarios) |
| `webapp/templates/base.html` | Mantener como legacy o eliminar si ya no se usa |
| `webapp/templates/index.html` | Cambiar extends a propifai_base.html |
| `webapp/matching/templates/matching/dashboard.html` | Cambiar extends a propifai_base.html |
| `webapp/matching/templates/matching/masivo.html` | Cambiar extends a propifai_base.html |
| `webapp/acm/templates/acm/acm_dashboard.html` | Heredar de propifai_base.html, eliminar sidebar propio |

## Templates que NO se modifican (archivos legacy en raíz)

- `test.html`, `dashboard_output.html`, `heatmap_*.html`, `home_render*.html`, etc.
- Son archivos de prueba/exportación, no templates activos de Django

## Orden de implementación

1. **Fase 1**: Intelligence Layer + WhatsApp Extractor (prioridad máxima, son los que tienen sidebar más grande)
2. **Fase 2**: Templates que usan base.html (index, matching)
3. **Fase 3**: acm_dashboard.html
4. **Fase 4**: Refinar submenús en propifai_base.html
5. **Fase 5**: Verificar que todo funciona
