# SPEC — Resultados inmobiliarios y panel derecho de artefactos

**Proyecto:** Propifai / PIL  
**Estado:** Lista para implementación  
**Prioridad:** Alta  
**Alcance inicial:** búsquedas de propiedades en Chat Web  
**Fecha:** 2026-07-23

---

## 1. Problema

La respuesta actual mezcla tres responsabilidades:

1. El LLM redacta una respuesta extensa en Markdown.
2. `formatear_propiedades` genera HTML, CSS y JavaScript incrustados.
3. El chat inserta o escapa ese contenido dentro del flujo de mensajes.

Esto produce:

- Markdown visible como texto (`**precio**`, separadores y listas sin renderizar).
- Respuestas largas que dificultan encontrar las propiedades.
- Carruseles y tablas frágiles, dependientes de HTML generado en backend.
- Scripts embebidos que no son compatibles con una CSP segura.
- Pérdida del conjunto original al reemplazar resultados por `{html, total, formato}`.
- Inconsistencias entre el número de resultados encontrados, los mencionados por el LLM y los mostrados.
- Imposibilidad de cambiar de carrusel a tabla o mapa sin ejecutar nuevamente la búsqueda.
- Imposibilidad de enlazar de manera confiable una tarjeta con su propiedad en base de datos.

### Comportamiento objetivo

El centro contiene solamente:

- confirmación breve de lo entendido;
- resumen de resultados;
- máximo tres datos relevantes;
- botones para abrir o cambiar la visualización.

El panel derecho contiene los resultados verificables y permite cambiar entre:

- tarjetas;
- tabla;
- mapa;
- comparación;
- detalle de una propiedad.

La presentación debe construirse con datos estructurados, nunca con HTML o JavaScript generado por el LLM.

---

## 2. Decisiones de arquitectura

### 2.1 Separar conversación y artefactos

La API devolverá dos salidas vinculadas al mismo conjunto de resultados:

```text
respuesta breve para la conversación
                 +
artefacto estructurado para el panel derecho
```

El texto no enumerará todas las propiedades. El artefacto será la fuente visual.

### 2.2 `formatear_propiedades` deja de generar HTML

La skill se convertirá en un **normalizador de presentación**:

- recibe resultados de `busqueda_propiedades`;
- valida y normaliza campos;
- conserva `source_id` y fuente;
- devuelve un `PropertyCollectionArtifact`;
- no devuelve `<style>`, `<script>` ni manejadores `onclick`;
- no decide el diseño final.

Durante la transición se podrá conservar el formato HTML únicamente para consumidores legacy mediante `output_mode="legacy_html"`. Chat Web usará siempre `output_mode="artifact"`.

### 2.3 El frontend controla todas las vistas

Un mismo artefacto podrá mostrarse como tarjetas, tabla, mapa o comparación sin repetir la consulta ni gastar tokens adicionales.

### 2.4 Una sola fuente de verdad

El texto, contador, panel y auditoría usarán el mismo `artifact.items`.

```text
result_count == artifact.items.length == cantidad mostrada
```

No se permitirá que el LLM agregue propiedades al artefacto.

---

## 3. Experiencia de usuario

## 3.1 Respuesta central

Ejemplo:

> Encontré 8 departamentos verificados en Cayma por encima de US$150,000.  
> El rango disponible va de US$155,000 a US$235,000.

Debajo aparecerá una barra de acciones:

```text
[ Ver 8 propiedades ] [ Tarjetas ] [ Tabla ] [ Mapa ] [ Comparar ]
```

Reglas:

- Máximo recomendado: 280 caracteres antes de las acciones.
- No listar individualmente más de tres propiedades.
- No repetir descripciones completas.
- No incluir datos que no estén presentes en el artefacto.
- “Ver N propiedades” abre el panel derecho.
- Si sólo existe una propiedad, se abre directamente el detalle.

## 3.2 Panel derecho

### Cabecera persistente

- Título de la búsqueda.
- Contador total.
- Filtros aplicados como chips.
- Selector de vista.
- Cerrar.
- Expandir a pantalla completa.

Ejemplo:

```text
Departamentos en Cayma                  8 resultados
[Cayma] [Departamento] [> US$150,000]
[Tarjetas] [Tabla] [Mapa] [Comparar]             [×]
```

### Vista Tarjetas

Cada tarjeta muestra solamente:

- fotografía principal o placeholder;
- título corto;
- precio y moneda;
- distrito;
- tipo de propiedad;
- área;
- dormitorios, cuando corresponda;
- código o identificador verificable;
- estado de disponibilidad.

Acciones:

