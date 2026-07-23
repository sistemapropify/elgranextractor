# SPEC — Contrato único de filtros y finalización correcta de agentes

**ID:** SPEC-PIL-FILTERS-001  
**Fecha:** 2026-07-23  
**Prioridad:** crítica  
**Estado:** lista para implementación  
**Módulos:** AgentGraph, LangGraph, SearchAgent, RAG, skills de propiedades  
**Incidentes relacionados:**

- búsqueda “departamentos en Cayma con 3 dormitorios”;
- búsqueda “terreno en Cerro Colorado por menos de USD 170,000”;
- terreno real de USD 95,000 descartado por interpretar el límite como precio exacto.

---

## 1. Objetivo

Garantizar que todos los caminos de búsqueda:

1. preserven el significado de cada filtro;
2. distingan igualdad, mínimo, máximo, inclusión y texto;
3. produzcan los mismos candidatos ante los mismos parámetros;
4. informen qué filtros aplicaron realmente;
5. permitan que una sola búsqueda satisfaga requisitos de datos y filtros;
6. entreguen al fallback el plan estructurado original;
7. nunca declaren “sin resultados” cuando la recuperación falló o usó operadores incorrectos.

---

## 2. Causas raíz verificadas

### 2.1 Pérdida del operador en LangGraph

Archivo:
`webapp/intelligence/agents/search_agent.py`

Código actual:

```python
field_mapping = {
    'precio': 'price',
    'precio_min': 'price',
    'precio_max': 'price',
}

for param_key, field_name in field_mapping.items():
    filters[field_name] = value
```

Los tres parámetros terminan representados como:

```python
{'price': 170000.0}
```

`RAGService.search_dynamic()` interpreta esa estructura como igualdad:

```text
price = 170000
```

El significado original:

```text
price <= 170000
```

se pierde antes de ejecutar la consulta.

### 2.2 Una skill solo puede satisfacer un tipo de requisito

Archivo:
`webapp/intelligence/agents/base_agent.py`

Contrato actual:

```python
SKILL_SATISFIES_KIND: dict[str, str]
```

`busqueda_propiedades` está asociada a `data`. Cuando el extractor genera:

```json
[
  {"kind": "data", "description": "Buscar terrenos en Cerro Colorado"},
  {"kind": "filter", "description": "Precio menor a USD 170,000"}
]
```

la ejecución exitosa satisface únicamente `data`. El requisito `filter`
permanece pendiente hasta agotar las iteraciones.

### 2.3 El fallback vuelve a interpretar la consulta

AgentGraph extrae parámetros válidos, pero al fallar devuelve `None`.
LangGraph reconstruye filtros desde conversación/contexto y puede:

- perder operadores;
- perder dormitorios;
- heredar filtros antiguos;
- generar un conjunto distinto al de la primera ruta.

### 2.4 Dos motores con contratos diferentes

`BusquedaPropiedadesSkill` ya filtra rangos numéricos en Python para evitar
conversiones `nvarchar → int` en SQL Server.

`SearchAgent → RAGService.search_dynamic()` utiliza un diccionario plano y
pre-filtrado ORM. Ambos caminos no comparten semántica ni estrategia numérica.

---

## 3. Invariantes

Estas reglas deben cumplirse después de la implementación:

1. `precio_max=170000` nunca puede transformarse en `price=170000`.
2. Un filtro no puede cambiar de operador entre AgentGraph y LangGraph.
3. Los filtros numéricos sobre JSON no se comparan en SQL Server si el tipo
   persistido no está garantizado.
4. “Sin resultados” solo es válido si la búsqueda terminó técnicamente bien.
5. Todo resultado debe cumplir todos los filtros obligatorios.
6. Toda respuesta debe poder mostrar `applied_filters`.
7. Un requisito solo se marca cumplido mediante evidencia del resultado.
8. Un fallback reutiliza el `SearchPlan`; no reextrae filtros desde texto.
9. Parámetros nuevos prevalecen sobre contexto anterior.
10. Contexto anterior no añade filtros no mencionados sin una referencia explícita.

