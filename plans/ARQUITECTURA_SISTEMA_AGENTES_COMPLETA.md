# Arquitectura integral del sistema inteligente Propifai / PIL

**Versión:** 4.0

**Actualización:** 2026-07-23

**Alcance:** estado completo consolidado durante el ciclo de diagnóstico e implementación
**Fuente de pendientes:** `plans/implementaciones_pendientes/REGISTRO_MAESTRO.md`

---

## 1. Propósito del sistema

Propifai/PIL es una plataforma inmobiliaria inteligente que recibe consultas en
lenguaje natural, selecciona agentes y skills, consulta inventario y fuentes
vectoriales, valida resultados y presenta respuestas conversacionales junto con
artefactos visuales.

La arquitectura actual busca resolver cinco problemas centrales:

1. recuperar propiedades reales sin inventar datos;
2. conservar todos los requisitos de una consulta;
3. detectar errores silenciosos antes de responder;
4. cambiar de plan de forma segura cuando un resultado es incorrecto;
5. convertir las trazas en aprendizaje operativo futuro.

El sistema no considera equivalentes estos conceptos:

```text
HTTP 200
≠ ejecución técnica exitosa
≠ requisitos cumplidos
≠ respuesta correcta
≠ experiencia de usuario correcta
```

---

## 2. Transformación realizada durante este ciclo

### 2.1 Estado inicial

El sistema podía corregirse dentro de una conversación mediante guardrails,
fallbacks y reintentos, pero no aprendía entre conversaciones. Los errores se
detectaban leyendo logs manualmente.

Además, la ruta agentic era principalmente lineal:

```text
consulta → supervisor → agente → skill → resultados → formatter → respuesta
```

Una skill sin excepción se consideraba exitosa incluso cuando:

- había omitido filtros;
- devolvía tipos incompatibles;
- devolvía propiedades vendidas;
- entregaba todo el inventario;
- no podía demostrar la recomendación solicitada;
- el primer agente había fallado y se usaba un fallback;
- el LLM formateador presentaba resultados incompletos o inventados.

### 2.2 Incidentes reales que motivaron los cambios

Durante el diagnóstico se observaron estos casos:

| Incidente | Comportamiento incorrecto |
|---|---|
| Terreno en Cerro Colorado | no encontraba una propiedad que supuestamente existía; después se verificó que estaba vendida |
| Departamentos en Cayma > USD 150 000 | había ocho coincidencias, pero la respuesta mostraba sólo algunas sin explicar el límite |
| Terrenos en Cerro Colorado | se mezclaban estados disponibles, vendidos y en captación |
| Propiedad para tienda de abarrotes | la auditoría interpretó propiedades existentes como inventadas por falta de evidencia estructurada |
| Construir un colegio | devolvió 147 propiedades, incluyendo departamentos, dúplex y oficinas |
| Consulta escolar en dos turnos | perdió “construir un colegio” y trató Cayma/500 m²/300 alumnos como consulta independiente |
| Fallback AgentGraph → LangGraph | el dashboard mostraba `completed`, ocultando el fallo primario |
| Requisitos del agente | distrito, área y alumnos se marcaron cumplidos sólo porque existía algún filtro |
| Chat web | respuesta Markdown aparecía como texto plano con `**`, propiedades pegadas y sin jerarquía |
| Panel derecho | no se podía redimensionar y las tarjetas iniciales no mostraban imágenes |
| Detalle de propiedad | faltaban galería en carrusel y videos |
| Producción Azure | algunos assets Canvas devolvían 404/HTML y fallaban por MIME type |

### 2.3 Resultado de la transformación

La arquitectura vigente es:

```text
mensaje del usuario
  → resolver tarea conversacional
  → construir SearchPlan canónico
  → preflight determinista
  → Supervisor
  → agente(s) ReAct
  → skills
  → evidencia por requisito
  → agregación de resultados
  → Nivel 1: evaluación determinista
  → Nivel 2: juez semántico
  → Nivel 3A: advisory con autoridad limitada
  → revalidación si hubo replan
  → respuesta fundamentada
  → artefactos para panel derecho
  → auditoría posterior
  → traza final
```

---

## 3. Stack y componentes principales

| Capa | Tecnología |
|---|---|
| Backend | Django 5 + Django REST Framework |
| Base principal | Azure SQL mediante `mssql-django` |
| Recuperación | búsqueda exacta, SQL, RAG, FAISS HNSW |
| Embeddings | `multilingual-e5-small`, 384 dimensiones |
| LLM | DeepSeek API |
| Orquestación primaria | `AgentGraphBuilder` |
| Fallback 1 | `PILOrchestrator` / LangGraph |
| Fallback 2 | pipeline secuencial legacy |
| Frontend | HTML, CSS y JavaScript |
| Archivos estáticos | WhiteNoise / `collectstatic` |
| Telemetría | trazas persistidas, eventos estructurados y dashboard |

---

## 4. Mapa actualizado del código

```text
webapp/intelligence/
├── agents/
│   ├── base_agent.py
│   ├── orchestrator.py
│   ├── supervisor.py
│   ├── propiedades_agent.py
│   ├── mercado_agent.py
│   ├── requerimientos_agent.py
│   ├── skill_preconditions.py
│   ├── execution_evaluator.py
│   ├── semantic_execution_judge.py
│   └── semantic_advisory_controller.py
├── search/
│   ├── contracts.py
│   └── normalizer.py
├── services/
│   ├── chat_processor.py
│   ├── conversation_task_state.py
│   ├── property_artifacts.py
│   ├── llm.py
│   ├── rag.py
│   ├── metrics.py
│   └── episodic_memory.py
├── learning/
│   ├── events.py
│   ├── auditor.py
│   └── redaction.py
├── skills/
│   ├── propiedades/skill.py
│   ├── busqueda_exacta.py
│   ├── formatear_propiedades.py
│   ├── matching_hybrid.py
│   └── acm_analisis.py
├── tests/
│   ├── test_execution_evaluator.py
│   ├── test_semantic_execution_judge.py
│   ├── test_semantic_advisory_controller.py
│   ├── test_conversation_task_state.py
│   ├── test_agent_requirement_evidence.py
│   └── test_property_artifacts.py
└── static/intelligence/
    ├── chat.js
    └── chat-workspace.css
```

