# Plan de Implementación — Refactorización del Sistema de Inteligencia Propifai

> **Versión:** 1.0
> **Fecha:** 2026-05-11
> **Propósito:** Roadmap detallado para implementar los 4 refactors especificados

---

## 📊 Tabla Maestra de Tareas

| ID | Tarea | Archivos | Líneas | Depende de | Riesgo |
|----|-------|----------|--------|------------|--------|
| **A1** | Crear `ContextManager` con `ActiveContext` dataclass | `NUEVO: context_manager.py` | — | Ninguna | 🟢 Bajo |
| **A2** | Reemplazar `_get_contexto_activo()` por `ContextManager.get_active_context()` | `chat_processor.py` | 1089-1144 | A1 | 🟢 Bajo |
| **A3** | Reemplazar `_guardar_contexto_activo()` por `ContextManager.save_active_context()` | `chat_processor.py` | 1168-1179 | A1 | 🟢 Bajo |
| **A4** | Eliminar `campos_contexto` hardcodeado | `chat_processor.py` | 1121-1125 | A1 | 🟢 Bajo |
| **A5** | Usar `ActiveContext.merge()` para fusión de contexto | `chat_processor.py` | 1248-1250 | A1 | 🟢 Bajo |
| **B1** | Ampliar `_KEYWORDS_PROPIEDADES` con términos faltantes | `registry.py` | 25-38 | Ninguna | 🟢 Bajo |
| **B2** | Hacer keywords configurables desde settings | `registry.py` | 25-38, `__init__` | B1 | 🟢 Bajo |
| **B3** | Agregar `active_context` a `find_best_skill()` | `registry.py` | 114-216 | A1 | 🟡 Medio |
| **B4** | Agregar detección de mensajes de seguimiento | `registry.py` | 114-216 | B3 | 🟡 Medio |
| **B5** | Simplificar `_infer_skill_request()` — eliminar sistema antiguo | `chat_processor.py` | 748-867 | B3 | 🔴 Alto |
| **B6** | Eliminar `_find_skill_candidate()` | `chat_processor.py` | 869-886 | B5 | 🟡 Medio |
| **B7** | Eliminar `_find_math_skill_candidate()` | `chat_processor.py` | 888-907 | B5 | 🟢 Bajo |
| **C1** | Hacer pipeline condicional según contexto activo | `chat_processor.py` | 1209-1237 | A1 | 🟡 Medio |
| **C2** | Agregar ruta de ejecución directa sin `resolver_contexto` | `chat_processor.py` | 1209-1237 | C1 | 🟡 Medio |
| **C3** | Unificar extracción de propiedades para ambos casos | `chat_processor.py` | 1252-1375 | C1 | 🟢 Bajo |
| **D1** | Agregar campo `semantic_tags` a `IntelligenceCollection` | `models.py` | 301-405 | Ninguna | 🟡 Medio |
| **D2** | Crear migración para `semantic_tags` | `intelligence/migrations/` | — | D1 | 🟡 Medio |
| **D3** | Agregar enriquecimiento semántico en `sync_collection_dynamic` | `rag.py` | 1278-1288 | D1 | 🟢 Bajo |
| **D4** | Resincronizar colecciones RAG existentes | Comando management | — | D3 | 🟡 Medio |

---

## 🗺️ Roadmap de Implementación

### Fase 1 — Fundación (Refactor A)
**Objetivo:** Unificar el sistema de contexto sin cambiar comportamiento externo.

```
Semana 1
├── Día 1-2: Crear ContextManager + ActiveContext
│   ├── Crear webapp/intelligence/services/context_manager.py
│   ├── Implementar ActiveContext dataclass con merge()
│   ├── Implementar ContextManager.get_active_context()
│   ├── Implementar ContextManager.save_active_context()
│   └── Implementar ContextManager._normalize_context() con FIELD_ALIASES
│
├── Día 3: Integrar en chat_processor.py
│   ├── Reemplazar _get_contexto_activo() → ContextManager.get_active_context()
│   ├── Reemplazar _guardar_contexto_activo() → ContextManager.save_active_context()
│   ├── Eliminar campos_contexto hardcodeado
│   └── Usar ActiveContext.merge() en línea 1248
│
└── Día 4-5: Pruebas
    ├── Test: contexto se hereda correctamente entre turnos
    ├── Test: contexto vacío en primer mensaje
    ├── Test: fusión de contexto (params nuevos + contexto activo)
    └── Test: normalización de nombres de campo
```