---

## 4. Diseño objetivo

### 4.1 Modelo canónico `FilterCondition`

Crear:

`webapp/intelligence/search/contracts.py`

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FilterOperator(str, Enum):
    EQ = 'eq'
    LTE = 'lte'
    GTE = 'gte'
    IN = 'in'
    ICONTAINS = 'icontains'


@dataclass(frozen=True)
class FilterCondition:
    logical_name: str
    field_name: str
    operator: FilterOperator
    value: Any
    value_type: str
    required: bool = True
    source: str = 'current_message'
    currency: Optional[str] = None


@dataclass
class SearchPlan:
    query: str
    collections: list[str]
    conditions: list[FilterCondition] = field(default_factory=list)
    semantic_query: str = ''
    top_k: int = 10
    schema_version: str = '1'
```

Ejemplo:

```python
SearchPlan(
    query='terreno en Cerro Colorado por menos de 170000 dólares',
    collections=['propiedadespropify'],
    conditions=[
        FilterCondition(
            logical_name='distrito',
            field_name='district_name',
            operator=FilterOperator.EQ,
            value='Cerro Colorado',
            value_type='string',
        ),
        FilterCondition(
            logical_name='tipo_propiedad',
            field_name='property_type_name',
            operator=FilterOperator.EQ,
            value='Terreno',
            value_type='string',
        ),
        FilterCondition(
            logical_name='precio_max',
            field_name='price',
            operator=FilterOperator.LTE,
            value=170000.0,
            value_type='decimal',
            currency='USD',
        ),
    ],
)
```

No se permiten diccionarios ambiguos como:

```python
{'price': 170000}
```

para búsquedas nuevas.

### 4.2 Resultado canónico `SearchExecutionResult`

```python
@dataclass
class AppliedFilter:
    logical_name: str
    field_name: str
    operator: str
    requested_value: Any
    matched_count_before: int
    matched_count_after: int
    execution_mode: str


@dataclass
class SearchExecutionResult:
    success: bool
    items: list[dict]
    applied_filters: list[AppliedFilter]
    rejected_counts: dict[str, int]
    search_plan: SearchPlan
    error_code: str = ''
    error_message: str = ''