---

## 5. Entrada y continuidad conversacional

### 5.1 Problema anterior

El ReAct loop conservaba `original_message` dentro de una ejecución, pero una
pregunta de aclaración terminaba ese turno. El mensaje siguiente iniciaba otra
ejecución y podía perder la intención original.

Ejemplo:

```text
Turno 1: propiedades ideales para construir un colegio
Turno 2: en Cayma, 500 metros, 300 alumnos
```

El turno 2 se interpretaba como una búsqueda inmobiliaria general.

### 5.2 Estado estructurado de tarea

`ConversationTaskState` utiliza:

```text
Conversation.metadata.pending_agent_task
```

Ejemplo:

```json
{
  "schema_version": 1,
  "intent": "school_site_search",
  "purpose": "construir_colegio",
  "status": "collecting_requirements",
  "required_fields": [
    "distrito",
    "area_min",
    "cantidad_alumnos"
  ],
  "optional_fields": ["presupuesto_max"],
  "collected_fields": {},
  "missing_fields": [
    "distrito",
    "area_min",
    "cantidad_alumnos"
  ]
}
```

### 5.3 Máquina de estados

```text
new
  → collecting_requirements
  → ready
  → executing
  → validating
  → completed

Ramas:
  → needs_task_confirmation
  → cancelled_by_new_intent
  → blocked
  → failed
```

### 5.4 Relación entre mensajes

El mensaje nuevo se clasifica como:

- `continuation`: aporta campos a la tarea pendiente;
- `new_task`: contiene otra intención explícita;
- `ambiguous`: no hay evidencia suficiente y se pregunta al usuario.

Ejemplo de continuación:

```text
“En Cayma con un área de 500 metros y para 300 alumnos”
```

Ejemplo de nueva tarea:

```text
“Ahora muéstrame departamentos en Yanahuara”
```

### 5.5 Impacto

- la consulta no finaliza mientras falten requisitos obligatorios;
- se pregunta únicamente por campos faltantes;
- las consultas simples siguen siendo de un turno;
- el contexto operativo no se convierte en memoria personal del usuario;
- una consulta nueva no hereda accidentalmente criterios anteriores.

---

## 6. Contrato canónico de búsqueda

### 6.1 Motivo

Antes, cada ruta podía interpretar el mensaje de forma diferente. El LLM podía
omitir un filtro al crear parámetros para la skill.

### 6.2 `SearchPlan`

`SearchPlanNormalizer` crea una sola interpretación previa al routing:

```json
{
  "query": "terrenos en Cayma por menos de 190000 dólares",
  "collections": ["propiedadespropify"],
  "conditions": [
    {
      "logical_name": "distrito",
      "field_name": "district_name",
      "operator": "eq",
      "value": "Cayma",
      "value_type": "string"
    },
    {
      "logical_name": "tipo_propiedad",
      "field_name": "property_type_name",
      "operator": "eq",
      "value": "Terreno",
      "value_type": "string"
    },
    {
      "logical_name": "precio_max",
      "field_name": "price",
      "operator": "lte",
      "value": 190000,
      "value_type": "decimal",
      "currency": "USD"
    }
  ],
  "semantic_query": "...",
  "top_k": 9999
}
```

El plan canónico prevalece sobre los parámetros libres producidos por el LLM.

### 6.3 Extracciones añadidas

- operadores de precio: menor, mayor, desde, hasta;
- tipo de propiedad;
- distrito;
- habitaciones;
- moneda;
- área mínima expresada como `500 m²`, `500 metros` o `área de 500`;
- estado;
- normalización de consultas para construir colegio a candidatos tipo terreno.

### 6.4 Impacto

- AgentGraph y fallbacks pueden reutilizar el mismo contrato;
- los filtros exactos no dependen de similitud semántica;
- el dashboard puede mostrar filtros realmente aplicados;
- un replan seguro reutiliza el plan del usuario y no inventa otro.

---

## 7. Búsqueda de propiedades

### 7.1 Flujo

```text
SearchPlan
  → búsqueda semántica FAISS
  → refinamiento con filtros exactos
  → fallback SQL si corresponde
  → validación por documento
  → resultados estructurados
```

### 7.2 Reglas introducidas

- los filtros exactos se aplican después de la recuperación semántica;
- si la búsqueda semántica no entrega coincidencias válidas, puede usarse SQL;
- distrito, tipo, precio, habitaciones, área y estado se verifican por campo;
- una propiedad sin el campo necesario no se considera automáticamente válida;
- estados vendidos no se presentan como disponibles;
- una búsqueda no debe devolver toda la colección sólo porque el texto sea
  semánticamente amplio.

### 7.3 Cantidad de resultados

La recuperación puede encontrar más propiedades que las presentadas. La
respuesta y el artefacto deben indicar:

- coincidencias totales;
- cantidad mostrada;
- criterio de orden;
- paginación o límite.

Esto evita afirmar “encontré tres” cuando existen ocho y sólo se mostraron tres
por formato.

---

## 8. ReAct loop y requisitos

### 8.1 Flujo

```text
extract_requirements()
  → checklist inmutable de requisitos
  → think
  → act
  → observe
  → actualizar evidencia
  → continuar o finalizar
```

### 8.2 Correcciones realizadas

- `original_message` no cambia durante el loop;
- requisitos satisfechos no vuelven a pendientes;
- una skill sólo satisface tipos de requisito compatibles;
- skills no disponibles se excluyen por precondiciones;
- fallos repetidos excluyen una skill;
- `matching_hibrido` no se considera una búsqueda inmobiliaria genérica;
- cero resultados se confirma usando skills de búsqueda reales;
- formato se detecta determinísticamente y no como requisito fantasma;
- máximo de iteraciones y presupuesto permanecen acotados.

### 8.3 Evidencia específica

Antes:

```text
existe cualquier filtro → todos los requisitos de filtro satisfechos
```

Ahora:

| Requisito | Evidencia exigida |
|---|---|
| Cayma | `distrito` aplicado |
| mínimo 500 m² | `area_min` aplicado |
| menos de 190000 | `precio_max` aplicado |
| terreno | `tipo_propiedad` aplicado |
| disponible | `condicion` aplicada |

