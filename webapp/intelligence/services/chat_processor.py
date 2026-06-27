"""
ChatProcessor v2 — DeepSeek como agente orquestador.

ARQUITECTURA (refactor v2):
- DeepSeek ve la CONVERSACIÓN COMPLETA como contexto
- DeepSeek decide QUÉ skill ejecutar y CON QUÉ parámetros
- DeepSeek determina si es una nueva consulta o seguimiento
- NO más resolver_contexto, context_manager, intent_classifier
- NO más reglas duras de routing, pipelines condicionales

Flujo:
1. Construir prompt de orquestación: skills + historial + mensaje
2. DeepSeek responde con JSON: {"skill": "...", "params": {...}, "respuesta_directa": "..."}
3. Si eligió skill → ejecutar vía SkillOrchestrator
4. Construir prompt de respuesta: historial + skill result + consulta
5. DeepSeek genera respuesta natural
6. Guardar en conversación + post-process (memoria episódica)

Compatibilidad:
- Mantiene la misma interfaz pública (ChatProcessor.process_message, ChatResult, ChatContext)
- Views existentes no requieren cambios (solo importan estos mismos símbolos)
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Generator
from django.utils import timezone

from ..models import (
    User, AppConfig, Conversation,
    IntelligenceCollection,
)
from .memory import MemoryService
from .episodic_memory import EpisodicMemoryService
from .rag import RAGService
from .llm import LLMService
from .prompts import (
    PromptManager,
    build_orchestration_prompt,
    parse_orchestration_response,
    OrchestrationDecision,
    format_episodic_context,
    format_memory_context,
    format_rag_context,
    build_full_prompt,
)
from .metrics import MetricsService, log
from ..skills import create_skill_system
from ..skills.orchestrator import ExecutionContext

# F2-001: LangGraph Orchestration
from ..agents.orchestrator import PILOrchestrator, create_initial_state

# Skill system singleton
SKILL_SYSTEM = create_skill_system(enable_cache=True, auto_discover_examples=True)


# ── Dataclasses de resultado ─────────────────────────────────────────

@dataclass
class ChatResult:
    """Resultado completo del procesamiento de un mensaje."""
    success: bool
    response_text: str
    conversation_id: str
    message_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    context_summary: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: str = ""


@dataclass
class ChatContext:
    """Contexto completo para procesar un mensaje."""
    user: User
    message: str
    conversation: Conversation
    use_memory: bool = True
    use_rag: bool = True
    collections: List[str] = field(default_factory=list)
    app_id: str = 'chat-web'
    streaming: bool = False
    max_tokens: int = 2000
    temperature: float = 0.1
    skill_name: Optional[str] = None
    skill_params: Dict[str, Any] = field(default_factory=dict)
    # Campos de compatibilidad con vistas legacy (no usados en v2)
    flow_name: Optional[str] = None
    flow_params: Dict[str, Any] = field(default_factory=dict)
    # Contexto de origen (canvas, chat-web, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamChunk:
    """Un chunk de la respuesta en streaming."""
    type: str  # 'metadata', 'chunk', 'complete', 'error'
    data: Dict[str, Any]


# ── Prompt de respuesta final ────────────────────────────────────────

RESPONSE_SYSTEM_PROMPT = """Eres un asistente inmobiliario experto en Arequipa, Perú.

HISTORIAL DE CONVERSACIÓN:
{historial}

CONSULTA DEL USUARIO:
"{mensaje}"

RESULTADOS DEL SISTEMA:
{resultados_skill}

INSTRUCCIONES:
1. Genera una respuesta NATURAL y CONVERSACIONAL en español.
2. USA EL HISTORIAL completo para mantener coherencia con la conversación.
3. Los RESULTADOS DEL SISTEMA son la ÚNICA fuente de datos reales.
   Si la sección RESULTADOS DEL SISTEMA contiene propiedades, DEBES listarlas.
   NUNCA digas "no encontré" o "no hay datos" si los resultados contienen propiedades.
4. PRESENTA los datos de los resultados del sistema de forma organizada y amigable.
   Incluye: título, precio, distrito, tipo de propiedad, área y características relevantes.
5. Si el usuario preguntó por propiedades, incluye: tipo, distrito, precio, área, características.
6. Si hay un mensaje de la skill (como "Se encontraron X propiedades"), ÚSALO como base.
7. Si la skill ejecutada NO es de búsqueda de propiedades (matching, ACM, etc.),
   PRESENTA los resultados según corresponda al tipo de skill.
8. Si NO HAY RESULTADOS en la sección RESULTADOS DEL SISTEMA, indícalo amablemente
   y sugiere refinar la búsqueda.
