# Plan — Estimar el costo en dólares por lead evaluado

> Propifai · Módulo: lead_intelligence (evaluación de calidad de motor)

## Contexto

- Cada lead evaluado genera **1 a 3 llamadas** a DeepSeek:
  comando `analyze_lead_conversations` → `AnalizarConversacionLeadSkill` →
  `analyze_conversation_context` (reintenta hasta 3 veces, sale en el primer éxito) →
  `LLMService.extract_structured_data` → `_call_deepseek_api` → `AIConsumptionLog.registrar_llamada`.
- `AIConsumptionLog` ya guarda por llamada: `prompt_tokens`, `completion_tokens`,
  `total_tokens`, `estimated_cost_usd` y `trace_id`.
- **Problema actual:** `trace_id` se guarda vacío para las llamadas de evaluación;
  no hay forma de sumar el costo por lead (solo por llamada o global).

## Costo de una llamada

- Input:  prompt_tokens × (precio_input / 1M)
- Output: completion_tokens × (precio_output / 1M)
- El precio hoy está hardcodeado para `deepseek-chat` ($0.14 input / $0.28 output por 1M);
  el modelo real en uso es `deepseek-v4-flash`. Conviene parametrizarlo.

## Cambios propuestos

1. **Precios parametrizables** (settings/env):
   - `DEEPSEEK_PRICE_INPUT_PER_1M` y `DEEPSEEK_PRICE_OUTPUT_PER_1M` leídos en
     `AIConsumptionLog.registrar_llamada` (con default actual).

2. **Propagar trace_id con el id del lead**:
   - `LLMService.extract_structured_data(text, schema, *, trace_id="")`
   - `_call_deepseek_api(..., trace_id="")` → pasa a `registrar_llamada(trace_id=...)`
     en las 4 ramas (éxito + timeout + conexión + error inesperado).
   - `analyze_conversation_context(messages, *, trace_id="")` → pasa trace_id.
   - `AnalizarConversacionLeadSkill.execute(..., trace_id="")`.
   - Comando `analyze_lead_conversations` → `trace_id = f"lead:{row['id']}"`.

3. **Agregación** en `lead_intelligence/services.py`:
   - `get_lead_evaluation_costs(run_id)`: suma `estimated_cost_usd` agrupado por
     `trace_id` (formato `lead:{id}`) → costo por lead + total del run.

4. **Vista/API** (dashboard de calidad de motor):
   - Exponer el costo por lead en la lista de revisión y el total en el panel del run.

5. **UI**: columna "Costo IA $" por lead + contador "Costo IA total $" del run.

6. **Estimación retroactiva** (runs ya ejecutados sin trace_id):
   - Consulta sobre `AIConsumptionLog` (endpoint=extract_structured_data) en la ventana
     del run ÷ número de leads → promedio por lead (aproximado).

## No se toca

- No se cambia el modelo de evaluación ni los resultados.
- No hay migración: `trace_id` ya existe en `AIConsumptionLog`.
- No se crean bases de datos.

## Verificación

- `py -m py_compile` de los archivos modificados.
- Prueba del flujo: evaluar 1 lead con `--lead-id` y confirmar que sus llamadas
  quedan con `trace_id = lead:{id}` y con costo > 0.
- Confirmar agregación por run.
