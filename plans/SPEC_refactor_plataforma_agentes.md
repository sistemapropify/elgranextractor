# SPEC: Refactor a Plataforma de Agentes Independientes — Propifai (PIL)

> **Objetivo del documento:** especificación técnica completa para pasar de un pipeline lineal (Router → Search/Skill → Formatter) a una plataforma donde agentes independientes por dominio (propiedades, mercado, requerimientos, y futuros) razonan en loop, se activan dinámicamente y comparten el catálogo de 30+ skills ya existente.
> **Audiencia:** agente de implementación (VS Code MCP). Cada fase tiene criterios de aceptación verificables antes de pasar a la siguiente.
> **Principio rector:** ~70% de la lógica de dominio ya existe como skills. Este refactor envuelve y orquesta, no reescribe.

---

## 0. Diagnóstico que motiva el refactor

El sistema actual (`webapp/intelligence/agents/`) es un grafo LangGraph de un solo camino:

```
RouterAgent → (ContextAgent)? → SearchAgent → FormatterAgent
```

Problemas estructurales:

1. **No hay loop de razonamiento.** Cada nodo se ejecuta exactamente una vez. Si el resultado es pobre, no hay reintento ni cambio de estrategia.
2. **El Router elige una skill, no un agente.** No existe el concepto de "agente dueño de un dominio" que decida internamente qué hacer.
3. **No hay ejecución paralela real.** Una consulta compuesta ("buscame propiedades en Miraflores y dime cómo está el mercado ahí") no puede resolverse con dos flujos de trabajo simultáneos.
4. **No hay namespaces de estado.** Todo el estado vive en un único `state` compartido del grafo.
5. **No hay ciclo de aprendizaje.** El feedback en `EpisodicMemory` no retroalimenta thresholds, templates ni comportamiento futuro.
6. **Extender el sistema requiere tocar el core.** Agregar una nueva capacidad hoy significa registrar una skill más en el `SkillRegistry` y esperar que el Router la enrute bien — no hay un lugar natural para "un nuevo agente".

Este spec resuelve los 6 puntos, en ese orden de prioridad estructural (aunque la implementación real puede paralelizar algunas fases, ver sección 14).

---

## 1. Principios de diseño (no negociables)

- **Incremental, no big-bang.** El pipeline actual (`RouterAgent`/`SearchAgent`/`FormatterAgent`) se mantiene como fallback funcional durante toda la migración. Se apaga recién en la fase final, y es opcional.
- **Las skills no cambian.** `BaseSkill`, `SkillRegistry`, `SkillOrchestrator`, `SkillCache` se mantienen intactos. Los agentes las consumen, no las reemplazan.
- **Seguridad en código, no en prompts.** Qué skills puede usar cada agente se define y se hace cumplir en Python (listas explícitas, validación antes de ejecutar), nunca solo mediante instrucciones en el prompt del LLM.
- **Todo agente tiene límite de iteraciones.** Ningún loop ReAct es infinito. Máximo configurable por agente (default sugerido: 5).
- **Todo agente es observable.** Cada decisión (qué skill eligió, por qué, con qué score/razonamiento) queda trazada antes de que el agente termine.
- **Calibración empírica, no hardcodeada.** Cualquier threshold nuevo (confianza del supervisor, score de autocrítica) se dimensiona con datos reales antes de fijarse, siguiendo el mismo criterio que ya aplicaste en `SPEC_fix_busqueda_semantica.md`.

---

## 2. Arquitectura objetivo

```
Usuario
  │
  ▼
Supervisor (LangGraph, nodo raíz)
  │  clasifica intención → decide qué agente(s) activar → fan-out si aplica
  │
  ├──▶ AgentePropiedades   (ReAct loop, usa: BusquedaPropiedades, HybridMatching, ACM, BusquedaExacta)
  ├──▶ AgenteMercado       (ReAct loop, usa: ReportePrecios, MetricasMarketing, CampanasActivas, scrapers)
  ├──▶ AgenteRequerimientos(ReAct loop, usa: MisRequerimientos, MatchingOfertaDemanda, MisMatches)
  └──▶ [agentes futuros, mismo contrato]
  │
  ▼ (fan-in)
Agregador de resultados
  │
  ▼
Autocrítica (self-check antes de responder)
  │
  ▼
FormatterAgent (se reutiliza tal cual)
  │
  ▼
Respuesta al usuario
  │
  ▼ (async, post-respuesta)
Registro enriquecido en EpisodicMemory + señales de error
  │
  ▼ (job nocturno)
Recalibración de thresholds y templates
```

