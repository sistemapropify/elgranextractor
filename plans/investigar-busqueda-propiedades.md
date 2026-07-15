# Plan: Investigar por qué el chat no encuentra "Punta de Bombón"

## Resumen del problema
El chat del canvas (intelligence) no encuentra propiedades en "Punta de Bombón" cuando se le pide agregarlas, pero el usuario afirma que existen.

## Arquitectura del Chat
1. Frontend (`canvas_chat.js`) envía POST a `/api/v1/intelligence/chat-web/api/`
2. Backend (`intelligence/views.py:chat_web_api`) delega a `ChatProcessor.process_message()`
3. El procesador usa el semantic router para determinar qué skill ejecutar
4. La skill `busqueda_propiedades` (`intelligence/skills/propiedades/skill.py`) hace búsqueda híbrida:
   - **Paso 1**: Determina modo (solo_sql, solo_semantico, hibrido, sin_parametros)
   - **Paso 2**: Filtrado SQL sobre `field_values` de `IntelligenceDocument`
   - **Paso 3**: Re-ranking semántico con FAISS
   - **Paso 4**: Construye resultado

## Posibles causas

### 1. El distrito no existe en field_values
- La colección `propiedadespropify` se alimenta de la tabla `property` en `dbpropify_be`
- Si ninguna propiedad tiene `district_name = 'Punta de Bombón'`, el SQL filter no encuentra nada
- Podría estar almacenado como "Punta de Bombon" (sin acento), "Punta Bombón", etc.

### 2. El embedding/FAISS no tiene el término
- El índice FAISS se construye con embeddings de los field_values
- Si el embedding no capturó "Punta de Bombón", la búsqueda semántica falla
- El índice tiene 147 vectores para `propiedadespropify` (visto en logs)

### 3. El router semántico no envía a la skill correcta
- El mensaje "agrega propiedad en Punta de Bombón" podría no activar `busqueda_propiedades`
- Podría activar otra skill o quedar como "no entendido"

## Pasos para investigar

### Paso 1: Verificar datos en la BD
```python
# Con conexión 'propifai':
# 1. Buscar distinct_name en field_values de IntelligenceDocument
docs = IntelligenceDocument.objects.filter(
    collection__name='propiedadespropify'
).values_list('field_values', flat=True)[:5]

# 2. Buscar district_name que contengan "Bombón" o "Bombon"
from django.db.models import Q
docs = IntelligenceDocument.objects.filter(
    collection__name='propiedadespropify'
)
for doc in docs:
    fv = doc.field_values or {}
    dist = fv.get('district_name', '')
    if 'bomb' in dist.lower():
        print(doc.source_id, dist)
```

### Paso 2: Verificar FAISS index
- Revisar si el término "Punta de Bombón" está en los embeddings
- Buscar en el archivo de índices FAISS

### Paso 3: Simular la consulta del chat
- Llamar al endpoint del chat con "agrega propiedad en Punta de Bombón" y revisar logs
- Ver qué modo de búsqueda se activa y qué filtros SQL se generan

### Paso 4: Revisar ChatProcessor
- Ver cómo el semantic router clasifica el mensaje
- Ver si `use_rag=True` permite búsqueda semántica

## Acciones correctivas posibles
1. Si el distrito no está en field_values: actualizar la colección desde la BD
2. Si el embedding no capturó el término: re-indexar FAISS
3. Si el router no clasifica bien: ajustar el prompt del router
4. Si la búsqueda SQL no encuentra: agregar búsqueda por texto parcial (ILIKE)

## Modo de implementación
Esto requiere modo **Debug** para ejecutar consultas y revisar logs en vivo.