Estados:

```text
pending
verified
acknowledged_unverified
```

“Capacidad para 300 alumnos” se conserva como
`acknowledged_unverified`: el inventario no puede demostrarla.

### 8.4 Impacto

- el agente deja de declarar éxito sólo por tener una lista;
- los pasos del dashboard muestran requisitos totales y satisfechos;
- los requisitos no demostrables llegan como limitaciones a la respuesta;
- se reducen loops y skills irrelevantes.

---

## 9. Consultas de aptitud y recomendaciones

### 9.1 Problema

La búsqueda semántica interpretaba “ideal para construir un colegio” como una
consulta parecida a cualquier propiedad, devolviendo departamentos, dúplex,
casas y oficinas.

### 9.2 Nuevo tratamiento

Una consulta especializada tiene dos conjuntos de criterios.

Verificables:

- distrito;
- tipo;
- área;
- precio;
- disponibilidad.

No verificables únicamente con inventario:

- zonificación educativa;
- uso permitido;
- accesibilidad normativa;
- seguridad;
- capacidad técnica para alumnos;
- rentabilidad.

### 9.3 Respuesta permitida

```text
“Encontré terrenos candidatos que cumplen ubicación, área y disponibilidad”.
```

### 9.4 Respuesta prohibida

```text
“Estos terrenos son aptos para construir un colegio de 300 alumnos”.
```

### 9.5 Impacto

- no se presenta similitud semántica como prueba técnica;
- el usuario recibe candidatos reales y limitaciones claras;
- futuras skills legales/urbanísticas podrán completar la evaluación.

---

## 10. Nivel 1: evaluador determinista

### 10.1 Componente

```text
agents/execution_evaluator.py
```

### 10.2 Preflight

Antes de ejecutar:

- detecta intención de aptitud;
- comprueba criterios mínimos;
- evita búsquedas masivas prematuras;
- solicita aclaraciones.

### 10.3 Evaluación posterior

Después de ejecutar:

- comprueba agentes exitosos;
- cuenta resultados;
- valida filtros del SearchPlan;
- detecta tipos incompatibles;
- detecta estados incompatibles;
- detecta conjuntos excesivamente amplios;
- comprueba requisitos y evidencia.

### 10.4 Veredictos

| Veredicto | Acción |
|---|---|
| `pass` | continuar |
| `replan` | repetir con corrección segura |
| `clarify` | preguntar sin mostrar inventario |
| `block` | impedir respuesta no fiable |

### 10.5 Impacto

- bajo costo y comportamiento reproducible;
- detiene la mayoría de errores de filtros;
- convierte errores silenciosos en estados observables;
- vuelve a validar cualquier reintento del Nivel 3A.

---

## 11. Nivel 2: juez semántico

### 11.1 Componente

```text
agents/semantic_execution_judge.py
```

### 11.2 Activación

Es selectiva:

- consultas complejas;
- aptitud o recomendación;
- veredictos deterministas `clarify`, `replan` o `block`;
- situaciones donde las reglas pueden ser insuficientes.

### 11.3 Entrada

- consulta;
- evaluación determinista;
- intento;
- muestra máxima de ocho propiedades;
- campos truncados y controlados.

### 11.4 Salida

```json
{
  "verdict": "pass|replan|clarify|block",
  "confidence": 0.95,
  "reason": "...",
  "signals": ["TYPE_MISMATCH"],
  "missing_information": [],
  "suggested_action": "..."
}
```

### 11.5 Seguridad

- JSON inválido → `failed`;
- timeout/API caída → `failed`;
- no genera respuesta al usuario;
- no ejecuta tools;
- en `shadow` no tiene autoridad.

### 11.6 Impacto

- detecta incoherencias semánticas;
- registra desacuerdos con Nivel 1;
- crea evidencia para calibración;
- no se convierte en punto único de fallo.

---

## 12. Nivel 3A: advisory seguro

### 12.1 Componente

```text
agents/semantic_advisory_controller.py
```

### 12.2 Objetivo

Permitir que una observación semántica de alta confianza tenga impacto real sin
dar control libre al LLM.

### 12.3 Acciones permitidas

- `clarify`;
- `block`;
- `replan`.

### 12.4 Condiciones

```text
modo advisory/enforced
+ juez completado
+ confianza >= umbral
+ acción incluida en allowlist
+ evidencia estructurada
+ presupuesto de reintento disponible
```

### 12.5 Restricciones

- `clarify` exige campos faltantes;
- `block` exige señal de riesgo permitida;
- `replan` reutiliza el SearchPlan canónico;
- máximo un reintento total;
- Nivel 1 valida el resultado corregido;
- no se aceptan filtros libres del juez.

### 12.6 Prohibiciones

- editar código;
- modificar prompts;
- ejecutar SQL;
- cambiar datos;
- alterar permisos;
- crear migraciones;
- aplicar aprendizaje persistente;
- reintentos ilimitados.

### 12.7 Configuración

```env
EXECUTION_JUDGE_MODE=advisory
EXECUTION_JUDGE_MIN_CONFIDENCE=0.90
```

### 12.8 Impacto

- el sistema puede cambiar de plan ante incoherencias;
- una detección semántica grave puede impedir una mala respuesta;
- toda autoridad queda registrada;
- el LLM sigue subordinado a contratos deterministas.

---

## 13. Fallbacks y degradación

### 13.1 Rutas

```text
AgentGraph
  → LangGraph
  → pipeline secuencial
```

### 13.2 Problema anterior

Si AgentGraph fallaba y LangGraph respondía, la consulta figuraba como
`completed`. Se perdía el fallo interno.

### 13.3 Comportamiento actual

```text
orchestration.agent_graph.failed
fallback.activated
execution.agent.completed
trace.completed(status=completed_degraded)
```

El éxito del fallback no borra:

- ruta fallida;
- error;
- latencia perdida;
- cantidad de reintentos;
- motivo de activación.

### 13.4 Impacto

- confiabilidad medible por ruta;
- errores primarios visibles;
- dashboard capaz de separar éxito limpio y éxito degradado;
- patrones de fallback disponibles para aprendizaje futuro.

---

## 14. Observabilidad y dashboard de aprendizaje

### 14.1 Objetivo