Cada `Agente*` es una instancia del mismo contrato (`BaseAgent`, sección 3), configurada de forma distinta (dominio, skills permitidas, prompt de rol).

---

## 3. Fase 1 — Contrato de Agente

**Ubicación:** `webapp/intelligence/agents/base_agent.py` (nuevo)

Define la interfaz que todo agente debe cumplir — es el equivalente de `BaseSkill` pero para agentes.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AgentStatus(str, Enum):
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    DONE = "done"
    FAILED = "failed"
    MAX_ITERATIONS = "max_iterations"


@dataclass
class AgentStep:
    """Un paso individual dentro del loop ReAct de un agente."""
    iteration: int
    thought: str                     # razonamiento del LLM antes de actuar
    skill_used: Optional[str]        # None si decidió no usar ninguna skill
    skill_params: Optional[dict]
    skill_result: Optional[dict]
    status: AgentStatus


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    final_answer: Optional[dict]     # datos estructurados que el Formatter consumirá
    steps: list[AgentStep] = field(default_factory=list)
    iterations_used: int = 0
    error_message: Optional[str] = None
    confidence: float = 0.0          # autoevaluación del propio agente


@dataclass
class AgentDefinition:
    """Metadatos declarativos de un agente — análogo a los atributos de BaseSkill."""
    name: str                        # snake_case único, ej. "agente_propiedades"
    description: str                 # usado por el Supervisor para enrutar
    domain: str                      # publico, legal, marketing, gerencia, ti, general
    allowed_skills: list[str]        # nombres exactos registrados en SkillRegistry
    access_level: int                # 1-5, igual que las skills
    max_iterations: int = 5
    system_prompt: str = ""          # rol y objetivo del agente
    is_active: bool = True


class BaseAgent(ABC):
    definition: AgentDefinition

    @abstractmethod
    def run(self, message: str, context: dict) -> AgentResult:
        """Ejecuta el loop ReAct completo. Debe respetar max_iterations."""
        ...

    def _validate_skill_access(self, skill_name: str) -> bool:
        """Guardrail obligatorio: nunca ejecutar una skill fuera de allowed_skills.
        Esta validación vive en código, no depende de que el LLM 'se porte bien'."""
        return skill_name in self.definition.allowed_skills
```

**Criterios de aceptación fase 1:**
- [ ] `BaseAgent` no puede instanciarse directamente (ABC).
- [ ] `_validate_skill_access` tiene test unitario que confirma que una skill no listada se rechaza aunque el LLM la solicite.
- [ ] `AgentResult` serializa a JSON sin pérdida (para loguear en `SkillExecution` o tabla nueva, ver fase 8).

---

## 4. Fase 2 — AgentRegistry

**Ubicación:** `webapp/intelligence/agents/registry.py` (nuevo)

Mismo patrón que `SkillRegistry` (singleton, registro en `apps.py`).

```python
class AgentRegistry:
    _instance = None
    _agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        cls._agents[agent.definition.name] = agent

    @classmethod
    def get_by_name(cls, name: str) -> Optional[BaseAgent]:
        return cls._agents.get(name)

    @classmethod
    def list_available(cls, user_level: int, domain: Optional[str] = None) -> list[AgentDefinition]:
        return [
            a.definition for a in cls._agents.values()
            if a.definition.is_active
            and a.definition.access_level <= user_level
            and (domain is None or a.definition.domain == domain)
        ]
```

Registro en `apps.py`, junto a las 30+ skills existentes (sección "Registrar 30+ skills"):

```python
# apps.py, dentro de IntelligenceConfig.ready()
from .agents.propiedades_agent import AgentePropiedades
from .agents.mercado_agent import AgenteMercado
from .agents.requerimientos_agent import AgenteRequerimientos

