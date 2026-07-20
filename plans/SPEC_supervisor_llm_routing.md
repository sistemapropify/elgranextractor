# SPEC: Supervisor con LLM Routing (Function Calling) — Propifai (PIL)

> **Objetivo:** reemplazar el mecanismo de routing del Supervisor (templates + similitud de embeddings E5) por decisión directa del LLM vía function calling — el mismo mecanismo que usa Claude para elegir qué herramienta usar.
> **No afecta:** `SemanticSkillRouter` a nivel de skills dentro del loop ReAct de cada agente, ni el `SkillRegistry`. Ese nivel se mantiene con embeddings (justificación en sección 1.2).
> **Motivador:** bug documentado — "que terrenos en cayma tienes" enrutado a `agente_mercado` en vez de `agente_propiedades` por colisión léxica entre templates (score 0.8748, decisión "segura" pero incorrecta).
> **Audiencia:** agente de implementación (VS Code MCP).

---

## 1. Contexto y alcance

### 1.1 Qué se reemplaza

Hoy `Supervisor.route()` (`agents/supervisor.py`) usa `SemanticSkillRouter`: calcula el embedding E5 del mensaje, lo compara contra 44 templates predefinidos, y devuelve el agente del template con mayor similitud coseno. Es matching léxico-vectorial, no comprensión.

Se reemplaza por: el Supervisor le pasa al LLM (DeepSeek) el mensaje del usuario + la lista de agentes disponibles con su descripción, y el LLM decide directamente cuál(es) invocar, con razonamiento explícito.

### 1.2 Qué NO se reemplaza (y por qué)

El `SemanticSkillRouter` sigue existiendo y se usa dentro del loop ReAct de cada agente para elegir entre sus propias skills (ej. `AgentePropiedades` decidiendo entre `busqueda_propiedades`, `busqueda_exacta`, `matching_hibrido`, `acm_analisis`). Ahí el trade-off de costo/latencia sigue siendo favorable a embeddings porque:

- Un agente puede llamar a `_think()` varias veces por iteración (hasta 5) — hacerlo con LLM completo en cada paso multiplicaría el costo dentro del propio loop.
- El universo de opciones dentro de un agente es más chico (3-4 skills) y más homogéneo semánticamente — menos propenso a colisiones graves.
- El costo de un error a este nivel es menor: el propio `_observe()` del ReAct loop ya detecta si la skill elegida no sirvió y reintenta.

**Regla general que deja este spec:** decisiones de alto impacto y baja frecuencia (qué agente, 1 vez por mensaje) → LLM. Decisiones de bajo impacto y alta frecuencia (qué skill, hasta 5 veces por mensaje dentro de un loop) → embeddings, con guardrails de reintento que ya existen.

---

## 2. Diseño

### 2.1 Contrato de herramientas del Supervisor

**Ubicación:** `agents/supervisor.py`

Cada agente registrado en `AgentRegistry` ya tiene `AgentDefinition.description` — se reutiliza como base, pero se reescribe con foco en **diferenciación de intención**, no en similitud léxica (el error de fondo del sistema actual era que las descripciones/templates compartían vocabulario en vez de competir por intención).

```python
def build_supervisor_tools(available_agents: list[AgentDefinition]) -> list[dict]:
    """Convierte AgentDefinition en el formato de tools que espera DeepSeek."""
    return [
        {
            "type": "function",
            "function": {
                "name": agent.name,
                "description": agent.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sub_query": {
                            "type": "string",
                            "description": "La parte del mensaje del usuario que este agente debe resolver. Si el mensaje completo aplica, repítelo tal cual."
                        }
                    },
                    "required": ["sub_query"]
                }
            }
        }
        for agent in available_agents
    ]
```

**Descripciones reescritas (reemplazan los 44 templates actuales):**

```python
AGENT_DESCRIPTIONS = {
    "agente_propiedades": (
        "Busca o consulta el INVENTARIO EXISTENTE de propiedades: qué propiedades hay, "
        "disponibilidad, características, ubicación, matching entre oferta y requerimientos. "
        "Úsalo cuando el usuario pregunta qué tiene la empresa, busca algo específico, "
        "o quiere ver listados. Ejemplos de intención (no frases literales): "
        "'qué tienes', 'busco', 'muéstrame', 'tienen algo de'."
    ),
    "agente_mercado": (
        "Genera ANÁLISIS y REPORTES de mercado: precios promedio, evolución histórica de precios, "
        "tendencias por zona, estado de campañas de marketing. NO se usa para listar propiedades "
        "existentes, sino para responder preguntas de tipo analítico. "
        "Ejemplos de intención: 'cuál es el precio promedio', 'cómo ha evolucionado', "
        "'dame un reporte de', 'qué campañas están activas'."
    ),
    "agente_requerimientos": (
        "Gestiona los requerimientos de clientes/compradores y su cruce con el inventario. "
        "Úsalo cuando la consulta es sobre lo que un cliente busca, no sobre el inventario en sí."
    ),
}
```

### 2.2 Llamada al LLM con tools

**Ubicación:** `services/llm.py` (extiende `LLMService`, no lo reemplaza)

