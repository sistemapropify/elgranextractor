# Análisis del Motor de Matching — Problemas y Soluciones

## Estado actual

### 1. `_get_matches_by_embedding` en [`canvas/views.py`](webapp/canvas/views.py:259)

**Problema:** Calcula SOLO score semántico (cosine similarity de embeddings). El `score_estructural` es falso:
```python
'score_estructural': round(similarity * 100),  # ¡ES LO MISMO QUE EL SEMÁNTICO!
```

Esto explica por qué todos los matches muestran 88% o 87% — es el score semántico disfrazado de estructural.

**Además:** No usa el motor legacy [`MatchingEngine`](webapp/matching/engine.py:270) ni el [`HybridMatchingSkill`](webapp/intelligence/skills/matching_hybrid.py:94), que hacen el scoring estructural real con pesos (distrito 30%, tipo 30%, precio 30%).

### 2. Flujo correcto que debería usarse

```
Propiedad ID → MatchingEngine.ejecutar_matching() 
    → Devuelve resultados con:
        - score_total (combinado structural + semántico)
        - score_detalle (precio, distrito, tipo, etc.)
        - propiedad_dict (datos completos)

O mejor: HybridMatchingSkill.execute()
    → Usa FAISS + filtros duros + scoring estructural
    → Devuelve: score_total, score_structural, score_semantico, score_detalle
```

### 3. Solución propuesta

Reemplazar `_get_matches_by_embedding` para que use [`ejecutar_matching_requerimiento`](webapp/matching/engine.py:759) pero **a la inversa** (propiedad → requerimientos en vez de requerimiento → propiedades).

O mejor: crear una función `get_matches_for_property(property_id)` que:
1. Obtiene la propiedad desde `propiedadespropify`
2. Itera sobre `requerimientos_enbedados`
3. Calcula score semántico (cosine similarity)
4. Calcula score estructural con los mismos pesos del MatchingEngine
5. Filtra por tipo de operación (compra vs alquiler)
6. Elimina duplicados

### 4. Pesos correctos para score estructural

```python
PESOS = {
    'distrito': 30,
    'tipo_propiedad': 30,
    'precio': 30,
    'habitaciones': 3,
    'banos': 2,
    'area': 2,
    'amenities': 2,
    'ascensor': 1,
}
```

### 5. Score final

```python
score_final = alpha * score_estructural + (1 - alpha) * (score_semantico * 100)
# donde alpha = 0.6
```