**Criterios de éxito:**
- [ ] El contexto activo se lee/guarda desde un solo punto
- [ ] Los nombres de campo se normalizan automáticamente
- [ ] No hay regresión en la herencia de contexto entre turnos
- [ ] Todos los tests existentes pasan

---

### Fase 2 — Unificación de Detección (Refactor B)
**Objetivo:** Unificar los dos sistemas de detección de skills en uno solo.

```
Semana 2
├── Día 1-2: Mejorar SkillRegistry
│   ├── Ampliar _KEYWORDS_PROPIEDADES con términos faltantes
│   ├── Hacer keywords configurables desde settings.py
│   ├── Agregar parámetro active_context a find_best_skill()
│   └── Implementar _is_follow_up_message() para detección de seguimiento
│
├── Día 3-4: Simplificar chat_processor.py
│   ├── Simplificar _infer_skill_request() — unificar routing
│   ├── Eliminar _find_skill_candidate()
│   ├── Eliminar _find_math_skill_candidate()
│   └── Verificar que no haya otros callers de estos métodos
│
└── Día 5: Pruebas
    ├── Test: "solo departamentos" detecta busqueda_propiedades con contexto
    ├── Test: "hola" no detecta ninguna skill
    ├── Test: "construir un colegio" detecta busqueda_propiedades
    ├── Test: mensaje de precio detecta skill de precio
    └── Test: keywords configurables desde settings
```

**Criterios de éxito:**
- [ ] Solo existe un mecanismo de detección de skills
- [ ] "construir un colegio" dispara `busqueda_propiedades`
- [ ] Mensajes de seguimiento ("solo departamentos") funcionan con contexto
- [ ] Keywords son configurables sin modificar código

---

### Fase 3 — Pipeline Inteligente (Refactor C)
**Objetivo:** Hacer que el pipeline sea condicional para evitar llamadas DeepSeek innecesarias.

```
Semana 3
├── Día 1-2: Implementar pipeline condicional
│   ├── Modificar bloque if ctx.skill_name == 'busqueda_propiedades'
│   ├── Agregar condición: solo pipeline si hay contexto o historial
│   ├── Agregar ruta de ejecución directa sin resolver_contexto
│   └── Unificar extracción de propiedades post-ejecución
│
├── Día 3: Ajustar guardado de contexto
│   ├── En ruta directa: guardar skill_params como contexto
│   ├── En ruta pipeline: mantener lógica existente
│   └── Verificar que _save_post_process reciba contexto RAG
│
└── Día 4-5: Pruebas
    ├── Test: primer mensaje NO ejecuta resolver_contexto
    ├── Test: segundo mensaje SÍ ejecuta resolver_contexto
    ├── Test: latencia reducida en primer mensaje
    ├── Test: herencia de contexto funciona en ambos modos
    └── Test: post-process guarda episodio correctamente
```

**Criterios de éxito:**
- [ ] Primer mensaje de la conversación no ejecuta `resolver_contexto`
- [ ] Latencia del primer mensaje se reduce en ~500ms-1s
- [ ] La herencia de contexto sigue funcionando en mensajes siguientes
- [ ] `_save_post_process` recibe contexto RAG en flujo de pipeline

---

### Fase 4 — Embeddings Enriquecidos (Refactor D)
**Objetivo:** Mejorar la búsqueda semántica para encontrar propiedades por concepto.

```
Semana 4
├── Día 1: Modelo y migración
│   ├── Agregar campo semantic_tags a IntelligenceCollection
│   ├── Crear migración
│   └── Configurar tags por defecto para colecciones existentes
│
├── Día 2-3: Enriquecimiento en sync
│   ├── Modificar sync_collection_dynamic para usar semantic_tags
│   ├── Agregar lógica de enriquecimiento por tipo de propiedad
│   └── Agregar contexto geográfico (distrito + ciudad)
│
└── Día 4-5: Resincronización y pruebas
    ├── Resincronizar colección propiedades_propifai
    ├── Resincronizar colección propiedades_competencia
    ├── Test: "construir un colegio" encuentra terrenos
    ├── Test: "local comercial" encuentra locales
    └── Test: búsqueda por distrito sigue funcionando
```

**Criterios de éxito:**
- [ ] "construir un colegio" encuentra terrenos en la búsqueda semántica
- [ ] "local comercial en cayma" encuentra locales comerciales
- [ ] Las colecciones existentes se resincronizan sin pérdida de datos
- [ ] No hay regresión en búsquedas existentes