```python
def call_with_tools(self, system_prompt: str, message: str, tools: list[dict],
                     conversation_history: list[dict] | None = None) -> ToolCallResult:
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            *(conversation_history or []),
            {"role": "user", "content": message},
        ],
        "tools": tools,
        "tool_choice": "required",   # fuerza a elegir al menos una herramienta;
                                       # nunca debe responder texto libre en este paso
    }
    response = self._call_deepseek_api(payload, caller_app="supervisor_routing")
    return self._parse_tool_calls(response)
```

> **Nota de verificación obligatoria antes de implementar:** confirmar en la documentación actual de DeepSeek API que el endpoint `deepseek-chat` soporta `tools`/`tool_choice` en el formato compatible con OpenAI (es el estándar que DeepSeek dice seguir). Si en el momento de implementar hay restricciones (ej. no soporta `tool_choice: "required"`, solo `"auto"`), ajustar el prompt de sistema para forzar explícitamente la selección y validar en post-proceso que la respuesta contenga al menos un `tool_call`.

### 2.3 Supervisor.route() actualizado

```python
class Supervisor:
    def route(self, message: str, user_level: int, user_context: dict = None) -> dict:
        available = self.registry.list_available(user_level)
        tools = build_supervisor_tools(available)

        result = self.llm_service.call_with_tools(
            system_prompt=(
                "Eres el supervisor de un sistema inmobiliario. Tu única tarea es decidir "
                "qué agente(s) deben resolver la consulta del usuario. Si la consulta tiene "
                "más de una intención distinta (ej. buscar propiedades Y pedir un análisis de precios), "
                "llama a más de un agente, cada uno con su sub_query correspondiente. "
                "No inventes agentes que no estén en la lista de herramientas."
            ),
            message=message,
            tools=tools,
        )

        if not result.tool_calls:
            # nunca debe pasar con tool_choice=required, pero es el guardrail de piso
            return {'agent': 'agente_fallback_rag', 'execution_mode': 'single',
                    'reasoning': 'LLM no seleccionó ningún agente'}

        if len(result.tool_calls) == 1:
            call = result.tool_calls[0]
            return {'agent': call.name, 'execution_mode': 'single',
                    'sub_query': call.arguments['sub_query'], 'reasoning': result.reasoning}

        return {
            'agents': [{'agent': c.name, 'sub_query': c.arguments['sub_query']} for c in result.tool_calls],
            'execution_mode': 'parallel',
            'reasoning': result.reasoning,
        }
```

**Ventaja estructural respecto al sistema actual:** la detección de consultas compuestas (`_es_consulta_compuesta`, `_descomponer_consulta`) deja de ser lógica separada basada en conectores textuales ("y", "además", ";") — el LLM decide naturalmente si necesita uno o varios agentes, y genera la sub-consulta apropiada para cada uno. Ese código se puede retirar una vez validado el nuevo Supervisor (sección 6).

### 2.4 Fallback si DeepSeek falla o no responde

El Supervisor por LLM depende de una llamada de red. Si DeepSeek falla (timeout, error 5xx), no debe tumbar la conversación:

```python
def route(self, message: str, user_level: int, user_context: dict = None) -> dict:
    try:
        return self._route_with_llm(message, user_level, user_context)
    except (DeepSeekAPIError, TimeoutError) as e:
        logger.warning("Supervisor LLM routing falló, usando fallback por embeddings", error=str(e))
        return self._route_with_embeddings_fallback(message, user_level, user_context)
```

`_route_with_embeddings_fallback` reutiliza el `SemanticSkillRouter` actual tal cual — **no se elimina el sistema de templates, se degrada a fallback**, siguiendo el mismo principio que ya aplicaste en el resto del sistema (PILOrchestrator como fallback de AgentGraphBuilder). Esto también resuelve de forma natural la pregunta de "qué pasa si DeepSeek está caído": el sistema sigue funcionando, solo con el routing menos preciso.

---

## 3. Observabilidad y explicabilidad

El LLM debe devolver su razonamiento junto con la elección de herramienta — esto es lo que hace que el error sea diagnosticable (ventaja mencionada frente a los embeddings: "por qué matcheó" vs "el LLM razonó mal esto, puedo ver por qué").

Extender `reasoning_steps` en `ChatResult.metadata` con:

```python
{
    "icon": "🧠",
    "title": "Supervisor decidió con LLM",
    "description": result.reasoning,   # texto explicando por qué eligió ese agente
    "type": "router_llm",
    "routing_method": "llm" | "embeddings_fallback",
    "order": 0,
}
```

Persistir también `routing_method` en `AgentExecution` (tabla ya definida en el spec de refactor previo) — permite medir, con el tiempo, con qué frecuencia se usa el fallback y si el LLM routing realmente reduce los errores de clasificación frente al baseline de embeddings.

---

## 4. Costo y latencia — presupuesto explícito

Tu propia métrica documentada: 31.4s totales, ~5 llamadas DeepSeek (3 think + 2 formateo/episodio). Este cambio agrega **1 llamada más**, específicamente para el routing.