- `Ver detalle`
- `Comparar`
- `Guardar`
- `Abrir ubicación`, sólo si hay coordenadas

La descripción extensa, baños, estacionamientos, características y fuente aparecen en el detalle, no en la tarjeta.

### Vista Tabla

Columnas iniciales:

- código;
- propiedad;
- distrito;
- precio;
- área;
- dormitorios;
- estado;
- acciones.

Capacidades:

- ordenar;
- filtrar localmente;
- elegir columnas;
- paginar;
- exportar CSV;
- seleccionar propiedades para comparar.

### Vista Mapa

- Disponible únicamente si existen coordenadas válidas.
- Las propiedades sin coordenadas se indican en un contador separado.
- Seleccionar un marcador abre una tarjeta resumida.
- El mapa nunca geocodifica automáticamente una dirección inventada.

### Vista Comparar

- Entre 2 y 4 propiedades.
- Filas: precio, precio/m², área, dormitorios, baños, estacionamientos, estado y distrito.
- Los valores ausentes se muestran como “No registrado”.
- No interpretar ausencia como cero.

### Detalle

El detalle se abre dentro del panel derecho y conserva un botón “Volver a resultados”.

Secciones:

- galería;
- información principal;
- características;
- descripción;
- ubicación;
- fuente y fecha de actualización;
- acciones autorizadas.

---

## 4. Contrato de datos

## 4.1 Respuesta del endpoint

`POST /api/v1/intelligence/chat-web/api/`

```json
{
  "success": true,
  "conversation_id": "uuid",
  "message_id": "uuid",
  "response": "Encontré 8 departamentos verificados en Cayma por encima de US$150,000.",
  "reasoning_steps": [],
  "artifacts": [
    {
      "schema_version": "1.0",
      "type": "property_collection",
      "id": "properties-uuid",
      "message_id": "uuid",
      "title": "Departamentos en Cayma",
      "summary": "8 resultados verificados",
      "default_view": "cards",
      "available_views": ["cards", "table", "map", "compare"],
      "result_count": 8,
      "filters": [
        {"key": "district", "label": "Distrito", "operator": "eq", "value": "Cayma"},
        {"key": "price", "label": "Precio", "operator": "gt", "value": 150000, "currency": "USD"}
      ],
      "items": [],
      "provenance": {
        "skill": "busqueda_propiedades",
        "collection": "propiedadespropify",
        "trace_id": "uuid",
        "grounded": true
      }
    }
  ],
  "metadata": {
    "result_count": 8,
    "grounded": true,
    "trace_id": "uuid"
  }
}
```

## 4.2 Propiedad normalizada

```json
{
  "id": "source-id",
  "code": "PROP-001",
  "title": "Departamento de estreno en Cayma",
  "property_type": "Departamento",
  "operation_type": "Venta",
  "status": "Disponible",
  "district": "Cayma",
  "address": null,
  "price": 155000,
  "currency": "USD",
  "area_m2": 124.02,
  "land_area_m2": null,
  "bedrooms": 3,
  "bathrooms": 3,
  "parking_spaces": null,
  "price_per_m2": 1249.80,
  "description": "Texto registrado en la fuente.",
  "features": [],
  "images": [
    {
      "url": "https://...",
      "alt": "Departamento PROP-001",
      "is_primary": true
    }
  ],
  "location": {
    "latitude": null,
    "longitude": null
  },
  "source": {
    "collection": "propiedadespropify",
    "source_id": "source-id",
    "detail_url": null,
    "updated_at": null
  }
}
```

### Reglas de normalización

- `id` y `source.source_id` son obligatorios.
- Precio y áreas son números o `null`, nunca strings formateados.
- La moneda se normaliza a `USD`, `PEN` o `null`.
- Los textos se entregan sin HTML.
- Imágenes deben usar HTTPS y dominios autorizados.
- Coordenadas deben estar dentro de rangos válidos.
- Campos desconocidos no se inventan.
- Los nombres originales pueden conservarse en `raw_fields` sólo para depuración autorizada; no se envían por defecto al navegador.

---

## 5. Cambios en backend

## 5.1 `FormatearPropiedadesSkill`

Archivo:

`webapp/intelligence/skills/formatear_propiedades.py`

Cambios:

1. Agregar `output_mode` con valores `artifact` y `legacy_html`.
2. Hacer `artifact` el modo usado por Chat Web.
3. Reemplazar `_generar_carrusel`, `_generar_matriz` y `_generar_lista` por:
   - `_normalize_property`;
   - `_normalize_currency`;
   - `_normalize_number`;
   - `_normalize_images`;
   - `_build_available_views`;
   - `_build_property_collection_artifact`.