```

Esto permite diferenciar:

```text
success=True, items=[]
```

de:

```text
success=False, error_code=DB_TYPE_CONVERSION
```

---

## 5. Normalización de filtros

Crear:

`webapp/intelligence/search/normalizer.py`

Entrada permitida temporalmente:

```python
{
    'distrito': 'Cerro Colorado',
    'tipo_propiedad': 'Terreno',
    'precio_max': 170000,
    'moneda': 'USD',
}
```

Salida:

```python
[
    FilterCondition('distrito', 'district_name', EQ, 'Cerro Colorado', 'string'),
    FilterCondition('tipo_propiedad', 'property_type_name', EQ, 'Terreno', 'string'),
    FilterCondition('precio_max', 'price', LTE, 170000.0, 'decimal', currency='USD'),
]
```

Mapa inicial obligatorio:

| Parámetro | Campo | Operador | Tipo |
|---|---|---|---|
| `distrito` | `district_name` | `eq` | string |
| `tipo_propiedad` | `property_type_name` | `eq` | string |
| `operacion` | `operation_type_name` | `eq` | string |
| `condicion` | `property_status_name` | `eq` | string |
| `precio` | `price` | `eq` | decimal |
| `precio_min` | `price` | `gte` | decimal |
| `precio_max` | `price` | `lte` | decimal |
| `habitaciones` | `bedrooms` | `eq` | integer |
| `habitaciones_min` | `bedrooms` | `gte` | integer |
| `area_min` | `built_area` | `gte` | decimal |
| `area_max` | `built_area` | `lte` | decimal |

Si llega un parámetro no registrado:

```text
INVALID_FILTER_PARAMETER
```

No debe degradarse silenciosamente a igualdad.

---

## 6. Ejecución segura

### 6.1 Filtros categóricos

Distrito, tipo, operación y estado pueden prefiltrarse en SQL si el schema
confirma que son strings.

### 6.2 Filtros numéricos

Hasta normalizar los registros históricos:

1. ejecutar prefiltrado categórico;
2. materializar candidatos acotados;
3. convertir el primer campo numérico válido con `Decimal(str(value))`;
4. aplicar el operador en Python;
5. registrar descartes por filtro.

No usar:

```python
field_values__price__lte=170000
```

contra JSON de SQL Server mientras existan valores como `"95000.0"`.

### 6.3 Moneda

Un límite monetario solo puede compararse cuando:

- la moneda de la propiedad coincide; o
- existe conversión explícita versionada.

La primera versión debe exigir coincidencia y registrar:

```text
CURRENCY_MISMATCH
```

No asumir PEN o USD cuando el campo está ausente.

### 6.4 Campos provenientes de relaciones

`bedrooms`, áreas, estacionamientos y amenidades pueden estar en
`property_specs`, no en la tabla principal.

El contrato de colección debe declarar:

```json
{
  "bedrooms": {
    "source": "property_specs",
    "joined": true,
    "type": "integer"
  }
}
```

Si el campo no está disponible:

```text
FILTER_FIELD_UNAVAILABLE
```

No afirmar que el filtro fue aplicado.

---

## 7. Corrección de AgentGraph

### 7.1 Capacidades múltiples por skill

Reemplazar:

```python
SKILL_SATISFIES_KIND: dict[str, str]
```

por:

```python
SKILL_CAPABILITIES: dict[str, set[str]] = {
    'busqueda_propiedades': {'data', 'filter'},
    'busqueda_exacta': {'data', 'filter'},
    'matching_hibrido': {'matching', 'filter'},
    'formatear_propiedades': {'format'},
}
```

Esto solamente indica capacidad; no satisface automáticamente requisitos.

### 7.2 Satisfacción basada en evidencia

Modificar `_update_requirements_status()` para utilizar:

```python
step.skill_result['applied_filters']
```

Reglas:

- requisito `data`: se satisface si la búsqueda terminó técnicamente bien;
- requisito `filter`: se satisface si existe un `AppliedFilter` equivalente;
- requisito de filtro no se satisface si el campo estaba ausente;
- resultado vacío genuino puede satisfacer `data` y `filter`;
- error técnico no satisface nada.

Ejemplo:

```json
{
  "success": true,
  "data": [{"property_id": 123, "price": 95000}],
  "applied_filters": [
    {
      "logical_name": "precio_max",
      "operator": "lte",
      "requested_value": 170000,
      "matched_count_before": 8,
      "matched_count_after": 3
    }
  ]
}
```

El requisito “menos de USD 170,000” se marca cumplido sin otra iteración.

### 7.3 Límite de iteraciones

Si una skill devuelve:

```text
success=True
all requirements evidenced=True
```

el agente debe finalizar en la misma iteración.

Si quedan requisitos que ninguna skill disponible puede satisfacer:

```text
UNSATISFIABLE_REQUIREMENT
```

No consumir cuatro llamadas adicionales al LLM.

---

## 8. Corrección de LangGraph

### 8.1 `SearchAgent._build_filters`

Debe reemplazarse por:

```python
plan = SearchPlanNormalizer.from_params(
    query=message,
    params=params,
    collections=collections,
)
```

`SearchAgent` no debe mantener otro `field_mapping`.

### 8.2 `RAGService.search_dynamic`

Agregar interfaz:

```python
search_dynamic(plan: SearchPlan) -> SearchExecutionResult
```

Mantener temporalmente la interfaz anterior mediante adaptador que:

- emita warning;
- prohíba rangos ambiguos;
- se elimine después de migrar callers.

### 8.3 Fallback con el mismo plan

Antes de ejecutar AgentGraph, guardar:

```python
state['search_plan']
```

Si AgentGraph falla:

```python
LangGraph.run(search_plan=existing_plan)
```

Prohibido volver a extraer filtros salvo que el plan sea inválido. En ese caso,
la respuesta debe solicitar aclaración o reportar error.

---

## 9. Contexto entre turnos

Esta spec no implementa personalización. Solo regula filtros operativos.

Reglas:

1. filtros del mensaje actual tienen `source='current_message'`;
2. filtros heredados tienen `source='conversation_context'`;
3. si el usuario inicia una búsqueda completa nueva, no heredar filtros omitidos;
4. expresiones como “de esos”, “mantén el presupuesto” o “ahora en Cayma”
   autorizan herencia;
5. el formatter debe mostrar qué filtros heredó.

Un presupuesto anterior nunca debe aparecer como vigente sin una señal de continuidad.

---

## 10. Guardrails

Antes de formatear:

```python
validate_search_result(result)
```

Validaciones:

- cada item cumple todos los filtros requeridos;
- `applied_filters` contiene cada requisito `filter`;
- cada precio mostrado existe en el item;
- moneda compatible;
- `success=False` no puede convertirse en “no encontré”;
- `success=True, items=[]` produce mensaje determinista;
- si una propiedad incumple un filtro, se elimina y se registra
  `EXACT_FILTER_VIOLATION`.

---

## 11. Observabilidad

Eventos nuevos:

| Evento | Cuándo |
|---|---|
| `search.plan.created` | plan normalizado |
| `search.filter.applied` | después de cada filtro |
| `search.filter.unavailable` | campo ausente |
| `search.completed` | éxito con conteo |
| `search.failed` | fallo técnico |
| `requirement.satisfied` | evidencia encontrada |
| `requirement.unsatisfied` | evidencia ausente |
| `fallback.plan_reused` | fallback conserva plan |
| `fallback.plan_rebuilt` | situación excepcional |

Payload de filtro:

```json
{
  "logical_name": "precio_max",
  "field_name": "price",
  "operator": "lte",
  "value_type": "decimal",
  "matched_before": 8,
  "matched_after": 3
}
```

No registrar valores personales ni consultas completas.

Alertas:

- `FILTER_OPERATOR_LOST`;
- `FILTER_FIELD_UNAVAILABLE`;
- `FAILURE_MISREPORTED_AS_EMPTY`;
- `FALLBACK_PLAN_DIVERGENCE`;
- `UNSATISFIABLE_REQUIREMENT`;
- `EXACT_FILTER_VIOLATION`.

---

## 12. Archivos

### Crear

- `webapp/intelligence/search/__init__.py`
- `webapp/intelligence/search/contracts.py`
- `webapp/intelligence/search/normalizer.py`
- `webapp/intelligence/search/executor.py`
- `webapp/intelligence/search/validators.py`
- `webapp/intelligence/tests/test_search_filter_contract.py`
- `webapp/intelligence/tests/test_agent_requirement_evidence.py`
- `webapp/intelligence/tests/test_fallback_search_plan.py`

### Modificar

- `webapp/intelligence/agents/search_agent.py`
- `webapp/intelligence/agents/base_agent.py`
- `webapp/intelligence/agents/orchestrator.py`
- `webapp/intelligence/services/rag.py`
- `webapp/intelligence/services/chat_processor.py`
- `webapp/intelligence/skills/propiedades/skill.py`
- `webapp/intelligence/skills/base.py`
- `webapp/intelligence/learning/events.py`

---

## 13. Plan de implementación

### Fase 0 — Baseline

Guardar resultados reales para:

1. terrenos en Cerro Colorado;
2. terreno de USD 95,000;
3. departamentos de tres dormitorios en Cayma;
4. propiedades en límites exactos;
5. monedas PEN y USD.

### Fase 1 — Contratos

1. crear dataclasses y enums;
2. crear normalizador;
3. unit tests de operadores;
4. no cambiar producción todavía.

### Fase 2 — Ejecutor común

1. extraer filtrado seguro desde `BusquedaPropiedadesSkill`;
2. implementar categóricos SQL + numéricos Python;
3. producir `applied_filters`;
4. comparar contra motor actual en shadow.

### Fase 3 — Migrar LangGraph

1. reemplazar `_build_filters`;
2. migrar `search_dynamic`;
3. habilitar guardrail de paridad;
4. verificar el terreno de USD 95,000.

### Fase 4 — Migrar AgentGraph

1. introducir capacidades múltiples;
2. satisfacción por evidencia;
3. corte temprano de iteraciones;
4. registrar requisitos no satisfacibles.

### Fase 5 — Fallback

1. serializar `SearchPlan` en estado;
2. pasar el mismo plan a LangGraph;
3. comparar hashes de plan;
4. bloquear divergencias.

### Fase 6 — Activación

1. shadow por 48 horas;
2. comparar candidatos old/new;
3. activar al 100 % si supera gates;
4. conservar feature flag de rollback.

---

## 14. Pruebas obligatorias

### Operadores

```text
precio=170000      → eq
precio_min=170000  → gte
precio_max=170000  → lte
```

### Incidente de Cerro Colorado

Dataset:

```json
[
  {"id": 1, "district": "Cerro Colorado", "type": "Terreno", "price": "95000.0", "currency": "USD"},
  {"id": 2, "district": "Cerro Colorado", "type": "Terreno", "price": "175000.0", "currency": "USD"},
  {"id": 3, "district": "Cayma", "type": "Terreno", "price": "90000.0", "currency": "USD"}
]
```

Consulta:

```text
terreno en Cerro Colorado con menos de 170000 dólares
```

Esperado:

- incluye ID 1;
- excluye ID 2 por precio;
- excluye ID 3 por distrito;
- `price operator=lte`;
- una sola iteración de AgentGraph;
- sin fallback.

### Dormitorios

Consulta:

```text
departamentos en Cayma de 3 dormitorios
```

Esperado:

- `bedrooms operator=eq value=3`;
- todos los resultados tienen tres dormitorios;
- requisito `filter` satisfecho por evidencia;
- no usar historial para añadir presupuesto.

### Fallos

- string decimal válido;
- precio inválido;
- moneda ausente;
- campo dormitorios no unido;
- error SQL;
- cero resultados genuino;
- AgentGraph falla y LangGraph reutiliza plan idéntico.

### Paridad

Para cada fixture:

```text
IDs AgentGraph == IDs LangGraph
applied_filters AgentGraph == applied_filters LangGraph
```

---

## 15. Criterios de aceptación

La corrección se considera lista cuando:

1. el terreno de USD 95,000 aparece en la consulta reportada;
2. `precio_max` nunca aparece como igualdad en logs;
3. AgentGraph termina la consulta en una iteración;
4. AgentGraph y LangGraph devuelven los mismos IDs;
5. dormitorios y áreas no se declaran aplicados si el campo está ausente;
6. fallos técnicos no se reportan como inventario vacío;
7. fallback reutiliza el mismo hash de `SearchPlan`;
8. cero regresiones en filtros categóricos;
9. pruebas unitarias e integración pasan;
10. 48 horas de shadow sin `FALLBACK_PLAN_DIVERGENCE`.

---

## 16. Rollback

Feature flags:

```text
PIL_TYPED_FILTERS_ENABLED
PIL_EVIDENCE_REQUIREMENTS_ENABLED
PIL_REUSE_SEARCH_PLAN_ON_FALLBACK
```

Rollback:

1. desactivar flags;
2. volver al motor anterior;
3. conservar eventos y comparaciones shadow;
4. no eliminar contratos ni datos de observabilidad.

Nunca hacer rollback desactivando los guardrails anti-alucinación.

---

## 17. Definition of Done

- contratos documentados;
- motor común activo;
- ambas rutas migradas;
- evidencia de filtros persistida;
- incidentes originales convertidos en regresiones;
- dashboard muestra operadores y descartes;
- fallback sin reinterpretación;
- documentación de despliegue y rollback actualizada.

