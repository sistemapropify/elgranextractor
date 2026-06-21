# Plan de Robustez — `/requerimientos/lista/`

## Diagnóstico y Priorización

### 🔴 FASE 1 — Correcciones Críticas

| # | Tarea | Archivos | Descripción |
|---|-------|----------|-------------|
| 1 | **Agregar AbortController a fetch** | `lista.html` | Evitar race conditions en autocomplete (distritos, urbanización, zona) y búsqueda de agente |
| 2 | **Reemplazar silent failures con logging** | `views.py` | Cambiar `try/except pass` por logging + posible feedback al usuario |
| 3 | **Validación client-side en modal** | `lista.html` | Validar tipos numéricos, campos requeridos antes de enviar POST |
| 4 | **Dirty-state tracking** | `lista.html` | Confirmar al cerrar modal si hay cambios sin guardar |
| 5 | **Cachear ApiEstadisticasCalidadView** | `views.py` | Evitar iterar todos los requerimientos en cada request |

### 🟡 FASE 2 — Performance y UX

| # | Tarea | Archivos | Descripción |
|---|-------|----------|-------------|
| 6 | **Convertir filtros a GET con límite o sessionStorage** | `lista.html`, `views.py` | Evitar URL explosion con 20+ parámetros |
| 7 | **AJAX filtering con debounce** | `lista.html`, `views.py` | Evitar full page reload al filtrar |
| 8 | **Toggle de columnas visibles** | `lista.html` | Mejorar UX en pantallas pequeñas |
| 9 | **Agregar db_index a campos frecuentes** | `models.py` | Optimizar queries de filtros |
| 10 | **Agregar select_related** | `views.py` | Optimizar N+1 queries |

### 🟢 FASE 3 — Refactor de Deuda Técnica

| # | Tarea | Archivos | Descripción |
|---|-------|----------|-------------|
| 11 | **Extraer JS a `lista.js`** | `lista.html` → `static/` | Separar lógica del template |
| 12 | **Extraer CSS a `lista.css`** | `lista.html` → `static/` | Separar estilos del template |
| 13 | **Unificar `val()` y `valClone()`** | `lista.html` | Una sola función con modo clonación como flag |
| 14 | **Estandarizar const/let** | `lista.html` | Reemplazar `var` inconsistente |
| 15 | **Unificar URLs duras con `{% url %}`** | `lista.html` | Evitar URLs rotas |
