# SPEC — Ciclo seguro de evaluación y replanificación agentic

**Proyecto:** Propifai / PIL  
**Estado:** Nivel 1 implementado · Nivel 2 shadow implementado · Nivel 3A advisory implementado  
**Fecha:** 2026-07-23

## 1. Objetivo

Impedir que PIL confunda una ejecución técnicamente exitosa con una respuesta
correcta. Antes de responder, el sistema debe evaluar evidencia, decidir si
puede responder y, cuando sea seguro, cambiar el plan.

```text
consulta → plan → acción → observación → evaluación
                                      ├─ aprobar → responder
                                      ├─ replanificar → nueva acción
                                      ├─ aclarar → preguntar al usuario
                                      └─ bloquear → respuesta honesta
```

## 2. Principios

1. Una skill exitosa no implica un requisito satisfecho.
2. Cada afirmación importante necesita evidencia estructurada.
3. Los filtros exactos se validan de forma determinista.
4. El LLM no puede aprobarse a sí mismo sin guardrails.
5. La replanificación tiene máximo dos intentos.
6. Si faltan criterios esenciales, se pregunta; no se adivina.
7. Ningún evaluador modifica código, prompts o datos de producción.
8. El auditor posterior sigue existiendo como segunda línea de defensa.

## 3. Veredicto

```json
{
  "verdict": "pass|replan|clarify|block",
  "confidence": 0.95,
  "signals": [],
  "reason": "...",
  "clarification_question": null,
  "suggested_plan": null,
  "metrics": {
    "result_count": 0,
    "requirements_total": 0,
    "requirements_satisfied": 0
  }
}
```

## 4. Evaluación Nivel 1

La primera versión es determinista y comprueba:

- agentes exitosos;
- existencia y cantidad de resultados;
- consultas de aptitud/recomendación;
- ausencia de criterios esenciales;
- inventarios completos o cantidades anómalas;
- tipos de propiedad incompatibles con un filtro explícito;
- propiedades vendidas cuando se solicita disponibilidad;
- requisitos marcados como satisfechos sin evidencia específica;
- coincidencia entre conteo y artefacto.

### Consultas de aptitud

Ejemplos:

- ideal para construir un colegio;
- apta para clínica;
- dónde poner una tienda;
- buena para inversión.

No se aprueban únicamente por similitud semántica. Requieren una skill
especializada o criterios verificables. Si faltan, el sistema solicita:

- distrito o zona;
- presupuesto;
- área/capacidad;
- uso y restricciones relevantes.

## 5. Replanificación

Se permite automáticamente cuando existe una corrección determinista:

- reaplicar tipo explícito;
- reaplicar distrito;
- reaplicar rango de precio;
- excluir estados no disponibles;
- reducir un resultado masivo mediante filtros ya expresados por el usuario.

No se permite inventar:

- zonificación;
- aptitud legal;
- rentabilidad;
- área mínima no indicada;
- presupuesto no indicado.

Si no existe un plan seguro, el veredicto es `clarify`.

## 6. Integración

### AgentGraph

1. Ejecuta el plan.
2. Agrega resultados.
3. `ExecutionEvaluator` produce el veredicto.
4. `pass`: continúa al formatter.
5. `replan`: ejecuta otra vez con plan corregido.
6. `clarify`: responde una pregunta breve sin mostrar inventario.
7. `block`: explica honestamente la limitación.

### ReAct

Un requisito sólo se marca satisfecho cuando:

- la skill declara la capacidad correspondiente;
- existe evidencia requerida;
- los filtros solicitados aparecen en `applied_filters`;
- la relevancia no depende sólo de `item_count > 0`.

### Auditoría

Persistir:

- veredicto;
- señales;
- plan original;
- plan revisado;
- número de intento;
- motivo de terminación.

## 7. Límites

- `MAX_REPLAN_ATTEMPTS = 2`.
- Máximo 25 iteraciones totales.
- Sin mutaciones automáticas.
- Sin aprendizaje entre conversaciones en Nivel 1.
- Una aclaración termina el turno y espera al usuario.

## 8. Criterios de aceptación Nivel 1

1. “Terrenos en Cayma” puede responder directamente.
2. “Ideal para construir un colegio” no devuelve todo el inventario.
3. La consulta anterior solicita criterios o usa una evaluación especializada.
4. Una búsqueda de terrenos no acepta departamentos.
5. Una búsqueda disponible no incluye vendidas.
6. Más de 50 resultados sin filtros genera señal de amplitud anómala.
7. El evaluador aparece en la traza.
8. La respuesta final incluye el veredicto interno en metadata, no en texto.
9. Nunca existen más de dos replans.
10. Las pruebas de regresión cubren aprobación, aclaración y bloqueo.

## 9. Niveles posteriores

### Nivel 2

Juez LLM con salida JSON, utilizado sólo después de los controles
deterministas y sobre una muestra limitada de resultados.

### Nivel 3A

Advisory seguro con autoridad limitada para aclarar, bloquear o repetir una
vez el plan canónico. Requiere confianza mínima, allowlist de señales y
validación determinista posterior.

### Nivel 3B

Activación selectiva por patrones calibrados con trazas reales.

### Nivel 3C

Correcciones persistentes, sólo después de replay, versionado, aprobación y
rollback.

### Nivel 4

Aprendizaje offline desde trazas revisadas, despliegue mediante evaluación y
aprobación humana. Nunca cambios directos desde una conversación individual.
