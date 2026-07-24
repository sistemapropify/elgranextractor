# Track A — Robustez del ciclo agentic en tiempo de ejecución

## Nivel 1 — Determinista

**Estado:** implementado.

- valida filtros y resultados;
- distingue éxito técnico de calidad;
- aclara, bloquea o reintenta una vez;
- mantiene requisitos con evidencia.

## Nivel 2 — Juez LLM

**Estado:** implementado en shadow.

- ejecución selectiva;
- JSON estricto;
- comparación con Nivel 1;
- sin autoridad en modo `shadow`;
- fallo del juez no rompe la consulta.

## Nivel 3A — Advisory seguro

**Estado:** implementado.

- activo únicamente con `EXECUTION_JUDGE_MODE=advisory`;
- confianza mínima configurable, piso de 0.80;
- acciones permitidas: `clarify`, `block`, `replan`;
- `clarify` requiere campos faltantes estructurados;
- `block` requiere una señal de riesgo permitida;
- `replan` reutiliza el plan canónico y sólo puede ocurrir una vez;
- Nivel 1 valida obligatoriamente el resultado del reintento;
- toda autoridad aplicada se registra en telemetría.

Configuración inicial:

```env
EXECUTION_JUDGE_MODE=advisory
EXECUTION_JUDGE_MIN_CONFIDENCE=0.90
```

## Nivel 3B — Activación calibrada

**Estado:** pendiente.

Requiere métricas por señal, intención y tasa de falsos positivos. Permitirá
activar autoridad sólo para patrones demostrablemente confiables.

## Nivel 3C — Correcciones persistentes

**Estado:** bloqueado por seguridad.

No se implementa hasta disponer de replay, versionado, aprobación humana y
rollback. Nunca incluirá edición autónoma libre de código o datos.

