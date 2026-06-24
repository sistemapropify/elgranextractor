# F1-002: SQL Pre-filtering for RAG

> **Phase:** 1 — Function Calling
> **Priority:** 🔴 HIGH
> **Estimated Effort:** 1 day
> **Dependencies:** None (standalone optimization)
> **Status:** ✅ Implemented (2026-06-21)

---

## Description

Migrar el filtrado por `field_values` de un loop en Python (que carga TODOS los documentos a memoria) a filtrado directo en SQL Server usando `JSON_VALUE()`. El sistema actual itera sobre todos los documentos en memoria para aplicar filtros, lo que es ineficiente para colecciones grandes.

## Goals

- [x] **2.1** Analizar filtrado actual en `rag.py` search_dynamic()
- [x] **2.2** Implementar opción 1: Django JSONField lookups (`field_values__{field_name}`)
- [x] **2.3** Implementar opción 2: RawSQL con `JSON_VALUE()` como fallback
- [x] **2.4** Migrar `search_dynamic()` a usar pre-filtrado SQL
- [x] **2.5** Agregar logging de documentos filtrados (count, filtros aplicados)
- [x] **2.6** Aplicar filtros SQL también en `_text_search_fallback()` (antes ignoraba filters)
- [x] **2.7** Documentar cambio y métricas de performance

_Prompt: Replace the in-memory Python filtering loop in RAGService.search_dynamic() with SQL-level pre-filtering using JSON_VALUE() on the field_values JSON column. This reduces memory usage and improves response time for large collections._

_Requirements: Django JSONField lookups, SQL Server JSON_VALUE(), field_values JSON structure_

_Leverage: existing IntelligenceDocument model, existing search_dynamic() signature_

_Files: webapp/intelligence/services/rag.py (modify lines 1501-1511)_

## Current Inefficient Code

```python
# ACTUAL — Carga TODOS los documentos a memoria
if filters:
    for field_name, field_value in filters.items():
        filtered_docs = []
        for doc in documents:  # ← Itera sobre TODOS en memoria
            if field_name in doc.field_values and doc.field_values[field_name] == field_value:
                filtered_docs.append(doc)
        documents = filtered_docs
```

## Target Efficient Code

```python
# OPCIÓN 1 — Django JSONField lookups
if filters:
    filter_q = Q()
    for field_name, field_value in filters.items():
        filter_q &= Q(**{f'field_values__{field_name}': field_value})
    documents = documents.filter(filter_q)

# OPCIÓN 2 — RawSQL con JSON_VALUE (SQL Server)
if filters:
    for field_name, field_value in filters.items():
        sql = f"JSON_VALUE(field_values, '$.\"{field_name}\"') = %s"
        documents = documents.extra(where=[sql], params=[str(field_value)])
```

## Acceptance Criteria

- [x] **2.a** Filtrado en SQL, no en memoria Python
- [x] **2.b** Soporte para filtros combinados (distrito + precio + tipo_propiedad) — usa `&=` entre Q objects
- [x] **2.c** Sin breaking changes en API — firma de `search_dynamic()` no cambia
- [x] **2.d** Logging de count de documentos pre/post filtro con tag `F1-002`
- [x] **2.e** Fallback a `JSON_VALUE()` RawSQL si el ORM falla (compatibilidad SQL Server)
- [x] **2.f** Filtros aplicados también en `_text_search_fallback()` (antes se ignoraban)
