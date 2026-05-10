"""
Procesador de mensajes de chat (ChatProcessor).

Contiene TODA la lógica de negocio que antes estaba duplicada en
chat_web_api y chat_web_stream de views.py.

NO depende de Django REST Framework. Recibe objetos Python y devuelve
dataclasses. Esto permite reutilizarlo desde:
- Views de DRF (chat_web_api, chat_web_stream)
- Management commands
- MCP servers
- Celery tasks
"""
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from django.utils import timezone

from ..models import (
    User, AppConfig, Conversation,
    IntelligenceCollection, ConversationFlow,
    ConversationFlowState, UserIntelligenceProfile,
)
from .memory import MemoryService
from .episodic_memory import EpisodicMemoryService
from .rag import RAGService
from .llm import LLMService
from .prompts import (
    PromptManager,
    format_episodic_context,
    format_memory_context,
    format_rag_context,
    build_full_prompt,
)
from .intent_classifier import IntentClassifier, IntentType
from .metrics import MetricsService, log
from ..services.skill_base import SkillResult
from ..skills import create_skill_system
from ..skills.orchestrator import ExecutionContext

# Skill system singleton para el pipeline de chat
SKILL_SYSTEM = create_skill_system(enable_cache=True, auto_discover_examples=True)


# ── Dataclasses de resultado (sin dependencia DRF) ─────────────────────────

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
    flow_name: Optional[str] = None
    flow_params: Dict[str, Any] = field(default_factory=dict)
    skill_pipeline: Optional[List[Dict[str, Any]]] = None
    skill_pipeline_mode: str = 'sequential'
    skill_pipeline_abort_on_error: bool = True


@dataclass
class StreamChunk:
    """Un chunk de la respuesta en streaming."""
    type: str  # 'metadata', 'chunk', 'complete', 'error'
    data: Dict[str, Any]


# ── ChatProcessor ──────────────────────────────────────────────────────────