9. NO inventes propiedades ni datos que no estén en los resultados del sistema.
10. Usa un tono profesional pero cercano, como un asesor inmobiliario de confianza.
11. NO devuelvas JSON ni datos técnicos. Solo texto legible.
12. Responde en español."""


# ── ChatProcessor ────────────────────────────────────────────────────

class ChatProcessor:
    """
    Procesador de mensajes v2 con DeepSeek como agente orquestador.

    Flujo:
    1. Orquestación: DeepSeek decide qué skill ejecutar
    2. Ejecución: sistema ejecuta la skill elegida
    3. Respuesta: DeepSeek genera respuesta natural con los resultados

    F2-001: Integración con LangGraph PILOrchestrator.
    - Si USE_LANGGRAPH=True, usa StateGraph con 4 nodos
    - Si USE_LANGGRAPH=False, usa pipeline secuencial original
    """

    # F2-001: Usar LangGraph para orquestación multi-agente
    USE_LANGGRAPH = True

    # ── Método principal (no streaming) ─────────────────────────────────

    @classmethod
    def process_message(cls, ctx: ChatContext) -> ChatResult:
        """
        Procesa un mensaje completo (no streaming).

        Args:
            ctx: ChatContext con todos los parámetros.

        Returns:
            ChatResult con la respuesta y metadata.
        """
        with MetricsService.timer(
            'chat.process_message',
            user_id=str(ctx.user.id),
            app_id=ctx.app_id,
        ) as timer:
            try:
                # Guardar mensaje del usuario
                cls._save_user_message(ctx.conversation, ctx.message)

                # ── F2-001: LANGGRAPH ORCHESTRATION ──
                # EJECUCIÓN DIRECTION (sin ThreadPool + timeout):
                # Anteriormente usaba ThreadPoolExecutor con timeout=12s, lo que causaba:
                # 1. LangGraph corría en un hilo mientras el pipeline secuencial corría EN PARALELO
                # 2. Ambos ejecutaban search_dynamic() simultáneamente, duplicando el trabajo
                # 3. La respuesta de LangGraph era RECHAZADA por el filtro de "Estas son las propiedades"
                # 4. El sistema hacía TODO el trabajo DOS VECES (60-90s cada uno)
                #
                # Ahora: LangGraph corre sincrónicamente. Si falla o devuelve respuesta vacía,
                # se cae al pipeline secuencial como fallback. Nunca ambos al mismo tiempo.
                # Deshabilitar LangGraph para mensajes del canvas (usa pipeline secuencial
                # que tiene el contexto del lienzo via _orquestar y construye acciones add_nodes)
                # BUG ANTERIOR: La condición chequeaba canvas_ctx.get('propiedades') lo cual
                # falla cuando el canvas está vacío porque [] es falsy en Python.
                # Ahora: si el source es 'canvas', SIEMPRE usamos pipeline secuencial.
                usar_lg = cls.USE_LANGGRAPH
                if usar_lg and ctx.metadata and ctx.metadata.get('source') == 'canvas':
                    log.info("[Canvas] Mensaje del canvas. Usando pipeline secuencial (orquestacion canvas).")
                    usar_lg = False

                if usar_lg:
                    try:
                        lg_result = cls._process_with_langgraph(ctx, timer)
                        if lg_result and lg_result.response_text:
                            log.info(
                                f"[F2-001] LangGraph completado exitosamente",
                                skill=getattr(lg_result, 'skill_detectada', None),
                                latency_ms=getattr(timer, 'latency_ms', 0),
                            )
                            return lg_result
                        else:
                            log.info(f"[F2-001] LangGraph devolvió respuesta vacía. Usando fallback secuencial.")
                    except Exception as lg_err:
                        log.warning(f"[F2-001] LangGraph falló: {lg_err}. Usando fallback secuencial.")

                # ── PIPELINE SECUENCIAL ORIGINAL ──
                # PASO 1: ORQUESTACIÓN
                decision = cls._orquestar(ctx)

                if decision.respuesta_directa:
                    response_text = decision.respuesta_directa
                    resultados = None
                    skill_ejecutada = None
                else:
                    # PASO 2: EJECUCIÓN DE SKILL
                    skill_ejecutada = decision.skill
                    resultados = cls._ejecutar_skill(
                        skill_name=decision.skill,
                        params=decision.params,
                        ctx=ctx,
                        trace_id=timer.trace_id,
                    )

                    # Guardar resultados de busqueda_propiedades en la conversacion
                    if (resultados and resultados.get('success')
                        and decision.skill == 'busqueda_propiedades'
                        and resultados.get('data')):
                        try:
                            meta = ctx.conversation.metadata or {}
                            meta['ultima_busqueda'] = {
                                'resultados': resultados['data'][:50],
                                'total': len(resultados['data']),
                                'params': decision.params,
                            }
                            ctx.conversation.metadata = meta
                            ctx.conversation.save(update_fields=['metadata'])
                        except Exception as e:
                            log.warning(f"No se pudo guardar ultima busqueda: {e}")

                    # PASO 3: RESPUESTA NATURAL
                    response_text = cls._generar_respuesta(
                        ctx=ctx,
                        resultados=resultados,
                        skill_name=decision.skill,
                        trace_id=timer.trace_id,
                    )

                # Guardar respuesta en conversación
                texto_guardar = response_text
                if texto_guardar.startswith('__HTML__') and texto_guardar.endswith('__HTML__'):
                    texto_guardar = '🖼️ Resultados mostrados en formato visual.'
                message_id = cls._save_response(ctx.conversation, texto_guardar)

                # Post-process (memoria episódica, hechos)
                cls._save_post_process(
                    ctx=ctx,
                    response_text=response_text,
                    trace_id=timer.trace_id,
                )

                # NUEVO: extraer action de los resultados si existe
                action_data = None
                if resultados and isinstance(resultados, dict):
                    action_data = resultados.get('action')
                
                result = ChatResult(
                    success=True,
                    response_text=response_text,
                    conversation_id=str(ctx.conversation.id),
                    message_id=message_id,
                    metadata={
                        'response': response_text,
                        'skill_executed': skill_ejecutada,
                        'had_skill_results': bool(resultados),
                        'action': action_data,  # Puede ser None o dict
                    },
                    context_summary={
                        'orchestration_mode': 'deepseek_v2',
                        'skill_name': skill_ejecutada or 'direct_response',
                        'skill_success': resultados.get('success', True)
                        if resultados else True,
                    },
                    timestamp=timezone.now().isoformat(),
                )

                log.info(
                    "Mensaje procesado v2",
                    skill=skill_ejecutada,
                    latency_ms=f"{timer.latency_ms:.1f}",
                    trace_id=timer.trace_id,
                )
                return result

            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                log.error(
                    f"Error en ChatProcessor v2: {str(e)}",
                    exc_info=True,
                    trace_id=timer.trace_id,
                )
                return ChatResult(
                    success=False,
                    response_text=f"Error al procesar mensaje: {str(e)}",
                    conversation_id=str(ctx.conversation.id) if ctx.conversation else '',
                    message_id='',
                    error=str(e),
                    metadata={'error': str(e), 'traceback': error_details},
                    timestamp=timezone.now().isoformat(),
                )

    # ── F2-001: LangGraph Orchestration ───────────────────────────────

    @classmethod
    def _process_with_langgraph(cls, ctx: ChatContext, timer) -> ChatResult:
        """
        Procesa mensaje usando PILOrchestrator con LangGraph StateGraph.

        F2-001 (6.9): Reemplaza el pipeline secuencial por un grafo
        dirigido con 4 nodos (router, context, search, formatter) y
        edges condicionales.

        Args:
            ctx: ChatContext con mensaje, conversación, usuario
            timer: MetricsService.timer para métricas

        Returns:
            ChatResult con respuesta generada por LangGraph
        """
        # Fast path para saludos/agradecimientos/despedidas
        msg_lower = ctx.message.lower().strip()
        fast_map = {
            'hola': 'iHola! Soy el asistente de Propifai. iEn que puedo ayudarte hoy?',
            'hola!': 'iHola! Soy el asistente de Propifai. iEn que puedo ayudarte hoy?',
            'buenos dias': 'iBuenos dias! Soy el asistente de Propifai. iEn que puedo ayudarte?',
            'buenas tardes': 'iBuenas tardes! iEn que puedo ayudarte?',
            'buenas noches': 'iBuenas noches! iEn que puedo ayudarte?',
            'gracias': 'iDe nada! Si necesitas algo mas, aqui estoy.',
            'muchas gracias': 'iDe nada! Para eso estoy.',
            'chau': 'iHasta luego! Si necesitas algo mas, no dudes en escribirme.',
            'adios': 'iHasta luego! Si necesitas algo mas, no dudes en escribirme.',
            'bye': 'iHasta luego!',
        }
        if msg_lower in fast_map:
            log.info(f"[FastPath] '{ctx.message}' -> respuesta directa")
            cls._save_user_message(ctx.conversation, ctx.message)
            response = fast_map[msg_lower]
            message_id = cls._save_response(ctx.conversation, response)
            return ChatResult(
                success=True, response_text=response,
                conversation_id=str(ctx.conversation.id), message_id=message_id,
                metadata={'response': response, 'fast_path': True},
                context_summary={'orchestration_mode': 'fast_path'},
                timestamp=timezone.now().isoformat(),
            )

        # Obtener contexto activo de la conversacion anterior
        contexto_activo = None
        try:
            meta = ctx.conversation.metadata or {}
            if 'ultimo_contexto' in meta:
                contexto_activo = meta['ultimo_contexto']
        except Exception:
            pass

        # Inyectar canvas_context si viene del lienzo
        if ctx.metadata and ctx.metadata.get('source') == 'canvas':
            canvas_ctx = ctx.metadata.get('canvas_context', {})
            if canvas_ctx:
                if not isinstance(contexto_activo, dict):
                    contexto_activo = {}
                contexto_activo['canvas_context'] = canvas_ctx
                contexto_activo['source'] = 'canvas'

        # Ejecutar orquestador LangGraph
        orchestrator = PILOrchestrator()
        state = orchestrator.run(
            message=ctx.message,
            conversation_id=str(ctx.conversation.id),
            user_id=str(ctx.user.id) if ctx.user else None,
            contexto_activo=contexto_activo,
        )

        response_text = state.get('respuesta_generada', '')
        if not response_text:
            response_text = (
                "Lo siento, no pude generar una respuesta. "
                "¿Puedes reformular tu pregunta?"
            )

        # Guardar respuesta en conversación
        texto_guardar = response_text
        if texto_guardar.startswith('__HTML__') and texto_guardar.endswith('__HTML__'):
            texto_guardar = '🖼️ Resultados mostrados en formato visual.'
        message_id = cls._save_response(ctx.conversation, texto_guardar)

        # Guardar contexto actual para el siguiente turno
        if state.get('params_extraidos'):
            try:
                meta = ctx.conversation.metadata or {}
                meta['ultimo_contexto'] = state['params_extraidos']
                ctx.conversation.metadata = meta
                ctx.conversation.save(update_fields=['metadata'])
            except Exception as e:
                log.debug(f"No se pudo guardar contexto para siguiente turno: {e}")

        # Post-process (memoria episódica)
        cls._save_post_process(
            ctx=ctx,
            response_text=response_text,
            trace_id=timer.trace_id,
        )

        log.info(
            f"[F2-001] Mensaje procesado con LangGraph",
            skill=state.get('skill_detectada'),
            nodos=state.get('nodos_ejecutados', []),
            latency_ms=f"{timer.latency_ms:.1f}",
            trace_id=state.get('trace_id', timer.trace_id),
        )

        return ChatResult(
            success=True,
            response_text=response_text,
            conversation_id=str(ctx.conversation.id),
            message_id=message_id,
            metadata={
                'response': response_text,
                'skill_executed': state.get('skill_detectada'),
                'had_skill_results': state.get('total_resultados', 0) > 0,
                'orchestration_mode': 'langgraph',
                'trace_id': state.get('trace_id', ''),
                'nodos_ejecutados': state.get('nodos_ejecutados', []),
                'total_resultados': state.get('total_resultados', 0),
                'router_score': state.get('score_routing', 0),
            },
            context_summary={
                'orchestration_mode': 'langgraph',
                'skill_name': state.get('skill_detectada') or 'rag_puro',
                'skill_success': state.get('error') is None,
            },
            timestamp=timezone.now().isoformat(),
        )

    # ── Streaming ──────────────────────────────────────────────────────

    @classmethod
    def process_message_stream(cls, ctx: ChatContext) -> Generator[StreamChunk, None, None]:
        """
        Procesa un mensaje en streaming.

        Args:
            ctx: ChatContext con todos los parámetros.

        Yields:
            StreamChunk con cada fragmento.
        """
        with MetricsService.timer(
            'chat.process_stream',
            user_id=str(ctx.user.id),
            app_id=ctx.app_id,
        ) as timer:
            try:
                # Guardar mensaje del usuario
                cls._save_user_message(ctx.conversation, ctx.message)

                # PASO 1: Orquestación
                yield StreamChunk('metadata', {
                    'conversation_id': str(ctx.conversation.id),
                    'context_summary': {
                        'orchestration_mode': 'deepseek_v2',
                        'intent': 'orchestrating',
                    },
                    'trace_id': timer.trace_id,
                })

                decision = cls._orquestar(ctx)

                if decision.respuesta_directa:
                    # Respuesta directa sin skill
                    response_text = decision.respuesta_directa
                    message_id = cls._save_response(ctx.conversation, response_text)
                    cls._save_post_process(ctx, response_text, timer.trace_id)

                    yield StreamChunk('chunk', {'content': response_text})
                    yield StreamChunk('complete', {
                        'message_id': message_id,
                        'full_response': response_text,
                        'timestamp': timezone.now().isoformat(),
                    })
                    return

                # PASO 2: Ejecución de skill
                resultados = cls._ejecutar_skill(
                    skill_name=decision.skill,
                    params=decision.params,
                    ctx=ctx,
                    trace_id=timer.trace_id,
                )

                if not resultados.get('success', False):
                    yield StreamChunk('error', {
                        'error': resultados.get('error', 'Error ejecutando skill')
                    })
                    return

                # Detectar si el skill genero HTML (formatear_propiedades)
                data = resultados.get('data')
                html_content = None
                if isinstance(data, dict) and data.get('html'):
                    html_content = data['html']
                    total = data.get('total', 0)
                    formato = data.get('formato', '')
                    
                    yield StreamChunk('chunk', {'content': f'📊 {total} propiedades en formato {formato}'})
                    yield StreamChunk('html', {'content': html_content})
                    
                    texto_guardar = '🖼️ Resultados mostrados en formato visual.'
                    message_id = cls._save_response(ctx.conversation, texto_guardar)
                    cls._save_post_process(ctx, texto_guardar, timer.trace_id)
                    
                    yield StreamChunk('complete', {
                        'message_id': message_id,
                        'full_response': texto_guardar,
                        'html': html_content,
                        'timestamp': timezone.now().isoformat(),
                    })
                    return

                # PASO 3: Streaming de respuesta natural
                full_response = ""
                try:
                    prompt_respuesta = cls._construir_prompt_respuesta(
                        ctx=ctx,
                        resultados=resultados,
                        skill_name=decision.skill,
                    )

                    for chunk in LLMService.generate_streaming_response(
                        query=prompt_respuesta,
                        context={
                            'user': {
                                'id': str(ctx.user.id),
                                'name': cls._get_user_name(ctx.user),
                                'level': cls._get_user_level(ctx.user),
                            },
                            'conversation_id': str(ctx.conversation.id),
                            'timestamp': timezone.now().isoformat(),
                        },
                        max_tokens=ctx.max_tokens,
                        temperature=ctx.temperature,
                    ):
                        chunk_data = chunk if isinstance(chunk, dict) else json.loads(chunk)

                        if chunk_data.get('type') == 'error':
                            yield StreamChunk('error', {
                                'error': chunk_data.get('error', 'Error en streaming'),
                            })
                            return

                        elif chunk_data.get('type') == 'chunk':
                            content = chunk_data.get('content', '')
                            full_response += content
                            yield StreamChunk('chunk', {'content': content})

                        elif chunk_data.get('type') == 'complete':
                            message_id = cls._save_response(ctx.conversation, full_response)
                            cls._save_post_process(ctx, full_response, timer.trace_id)

                            yield StreamChunk('complete', {
                                'message_id': message_id,
                                'full_response': full_response,
                                'timestamp': timezone.now().isoformat(),
                            })
                            return

                except Exception as e:
                    log.error(f"Error en stream de respuesta: {e}", exc_info=True)
                    yield StreamChunk('error', {
                        'error': f'Error en streaming: {str(e)}',
                    })

            except Exception as e:
                log.error(f"Error en process_message_stream: {e}", exc_info=True)
                yield StreamChunk('error', {'error': str(e)})

    # ── ORQUESTACIÓN ─────────────────────────────────────────────────

    @classmethod
    def _orquestar(cls, ctx: ChatContext) -> OrchestrationDecision:
        """
        PASO 1: Decide qué habilidad ejecutar según el origen y contexto.
        
        - Si el mensaje viene del canvas (metadata.source === 'canvas') con
          canvas_context, detecta si el usuario quiere AGREGAR propiedades al
          lienzo (busca en BD y devuelve acción) o solo conversar.
        - En cualquier otro caso, ejecuta busqueda_propiedades como antes.
        """
        canvas_ctx = (ctx.metadata or {}).get('canvas_context', {})
        es_canvas = (ctx.metadata or {}).get('source') == 'canvas'
        mensaje_lower = ctx.message.lower().strip()
        
        # Detectar intención de agregar propiedades al canvas
        # Soporta todas las formas verbales: tú (agrega), usted (agregue),
        # infinitivo (agregar), y variantes regionales
        INTENCION_AGREGAR = [
            'agrega', 'agregue', 'agregar', 'agrégalo', 'agrégueme',
            'añade', 'añada', 'añadir',
            'pon', 'ponlo', 'ponlos', 'poner en el lienzo', 'poner',
            'mételo', 'métalos',
            'trae', 'traiga', 'traer',
            'cargar', 'carga', 'colocar', 'coloca',
            'agrega al lienzo', 'agregue al lienzo',
        ]
        quiere_agregar = any(p in mensaje_lower for p in INTENCION_AGREGAR)
        
        # Siempre verificar source == 'canvas' independientemente de si canvas_ctx esta vacio.
        # Cuando el lienzo está vacío, canvas_ctx puede ser {} (falsy en Python),
        # pero aun así debemos detectar la intención de agregar propiedades.
        if es_canvas:
            props = (canvas_ctx or {}).get('propiedades', [])
            reqs = (canvas_ctx or {}).get('requerimientos', [])
            
            if quiere_agregar:
                log.info(
                    f"Orquestacion canvas con intención de AGREGAR: "
                    f"{len(props)} props, {len(reqs)} reqs en el lienzo. "
                    f"Buscando en BD para agregar.",
                    mensaje=ctx.message[:100],
                )
                return OrchestrationDecision(
                    skill='busqueda_propiedades',
                    params={
                        'semantic_query': ctx.message,
                        'modo_retorno': 'accion_agregar',
                    },
                )
            
            log.info(
                f"Orquestacion canvas (solo conversar): {len(props)} props, {len(reqs)} reqs en el lienzo.",
                mensaje=ctx.message[:100],
            )
            return OrchestrationDecision(
                skill='usar_contexto_canvas',
                params={
                    'canvas_propiedades': props,
                    'canvas_requerimientos': reqs,
                    'semantic_query': ctx.message,
                },
            )
        
        log.info(
            "Orquestacion directa: busqueda_propiedades con mensaje completo.",
            mensaje=ctx.message[:100],
        )
        return OrchestrationDecision(
            skill='busqueda_propiedades',
            params={'semantic_query': ctx.message},
        )

    @classmethod
    def _log_orchestration_error(cls, ctx: ChatContext, mensaje: str):
        """Registra un error de orquestacion en la tabla de errores del sistema."""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO intelligence_skill_execution "
                    "(skill_name, status, error_message, params, executed_at, user_id) "
                    "VALUES (%s, %s, %s, %s, NOW(), %s)",
                    ['chat_web_orquestador', 'error', mensaje[:500],
                     '{}', str(ctx.user.id) if ctx.user else None]
                )
        except Exception:
            pass  # No romper el flujo si falla el log

    # ── EJECUCIÓN DE SKILL ─────────────────────────────────────────────

    @classmethod
    def _ejecutar_skill(
        cls,
        skill_name: Optional[str],
        params: Dict[str, Any],
        ctx: ChatContext,
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        PASO 2: Ejecuta la skill que DeepSeek eligió.

        Args:
            skill_name: Nombre de la skill a ejecutar (None si es respuesta directa).
            params: Parámetros para la skill.
            ctx: ChatContext completo.
            trace_id: ID de trazabilidad.

        Returns:
            Dict con resultado de la skill.
        """
        # Skill virtual: usar contexto del canvas directamente
        if skill_name == 'usar_contexto_canvas':
            canvas_props = (params or {}).get('canvas_propiedades', [])
            canvas_reqs = (params or {}).get('canvas_requerimientos', [])
            log.info(
                f"Usando contexto canvas: {len(canvas_props)} props, {len(canvas_reqs)} reqs",
                trace_id=trace_id,
            )
            # Formatear como si fuera resultado de busqueda_propiedades
            data = {
                'total_propiedades': len(canvas_props),
                'total_requerimientos': len(canvas_reqs),
                'propiedades': canvas_props,
                'requerimientos': canvas_reqs,
                'origen': 'canvas_context',
            }
            return {
                'success': True,
                'data': data,
                'message': f'Se encontraron {len(canvas_props)} propiedades y {len(canvas_reqs)} requerimientos en el lienzo.',
                'skill_name': 'usar_contexto_canvas',
                'params': params,
            }

        if not skill_name:
            return {'success': True, 'data': None, 'message': 'Sin skill necesaria'}

        execution_context = ExecutionContext(
            user_id=str(ctx.user.id),
            session_id=ctx.conversation.session_id if ctx.conversation else '',
            conversation_id=str(ctx.conversation.id),
            permissions=(ctx.user.role.capabilities.keys()
                         if ctx.user.role and ctx.user.role.capabilities else []),
            environment='production',
            metadata={
                'app_id': ctx.app_id,
                'message': ctx.message,
            },
        )

        with MetricsService.timer(
            'chat.execute_skill',
            skill_name=skill_name,
            user_id=str(ctx.user.id),
            trace_id=trace_id,
        ) as timer:
            try:
                skill_result = SKILL_SYSTEM.execute_skill(
                    skill_name=skill_name,
                    parameters=params,
                    context=execution_context,
                )

                log.info(
                    f"Skill ejecutada: {skill_name}",
                    success=skill_result.success,
                    latency_ms=f"{timer.latency_ms:.1f}",
                    trace_id=trace_id,
                )

                resultado = {
                    'success': skill_result.success,
                    'data': skill_result.data,
                    'message': skill_result.message,
                    'error': skill_result.error_message,
                    'metadata': skill_result.metadata,
                    'skill_name': skill_name,
                    'params': params,
                }

                # PIPELINE: Si busqueda_propiedades tuvo exito con datos
                # y el usuario pidio o DeepSeek definio un formato,
                # ejecutar formatear_propiedades en secuencia
                if (skill_result.success
                    and skill_name == 'busqueda_propiedades'
                    and skill_result.data
                    and isinstance(skill_result.data, list)
                    and len(skill_result.data) > 0):
                    
                    formato = params.get('formato') or 'lista'
                    log.info(
                        f"Pipeline: formateando {len(skill_result.data)} propiedades en {formato}",
                        trace_id=trace_id,
                    )
                    
                    try:
                        fmt_result = SKILL_SYSTEM.execute_skill(
                            skill_name='formatear_propiedades',
                            parameters={
                                'propiedades': skill_result.data,
                                'formato': formato,
                            },
                            context=execution_context,
                        )
                        
                        if fmt_result.success and fmt_result.data:
                            resultado['data'] = fmt_result.data
                            resultado['message'] = fmt_result.message
                            resultado['skill_name'] = 'busqueda_propiedades + formatear_propiedades'
                            log.info(
                                f"Pipeline completado: propiedades formateadas en {formato}",
                                trace_id=trace_id,
                            )
                    except Exception as fmt_e:
                        log.warning(
                            f"Pipeline: error formateando propiedades: {fmt_e}",
                            trace_id=trace_id,
                        )
                    
                    # NUEVO: Si el modo de retorno es 'accion_agregar',
                    # construir estructura de acción para que el frontend
                    # agregue nodos al canvas
                    if params.get('modo_retorno') == 'accion_agregar':
                        action_nodes = []
                        # Usar skill_result.data (la lista original de busqueda_propiedades)
                        # en lugar de resultado['data'] que puede haber sido sobrescrito
                        # por formatear_propiedades (que retorna un dict sin 'propiedades').
                        propiedades_data = skill_result.data
                        props_list = []
                        if isinstance(propiedades_data, list):
                            props_list = propiedades_data
                        elif isinstance(propiedades_data, dict):
                            props_list = propiedades_data.get('propiedades', [])
                        
                        for prop in props_list[:10]:  # Máximo 10 nodos
                            fv = prop.get('field_values', prop)
                            source_id = prop.get('source_id') or fv.get('_source_id')
                            if not source_id:
                                continue
                            # Los nombres de campo reales en field_values de la BD
                            # (tabla property en dbpropify_be):
                            #   title, price, map_address, currency_name, district_name,
                            #   property_type_name, operation_type_name, property_status_name,
                            #   code, description
                            # NOTA: bedrooms, bathrooms, built_area NO estan en field_values,
                            # estan en property_specs (tabla separada).
                            action_nodes.append({
                                'node_type': 'propiedad',
                                'source_id': int(source_id) if str(source_id).isdigit() else source_id,
                                'data': {
                                    'title': fv.get('title', ''),
                                    'price': fv.get('price'),
                                    'currency': fv.get('currency_name') or fv.get('currency'),
                                    'district_name': fv.get('district_name'),
                                    'tipo_propiedad': fv.get('property_type_name') or fv.get('tipo_propiedad', ''),
                                    'direction': fv.get('map_address') or fv.get('display_address') or fv.get('direction', ''),
                                    'area_construida': fv.get('built_area') or fv.get('area_construida') or fv.get('area', ''),
                                    'dormitorios': fv.get('bedrooms'),
                                    'banos': fv.get('bathrooms'),
                                },
                            })
                        
                        if action_nodes:
                            resultado['action'] = {
                                'type': 'add_nodes',
                                'nodes': action_nodes,
                                'position_strategy': 'cascade',
                            }
                            log.info(
                                f"Acción add_nodes construida: {len(action_nodes)} propiedades",
                                trace_id=trace_id,
                            )

                return resultado

            except Exception as e:
                log.error(
                    f"Error ejecutando skill {skill_name}: {e}",
                    exc_info=True,
                    trace_id=trace_id,
                )
                return {
                    'success': False,
                    'data': None,
                    'message': '',
                    'error': str(e),
                    'metadata': {},
                    'skill_name': skill_name,
                    'params': params,
                }

    # ── RESPUESTA NATURAL ──────────────────────────────────────────────

    @classmethod
    def _generar_respuesta(
        cls,
        ctx: ChatContext,
        resultados: Dict[str, Any],
        skill_name: Optional[str],
        trace_id: str,
    ) -> str:
        """
        PASO 3: Genera respuesta natural.

        Si el skill ejecutado fue formatear_propiedades y devolvió HTML,
        se retorna el HTML directamente (con marcador) sin pasar por DeepSeek.
        En cualquier otro caso, DeepSeek genera respuesta natural con los datos.

        Args:
            ctx: ChatContext completo.
            resultados: Resultados de la skill ejecutada.
            skill_name: Nombre de la skill ejecutada.
            trace_id: ID de trazabilidad.

        Returns:
            Texto de respuesta (puede contener HTML).
        """
        if not resultados.get('success'):
            return resultados.get('error', 'Lo siento, no pude completar la búsqueda.')

        # Si el skill generó HTML (formatear_propiedades), retornarlo directamente
        data = resultados.get('data')
        if isinstance(data, dict) and data.get('html'):
            html = data['html']
            total = data.get('total', 0)
            formato = data.get('formato', 'desconocido')
            log.info(
                f"Respuesta con HTML generado: {total} propiedades en formato {formato}",
                trace_id=trace_id,
            )
            return f"__HTML__{html}__HTML__"

        # Para otros skills, usar DeepSeek para generar respuesta natural
        prompt = cls._construir_prompt_respuesta(ctx, resultados, skill_name)

        system_prompt = PromptManager.get_deepseek_system_prompt(ctx.app_id)

        success, message, response_data = LLMService._call_deepseek_api(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt,
        )

        if success and isinstance(response_data, dict):
            return response_data.get(
                'content',
                resultados.get('message', 'Búsqueda completada.')
            )

        log.warning(
            "DeepSeek falló al generar respuesta natural, usando mensaje de skill",
            trace_id=trace_id,
        )
        return resultados.get('message', 'Búsqueda completada.')

    @classmethod
    def _construir_prompt_respuesta(
        cls,
        ctx: ChatContext,
        resultados: Dict[str, Any],
        skill_name: Optional[str],
    ) -> str:
        """
        Construye el prompt para la respuesta natural con los resultados de la skill.
        """
        historial = cls._get_historial_mensajes(ctx.conversation)
        historial_str = "\n".join(historial) if historial else "(sin historial previo)"

        # Formatear resultados de skill para el prompt
        resultados_str = cls._formatear_resultados_skill(resultados, skill_name)

        return RESPONSE_SYSTEM_PROMPT.format(
            historial=historial_str,
            mensaje=ctx.message,
            resultados_skill=resultados_str,
        )

    @classmethod
    def _formatear_resultados_skill(
        cls,
        resultados: Dict[str, Any],
        skill_name: Optional[str],
    ) -> str:
        """
        Convierte los resultados de una skill en texto legible para el prompt.
        """
        if not resultados:
            return "  (sin resultados)"

        skill = skill_name or 'desconocida'
        success = resultados.get('success', False)
        data = resultados.get('data')
        message = resultados.get('message', '')
        params = resultados.get('params', {})
        error = resultados.get('error', '')

        lines = [f"  Skill ejecutada: {skill}"]
        lines.append(f"  Éxito: {'Sí' if success else 'No'}")
        lines.append(f"  Parámetros usados: {json.dumps(params, ensure_ascii=False)}")

        if not success:
            lines.append(f"  Error: {error}")
            return "\n".join(lines)

        if message:
            lines.append(f"  Mensaje: {message}")

        # Si el resultado contiene HTML (skill formatear_propiedades),
        # pasar el HTML directamente para que el template lo renderice
        html_content = None
        if isinstance(data, dict) and data.get('html'):
            html_content = data['html']
            formato = data.get('formato', 'desconocido')
            total = data.get('total', 0)
            lines.append(f"  HTML_GENERADO: formato={formato}, total={total}")
            lines.append(f"  HTML_CONTENT:{html_content}")

        elif data is None:
            lines.append("  Datos: (sin datos)")
        elif isinstance(data, str):
            lines.append(f"  Datos: {data}")
        elif isinstance(data, list):
            lines.append(f"  Total de resultados: {len(data)}")
            for i, item in enumerate(data[:20], 1):
                item_str = cls._formatear_item_resultado(item)
                lines.append(f"  [{i}] {item_str}")
            if len(data) > 20:
                lines.append(f"  ... y {len(data) - 20} resultados más")
        elif isinstance(data, dict):
            for key, value in data.items():
                if key == 'html':
                    continue  # Ya procesado arriba
                if isinstance(value, list):
                    lines.append(f"  {key}: {len(value)} resultados")
                    for j, item in enumerate(value[:10], 1):
                        item_str = cls._formatear_item_resultado(item)
                        lines.append(f"    [{j}] {item_str}")
                    if len(value) > 10:
                        lines.append(f"    ... y {len(value) - 10} más")
                else:
                    lines.append(f"  {key}: {value}")
        else:
            lines.append(f"  Datos: {str(data)}")

        return "\n".join(lines)

    @staticmethod
    def _formatear_item_resultado(item: Any) -> str:
        """Formatea un item individual de resultado."""
        if not item:
            return "Sin datos"

        if isinstance(item, str):
            return item[:300]

        if isinstance(item, dict):
            field_values = item.get('field_values', item)
            if not isinstance(field_values, dict):
                return str(item)[:300]

            partes = []
            titulo = (
                field_values.get('title')
                or field_values.get('titulo')
                or field_values.get('name')
                or field_values.get('nombre')
            )
            if titulo:
                partes.append(str(titulo))

            precio = (
                field_values.get('price')
                or field_values.get('precio')
                or field_values.get('sale_price')
            )
            if precio:
                moneda = field_values.get('currency_name', field_values.get('moneda', ''))
                partes.append(f"Precio: {precio} {moneda}".strip())

            distrito = (
                field_values.get('district_name')
                or field_values.get('district')
                or field_values.get('distrito')
            )
            if distrito:
                partes.append(f"Distrito: {distrito}")

            tipo = (
                field_values.get('property_type_name')
                or field_values.get('tipo_propiedad')
                or field_values.get('property_type')
            )
            if tipo:
                partes.append(f"Tipo: {tipo}")

            area = (
                field_values.get('built_area')
                or field_values.get('area_construida')
                or field_values.get('total_area')
                or field_values.get('land_area')
            )
            if area:
                partes.append(f"Área: {area} m²")

            habitaciones = (
                field_values.get('bedrooms')
                or field_values.get('habitaciones')
            )
            if habitaciones:
                partes.append(f"Hab: {habitaciones}")

            return " | ".join(partes) if partes else json.dumps(item, ensure_ascii=False)[:300]

        return str(item)[:300]

    # ── UTILIDADES ─────────────────────────────────────────────────────

    @classmethod
    def _get_user_level(cls, user: User) -> int:
        """Obtiene el nivel de inteligencia del usuario."""
        try:
            from ..models import UserIntelligenceProfile
            profile = UserIntelligenceProfile.objects.get(user=user)
            return profile.level
        except Exception:
            if user.role:
                return user.role.default_level
            return 1

    @classmethod
    def _get_user_name(cls, user: User) -> str:
        """Obtiene el nombre legible del usuario."""
        if user.metadata and isinstance(user.metadata, dict):
            name = user.metadata.get('name')
            if name:
                return name
        return user.phone or user.email or 'Usuario'

    @classmethod
    def _get_or_create_app(cls, app_id: str) -> AppConfig:
        """Obtiene o crea una configuración de app."""
        app, _ = AppConfig.objects.get_or_create(
            id=app_id,
            defaults={
                'name': f'App {app_id}',
                'level': 2,
                'capabilities': {
                    'memory': True,
                    'knowledge_base': True,
                    'metrics': False,
                    'projects': False,
                },
                'is_active': True,
            },
        )
        return app

    @classmethod
    def _get_or_create_conversation(
        cls,
        user: User,
        app_id: str,
        conversation_id: Optional[str] = None,
        streaming: bool = False,
    ) -> Conversation:
        """Obtiene o crea una conversación para el usuario."""
        conversation = None

        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=user)
            except Conversation.DoesNotExist:
                conversation = None

        if not conversation:
            try:
                app = cls._get_or_create_app(app_id)
                conversation = Conversation.objects.filter(
                    user=user,
                    app=app,
                    is_active=True,
                ).order_by('-last_message_at').first()
            except Exception:
                conversation = None

        if not conversation:
            app = cls._get_or_create_app(app_id)
            session_id = f'chat_{uuid.uuid4().hex[:16]}'
            conversation = Conversation.objects.create(
                user=user,
                app=app,
                session_id=session_id,
                messages=[],
                metadata={'source': app_id},
                is_active=True,
            )

        return conversation

    @classmethod
    def _get_historial_mensajes(cls, conversation, max_mensajes: int = 6) -> List[str]:
        """Extrae los últimos mensajes de la conversación."""
        try:
            messages = conversation.messages or []
        except Exception:
            return []

        historial = []
        for msg in messages[-max_mensajes:]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if content:
                historial.append(f"{role}: {content}")
        return historial

    # ── PERSISTENCIA ───────────────────────────────────────────────────

    @classmethod
    def _save_response(cls, conversation: Conversation, response_text: str) -> str:
        """Guarda la respuesta del asistente en la conversación."""
        message = {
            'role': 'assistant',
            'content': response_text,
            'timestamp': timezone.now().isoformat(),
            'id': str(uuid.uuid4()),
        }

        messages = conversation.messages or []
        messages.append(message)

        # Limitar a 50 mensajes
        if len(messages) > 50:
            messages = messages[-50:]

        conversation.messages = messages
        conversation.last_message_at = timezone.now()
        conversation.save()

        return message['id']

    @classmethod
    def _save_user_message(
        cls,
        conversation: Conversation,
        message: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Guarda el mensaje del usuario en la conversación."""
        msg = {
            'role': 'user',
            'content': message,
            'timestamp': timezone.now().isoformat(),
            'id': str(uuid.uuid4()),
        }
        if metadata:
            msg['metadata'] = metadata

        messages = conversation.messages or []
        messages.append(msg)

        if len(messages) > 50:
            messages = messages[-50:]

        conversation.messages = messages
        conversation.last_message_at = timezone.now()
        conversation.save()

        return msg['id']

    @classmethod
    def _save_post_process(
        cls,
        ctx: ChatContext,
        response_text: str,
        trace_id: str = '',
    ):
        """Post-procesamiento: memoria episódica y extracción de hechos."""
        if not ctx.use_memory:
            return

        # Guardar episodio en memoria episódica
        try:
            enriched_context = {
                'collections_used': ctx.collections if ctx.collections else [],
                'user_level': cls._get_user_level(ctx.user),
                'use_rag': ctx.use_rag,
                'use_memory': ctx.use_memory,
                'orchestration_mode': 'deepseek_v2',
                'trace_id': trace_id,
            }

            EpisodicMemoryService.save_episode(
                user_id=str(ctx.user.id),
                conversation_id=str(ctx.conversation.id),
                user_message=ctx.message,
                assistant_response=response_text,
                rag_context_used=None,
                memory_context_used=None,
                context=enriched_context,
            )
        except Exception as e:
            log.error(f"Error guardando episodio: {e}", exc_info=True)

        # Extraer hechos
        try:
            MemoryService.extract_and_save_facts(
                user_id=ctx.user.id,
                message=ctx.message,
                response=response_text,
            )
        except Exception as e:
            log.error(f"Error extrayendo hechos: {e}", exc_info=True)


# ── Atajo para importar ──────────────────────────────────────────────
chat_processor = ChatProcessor()