AgentRegistry.register(AgentePropiedades())
AgentRegistry.register(AgenteMercado())
AgentRegistry.register(AgenteRequerimientos())
```

**Criterios de aceptación fase 2:**
- [ ] `AgentRegistry.list_available()` respeta niveles de acceso igual que `SkillRegistry.list_available()`.
- [ ] Los 3 agentes piloto quedan registrados y visibles en un endpoint de diagnóstico (`agents/dashboard/`, análogo a `skills/dashboard/`).

---

## 5. Fase 3 — Supervisor dinámico

**Ubicación:** `webapp/intelligence/agents/supervisor.py` (reemplaza gradualmente a `router_agent.py`)

El Supervisor no elige una skill — elige **uno o más agentes**. Reutiliza el mismo mecanismo de `SemanticSkillRouter` (embeddings E5 + templates) pero aplicado a `AgentDefinition.description` en vez de a skills individuales.

```python
class Supervisor:
    def __init__(self, router: SemanticSkillRouter, registry: AgentRegistry):
        self.router = router          # reutiliza infraestructura de embeddings E5 existente
        self.registry = registry

    def route(self, message: str, user_level: int) -> list[str]:
        """Devuelve una lista de nombres de agentes a activar.
        Lista de 1 = flujo simple. Lista de 2+ = ejecución en paralelo (fase 5)."""
        candidates = self.registry.list_available(user_level)
        sub_queries = self._decompose_if_compound(message)  # reutiliza lógica
                                                              # de Multi-Skill Orchestration
                                                              # ya existente en semantic_router.py
        selected = []
        for sq in sub_queries:
            result = self.router.classify_against(sq, candidates)
            if result.accepted:
                selected.append(result.agent_name)
        return selected or ["agente_fallback_rag"]  # nunca deja al usuario sin respuesta
```

**Nota importante:** la lógica de "Multi-Skill Orchestration" (detección de consultas compuestas con conectores "y", "además", ";") que ya está en `semantic_router.py` (SPEC v2.1) se reutiliza tal cual — es exactamente lo que este Supervisor necesita. No se reescribe, se apunta a agentes en vez de a skills.

**Criterios de aceptación fase 3:**
- [ ] Una consulta simple activa exactamente 1 agente.
- [ ] Una consulta compuesta ("propiedades en Miraflores y cómo está el mercado ahí") activa 2 agentes.
- [ ] Ninguna consulta queda sin agente asignado (fallback garantizado).
- [ ] Test de regresión con al menos 30 consultas reales etiquetadas manualmente (agente esperado vs agente obtenido).

---

## 6. Fase 4 — Loop ReAct por agente

**Ubicación:** `webapp/intelligence/agents/react_loop.py` (mixin/helper reutilizado por todos los agentes concretos)

Este es el corazón de "que aprendan y se corrijan": cada agente puede intentar, observar, y decidir si reintenta con otra skill o con otros parámetros — dentro de su propia ejecución, no como fallback externo.

```python
class ReActLoopMixin:
    def run(self, message: str, context: dict) -> AgentResult:
        steps = []
        for i in range(self.definition.max_iterations):
            thought = self._think(message, context, steps)          # LLM decide próxima acción
            if thought.is_final:
                return self._finalize(steps, thought)

            if not self._validate_skill_access(thought.skill_name):
                steps.append(AgentStep(i, thought.reasoning, None, None, None, AgentStatus.FAILED))
                continue  # el LLM pidió algo fuera de su alcance; se ignora y se reintenta

            result = SkillOrchestrator.execute(thought.skill_name, thought.params, context)
            observation = self._observe(result)                     # ¿el resultado sirve?
            steps.append(AgentStep(i, thought.reasoning, thought.skill_name,
                                    thought.params, result.data, AgentStatus.OBSERVING))

            if observation.is_sufficient:
                return self._finalize(steps, observation)
            # si no es suficiente, el loop continúa: el agente puede probar otra skill
            # o los mismos con otros parámetros, informado por lo que observó

        return AgentResult(self.definition.name, success=False, final_answer=None,
                            steps=steps, iterations_used=self.definition.max_iterations,
                            error_message="max_iterations alcanzado", confidence=0.0)