Capturar cada etapa y permitir que el sistema y el equipo detecten errores sin
leer logs terminales manualmente.

### 14.2 Eventos principales

| Evento | Significado |
|---|---|
| `trace.started` | inicio |
| `orchestration.agent_graph.started` | ruta primaria |
| `orchestration.agent_graph.failed` | fallo primario |
| `fallback.activated` | activación de respaldo |
| `execution.agent.completed` | agente, skills, requisitos |
| `evaluation.completed` | Nivel 1 |
| `evaluation.semantic.completed` | Nivel 2 |
| `evaluation.advisory.decided` | Nivel 3A |
| `audit.completed` | auditoría posterior |
| `trace.completed` | estado final |

### 14.3 Estados de calidad

- `completed`;
- `completed_degraded`;
- `needs_clarification`;
- `blocked_by_evaluator`;
- `needs_review`;
- `failed`.

### 14.4 Datos por traza

- consulta redactada/hash;
- ruta;
- latencia;
- agente;
- iteraciones;
- skills;
- resultados;
- filtros;
- requisitos totales;
- requisitos satisfechos;
- evidencia;
- fallbacks;
- veredicto determinista;
- veredicto semántico;
- desacuerdo;
- autoridad advisory;
- auditoría final.

El resumen incorpora además:

- juicios semánticos ejecutados y fallidos;
- desacuerdos entre Niveles 1 y 2;
- tasa de desacuerdo;
- decisiones advisory;
- autoridad aplicada;
- tasa de intervención;
- acciones `clarify`, `block` y `replan`.

El detalle de una traza presenta en paralelo el veredicto determinista, el
veredicto semántico y la decisión del controlador advisory.

### 14.5 Corrección de falsos positivos de auditoría

La auditoría llegó a marcar propiedades reales como inventadas porque la
ejecución sólo reportaba el número de resultados y no la evidencia de cada
propiedad. Se agregó `result_evidence` para comparar identificadores y campos
recuperados contra afirmaciones del formatter.

### 14.6 Impacto

- una traza “completada” ya no oculta errores internos;
- el dashboard puede explicar por qué una respuesta es sospechosa;
- se obtiene materia prima para incidentes, replay y regresión;
- se diferencian problemas técnicos, de búsqueda y de grounding.

---

## 15. Auditoría posterior

El evaluador previo impide errores antes de responder. El auditor posterior es
una segunda línea de defensa.

Evalúa:

- grounding;
- conteos;
- filtros omitidos;
- datos supuestamente inventados;
- pasos marcados exitosos sin requisitos;
- consistencia entre ejecución y respuesta.

El auditor no modifica la respuesta ya emitida; marca la traza como
`needs_review` y produce señales para aprendizaje.

---

## 16. Interfaz Chat Workspace de tres paneles

### 16.1 Objetivo

Evolucionar desde un chat Vanilla simple hacia una interfaz de trabajo:

```text
┌──────────────┬──────────────────────────┬─────────────────────┐
│ navegación   │ conversación             │ resultado activo    │
│ herramientas │ mensajes + razonamiento  │ HTML/gráficos/datos │
│ proyectos    │ composer                 │ detalle propiedad   │
│ chats/login  │                          │                     │
└──────────────┴──────────────────────────┴─────────────────────┘
```

### 16.2 Panel izquierdo

- herramientas;
- proyectos;
- conversaciones;
- usuario y estado de sesión;
- modo colapsable.

### 16.3 Panel central

- conversación;
- pasos de ejecución;
- scroll independiente;
- Markdown renderizado y sanitizado;
- respuestas separadas de las trazas;
- tarjetas resumidas.

Se corrigió la falta de scroll que hacía que la respuesta quedara fuera de
vista después de mostrar razonamiento.

### 16.4 Panel derecho

- ancho redimensionable;
- estado vacío;
- colección de propiedades;
- detalle;
- galería;
- videos;
- futuros HTML, PDF y gráficos.

### 16.5 Diseño

- identidad Propifai;
- logo del proyecto;
- verde oscuro como acento/borde;
- fondos verde muy claro en tema luminoso;
- tema oscuro;
- contrastes progresivos;
- tipografía moderna y jerarquía profesional.

---

## 17. Respuestas estructuradas y Markdown

### 17.1 Problema anterior

El frontend mostraba:

```text
**Precio:** ... **Tipo:** ... **Distrito:** ...
```

como texto plano, sin espacios ni separación entre propiedades.

### 17.2 Corrección

- renderizado Markdown controlado;
- párrafos y tarjetas;
- separación visual por propiedad;
- datos principales en el centro;
- acciones/tags para abrir vistas en el panel derecho;
- el razonamiento técnico se diferencia de la respuesta final.

### 17.3 Principio

El LLM no debe decidir toda la estructura visual. La respuesta utiliza datos
estructurados y el frontend selecciona el componente apropiado.

---

## 18. Artefactos de propiedades

### 18.1 Colección

```json
{
  "artifact_type": "property_collection",
  "result_count": 3,
  "items": [
    {
      "property_id": "PROP000220",
      "title": "Terreno Urb Sol y Luna",
      "price": 86000,
      "currency": "USD",
      "district": "Jose Luis Bustamante y Rivero",
      "status": "Disponible",
      "image_url": "..."
    }
  ]
}
```

### 18.2 Detalle

Al seleccionar una tarjeta:

- se usa el identificador real;
- se consulta información completa;
- se muestran campos dinámicos;
- se abre el panel derecho;
- no se ejecuta una búsqueda semántica nueva.

Esto no es una skill de razonamiento: es una operación determinista de lectura.

### 18.3 Galería y videos

- carrusel de imágenes;
- controles anterior/siguiente;
- miniaturas;
- fallback visual si no hay imagen;
- videos debajo de la galería;
- URLs normalizadas desde los datos de propiedad.

### 18.4 Corrección de tarjetas sin imagen

Las tarjetas iniciales deben usar una imagen principal normalizada desde los
campos disponibles y mostrar placeholder cuando no exista.

### 18.5 Extensibilidad

El mismo contrato de artefactos permitirá:

- Plotly 2D/3D interactivo;
- mapas;
- tablas;
- comparadores;
- HTML aislado;
- PDFs generados;
- reportes y descargas.

