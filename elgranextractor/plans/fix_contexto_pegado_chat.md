# Fix: Contexto pegado en chat-web

## Problema
Cuando el usuario pregunta "propiedades en Cayma" y luego "cuantas hay en total", el chat sigue filtrando solo Cayma porque el `contexto_activo` guarda `{distrito: "Cayma"}` y lo hereda en el siguiente turno.

## Causa raíz
En [`chat_processor.py:1185-1190`](../webapp/intelligence/services/chat_processor.py:1185), la detección de "búsqueda nueva" solo verifica si el mensaje tiene `distrito` o `tipo_propiedad`. Si no tiene, asume "seguimiento" y fusiona el contexto anterior.

## Fix propuesto
Agregar detección de palabras/frases que indican que el usuario QUIERE ampliar/quitar filtros:

### En `chat_processor.py` (línea 1185)
Agregar una lista de palabras que indican "broaden scope":

```python
# Palabras que indican que el usuario QUIERE quitar filtros (scope general)
BROADEN_KEYWORDS = ['en total', 'todos', 'todas', 'todas las', 'general', 
                     'global', 'completo', 'completa', 'sin filtro',
                     'todos los distritos', 'todas las zonas',
                     'cualquier distrito', 'cualquier zona',
                     'total', 'todo', 'todos los']

es_busqueda_nueva = bool(
    skill_params.get('distrito') or skill_params.get('tipo_propiedad')
) or any(
    kw in ctx.message.lower() for kw in BROADEN_KEYWORDS
)
```

### En el merge de contexto (línea 1205-1207)
Si se detecta "broaden scope", NO heredar el distrito/tipo del contexto activo:

```python
if any(kw in ctx.message.lower() for kw in BROADEN_KEYWORDS):
    # Usuario quiere ver todo, no heredar filtros anteriores
    params_fusionados = {}
    params_fusionados.update(skill_params)
    params_fusionados.update(params_resueltos)
    log.info(f"[_process_skill_request] Broadening detectado. NO se heredan filtros anteriores.")
else:
    # Seguimiento normal: heredar contexto activo
    params_fusionados = {}
    params_fusionados.update(contexto_activo.to_dict())
    params_fusionados.update(skill_params)
    params_fusionados.update(params_resueltos)
```

## Archivos a modificar
- `webapp/intelligence/services/chat_processor.py` (líneas 1185-1207)