4. Mantener la lista completa hasta el límite real de la consulta.
5. Devolver:

```python
SkillResult.ok(
    data={
        "artifact": artifact,
        "total": len(artifact["items"]),
        "format": "artifact",
    },
    metadata={
        "artifact_type": "property_collection",
        "result_count": len(artifact["items"]),
    },
)
```

6. Nunca retornar scripts o estilos.
7. Registrar propiedades descartadas por no tener ID.

## 5.2 `ChatProcessor`

Archivo:

`webapp/intelligence/services/chat_processor.py`

Cambios:

1. No sobrescribir los resultados originales de `busqueda_propiedades`.
2. Guardar por separado:

```python
resultado["raw_items"] = skill_result.data
resultado["artifacts"] = [fmt_result.data["artifact"]]
```

3. Construir la respuesta textual breve desde estadísticas deterministas:
   - total;
   - tipo;
   - distrito;
   - rango mínimo/máximo;
   - filtros aplicados.
4. El LLM puede mejorar el tono, pero recibe esas estadísticas y no la responsabilidad de enumerar propiedades.
5. Si falla el LLM, usar el resumen determinista.
6. Propagar `artifacts` en `ChatResult.metadata` o, preferentemente, como campo explícito.
7. Verificar antes de completar:

```python
metadata["result_count"] == len(artifact["items"])
```

8. Si no coincide, marcar la ejecución como degradada y no mostrar un contador falso.

## 5.3 Endpoint

Archivo:

`webapp/intelligence/views.py`

Cambios:

- agregar `artifacts` al payload;
- mantener temporalmente `html` para compatibilidad;
- no marcar `response_text=""` cuando exista artefacto;
- devolver siempre un resumen textual;
- añadir `schema_version`;
- añadir `metadata.grounded`, `metadata.result_count` y `metadata.trace_id`.

## 5.4 FormatterAgent

Archivo:

`webapp/intelligence/agents/formatter_agent.py`

Cambios:

- eliminar la generación de HTML para búsquedas de propiedades en Chat Web;
- aplicar una plantilla corta;
- prohibir listados extensos cuando exista un artefacto;
- no elegir entre carrusel, tabla o mapa mediante LLM;
- permitir que el usuario solicite una vista, pero resolverla como `default_view`.

Plantilla:

```text
Encontré {count} {property_type_plural} verificados en {district}.
{price_summary}
```

---

## 6. Cambios en frontend

## 6.1 Estado

Agregar:

```javascript
state.artifacts = [];
state.activeArtifactId = null;
state.activeArtifactView = "cards";
state.comparisonIds = [];
```

Persistir por conversación:

- artefacto activo;
- vista seleccionada;
- propiedades seleccionadas para comparar;
- estado abierto/cerrado del panel.

## 6.2 Procesamiento de respuesta

Al recibir la API:

1. renderizar `response` como contenido conversacional seguro;
2. registrar `artifacts`;
3. abrir automáticamente el primer artefacto nuevo;
4. mostrar acciones debajo del mensaje;
5. enlazar el mensaje con `artifact.id`;
6. validar `result_count` antes de renderizar.

## 6.3 Markdown

Solución inmediata:

- implementar un renderizador restringido para párrafos, énfasis, listas, enlaces y saltos;
- sanitizar el resultado;
- no permitir HTML arbitrario.

Solución objetivo al migrar a React:

- `react-markdown`;
- `remark-gfm`;
- DOMPurify para cualquier fragmento HTML autorizado.

El artefacto de propiedades no depende del renderizador Markdown.

## 6.4 Componentes

Aunque la primera implementación siga en JavaScript vanilla, separar módulos:

```text
static/intelligence/chat-workspace/
├── artifact-store.js
├── artifact-panel.js
├── property-cards.js
├── property-table.js
├── property-map.js
├── property-compare.js
├── property-detail.js
├── message-actions.js
└── artifact-utils.js
```

No volver a concentrar la lógica dentro de `chat.js`.

## 6.5 Seguridad

- construir tarjetas mediante DOM APIs o templates controlados;
- escapar todo texto proveniente de base de datos;
- no ejecutar contenido de `description`;
- validar URLs;
- no usar `innerHTML` con datos sin sanitizar;
- no ejecutar scripts devueltos por la API;
- usar `rel="noopener noreferrer"` en enlaces externos.

---

## 7. Compatibilidad y despliegue gradual

Feature flags:

```text
CHAT_PROPERTY_ARTIFACTS_ENABLED
CHAT_LEGACY_PROPERTY_HTML_ENABLED
CHAT_PROPERTY_MAP_ENABLED
```