class ChatProcessor:
    """
    Procesa mensajes de chat con todo el pipeline de inteligencia.

    Flujo completo:
    1. Clasificar intención del mensaje
    2. Obtener memoria del usuario (si aplica)
    3. Obtener contexto RAG (si aplica)
    4. Obtener episodios relevantes (si aplica)
    5. Construir prompt con todo el contexto
    6. Llamar a DeepSeek
    7. Guardar respuesta en conversación
    8. Guardar episodio en memoria episódica
    9. Extraer hechos relevantes
    """

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
                # Guardar mensaje del usuario en la conversación
                cls._save_user_message(ctx.conversation, ctx.message)

                # 1. Clasificar intención
                intent = IntentClassifier.classify(ctx.message)
                log.info(
                    f"Intención detectada: {intent.intent.value} "
                    f"(confianza: {intent.confidence:.2f})",
                    intent=intent.intent.value,
                    confidence=intent.confidence,
                    trace_id=timer.trace_id,
                )

                # Si se pidió ejecutar un pipeline de skills explícito, ir por el motor de skills
                if ctx.skill_pipeline:
                    return cls._process_skill_pipeline_request(ctx, timer.trace_id)

                # Si hay un flujo de conversación activo o se solicitó uno, procesarlo primero
                if ctx.flow_name or cls._conversation_has_active_flow(ctx.conversation):
                    flow_result = cls._process_flow_request(ctx, timer.trace_id)
                    if flow_result:
                        return flow_result

                # Si se pidió ejecutar una skill explícita, ir por el motor de skills
                if ctx.skill_name:
                    return cls._process_skill_request(ctx, timer.trace_id)

                # Intentar inferir si la consulta debe disparar una skill automáticamente
                inferred_skill_result = cls._infer_skill_request(
                    ctx, intent, timer.trace_id
                )
                if inferred_skill_result:
                    return inferred_skill_result

                # 2-4. Obtener contextos (según intención)
                memory_context = cls._get_memory_context(
                    ctx, intent, timer.trace_id
                )
                rag_context = cls._get_rag_context(
                    ctx, intent, timer.trace_id
                )
                episodic_context = cls._get_episodic_context(
                    ctx, intent, timer.trace_id
                )

                # 5. Construir prompt
                full_prompt = cls._build_prompt(
                    ctx=ctx,
                    memory_context=memory_context,
                    rag_context=rag_context,
                    episodic_context=episodic_context,
                )

                # 6. Llamar a DeepSeek
                system_prompt = PromptManager.get_deepseek_system_prompt(
                    ctx.app_id
                )
                success, api_message, api_response = (
                    LLMService._call_deepseek_api(
                        messages=[{"role": "user", "content": full_prompt}],
                        system_prompt=system_prompt,
                    )
                )

                if success:
                    if isinstance(api_response, dict):
                        response_text = api_response.get(
                            'content',
                            'Lo siento, no pude generar una respuesta.'
                        )
                    else:
                        log.warning(
                            f"api_response inesperado: type={type(api_response)}"
                        )
                        response_text = 'Lo siento, no pude generar una respuesta.'
                else:
                    response_text = f"Error al generar respuesta: {api_message}"

                # 7. Guardar respuesta en conversación
                message_id = cls._save_response(
                    ctx.conversation, response_text
                )

                # 8-9. Guardar episodio y extraer hechos
                cls._save_post_process(
                    ctx=ctx,
                    response_text=response_text,
                    memory_context=memory_context,
                    rag_context=rag_context,
                    intent=intent,
                    trace_id=timer.trace_id,
                )

                # Construir resultado
                result = ChatResult(
                    success=True,
                    response_text=response_text,
                    conversation_id=str(ctx.conversation.id),
                    message_id=message_id,
                    metadata={
                        'response': response_text,
                        'rag_context_used': bool(rag_context),
                        'retrieved_documents_count': len(rag_context)
                        if rag_context else 0,
                    },
                    context_summary={
                        'memory_used': len(memory_context)
                        if memory_context else 0,
                        'rag_used': len(rag_context) if rag_context else 0,
                        'collections_used': ctx.collections
                        if ctx.collections else [],
                        'intent': intent.intent.value,
                        'intent_confidence': intent.confidence,
                    },
                    timestamp=timezone.now().isoformat(),
                )

                log.info(
                    "Mensaje procesado exitosamente",
                    latency_ms=f"{timer.latency_ms:.1f}",
                    trace_id=timer.trace_id,
                )
                return result

            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                log.error(
                    f"Error en ChatProcessor: {str(e)}",
                    exc_info=True,
                    trace_id=timer.trace_id,
                )
                return ChatResult(
                    success=False,
                    response_text=f"Error al procesar mensaje: {str(e)}",
                    conversation_id=str(ctx.conversation.id)
                    if ctx.conversation else '',
                    message_id='',
                    error=str(e),
                    metadata={'error': str(e), 'traceback': error_details},
                    timestamp=timezone.now().isoformat(),
                )

    @classmethod
    def process_message_stream(
        cls, ctx: ChatContext
    ):
        """
        Procesa un mensaje en streaming.

        Es un generador que produce StreamChunk con:
        - 'metadata': información inicial
        - 'chunk': fragmento de respuesta
        - 'complete': respuesta completa
        - 'error': error ocurrido

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
                # 1. Clasificar intención
                intent = IntentClassifier.classify(ctx.message)
                log.info(
                    f"Intención detectada (stream): {intent.intent.value}",
                    intent=intent.intent.value,
                    trace_id=timer.trace_id,
                )

                # Guardar mensaje del usuario en la conversación
                cls._save_user_message(ctx.conversation, ctx.message)

                # 2-4. Obtener contextos
                inferred_skill_result = cls._infer_skill_request(
                    ctx, intent, timer.trace_id
                )
                if inferred_skill_result:
                    yield StreamChunk('metadata', {
                        'conversation_id': str(ctx.conversation.id),
                        'context_summary': {
                            'skill_name': inferred_skill_result.metadata.get('skill_name'),
                            'skill_success': True,
                            'intent': intent.intent.value,
                        },
                        'trace_id': timer.trace_id,
                    })
                    yield StreamChunk('chunk', {
                        'content': inferred_skill_result.response_text
                    })
                    yield StreamChunk('complete', {
                        'message_id': inferred_skill_result.message_id,
                        'full_response': inferred_skill_result.response_text,
                        'timestamp': inferred_skill_result.timestamp,
                    })
                    return

                if ctx.skill_pipeline:
                    yield StreamChunk('metadata', {
                        'conversation_id': str(ctx.conversation.id),
                        'context_summary': {
                            'pipeline_mode': ctx.skill_pipeline_mode,
                            'skill_count': len(ctx.skill_pipeline),
                            'memory_used': 0,
                            'rag_used': 0,
                            'collections_used': [],
                            'intent': 'skill_pipeline',
                        },
                        'trace_id': timer.trace_id,
                    })

                    skill_result = cls._process_skill_pipeline_request(ctx, timer.trace_id)
                    if not skill_result.success:
                        yield StreamChunk('error', {
                            'error': skill_result.error or 'Error ejecutando pipeline de skills'
                        })
                        return

                    yield StreamChunk('chunk', {
                        'content': skill_result.response_text
                    })
                    yield StreamChunk('complete', {
                        'message_id': skill_result.message_id,
                        'full_response': skill_result.response_text,
                        'timestamp': skill_result.timestamp,
                    })
                    return

                if ctx.flow_name or cls._conversation_has_active_flow(ctx.conversation):
                    flow_result = cls._process_flow_request(ctx, timer.trace_id)
                    if flow_result:
                        yield StreamChunk('metadata', {
                            'conversation_id': str(ctx.conversation.id),
                            'context_summary': {
                                'flow_name': flow_result.metadata.get('flow_name'),
                                'current_state': flow_result.metadata.get('flow_state'),
                                'intent': 'conversation_flow',
                            },
                            'trace_id': timer.trace_id,
                        })
                        yield StreamChunk('chunk', {'content': flow_result.response_text})
                        yield StreamChunk('complete', {
                            'message_id': flow_result.message_id,
                            'full_response': flow_result.response_text,
                            'timestamp': flow_result.timestamp,
                        })
                        return

                if ctx.skill_name:
                    # Emitir metadata antes de ejecutar la skill
                    yield StreamChunk('metadata', {
                        'conversation_id': str(ctx.conversation.id),
                        'context_summary': {
                            'skill_name': ctx.skill_name,
                            'memory_used': 0,
                            'rag_used': 0,
                            'collections_used': [],
                            'intent': 'skill_execution',
                        },
                        'trace_id': timer.trace_id,
                    })

                    skill_result = cls._process_skill_request(ctx, timer.trace_id)
                    if not skill_result.success:
                        yield StreamChunk('error', {
                            'error': skill_result.error or 'Error ejecutando skill'
                        })
                        return

                    yield StreamChunk('chunk', {
                        'content': skill_result.response_text
                    })
                    yield StreamChunk('complete', {
                        'message_id': skill_result.message_id,
                        'full_response': skill_result.response_text,
                        'timestamp': skill_result.timestamp,
                    })
                    return

                memory_context = cls._get_memory_context(
                    ctx, intent, timer.trace_id
                )
                rag_context = cls._get_rag_context(
                    ctx, intent, timer.trace_id
                )
                episodic_context = cls._get_episodic_context(
                    ctx, intent, timer.trace_id
                )

                # Yield metadata inicial
                yield StreamChunk('metadata', {
                    'conversation_id': str(ctx.conversation.id),
                    'context_summary': {
                        'memory_used': len(memory_context)
                        if memory_context else 0,
                        'rag_used': len(rag_context) if rag_context else 0,
                        'collections_used': ctx.collections
                        if ctx.collections else [],
                        'intent': intent.intent.value,
                    },
                    'trace_id': timer.trace_id,
                })

                # 5. Construir prompt
                full_prompt = cls._build_prompt(
                    ctx=ctx,
                    memory_context=memory_context,
                    rag_context=rag_context,
                    episodic_context=episodic_context,
                )

                # 6. Streaming de DeepSeek
                full_response = ""
                try:
                    for chunk in LLMService.generate_streaming_response(
                        query=full_prompt,
                        context={
                            'user': {
                                'id': str(ctx.user.id),
                                'name': ctx.user.metadata.get('name')
                                if ctx.user.metadata
                                else (ctx.user.phone or ctx.user.email
                                      or 'Usuario'),
                                'level': cls._get_user_level(ctx.user),
                            },
                            'conversation_id': str(ctx.conversation.id),
                            'timestamp': timezone.now().isoformat(),
                        },
                        max_tokens=ctx.max_tokens,
                        temperature=ctx.temperature,
                    ):
                        chunk_data = chunk if isinstance(chunk, dict) \
                            else json.loads(chunk)

                        if chunk_data.get('type') == 'error':
                            yield StreamChunk('error', {
                                'error': chunk_data.get(
                                    'error', 'Error desconocido'
                                ),
                            })
                            return

                        elif chunk_data.get('type') == 'chunk':
                            content = chunk_data.get('content', '')
                            full_response += content
                            yield StreamChunk('chunk', {'content': content})

                        elif chunk_data.get('type') == 'complete':
                            # 7. Guardar respuesta
                            message_id = cls._save_response(
                                ctx.conversation, full_response
                            )

                            # 8-9. Post-process
                            cls._save_post_process(
                                ctx=ctx,
                                response_text=full_response,
                                memory_context=memory_context,
                                rag_context=rag_context,
                                intent=intent,
                                trace_id=timer.trace_id,
                            )

                            yield StreamChunk('complete', {
                                'message_id': message_id,
                                'full_response': full_response,
                                'timestamp': timezone.now().isoformat(),
                            })
                            return

                except Exception as e:
                    log.error(
                        f"Error en stream: {str(e)}",
                        exc_info=True,
                        trace_id=timer.trace_id,
                    )
                    yield StreamChunk('error', {
                        'error': f'Error en el stream: {str(e)}',
                    })

            except Exception as e:
                log.error(
                    f"Error en process_message_stream: {str(e)}",
                    exc_info=True,
                    trace_id=timer.trace_id,
                )
                yield StreamChunk('error', {
                    'error': str(e),
                })

    # ── Métodos auxiliares ─────────────────────────────────────────────────

    @classmethod
    def _get_user_level(cls, user: User) -> int:
        """Calcula el nivel del usuario basado en su perfil de inteligencia."""
        try:
            profile = UserIntelligenceProfile.objects.get(user=user)
            return profile.level
        except UserIntelligenceProfile.DoesNotExist:
            if user.role:
                return user.role.default_level
            return 1

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
        """Obtiene o crea una conversación."""
        conversation = None
        if conversation_id:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id, user=user
                )
            except Conversation.DoesNotExist:
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
    def _get_memory_context(
        cls,
        ctx: ChatContext,
        intent: Any,
        trace_id: str,
    ) -> Optional[List[Dict]]:
        """Obtiene contexto de memoria si aplica."""
        if not ctx.use_memory or intent.skip_memory:
            return None

        with MetricsService.timer(
            'chat.memory',
            user_id=str(ctx.user.id),
            trace_id=trace_id,
        ) as timer:
            try:
                memory_service = MemoryService(user_id=str(ctx.user.id))
                context = memory_service.get_relevant_context(
                    query=ctx.message, limit=5
                )
                log.debug(
                    f"Memoria obtenida: {len(context)} items",
                    memory_count=len(context),
                    latency_ms=f"{timer.latency_ms:.1f}",
                )
                return context
            except Exception as e:
                log.error(
                    f"Error obteniendo memoria: {str(e)}",
                    exc_info=True,
                )
                return None

    @classmethod
    def _get_rag_context(
        cls,
        ctx: ChatContext,
        intent: Any,
        trace_id: str,
    ) -> Optional[List[Dict]]:
        """Obtiene contexto RAG si aplica."""
        if not ctx.use_rag or intent.skip_rag:
            return None

        with MetricsService.timer(
            'chat.rag',
            user_id=str(ctx.user.id),
            trace_id=trace_id,
        ) as timer:
            try:
                collections = ctx.collections
                if not collections:
                    user_level = cls._get_user_level(ctx.user)
                    accessible = IntelligenceCollection.objects.filter(
                        min_level__lte=user_level,
                        is_active=True,
                    ).values_list('name', flat=True)
                    collections = list(accessible)

                if collections:
                    rag_results = RAGService.search_dynamic(
                        query=ctx.message,
                        collection_names=collections,
                        top_k=3,
                    )
                    log.debug(
                        f"RAG obtenido: {len(rag_results)} resultados",
                        collections=collections,
                        latency_ms=f"{timer.latency_ms:.1f}",
                    )
                    return rag_results
                return None
            except Exception as e:
                log.error(
                    f"Error obteniendo RAG: {str(e)}",
                    exc_info=True,
                )
                return None

    @classmethod
    def _get_episodic_context(
        cls,
        ctx: ChatContext,
        intent: Any,
        trace_id: str,
    ) -> Optional[List[Dict]]:
        """Obtiene episodios relevantes si aplica."""
        if not ctx.use_memory or intent.skip_episodic:
            return None

        with MetricsService.timer(
            'chat.episodic',
            user_id=str(ctx.user.id),
            trace_id=trace_id,
        ) as timer:
            try:
                episodes = EpisodicMemoryService.get_relevant_episodes_static(
                    user_id=str(ctx.user.id),
                    query=ctx.message,
                    limit=3,
                )
                log.debug(
                    f"Episodios obtenidos: {len(episodes)}",
                    latency_ms=f"{timer.latency_ms:.1f}",
                )
                return episodes
            except Exception as e:
                log.error(
                    f"Error obteniendo episodios: {str(e)}",
                    exc_info=True,
                )
                return None

    @classmethod
    def _build_prompt(
        cls,
        ctx: ChatContext,
        memory_context: Optional[List[Dict]] = None,
        rag_context: Optional[List[Dict]] = None,
        episodic_context: Optional[List[Dict]] = None,
    ) -> str:
        """Construye el prompt completo con todos los contextos."""
        # Obtener system prompt desde BD (configurable)
        system_instruction = PromptManager.get_system_prompt(ctx.app_id)

        # Formatear cada sección
        episodic_str = format_episodic_context(episodic_context)
        memory_str = format_memory_context(memory_context)
        rag_str = format_rag_context(rag_context)

        # Construir prompt completo
        return build_full_prompt(
            message=ctx.message,
            system_instruction=system_instruction,
            episodic_context=episodic_str,
            memory_context=memory_str,
            rag_context=rag_str,
        )

    @classmethod
    def _render_skill_response(cls, result: SkillResult) -> str:
        """Renderiza un resultado de skill a texto legible."""
        if result.data is None:
            return 'Skill ejecutada correctamente.'

        if isinstance(result.data, str):
            return result.data

        if isinstance(result.data, dict):
            if len(result.data) == 1:
                key, value = next(iter(result.data.items()))
                return f"{key}: {value}"
            try:
                return json.dumps(result.data, ensure_ascii=False, indent=2)
            except TypeError:
                return str(result.data)

        return str(result.data)

    @classmethod
    def _infer_skill_request(cls, ctx: ChatContext, intent: Any, trace_id: str) -> Optional[ChatResult]:
        """Intenta inferir y ejecutar una skill a partir de la intención del mensaje."""
        if ctx.skill_name:
            return None

        candidate_skill = cls._find_skill_candidate(ctx.message)
        if not candidate_skill:
            return None

        if candidate_skill['name'] == 'reporte_precios_zona' or intent.intent == IntentType.PRICE_QUERY:
            skill_params = cls._build_skill_params_for_price_query(ctx, intent)
        else:
            skill_params = cls._build_params_for_inferred_skill(ctx, candidate_skill)

        if not skill_params:
            log.debug(
                "No se pudieron inferir parámetros para la skill detectada",
                intent=intent.intent.value,
                skill=candidate_skill.get('name'),
                trace_id=trace_id,
            )
            return None

        ctx.skill_name = candidate_skill['name']
        ctx.skill_params = skill_params

        log.info(
            "Skill inferida automáticamente",
            skill_name=ctx.skill_name,
            skill_params=list(skill_params.keys()),
            trace_id=trace_id,
        )
        return cls._process_skill_request(ctx, trace_id)

    @classmethod
    def _find_skill_candidate(cls, message: str) -> Optional[Dict[str, Any]]:
        """Busca una skill adecuada para la consulta del usuario."""
        candidates = SKILL_SYSTEM.registry.search_skills(message, limit=10)

        if candidates:
            # Priorizar skills explícitas de precio o matemáticas en la descripción
            for candidate in candidates:
                name = candidate.get('name', '').lower()
                description = candidate.get('description', '').lower()
                if 'precio' in name or 'precio' in description or 'precios' in description:
                    return candidate
                if any(term in description for term in ['multiplica', 'divide', 'suma', 'resta', 'potencia', 'raíz', 'raiz']):
                    return candidate

            return candidates[0]

        return cls._find_math_skill_candidate(message)

    @classmethod
    def _find_math_skill_candidate(cls, message: str) -> Optional[Dict[str, Any]]:
        """Busca una skill matemática basándose en palabras clave del mensaje."""
        lower_message = message.lower()
        math_skill_keywords = {
            'multiplicacion': ['por', 'multiplica', 'multiplicacion', 'multiplicar'],
            'division': ['entre', 'divide', 'division', 'dividir'],
            'suma': ['más', 'mas', 'suma', 'sumar', 'agrega', 'y'],
            'resta': ['menos', 'resta', 'restar'],
            'potencia': ['potencia', 'elevado', 'exponente', 'a la'],
            'raiz_cuadrada': ['raíz', 'raiz', 'raiz cuadrada'],
        }

        for skill_name, keywords in math_skill_keywords.items():
            if any(keyword in lower_message for keyword in keywords):
                candidate = SKILL_SYSTEM.registry.get_skill_info(skill_name)
                if candidate:
                    return candidate

        return None

    @classmethod
    def _build_params_for_inferred_skill(
        cls,
        ctx: ChatContext,
        candidate_skill: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Construye parámetros para la skill inferida."""
        name = candidate_skill.get('name', '').lower()
        params = cls._extract_numbers_from_message(ctx.message)

        if name in ['multiplicacion', 'suma', 'resta', 'division']:
            if len(params) < 2:
                return None
            return {'a': params[0], 'b': params[1]}

        if name == 'potencia':
            if len(params) < 2:
                return None
            return {'base': params[0], 'exponente': params[1]}

        if name == 'raiz_cuadrada':
            if len(params) < 1:
                return None
            return {'numero': params[0]}

        if name == 'estadisticas_basicas':
            if not params:
                return None
            return {'numeros': params}

        return None

    @classmethod
    def _extract_numbers_from_message(cls, message: str) -> List[float]:
        """Extrae números del mensaje de usuario como floats."""
        matches = re.findall(r'[-+]?[0-9]*\.?[0-9]+', message.replace(',', '.'))
        numbers = []
        for match in matches:
            try:
                numbers.append(float(match))
            except ValueError:
                continue
        return numbers

    @classmethod
    def _build_skill_params_for_price_query(
        cls,
        ctx: ChatContext,
        intent: Any,
    ) -> Optional[Dict[str, Any]]:
        """Construye parámetros de skill para consultas de precios."""
        registros = cls._fetch_price_records(ctx, intent)
        if not registros:
            return None

        zonas = intent.extracted_params.get('zonas', []) or []
        tipos = intent.extracted_params.get('tipos_propiedad', []) or []

        zona = zonas[0] if zonas else cls._infer_value_from_records(
            registros, ['zona', 'zone', 'district', 'district_name']
        )
        tipo_propiedad = tipos[0] if tipos else cls._infer_value_from_records(
            registros,
            ['tipo_propiedad', 'property_type', 'type', 'categoria', 'category'],
        )

        if not zona or not tipo_propiedad:
            return None

        return {
            'zona': str(zona),
            'tipo_propiedad': str(tipo_propiedad),
            'registros': registros,
        }

    @classmethod
    def _fetch_price_records(cls, ctx: ChatContext, intent: Any) -> List[Dict[str, Any]]:
        """Obtiene registros de propiedades relevantes para una consulta de precios."""
        collections = ctx.collections
        if not collections:
            user_level = cls._get_user_level(ctx.user)
            collections = list(
                IntelligenceCollection.objects.filter(
                    min_level__lte=user_level,
                    is_active=True,
                ).values_list('name', flat=True)
            )

        if not collections:
            return []

        try:
            rag_results = RAGService.search_dynamic(
                query=ctx.message,
                collection_names=collections,
                top_k=20,
            )
        except Exception as e:
            log.error(
                f"Error obteniendo registros de precios desde RAG: {e}",
                exc_info=True,
            )
            return []

        registros = []
        for result in rag_results:
            field_values = result.get('field_values', {}) or {}
            precio = cls._normalize_price_value(
                field_values.get('price')
                or field_values.get('precio')
                or field_values.get('monto')
                or field_values.get('value')
            )
            if precio is None:
                continue

            zona = (
                field_values.get('zona') or field_values.get('zone')
                or field_values.get('district')
                or field_values.get('district_name')
                or ''
            )
            tipo_propiedad = (
                field_values.get('tipo_propiedad')
                or field_values.get('property_type')
                or field_values.get('type')
                or field_values.get('categoria')
                or field_values.get('category')
                or ''
            )

            registro = {
                'zona': zona,
                'tipo_propiedad': tipo_propiedad,
                'precio': precio,
            }
            registro.update(field_values)
            registros.append(registro)

        return registros

    @classmethod
    def _infer_value_from_records(
        cls,
        registros: List[Dict[str, Any]],
        keys: List[str],
    ) -> Optional[str]:
        """Infiera un valor relevante a partir de registros de búsqueda."""
        for registro in registros:
            for key in keys:
                value = registro.get(key)
                if value:
                    return value
        return None

    @classmethod
    def _normalize_price_value(cls, value: Any) -> Optional[float]:
        """Convierte un valor de precio a float si es posible."""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            normalized = value.lower()
            normalized = normalized.replace('s/.', '')
            normalized = normalized.replace('soles', '')
            normalized = normalized.replace('usd', '')
            normalized = normalized.replace('$', '')
            normalized = normalized.replace(',', '')
            normalized = normalized.strip()
            normalized = re.sub(r'[^0-9\.\-]', '', normalized)
            try:
                return float(normalized)
            except ValueError:
                return None

        return None

    @classmethod
    def _process_skill_request(cls, ctx: ChatContext, trace_id: str) -> ChatResult:
        """Ejecuta una skill y convierte el resultado a ChatResult."""
        execution_context = ExecutionContext(
            user_id=str(ctx.user.id),
            session_id=ctx.conversation.session_id,
            permissions=(ctx.user.role.capabilities.keys()
                         if ctx.user.role and ctx.user.role.capabilities else []),
            environment='production',
            metadata={
                'app_id': ctx.app_id,
                'message': ctx.message,
            },
        )

        if ctx.skill_pipeline:
            return cls._process_skill_pipeline_request(ctx, trace_id)

        skill_result = SKILL_SYSTEM.execute_skill(
            ctx.skill_name,
            ctx.skill_params or {},
            execution_context,
        )

        response_text = cls._render_skill_response(skill_result)

        if skill_result.success:
            message_id = cls._save_response(ctx.conversation, response_text)
            cls._save_post_process(
                ctx=ctx,
                response_text=response_text,
                memory_context=None,
                rag_context=None,
                intent=None,
                trace_id=trace_id,
            )
            return ChatResult(
                success=True,
                response_text=response_text,
                conversation_id=str(ctx.conversation.id),
                message_id=message_id,
                metadata={
                    'skill_name': ctx.skill_name,
                    'skill_params': ctx.skill_params,
                    'skill_result': skill_result.data,
                },
                context_summary={
                    'skill_name': ctx.skill_name,
                    'skill_success': True,
                },
                timestamp=timezone.now().isoformat(),
            )

        return ChatResult(
            success=False,
            response_text=response_text,
            conversation_id=str(ctx.conversation.id),
            message_id='',
            metadata={
                'skill_name': ctx.skill_name,
                'skill_params': ctx.skill_params,
                'skill_error': skill_result.error_message,
            },
            context_summary={
                'skill_name': ctx.skill_name,
                'skill_success': False,
            },
            error=skill_result.error_message,
            timestamp=timezone.now().isoformat(),
        )

    @classmethod
    def _render_pipeline_response(cls, pipeline_result: Any) -> str:
        """Renderiza un resultado de pipeline de skills a texto legible."""
        if not pipeline_result.steps:
            return 'Pipeline de skills ejecutado correctamente.'

        rendered_steps = []
        for step in pipeline_result.steps:
            name = step.get('name')
            if step.get('success'):
                rendered_steps.append(
                    f"{name}: {json.dumps(step.get('result_data'), ensure_ascii=False)}"
                )
            else:
                rendered_steps.append(
                    f"{name} failed: {step.get('error_message')}"
                )

        return '\n'.join(rendered_steps)

    @classmethod
    def _process_skill_pipeline_request(cls, ctx: ChatContext, trace_id: str) -> ChatResult:
        """Ejecuta un pipeline de skills y convierte el resultado a ChatResult."""
        execution_context = ExecutionContext(
            user_id=str(ctx.user.id),
            session_id=ctx.conversation.session_id,
            permissions=(ctx.user.role.capabilities.keys()
                         if ctx.user.role and ctx.user.role.capabilities else []),
            environment='production',
            metadata={
                'app_id': ctx.app_id,
                'message': ctx.message,
            },
        )

        pipeline_result = SKILL_SYSTEM.execute_skill_pipeline(
            ctx.skill_pipeline,
            execution_context,
            mode=ctx.skill_pipeline_mode,
            stop_on_error=ctx.skill_pipeline_abort_on_error,
        )

        response_text = cls._render_pipeline_response(pipeline_result)

        if pipeline_result.success:
            message_id = cls._save_response(ctx.conversation, response_text)
            cls._save_post_process(
                ctx=ctx,
                response_text=response_text,
                memory_context=None,
                rag_context=None,
                intent=None,
                trace_id=trace_id,
            )
            return ChatResult(
                success=True,
                response_text=response_text,
                conversation_id=str(ctx.conversation.id),
                message_id=message_id,
                metadata={
                    'skill_pipeline': ctx.skill_pipeline,
                    'skill_pipeline_mode': ctx.skill_pipeline_mode,
                    'pipeline_result': pipeline_result.data,
                    'pipeline_steps': pipeline_result.steps,
                },
                context_summary={
                    'pipeline_mode': ctx.skill_pipeline_mode,
                    'skill_success': True,
                },
                timestamp=timezone.now().isoformat(),
            )

        return ChatResult(
            success=False,
            response_text=response_text,
            conversation_id=str(ctx.conversation.id),
            message_id='',
            metadata={
                'skill_pipeline': ctx.skill_pipeline,
                'skill_pipeline_mode': ctx.skill_pipeline_mode,
                'pipeline_error': pipeline_result.error_message,
                'pipeline_steps': pipeline_result.steps,
            },
            context_summary={
                'pipeline_mode': ctx.skill_pipeline_mode,
                'skill_success': False,
            },
            error=pipeline_result.error_message,
            timestamp=timezone.now().isoformat(),
        )

    @classmethod
    def _conversation_has_active_flow(cls, conversation: Conversation) -> bool:
        return (
            hasattr(conversation, 'flow_state')
            and conversation.flow_state is not None
            and not conversation.flow_state.is_completed
        )

    @classmethod
    def _resolve_flow_for_context(cls, ctx: ChatContext) -> Optional[ConversationFlow]:
        if cls._conversation_has_active_flow(ctx.conversation):
            return ctx.conversation.flow_state.flow

        if ctx.flow_name:
            return ConversationFlow.objects.filter(
                name=ctx.flow_name,
                is_active=True,
            ).first()

        return None

    @classmethod
    def _get_or_create_flow_state(
        cls,
        conversation: Conversation,
        flow: ConversationFlow,
    ) -> Tuple[ConversationFlowState, bool]:
        created = False
        try:
            flow_state = conversation.flow_state
        except ConversationFlowState.DoesNotExist:
            flow_state = ConversationFlowState.objects.create(
                conversation=conversation,
                flow=flow,
                current_state=flow.initial_state,
                state_history=[flow.initial_state],
            )
            created = True
            return flow_state, created

        if flow_state.flow != flow:
            if flow_state.is_completed:
                flow_state.delete()
                flow_state = ConversationFlowState.objects.create(
                    conversation=conversation,
                    flow=flow,
                    current_state=flow.initial_state,
                    state_history=[flow.initial_state],
                )
                created = True
            return flow_state, created

        return flow_state, created

    @classmethod
    def _process_flow_request(cls, ctx: ChatContext, trace_id: str) -> Optional[ChatResult]:
        flow = cls._resolve_flow_for_context(ctx)
        if not flow:
            return None

        flow_state, created = cls._get_or_create_flow_state(
            ctx.conversation,
            flow,
        )

        if created:
            response_text, buttons = cls._render_flow_state(flow, flow_state)
        else:
            response_text, buttons = cls._advance_flow_state(
                ctx, flow, flow_state
            )

        if response_text is None:
            return None

        message_id = cls._save_response(
            ctx.conversation,
            response_text,
        )

        cls._save_post_process(
            ctx=ctx,
            response_text=response_text,
            memory_context=None,
            rag_context=None,
            intent=None,
            trace_id=trace_id,
        )

        metadata = {
            'flow_name': flow.name,
            'flow_state': flow_state.current_state,
            'flow_completed': flow_state.is_completed,
        }
        if buttons:
            metadata['buttons'] = buttons

        return ChatResult(
            success=True,
            response_text=response_text,
            conversation_id=str(ctx.conversation.id),
            message_id=message_id,
            metadata=metadata,
            context_summary={
                'flow': flow.name,
                'flow_state': flow_state.current_state,
                'flow_completed': flow_state.is_completed,
            },
            timestamp=timezone.now().isoformat(),
        )

    @classmethod
    def _render_flow_state(
        cls,
        flow: ConversationFlow,
        flow_state: ConversationFlowState,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        node = flow.states.get(flow_state.current_state, {})
        if not isinstance(node, dict):
            return (
                'El flujo está mal configurado. Contacta al equipo de soporte.',
                [],
            )
        return node.get('message', ''), node.get('buttons', [])

    @classmethod
    def _advance_flow_state(
        cls,
        ctx: ChatContext,
        flow: ConversationFlow,
        flow_state: ConversationFlowState,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        node = flow.states.get(flow_state.current_state)
        if not isinstance(node, dict):
            return (
                'El estado del flujo no es válido. Contacta al equipo de soporte.',
                [],
            )

        if node.get('complete'):
            flow_state.is_completed = True
            flow_state.completed_at = timezone.now()
            flow_state.save(update_fields=['is_completed', 'completed_at'])
            return node.get('message', 'Flujo completado.'), node.get('buttons', [])

        if node.get('buttons'):
            button = cls._match_flow_button(ctx.message, node['buttons'])
            if button:
                next_state = button.get('next_state')
                if next_state:
                    return cls._transition_flow_state(
                        flow, flow_state, next_state
                    )
            return node.get('message', ''), node.get('buttons', [])

        if node.get('collect_data'):
            collect_fields = node.get('collect_data', [])
            missing_fields = [
                field for field in collect_fields
                if field not in flow_state.collected_data
            ]
            if missing_fields:
                flow_state.collected_data[missing_fields[0]] = ctx.message
                flow_state.save(update_fields=['collected_data'])
                if len(missing_fields) > 1:
                    return node.get('message', ''), node.get('buttons', [])
                if node.get('next_state'):
                    return cls._transition_flow_state(
                        flow, flow_state, node.get('next_state')
                    )
                return node.get('message', ''), node.get('buttons', [])

        if node.get('next_state'):
            return cls._transition_flow_state(
                flow, flow_state, node.get('next_state')
            )

        return node.get('message', ''), node.get('buttons', [])

    @classmethod
    def _transition_flow_state(
        cls,
        flow: ConversationFlow,
        flow_state: ConversationFlowState,
        next_state: str,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        next_node = flow.states.get(next_state)
        if not isinstance(next_node, dict):
            flow_state.is_completed = True
            flow_state.completed_at = timezone.now()
            flow_state.save(update_fields=['is_completed', 'completed_at'])
            return (
                'Flujo terminado o estado no encontrado. Contacta al equipo de soporte.',
                [],
            )

        flow_state.current_state = next_state
        if flow_state.state_history is None:
            flow_state.state_history = []
        flow_state.state_history.append(next_state)
        if next_node.get('complete'):
            flow_state.is_completed = True
            flow_state.completed_at = timezone.now()
        flow_state.save()

        return next_node.get('message', ''), next_node.get('buttons', [])

    @classmethod
    def _match_flow_button(
        cls,
        user_message: str,
        buttons: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        normalized = user_message.strip().lower()
        for button in buttons:
            if normalized == str(button.get('text', '')).strip().lower():
                return button
            if normalized == str(button.get('value', '')).strip().lower():
                return button
        return None

    @classmethod
    def _save_response(
        cls,
        conversation: Conversation,
        response_text: str,
    ) -> str:
        """Guarda la respuesta del asistente en la conversación."""
        message = {
            'role': 'assistant',
            'content': response_text,
            'timestamp': timezone.now().isoformat(),
            'id': str(uuid.uuid4()),
        }

        messages = conversation.messages
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

        messages = conversation.messages
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
        memory_context: Optional[List[Dict]] = None,
        rag_context: Optional[List[Dict]] = None,
        intent: Any = None,
        trace_id: str = '',
    ):
        """
        Post-procesamiento después de generar respuesta:
        - Guardar episodio en memoria episódica
        - Extraer y guardar hechos
        """
        if not ctx.use_memory:
            return

        # Guardar episodio
        try:
            enriched_context = {
                'collections_used': ctx.collections if ctx.collections else [],
                'user_level': cls._get_user_level(ctx.user),
                'use_rag': ctx.use_rag,
                'use_memory': ctx.use_memory,
                'intent': intent.intent.value if intent else None,
                'trace_id': trace_id,
            }

            episode_data = EpisodicMemoryService.save_episode(
                user_id=str(ctx.user.id),
                conversation_id=str(ctx.conversation.id),
                user_message=ctx.message,
                assistant_response=response_text,
                rag_context_used=rag_context if rag_context else None,
                memory_context_used=memory_context if memory_context else None,
                context=enriched_context,
            )

            if episode_data:
                log.info(
                    f"Episodio guardado: tipo={episode_data.get('episode_type')}, "
                    f"intent={episode_data.get('intent_detected')}, "
                    f"importancia={episode_data.get('importance_score'):.2f}",
                    trace_id=trace_id,
                )
        except Exception as e:
            log.error(
                f"Error guardando episodio: {str(e)}",
                exc_info=True,
            )

        # Extraer hechos
        try:
            extracted_facts = MemoryService.extract_and_save_facts(
                user_id=ctx.user.id,
                message=ctx.message,
                response=response_text,
            )
            if extracted_facts:
                log.info(
                    f"Extraídos {len(extracted_facts)} hechos: "
                    f"{[f['relation'] for f in extracted_facts]}",
                    trace_id=trace_id,
                )
        except Exception as e:
            log.error(
                f"Error extrayendo hechos: {str(e)}",
                exc_info=True,
            )


# ── Atajo para importar ────────────────────────────────────────────────────
# Para mantener compatibilidad con imports existentes
chat_processor = ChatProcessor()