---

## 19. Seguridad de contenido visual

Los HTMLs generados o adjuntos deben:

- ejecutarse en iframe sandbox;
- mantener CSP;
- no ejecutar scripts arbitrarios en el DOM principal;
- sanitizar Markdown;
- cargar datos por contratos;
- separar texto confiable de contenido generado.

---

## 20. Dashboard general de la plataforma

El dashboard principal no debe ser únicamente un dashboard ACM. Debe resumir
todos los módulos:

- inventario;
- requerimientos;
- matches;
- agentes;
- conversaciones;
- aprendizaje/observabilidad;
- campañas;
- mercado;
- operaciones;
- salud del sistema.

El ACM es un módulo analítico, no el centro conceptual de Propifai.

Principios visuales:

- diseño profesional oscuro;
- colores consistentes con el sistema;
- métricas globales;
- accesos por módulo;
- estados y alertas;
- actividad reciente;
- permisos visibles por nivel.

---

## 21. Roles y permisos

El sistema utiliza niveles 1–5. Un mensaje como:

```text
Niveles requeridos: [4, 5]. Su nivel: 2
```

significa que la vista o skill fue protegida para roles administrativos.

La arquitectura debe separar:

- permiso para ver un dashboard;
- permiso para ejecutar una skill;
- permiso para mutar datos;
- permiso para ver telemetría sensible.

La observabilidad de Nivel 1 es sólo lectura y no debe modificar el sistema.

---

## 22. Assets y despliegue

### 22.1 Incidente

En Azure se observaron:

```text
canvas.css → MIME text/html
canvas_*.js → 404
```

Esto indica que el servidor devolvió una página HTML de error para una URL
estática.

### 22.2 Controles necesarios

- ejecutar `collectstatic`;
- verificar rutas y nombres exactos;
- servir CSS como `text/css`;
- servir JS con MIME JavaScript;
- no redirigir `/static/` a login o página HTML;
- validar WhiteNoise;
- probar assets del manifest después del deploy;
- versionar recursos para invalidar caché.

---

## 23. Roadmap de aprendizaje entre conversaciones

Este roadmap es distinto de los niveles runtime.

### Track A: robustez dentro de la ejecución

| Nivel | Estado |
|---|---|
| Nivel 1 determinista | implementado |
| Nivel 2 juez semántico | implementado, shadow por defecto |
| Nivel 3A advisory | implementado |
| Nivel 3B activación calibrada | pendiente |
| Nivel 3C corrección persistente | bloqueado |

### Track B: aprendizaje global

| Nivel | Objetivo | Estado |
|---|---|---|
| 0 | baseline/congelamiento | requiere auditoría |
| 1 | trazabilidad/taxonomía | en desarrollo |
| 2 | patrones e incidentes | especificado/parcial |
| 3 | replay/regresión continua | pendiente de datos |
| 4 | propuestas en shadow | pendiente |
| 5 | aprobación y canary | pendiente |
| 6 | autocorrección limitada | pendiente |
| 7 | optimización avanzada | no diseñada |

Track B excluye memoria y personalización por usuario.

---

## 24. Qué puede aprender y qué no

### Permitido progresivamente

- detectar patrones;
- agrupar incidentes;
- crear casos de regresión;
- proponer reglas;
- comparar versiones;
- sugerir thresholds;
- canary de configuraciones aprobadas;
- rollback controlado.

### No permitido actualmente

- editar código desde una conversación;
- ejecutar migraciones automáticamente;
- cambiar permisos;
- modificar datos;
- desplegar prompts sin replay;
- tomar una sola consulta como regla global;
- aprender preferencias individuales dentro de este track.

---

## 25. Métricas de impacto

### Calidad

- tasa de respuestas no fundamentadas;
- filtros cumplidos por consulta;
- propiedades incompatibles bloqueadas;
- respuestas con estados vendidos;
- consultas masivas evitadas;
- falsos positivos del auditor.

### Agentes

- éxito limpio;
- éxito degradado;
- fallos AgentGraph;
- uso de fallback;
- iteraciones;
- replans;
- desacuerdos Nivel 1/Nivel 2;
- autoridad Nivel 3A.

### Operación

- latencia por etapa;
- costo LLM;
- cobertura de trazas;
- eventos inválidos;
- tiempo hasta detectar incidentes;
- tiempo hasta resolverlos.

### Interfaz

- apertura del panel derecho;
- propiedades con imagen;
- errores de galería;
- renderizado Markdown;
- uso de acciones;
- errores de assets.

---

## 26. Pruebas implementadas

Suites principales:

- `test_execution_evaluator.py`;
- `test_semantic_execution_judge.py`;
- `test_semantic_advisory_controller.py`;
- `test_conversation_task_state.py`;
- `test_agent_requirement_evidence.py`;
- `test_property_artifacts.py`.

Casos cubiertos:

- consulta simple;
- consulta escolar incompleta;
- continuación multitur​no;
- cambio de tarea;
- extracción de área;
- filtros escolares;
- departamento incompatible;
- shadow sin autoridad;
- aclaración advisory;
- señal de bloqueo permitida;
- replan máximo una vez;
- fallo seguro del juez;
- artefactos de propiedad.

Última ejecución focalizada: **27 pruebas aprobadas**.

---

## 27. Configuración actual

```env
# off | shadow | advisory | enforced
EXECUTION_JUDGE_MODE=shadow

EXECUTION_JUDGE_MIN_CONFIDENCE=0.90
```

Recomendación:

| Entorno | Modo |
|---|---|
| Desarrollo | advisory |
| Staging | advisory |
| Producción inicial | shadow |
| Producción calibrada | advisory selectivo |

Los niveles 1–3A y el estado conversacional no requieren migración: utilizan
estructuras Python y metadata JSON existente.

---

## 28. Impacto global antes/después