---

## 🔄 Estrategia de Rollback

Cada fase debe implementarse con **commits atómicos** y **feature flags** cuando sea posible.

### Feature Flags Sugeridos

```python
# settings.py
PROPIFAI_FEATURES = {
    'CONTEXT_MANAGER_ENABLED': True,      # Refactor A
    'UNIFIED_SKILL_REGISTRY': True,        # Refactor B
    'CONDITIONAL_PIPELINE': True,          # Refactor C
    'SEMANTIC_ENRICHMENT': True,           # Refactor D
}
```

Cada feature flag permite desactivar el cambio sin revertir el código:

```python
# Ejemplo de uso
from django.conf import settings

if settings.PROPIFAI_FEATURES.get('CONDITIONAL_PIPELINE', False):
    # Nuevo comportamiento
    if not contexto_activo.is_empty() or len(historial) > 1:
        ...
else:
    # Comportamiento legacy
    ...
```

### Plan de Rollback por Fase

| Fase | Rollback |
|------|----------|
| A | Desactivar flag `CONTEXT_MANAGER_ENABLED` + restaurar métodos originales |
| B | Desactivar flag `UNIFIED_SKILL_REGISTRY` + restaurar `_find_skill_candidate` |
| C | Desactivar flag `CONDITIONAL_PIPELINE` |
| D | Desactivar flag `SEMANTIC_ENRICHMENT` + re-sync sin enriquecimiento |

---

## 🧪 Estrategia de Pruebas

### Pruebas Unitarias

| Componente | Archivo de test | Casos clave |
|-----------|----------------|-------------|
| `ContextManager` | `tests/test_context_manager.py` | Normalización, merge, empty, save/load |
| `SkillRegistry` | `tests/test_registry.py` | Keywords ampliados, follow-up, contexto activo |
| `ActiveContext` | `tests/test_context_manager.py` | is_empty, merge, to_dict, field aliases |

### Pruebas de Integración

| Escenario | Pasos | Resultado esperado |
|-----------|-------|-------------------|
| Primer mensaje sin contexto | "propiedades en cayma" | No ejecuta resolver_contexto, encuentra propiedades |
| Mensaje de seguimiento | "solo departamentos" | Ejecuta resolver_contexto, hereda distrito=Cayma |
| Búsqueda semántica | "construir un colegio" | Encuentra terrenos por enriquecimiento semántico |
| Sin keywords | "hola" | No detecta skill, cae a RAG puro |

### Pruebas de Regresión

```bash
# Test de contexto entre turnos
1. "cuantas propiedades hay en cayma" → responde con lista
2. "solo departamentos" → responde con departamentos en Cayma
3. "y en cerro colorado" → responde con departamentos en Cerro Colorado

# Test de detección de skills
4. "construir un colegio" → detecta busqueda_propiedades
5. "precio promedio de casas" → detecta skill de precio
6. "hola" → no detecta skill, respuesta genérica

# Test de pipeline condicional
7. Primer mensaje → NO hay llamada a resolver_contexto
8. Segundo mensaje → SÍ hay llamada a resolver_contexto
```

---

## 📈 Métricas de Éxito

| Métrica | Valor Actual | Objetivo | Cómo medir |
|---------|-------------|----------|-----------|
| Latencia primer mensaje | ~2-3s | <1.5s | Logs de MetricsService |
| Latencia mensajes seguimiento | ~2-3s | <2s | Logs de MetricsService |
| Tasa de detección correcta de skills | ~70% | >90% | Tests de integración |
| Precisión en herencia de contexto | ~60% | >95% | Tests de contexto entre turnos |
| Cobertura de keywords semánticos | 40 términos | 60+ términos | Conteo en _KEYWORDS_PROPIEDADES |
| Llamadas DeepSeek innecesarias | 100% (siempre) | 0% en primer turno | Logs de pipeline |

---

## 📋 Checklist de Pre-Release

- [ ] Todos los tests unitarios pasan
- [ ] Todos los tests de integración pasan
- [ ] Feature flags implementados y documentados
- [ ] Migraciones BD aplicadas y reversibles
- [ ] Logging adecuado en cada nuevo componente
- [ ] Documentación actualizada (este documento)
- [ ] Rollback plan verificado
- [ ] Monitoreo de latencia configurado
- [ ] Alertas de error configuradas para nuevos componentes