Etapas:

### Etapa A — Contrato y tarjetas

- artefacto estructurado;
- resumen breve;
- panel derecho;
- tarjetas;
- detalle;
- botones bajo el mensaje.

### Etapa B — Tabla y comparación

- tabla;
- ordenamiento;
- selección;
- comparación;
- exportación CSV.

### Etapa C — Mapa

- mapa;
- marcadores;
- propiedades sin coordenadas;
- pantalla completa.

### Etapa D — Retiro de HTML legacy

- eliminar `__HTML__`;
- eliminar `<style>` y `<script>` de `formatear_propiedades`;
- retirar `html` del endpoint;
- reforzar CSP.

---

## 8. Pruebas

## 8.1 Unitarias de la skill

1. Normaliza `field_values`.
2. Conserva ID y fuente.
3. Convierte `Decimal` a número.
4. Normaliza monedas.
5. Mantiene `null` para datos ausentes.
6. Descarta elementos sin ID y lo registra.
7. No devuelve `<script>`, `<style>` ni `onclick`.
8. El total coincide con `items.length`.
9. Mapa sólo aparece cuando existe al menos una coordenada válida.
10. Comparación sólo aparece cuando existen dos o más propiedades.

## 8.2 Integración

1. La búsqueda devuelve texto y artefacto.
2. Ocho resultados producen ocho elementos.
3. El panel no altera el contenido original.
4. Cambiar de tarjetas a tabla no llama nuevamente al backend.
5. El texto no menciona propiedades inexistentes.
6. El artefacto y el trace comparten `trace_id`.
7. Un fallback conserva resultados y procedencia.
8. Un mismatch se marca como degradado.

## 8.3 Frontend

1. El panel se abre con un artefacto nuevo.
2. “Ver propiedades” reabre el artefacto correcto.
3. Cerrar el panel no borra resultados.
4. Las tarjetas toleran campos e imágenes ausentes.
5. El teclado opera selector de vistas y carrusel.
6. El diseño funciona a 360, 768, 1280 y 1440 px.
7. No aparecen `**` ni Markdown crudo.
8. No existen errores JavaScript ni recursos 404.

---

## 9. Observabilidad

Eventos:

```text
artifact.created
artifact.opened
artifact.view_changed
artifact.item_opened
artifact.compare_started
artifact.exported
artifact.validation_failed
```

Campos mínimos:

- `trace_id`;
- `conversation_id`;
- `message_id`;
- `artifact_id`;
- `artifact_type`;
- `result_count`;
- `view`;
- `validation_status`;
- `latency_ms`.

No registrar descripciones completas ni información personal en eventos.

---

## 10. Criterios de aceptación de la primera entrega

La Etapa A está lista cuando:

1. Una búsqueda devuelve `response` y `artifacts`.
2. La respuesta central ocupa como máximo un bloque breve.
3. No se ve Markdown crudo.
4. El panel se abre automáticamente.
5. Todas las propiedades verificadas aparecen en tarjetas.
6. Cada tarjeta tiene ID y fuente.
7. El detalle se abre y puede cerrarse sin perder la búsqueda.
8. El contador coincide en backend, mensaje y panel.
9. No existe HTML ejecutable proveniente de la skill.
10. Las pruebas unitarias y de integración pasan.
11. El flujo legacy permanece disponible mediante feature flag.
12. La observabilidad registra creación, apertura y fallos de validación.

---

## 11. Orden de implementación recomendado

1. Crear serializador/normalizador de `PropertyCollectionArtifact`.
2. Agregar pruebas unitarias del contrato.
3. Modificar `formatear_propiedades` para devolver el artefacto.
4. Separar `raw_items` de `artifacts` en `ChatProcessor`.
5. Exponer `artifacts` desde el endpoint.
6. Crear store de artefactos en frontend.
7. Implementar acciones debajo del mensaje.
8. Implementar tarjetas y detalle en el panel derecho.
9. Agregar renderizado seguro del texto.
10. Añadir telemetría.
11. Probar con consultas reales conocidas.
12. Activar el feature flag primero para usuarios internos.

---

## 12. Fuera de alcance de la primera entrega

- Plotly 3D.
- PDFs generados.
- HTML interactivo arbitrario.
- Edición de propiedades desde el panel.
- Favoritos persistentes si todavía no existe el modelo backend.
- Geocodificación automática.
- Reescritura completa del chat en React.

La arquitectura queda preparada para incorporar esos artefactos posteriormente sin modificar el contrato conversacional.