| Dimensión | Antes | Ahora |
|---|---|---|
| Consulta multitur​no | podía perder intención | tarea estructurada |
| Filtros | interpretaciones divergentes | SearchPlan único |
| Requisitos | cualquier filtro podía cumplirlos | evidencia específica |
| Éxito | skill sin excepción | ejecución validada |
| Recomendaciones | similitud = aptitud | candidatos + limitaciones |
| Replanificación | limitada/casi lineal | N1 + N3A acotados |
| Juez semántico | no existía | Nivel 2 |
| Autoridad LLM | implícita en formatter | controlador limitado |
| Fallback | ocultaba fallo primario | estado degradado |
| Grounding | evidencia insuficiente | `result_evidence` |
| Respuesta | texto/HTML frágil | Markdown + artefactos |
| Detalle | mezclado con respuesta | panel derecho |
| Imágenes/videos | incompletos | carrusel y media |
| Aprendizaje | logs manuales | trazas y roadmap |
| Pendientes | dispersos en specs | registro maestro |

---

## 29. Limitaciones vigentes

- los contratos multitur​no todavía deben extenderse a más intenciones;
- la zonificación requiere una fuente/skill especializada;
- Nivel 2 necesita calibración con trazas reales;
- Nivel 3A no debe activarse globalmente sin medir falsos positivos;
- el aprendizaje global todavía no tiene replay completo;
- el dashboard general debe continuar integrando módulos;
- Plotly, PDF y HTML extensible siguen como expansión;
- el inventario depende de calidad y actualización de datos;
- Redis local no disponible genera warnings y limita algunas métricas/caché;
- existen documentos históricos cuyo estado requiere auditoría.

---

## 30. Gobierno documental y pendientes

Fuentes de verdad:

| Archivo | Función |
|---|---|
| `ARQUITECTURA_SISTEMA_AGENTES_COMPLETA.md` | arquitectura integral actual |
| `SPEC_CICLO_EVALUACION_REPLANIFICACION_AGENTICA.md` | niveles runtime |
| `aprendizaje_sistema/ROADMAP_APRENDIZAJE_SEGURO_PIL.md` | aprendizaje global |
| `implementaciones_pendientes/REGISTRO_MAESTRO.md` | estado vivo |
| `implementaciones_pendientes/TRACK_A_CICLO_AGENTIC.md` | niveles agentic |
| `implementaciones_pendientes/TRACK_B_APRENDIZAJE_GLOBAL.md` | niveles globales |

Estados permitidos:

```text
propuesto
especificado
en_desarrollo
implementado_shadow
implementado
bloqueado
descartado
```

Un spec no se considera implementado sólo porque exista. Requiere evidencia de
código, pruebas y validación operativa.

---

## 31. Qué es Propifai/PIL ahora

Propifai/PIL es actualmente una **plataforma inmobiliaria inteligente agentic
en consolidación**, con recuperación híbrida, contratos deterministas,
evaluación previa a respuesta, continuidad conversacional estructurada,
observabilidad y una interfaz de trabajo orientada a artefactos.

No es solamente un chatbot. Sus capacidades actuales abarcan:

### 31.1 Sistema de consulta inmobiliaria

- interpreta consultas naturales;
- extrae filtros estructurados;
- consulta inventario real;
- combina recuperación semántica y exacta;
- conserva identificadores y evidencia;
- muestra colecciones y detalle de propiedades.

### 31.2 Sistema agentic

- Supervisor con function calling;
- agentes especializados;
- skills con contratos;
- ReAct loop;
- requisitos explícitos;
- precondiciones;
- replans acotados;
- fallbacks;
- evaluación determinista y semántica.

### 31.3 Sistema conversacional con tareas

- reconoce consultas nuevas;
- mantiene tareas pendientes;
- fusiona criterios entre turnos;
- detecta cambios de intención;
- evita finalizar tareas incompletas;
- conserva límites no verificables.

### 31.4 Sistema observable

- trazas correlacionadas;
- pasos por agente;
- filtros y requisitos;
- rutas y fallbacks;
- estados degradados;
- auditoría;
- dashboard de aprendizaje;
- señales para incidentes futuros.

### 31.5 Workspace operativo

- navegación lateral;
- conversación central;
- razonamiento visible;
- panel derecho;
- tarjetas;
- detalle;
- galería;
- videos;
- base para gráficos, documentos y HTML.

### 31.6 Estado de madurez

| Área | Madurez actual |
|---|---|
| Búsqueda exacta | media-alta, requiere más regresión |
| Búsqueda semántica | media, sensible a calidad de embeddings/datos |
| Agentes/ReAct | media, ya tiene controles pero requiere calibración |
| Continuidad multitur​no | inicial, implementada para un contrato principal |
| Evaluación Nivel 1 | implementada |
| Juez Nivel 2 | implementado en shadow |
| Advisory Nivel 3A | implementado, pendiente de activación calibrada |
| Observabilidad | funcional, todavía en consolidación |
| Aprendizaje global | temprano |
| Workspace visual | funcional parcial |
| Operación productiva | funcional, con deuda de assets, Redis y pruebas |

---

## 32. Qué dejó de ser

Con estas mejoras, Propifai/PIL dejó de ser:

### 32.1 Un wrapper simple de LLM

La respuesta ya no depende únicamente de enviar texto a DeepSeek. Existen
contratos, datos recuperados, validadores y decisiones controladas.

### 32.2 Un pipeline completamente lineal

Ahora puede aclarar, bloquear, replanificar y diferenciar éxito limpio de
degradado.

### 32.3 Un buscador puramente semántico

La similitud ayuda a recuperar candidatos, pero los filtros exactos se validan
por campos y operadores.

### 32.4 Un sistema que considera cualquier lista como éxito

Los resultados deben cumplir requisitos y SearchPlan.

### 32.5 Un chat que olvida necesariamente cada aclaración

Existe estado operativo de tarea entre turnos.

### 32.6 Un sistema opaco

Las etapas, fallos, fallbacks, requisitos y veredictos pueden persistirse y
consultarse.

### 32.7 Una interfaz de texto exclusivamente

La arquitectura contempla artefactos, panel derecho, media y futuras
visualizaciones.

### 32.8 Un sistema donde el fallback borra el error anterior

La degradación queda registrada.

---

## 33. Qué todavía no es

Para evitar una falsa percepción de madurez, el sistema todavía no es:

### 33.1 Un agente completamente autónomo

Puede replanificar dentro de límites, pero no diseña estrategias arbitrarias,
no crea tools y no modifica su arquitectura.

### 33.2 Un sistema que aprende automáticamente entre conversaciones