```

`_think()` y `_observe()` llaman a `LLMService` (DeepSeek) con prompts específicos por rol — reutilizan `PromptManager` existente.

**Criterios de aceptación fase 4:**
- [ ] Un agente que recibe un resultado vacío en su primer intento prueba una segunda skill o segundos parámetros antes de rendirse (verificable con un caso de prueba controlado).
- [ ] `max_iterations` se respeta estrictamente — test que fuerza un loop infinito potencial y confirma el corte.
- [ ] Cada `AgentStep` queda serializado para trazabilidad (fase 8).

---

## 7. Fase 5 — Ejecución paralela (fan-out / fan-in)

**Ubicación:** `webapp/intelligence/agents/orchestrator.py` (se extiende, no se reemplaza)

Usa el soporte nativo de LangGraph para nodos paralelos.

```python
from langgraph.graph import StateGraph

def build_graph():
    graph = StateGraph(SupervisorState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("agente_propiedades", agente_propiedades_node)
    graph.add_node("agente_mercado", agente_mercado_node)
    graph.add_node("agente_requerimientos", agente_requerimientos_node)
    graph.add_node("aggregator", aggregator_node)
    graph.add_node("self_critique", self_critique_node)     # fase 9
    graph.add_node("formatter", formatter_node)              # se reutiliza tal cual

    # fan-out condicional: el supervisor decide cuáles activar (puede ser 1, 2 o 3)
    graph.add_conditional_edges("supervisor", route_to_agents)
    # fan-in: todos los agentes activados convergen en el aggregator
    for agent_node in ["agente_propiedades", "agente_mercado", "agente_requerimientos"]:
        graph.add_edge(agent_node, "aggregator")
    graph.add_edge("aggregator", "self_critique")
    graph.add_edge("self_critique", "formatter")
    return graph.compile()
```

**Criterios de aceptación fase 5:**
- [ ] Dos agentes activados por la misma consulta corren efectivamente en paralelo (medible por timestamps de inicio/fin superpuestos, no secuenciales).
- [ ] El aggregator no pierde resultados de ningún agente activado, incluso si uno falla (`AgentResult.success=False`).

---

## 8. Fase 6 — State management y namespaces

**Problema a resolver:** si `AgentePropiedades` y `AgenteMercado` corren en paralelo sobre el mismo `state` de LangGraph, uno puede sobrescribir los campos del otro.

**Solución:** cada agente escribe exclusivamente en su propio namespace dentro del state compartido.

```python
class SupervisorState(TypedDict):
    message: str
    user_context: dict
    agents_activated: list[str]
    # namespace por agente — nunca se cruzan
    results: dict[str, AgentResult]   # key = agent_name, value = su resultado
    aggregated_answer: Optional[dict]
    critique_passed: bool
```

Cada nodo de agente en el grafo escribe únicamente en `state["results"][self.definition.name]`, nunca en una clave compartida sin prefijo.

**Criterios de aceptación fase 6:**
- [ ] Test con 2 agentes en paralelo que escriben resultados distintos, verificando que ambos sobreviven en el state final sin pisarse.

---

## 9. Fase 7 — Guardrails de seguridad en código

Ya cubierto parcialmente en `_validate_skill_access` (fase 1). Se agrega:

- **Whitelist de dominios por agente**: un agente de nivel `marketing` nunca puede invocar una skill de `access_level` 5 (TI), aunque esté en su `allowed_skills` por error de configuración — doble validación cruzando con `UserIntelligenceProfile.can_access_collection()`.
- **Límite de costo por ejecución de agente**: cada `AgentResult` acumula tokens/costo de todas sus iteraciones (via `AIConsumptionLog` existente); si supera un budget configurable, el loop se corta antes de `max_iterations`.

```python
def _check_budget(self, accumulated_cost_usd: float, budget_limit: float) -> bool:
    return accumulated_cost_usd < budget_limit
```

**Criterios de aceptación fase 7:**
- [ ] Un agente mal configurado (allowed_skills con una skill de nivel superior a su access_level) no logra ejecutarla — test que confirma el rechazo doble.
- [ ] Un agente que supera su presupuesto de costo corta el loop y responde con lo que tiene, no sigue iterando indefinidamente.

---

## 10. Fase 8 — Observabilidad y trazabilidad

**Ubicación:** nueva tabla `intelligence_agent_execution` (análoga a `SkillExecution`)

```python
class AgentExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    agent_name = models.CharField(max_length=100)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    steps = models.JSONField()            # lista de AgentStep serializados
    iterations_used = models.IntegerField()
    success = models.BooleanField()
    confidence = models.FloatField()
    total_cost_usd = models.DecimalField(max_digits=10, decimal_places=6)
    duration_ms = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
```

Cada `AgentResult` se persiste aquí antes de devolver la respuesta. Esto permite, en el dashboard (reutilizando el patrón de `skills_dashboard.html`), ver: qué agente se eligió, cuántas iteraciones usó, qué skills probó y en qué orden, y por qué se rindió si falló.

**Criterios de aceptación fase 8:**
- [ ] Toda ejecución de agente (exitosa o no) queda registrada, sin excepción.
- [ ] Vista de detalle (`agents/execution/{id}/`) muestra la traza completa de pensamiento → acción → observación por iteración.

---

## 11. Fase 9 — Ciclo de aprendizaje (autocrítica + feedback + recalibración)

Esta fase es la que responde directamente a "que aprendan de los errores y se corrijan".

### 11.1 Autocrítica (nodo `self_critique` del grafo)

Antes de llegar al Formatter, un paso adicional evalúa el resultado agregado:

```python
def self_critique_node(state: SupervisorState) -> SupervisorState:
    critique = LLMService.evaluate_response(
        original_message=state["message"],
        aggregated_answer=state["aggregated_answer"],
    )
    state["critique_passed"] = critique.is_sufficient
    if not critique.is_sufficient and state.get("critique_retries", 0) < 1:
        state["critique_retries"] = state.get("critique_retries", 0) + 1
        state["agents_activated"] = critique.suggested_retry_agents  # puede reintentar con otro agente
    return state
```

Un único reintento automático (no un loop infinito) cuando la autocrítica falla, antes de responder igual con una nota de baja confianza si el reintento tampoco mejora.

### 11.2 Registro enriquecido para aprendizaje

Extender `EpisodicMemory` (ya existe, no se crea tabla nueva) con:
- `agent_execution_ids`: referencia a los `AgentExecution` involucrados.
- `critique_result`: si pasó autocrítica en el primer intento o necesitó reintento.

### 11.3 Job de recalibración nocturna

**Ubicación:** nuevo management command `webapp/intelligence/management/commands/recalibrar_agentes.py`

```python
class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        # 1. Extraer episodios con feedback negativo o critique_result='retry_needed'
        casos_problema = EpisodicMemory.objects.filter(
            Q(feedback__thumbs='down') | Q(critique_result='retry_needed')
        ).select_related('conversation')

        # 2. Agrupar por agente y por skill para detectar patrones
        # 3. Para casos de bajo score de routing repetidos, generar candidatos
        #    a nuevos templates (requiere revisión humana antes de aplicar,
        #    al menos en la primera iteración de esta fase)
        # 4. Recalcular threshold óptimo del Supervisor con los datos acumulados
        #    (mismo criterio de calibración empírica que en SPEC_fix_busqueda_semantica.md)
        nuevo_threshold = calibrar_threshold(casos_problema)
        AgentConfig.objects.update_or_create(
            key='supervisor_threshold', defaults={'value': nuevo_threshold}
        )
```

**Criterios de aceptación fase 9:**
- [ ] Una respuesta que la autocrítica marca insuficiente dispara exactamente un reintento, nunca más de uno.
- [ ] El job nocturno corre sin intervención manual y genera un reporte (no aplica cambios automáticos a templates en la primera versión — solo al threshold numérico, que es seguro de ajustar automáticamente).
- [ ] Cambios de threshold quedan versionados (se puede revertir a un valor anterior).

---

## 12. Fase 10 — Suite de regresión continua

Ya especificada como fase 6 en `SPEC_fix_busqueda_semantica.md` para el router de skills. Se extiende al Supervisor y a los agentes:

- Set de consultas reales etiquetadas (agente esperado, skill esperada, resultado mínimo aceptable).
- Corre automáticamente después de cualquier cambio de threshold (fase 9) o de templates.
- Bloquea la recalibración si introduce regresiones (más del X% de casos que antes pasaban ahora fallan).

**Criterios de aceptación fase 10:**
- [ ] Suite con mínimo 50 casos reales cubriendo los 3 agentes piloto.
- [ ] La recalibración nocturna (fase 9) corre la suite antes de persistir el nuevo threshold; si hay regresión, no lo aplica y alerta.

---

## 13. Migración de los 3 agentes piloto

Mapeo directo de skills existentes a cada agente — no se reescribe lógica de dominio, solo se envuelve:

| Agente | Skills que envuelve (ya existentes) |
|---|---|
| `AgentePropiedades` | `BusquedaPropiedadesSkill`, `BusquedaExactaSkill`, `HybridMatchingSkill`, `ACMAnalisisSkill` |
| `AgenteMercado` | `ReportePreciosZonaSkill`, `MetricasMarketingSkill`, `CampanasActivasSkill`, `ScraperOrchestratorSkill` |
| `AgenteRequerimientos` | `MisRequerimientosSkill`, `MatchingOfertaDemandaSkill`, `MisMatchesSkill` |

Cada uno se implementa como subclase de `BaseAgent` + `ReActLoopMixin`, con su `system_prompt` propio definiendo su rol y objetivo (ej. "Eres el agente responsable de encontrar propiedades que coincidan con lo que pide el usuario. Tienes acceso a estas skills: ...").

---

## 14. Plan de migración incremental (orden sugerido)

1. **Fase 1 + 2** (Contrato + Registry) — sin impacto en producción, se puede desplegar en paralelo al sistema actual.
2. **Fase 13** (3 agentes piloto) usando el contrato — probar en modo sombra (shadow mode: se ejecutan pero no reemplazan la respuesta real todavía).
3. **Fase 3** (Supervisor) — activar para un porcentaje pequeño de tráfico o solo para usuarios internos/nivel 5.
4. **Fase 4** (ReAct loop) — ya viene incluido en fase 13, pero se valida a fondo aquí con casos reales.
5. **Fase 6** (namespaces) antes de fase 5 (paralelo) — el paralelismo sin namespaces es la fuente de bugs más probable.
6. **Fase 5** (paralelo real).
7. **Fase 7** (guardrails) — en paralelo a cualquier fase anterior, no bloquea nada, pero debe estar antes de exponer a más usuarios.
8. **Fase 8** (observabilidad) — idealmente antes de fase 9, para poder diagnosticar la recalibración automática.
9. **Fase 9** (autocrítica + recalibración).
10. **Fase 10** (regresión continua) — se apoya en los casos ya etiquetados de fase 3.
11. **Retiro del pipeline legacy** (`RouterAgent`/`SearchAgent` fijo) — opcional, solo cuando el Supervisor cubra el 100% de los dominios migrados y la suite de regresión esté verde de forma sostenida (ej. 2 semanas sin regresiones).

---

## 15. Decisiones abiertas (definir antes de fase 3)

- **¿Qué LLM actúa como Supervisor?** DeepSeek (consistente con el resto del sistema, sin fallback hoy) vs. un modelo más económico solo para clasificación de alto nivel.
- **¿La invocación de agentes es visible al usuario?** ej. "Estoy consultando el agente de mercado..." vs. respuesta transparente sin exponer la orquestación interna.
- **¿Cuántos reintentos de autocrítica son aceptables en costo?** Definido aquí como 1, pero depende del presupuesto real (ver `AIConsumptionLog`).
- **¿Los templates del Supervisor se ajustan automáticamente o requieren aprobación humana en la primera versión?** Este spec asume aprobación humana para templates y ajuste automático solo para el threshold numérico — a revisar según tolerancia al riesgo.

---

## 16. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Loops ReAct incrementan costo de DeepSeek significativamente | Budget por agente (fase 7) + cache de `SkillCache` ya existente reduce llamadas repetidas |
| Paralelismo introduce condiciones de carrera en el state | Namespaces estrictos (fase 6) + tests específicos antes de habilitar fase 5 |
| Autocrítica automática entra en loop de reintentos costoso | Límite duro de 1 reintento (fase 9) |
| Recalibración automática degrada el sistema silenciosamente | Suite de regresión bloqueante antes de persistir cualquier cambio (fase 10) |
| Nuevos agentes mal configurados acceden a skills fuera de su dominio | Doble validación en código: `allowed_skills` + `UserIntelligenceProfile` (fase 7) |