| Ítem | Antes | Después |
|---|---|---|
| Latencia de routing | ~28ms (embeddings) | ~1-3s (llamada DeepSeek) |
| Llamadas DeepSeek por mensaje | ~5 | ~6 |
| Costo adicional estimado | — | Marginal: prompt corto (mensaje + descripciones de 3-4 agentes), sin contexto RAG pesado |

**Mitigación de latencia:** el `_call_deepseek_api` para routing debe usar un prompt mínimo (sin historial completo de conversación salvo que sea necesario para resolver referencias — eso ya lo hace `ContextAgent` aparte) y, si DeepSeek expone un modelo más liviano/rápido para tareas de clasificación, evaluarlo en la decisión abierta de la sección 7. Si no hay alternativa más barata, el costo se acepta: es la decisión de mayor impacto de todo el flujo y vale la latencia extra frente al costo de que el agente equivocado ejecute skills equivocadas y dispare un reintento completo aguas abajo.

---

## 5. Suite de regresión (obligatoria antes de activar en producción)

Reutilizar/expandir el set de casos ya mencionado en el spec de refactor (fase 3/10), con foco específico en los casos de colisión léxica ya identificados:

```python
CASOS_REGRESION_SUPERVISOR = [
    {"query": "que terrenos en cayma tienes en la base de datos", "agente_esperado": "agente_propiedades"},
    {"query": "precio promedio de terrenos en Cayma", "agente_esperado": "agente_mercado"},
    {"query": "cuánto cuestan los terrenos en Cayma normalmente", "agente_esperado": "agente_mercado"},
    {"query": "busco terrenos en Cayma para comprar", "agente_esperado": "agente_propiedades"},
    {"query": "busco departamento en Cayma y quiero saber cómo está el precio ahí", "agente_esperado": "parallel:[agente_propiedades, agente_mercado]"},
    # ... mínimo 30 casos, incluyendo los reales que ya fallaron en producción
]
```

Correr esta suite comparando **routing por LLM vs routing por embeddings actual**, lado a lado, antes de reemplazar el default — es la validación empírica de que el cambio efectivamente mejora precisión y no solo cambia el tipo de error.

---

## 6. Plan de migración

1. **Implementar `call_with_tools` en `LLMService`** — aislado, sin tocar el Supervisor todavía. Test unitario con mocks de respuesta DeepSeek.
2. **Implementar `Supervisor._route_with_llm`** con fallback a embeddings (sección 2.4) desde el día uno — nunca se despliega sin la red de seguridad.
3. **Shadow mode:** correr ambos routings (LLM y embeddings) en paralelo por cada mensaje real, loguear ambos resultados en `AgentExecution` sin que el LLM decida todavía la ejecución real. Acumular al menos 100-200 mensajes reales.
4. **Comparar** con la suite de regresión (sección 5) + los casos reales acumulados en shadow mode. Medir: % de acuerdo entre ambos métodos, y en los desacuerdos, cuál acertó (revisión manual).
5. **Activar LLM routing como primario**, embeddings como fallback real (no solo shadow).
6. **Retirar la lógica de detección de consultas compuestas por conectores** (`_es_consulta_compuesta`, `_descomponer_consulta`) una vez confirmado que el LLM la resuelve mejor de forma nativa (sección 2.3) — no antes.
7. **Mantener** `SemanticSkillRouter` intacto para el routing de skills dentro de cada agente (sección 1.2) — este spec no lo toca.

---

## 7. Decisiones abiertas

- **¿`deepseek-chat` o un modelo más económico/rápido para routing?** Si DeepSeek ofrece un modelo más liviano apto para clasificación con tools, evaluarlo — el routing no necesita el mismo modelo que genera la respuesta final al usuario.
- **¿`tool_choice: "required"` está soportado tal cual, o hay que emularlo por prompt?** Verificar contra la documentación vigente de DeepSeek antes de implementar la sección 2.2.
- **¿Cuántos mensajes reales se acumulan en shadow mode antes de decidir el corte a producción?** Este spec sugiere 100-200 como piso, ajustable según volumen real de tráfico.
- **¿El fallback a embeddings se loguea como incidente o como comportamiento normal?** Afecta si generas alertas cuando el fallback se activa con frecuencia (podría ser señal de que DeepSeek tiene problemas de disponibilidad, más allá del routing).

---

## 8. Criterios de aceptación finales

- [ ] El caso "que terrenos en cayma tienes en la base de datos" enruta a `agente_propiedades` de forma consistente (10/10 corridas).
- [ ] La suite de regresión (sección 5) pasa con routing por LLM en ≥95% de los casos.
- [ ] Si DeepSeek falla (simulado con timeout forzado), el Supervisor responde igual, usando el fallback de embeddings, sin error visible al usuario.
- [ ] `reasoning_steps` muestra el razonamiento del LLM para cada decisión de routing, visible en el dashboard de agentes.
- [ ] Latencia total del flujo no aumenta más de ~2-3s respecto al baseline actual (31.4s → máximo ~34s), documentado con las mismas métricas de la sección 8 del documento de arquitectura.