Ya genera señales, pero todavía no existe el circuito completo:

```text
incidente → dataset → replay → propuesta → aprobación → canary → rollback
```

### 33.3 Un verificador legal o urbanístico

No confirma zonificación, uso permitido ni capacidad técnica sin fuentes
especializadas.

### 33.4 Un sistema libre de alucinaciones

Las reduce y detecta, pero ningún sistema basado en LLM puede declararse libre
de ellas. La defensa debe medirse continuamente.

### 33.5 Una plataforma completamente testeada

Existen regresiones focalizadas, pero falta cobertura integral, pruebas de
carga, caos, seguridad, accesibilidad y end-to-end productivo.

### 33.6 Un producto multiempresa totalmente gobernado

Roles, permisos y aislamiento existen parcialmente, pero requieren auditoría
formal de tenancy, datos y autorización.

### 33.7 Un referente todavía

Tiene una base diferenciadora, pero para ser referente necesita evidencia
operativa: precisión, confiabilidad, velocidad, seguridad, UX y resultados de
negocio superiores y medidos.

---

## 34. Capacidades implementadas, parciales y pendientes

### Implementadas

- SearchPlan canónico;
- filtros de precio, tipo, distrito, área y estado;
- ReAct con requisitos;
- evidencia por requisito;
- Nivel 1;
- Nivel 2 shadow;
- controlador Nivel 3A;
- tarea conversacional escolar;
- estados degradados;
- telemetría semántica/advisory;
- artefactos de propiedades;
- detalle, galería y videos;
- estructura de tres paneles;
- registro maestro de pendientes.

### Parciales

- cobertura de contratos multitur​no;
- dashboard de observabilidad;
- auditoría de grounding;
- clasificación completa de estados finales;
- paginación y explicación de límites;
- imágenes normalizadas para todos los orígenes;
- responsive/accessibility del workspace;
- health checks de assets;
- agrupación de incidentes;
- consistencia entre rutas AgentGraph/LangGraph.

### Pendientes críticos

- dataset de replay;
- evaluación offline;
- calibración del advisory;
- detección de patrones;
- fuentes legales/urbanísticas;
- seguridad y tenancy;
- SLO/SLI;
- pruebas E2E;
- pruebas de carga;
- canary/rollback;
- observabilidad de costos;
- calidad y frescura de inventario.

---

## 35. Principios para convertirlo en un sistema referente

1. **Datos antes que prosa:** ninguna afirmación inmobiliaria importante sin
   evidencia.
2. **Determinismo antes que juez:** reglas exactas para filtros exactos.
3. **LLM como razonador limitado:** no como autoridad absoluta.
4. **Errores visibles:** ningún fallback debe ocultar degradación.
5. **Evaluación continua:** cada incidente confirmado se vuelve regresión.
6. **Seguridad gradual:** shadow → advisory → canary → promoción.
7. **UX de trabajo:** conversación y artefactos, no sólo burbujas de chat.
8. **Especialización inmobiliaria:** contratos, normativa, mercado y operación.
9. **Interoperabilidad:** skills, APIs y artefactos con schemas versionados.
10. **Métricas competitivas:** precisión, latencia, conversión y confianza.

---

## 36. Hoja de ruta para un sistema sólido, robusto y competitivo

La prioridad no debe ser agregar más IA indiscriminadamente. Primero debe
consolidarse la confiabilidad del núcleo; después ampliar capacidades.

### Fase 0 — Inventario y verdad técnica

**Objetivo:** saber exactamente qué está implementado y qué no.

Acciones:

- auditar specs históricos contra código;
- eliminar duplicados y documentación contradictoria;
- registrar versiones de código, prompts, configuración, embeddings e índices;
- definir propietarios por módulo;
- consolidar el registro maestro;
- clasificar deuda crítica, funcional y estética.

Gate:

- 100 % de componentes críticos con estado y responsable;
- configuración productiva versionada;
- cero jobs de autocambio no gobernados.

### Fase 1 — Confiabilidad del dato inmobiliario

**Objetivo:** que el inventario sea una fuente confiable.

Acciones:

- normalizar tipos, distritos, monedas, áreas y estados;
- controlar duplicados;
- verificar URLs de imágenes/videos;
- registrar fecha de actualización;
- separar disponible, vendido, reservado y captación;
- alertar propiedades sin campos esenciales;
- validar sincronización FAISS ↔ Azure SQL;
- crear health dashboard de colecciones.

Gate:

- ≥ 98 % de propiedades activas con tipo, distrito, precio, estado e ID;
- cero vendidas en búsquedas de disponibles;
- diferencia SQL/índice explicada y < 1 %;
- freshness definida por fuente.

### Fase 2 — Contratos de intención completos

**Objetivo:** generalizar la continuidad y requisitos.

Contratos prioritarios:

- búsqueda simple;
- colegio;
- clínica;
- tienda/local comercial;
- inversión;
- alquiler;
- compra;
- análisis comparativo;
- matching requerimiento-propiedad;
- detalle de una propiedad;
- seguimiento y corrección.

Cada contrato debe definir:

- campos obligatorios;
- campos opcionales;
- evidencia disponible;
- evidencia externa;
- condiciones de finalización;
- pregunta de aclaración;
- artefacto de salida.

Gate:

- ≥ 95 % de consultas de prueba clasificadas correctamente;
- cero pérdida de intención en suites multitur​no;
- nuevas tareas no heredan filtros anteriores.

### Fase 3 — Evaluación y replay continuo

**Objetivo:** convertir errores reales en pruebas reproducibles.

Acciones:

- crear dataset sanitizado;
- incorporar incidentes del dashboard;
- snapshots de inventario;
- invariantes deterministas;
- judges secundarios;
- ejecución en CI;
- comparación baseline/candidato;
- bloqueo por regresión crítica.

Gate:

- ≥ 100 casos representativos;
- 100 % de incidentes críticos conocidos incluidos;
- replay reproducible;
- variación inexplicada < 5 %.

### Fase 4 — Calibración de Niveles 2 y 3A

**Objetivo:** dar autoridad sólo donde el juez demuestra precisión.

Acciones:

- medir por señal;
- etiquetar desacuerdos;
- calcular precisión/recall;
- separar intención y severidad;
- activar advisory selectivamente;
- thresholds por patrón;
- kill switch;
- dashboard de autoridad aplicada.

Gate:

- precisión ≥ 90 % para acciones de bloqueo;
- falsos bloqueos < 2 %;
- rollback probado;
- máximo de reintentos respetado en 100 % de trazas.

### Fase 5 — Observabilidad productiva y SRE

**Objetivo:** operar con compromisos medibles.

Definir SLI/SLO:

- disponibilidad;
- latencia p50/p95/p99;
- éxito limpio;
- degradación;
- grounding;
- cobertura de trazas;
- frescura del inventario;
- errores de assets;
- costo por consulta.

Acciones:

- Redis administrado o degradación formal;
- alertas con cooldown;
- correlación frontend/backend;
- health checks;
- synthetic tests;
- retención y redacción;
- runbooks;
- postmortems.

Gate:

- ≥ 99.5 % de disponibilidad inicial;
- ≥ 98 % de trazas completas;
- detección de incidentes críticos < 10 minutos;
- runbook para cada dependencia crítica.

### Fase 6 — Seguridad, privacidad y gobierno

**Objetivo:** estar preparado para clientes empresariales.

Acciones:

- auditoría RBAC;
- aislamiento por organización;
- permisos por skill y dato;
- secretos administrados;
- rate limiting;
- logs sanitizados;
- política de retención;
- protección contra prompt injection;
- sandbox para HTML;
- auditoría de dependencias;
- pruebas OWASP.

Gate:

- cero secretos en trazas;
- pruebas de autorización por nivel y tenant;
- threat model aprobado;
- proceso documentado de incidentes.

### Fase 7 — Experiencia de usuario de referencia

**Objetivo:** convertir el chat en un workspace inmobiliario superior.

Acciones:

- responsive completo;
- accesibilidad WCAG;
- búsqueda/conversaciones;
- proyectos;
- estados claros;
- paginación;
- ordenar y filtrar;
- mapas;
- comparador;
- Plotly;
- PDF;
- HTML sandbox;
- exportación;
- acciones explicables;
- feedback por respuesta.

Gate:

- pruebas de usabilidad;
- cero Markdown crudo;
- ≥ 95 % de propiedades con visual coherente o placeholder;
- tiempos de interacción medidos;
- accesibilidad automatizada sin errores críticos.

### Fase 8 — Inteligencia inmobiliaria especializada

**Objetivo:** crear ventaja difícil de copiar.

Capacidades:

- zonificación y normativa con fuentes;
- análisis de precio por m²;
- comparables;
- rentabilidad y escenarios;
- absorción de mercado;
- scoring de oportunidades;
- matching explicable;
- riesgos documentales;
- mapas y POI;
- reportes profesionales.

Regla:

Cada conclusión debe incluir fuente, fecha, confianza y limitación.

Gate:

- validación con especialistas;
- benchmarks frente a análisis manual;
- explicabilidad de cada score;
- fuentes actualizadas y auditables.

### Fase 9 — Integraciones y ecosistema

**Objetivo:** convertir Propifai en plataforma.

Acciones:

- API pública versionada;
- webhooks;
- CRM;
- WhatsApp;
- calendarios;
- firma/documentos;
- portales;
- MCP/tools;
- SDK;
- importación/exportación;
- marketplace de skills gobernado.

Gate:

- contratos API estables;
- idempotencia;
- rate limits;
- observabilidad por integración;
- certificación de skills externas.

### Fase 10 — Aprendizaje global controlado

**Objetivo:** reducir errores repetidos sin intervención manual constante.

Secuencia:

```text
traza
→ detector
→ incidente
→ revisión
→ caso de regresión
→ propuesta
→ replay
→ aprobación
→ canary
→ promoción o rollback
```

Sólo cambios de bajo riesgo y allowlist podrán automatizarse. Código,
migraciones, permisos y datos seguirán requiriendo revisión humana.

Gate:

- ≥ 20 propuestas evaluadas;
- ≥ 70 % útiles;
- canary y rollback confiables;
- seis semanas sin autocorrección dañina antes de ampliar autonomía.

### Fase 11 — Competitividad demostrable

**Objetivo:** probar que el producto es superior, no sólo más complejo.

Benchmarks:

- precisión de búsqueda;
- recall de propiedades;
- grounding;
- tiempo para encontrar inmueble;
- tiempo para producir análisis;
- conversión a contacto/visita;
- productividad del agente inmobiliario;
- satisfacción;
- costo por tarea;
- comparación con competidores y proceso manual.

Entregables:

- benchmark público o auditable;
- casos de éxito;
- métricas antes/después;
- documentación para desarrolladores;
- estándares de calidad;
- demostraciones reproducibles.

Gate:

- ventaja medible en al menos tres métricas clave;
- clientes de referencia;
- confiabilidad sostenida;
- diferenciación difícil de replicar.

---

## 37. Orden recomendado de ejecución

### Próximos 30 días

1. auditar inventario y specs;
2. estabilizar filtros/estados;
3. desplegar Nivel 3A en staging;
4. ampliar regresiones;
5. completar dashboard de calidad;
6. cerrar errores de assets y Redis.

### 30–90 días

1. contratos de intención;
2. replay continuo;
3. SLO y alertas;
4. seguridad/tenancy;
5. UX responsive y accesible;
6. Plotly/PDF/mapas.

### 3–6 meses

1. inteligencia normativa y de mercado;
2. advisory calibrado;
3. API e integraciones;
4. canary/rollback;
5. benchmarks competitivos.

### 6–12 meses

1. aprendizaje global controlado;
2. ecosistema de skills;
3. optimización avanzada;
4. expansión geográfica;
5. certificaciones, casos de éxito y posicionamiento como referente.

---

## 38. Definición de “sistema referente”

Propifai será un referente cuando pueda demostrar simultáneamente:

```text
datos confiables
+ respuestas fundamentadas
+ agentes controlables
+ evaluación continua
+ UX superior
+ seguridad empresarial
+ inteligencia inmobiliaria especializada
+ resultados de negocio medibles
```

El objetivo no es que el sistema parezca inteligente. El objetivo es que sea
confiable, útil, explicable, competitivo y consistentemente mejor que las
alternativas.
