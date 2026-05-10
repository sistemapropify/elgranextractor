"""
Servicio de memoria episódica: gestiona eventos completos de interacción
usuario-sistema, permitiendo recordar contextos específicos del pasado.
"""
import uuid
import logging
import json
import re
from datetime import timedelta
from typing import Optional, Dict, List, Any, Tuple
import numpy as np

from django.utils import timezone
from django.conf import settings

from ..models import User, Conversation, EpisodicMemory

logger = logging.getLogger(__name__)


def _make_json_serializable(obj: Any) -> Any:
    """
    Convierte objetos no serializables (UUID, objetos Django, etc.)
    a tipos JSON estándar recursivamente.
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    if hasattr(obj, 'id'):
        return str(obj.id)
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


class EpisodicMemoryService:
    """
    Servicio para gestionar memoria episódica.
    Cada "episodio" es una interacción completa: mensaje + respuesta + contexto.
    """

    # Configuración
    MAX_EPISODES_PER_USER = int(getattr(settings, 'EPISODIC_MEMORY_MAX_PER_USER', 500))
    PRUNE_AFTER_DAYS = int(getattr(settings, 'EPISODIC_MEMORY_PRUNE_DAYS', 30))
    MIN_IMPORTANCE_TO_KEEP = float(getattr(settings, 'EPISODIC_MEMORY_MIN_IMPORTANCE', 0.2))
    EMBEDDING_DIMENSIONS = 384

    def __init__(self, user_id: str = None):
        """
        Args:
            user_id: ID del usuario (string UUID)
        """
        self.user_id = user_id
        self.user = None
        if user_id:
            try:
                self.user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.user = None

    # =====================================================================
    # MÉTODOS PRINCIPALES
    # =====================================================================

    @staticmethod
    def save_episode(
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message: str,
        assistant_response: str,
        episode_type: str = 'general',
        intent_detected: str = '',
        context: Optional[Dict] = None,
        rag_context_used: Optional[Dict] = None,
        memory_context_used: Optional[Dict] = None,
        latency_ms: Optional[int] = None,
        generate_embedding: bool = True
    ) -> Optional[Dict]:
        """
        Guarda un episodio completo de interacción.

        Args:
            user_id: ID del usuario
            conversation_id: ID de la conversación
            user_message: Mensaje del usuario
            assistant_response: Respuesta del asistente
            episode_type: Tipo de episodio (property_search, general, etc.)
            intent_detected: Intención detectada
            context: Contexto enriquecido (entities, topics, sentiment, etc.)
            rag_context_used: Documentos RAG recuperados para esta respuesta
            memory_context_used: Hechos de memoria usados
            latency_ms: Latencia de generación en ms
            generate_embedding: Si se debe generar embedding para búsqueda semántica

        Returns:
            Dict con datos del episodio creado, o None si hay error
        """
        try:
            user = User.objects.get(id=user_id)
            conversation = Conversation.objects.get(id=conversation_id)
        except (User.DoesNotExist, Conversation.DoesNotExist) as e:
            logger.error(f"Error al guardar episodio: {e}")
            return None

        # Generar embedding del mensaje del usuario si se solicita
        embedding_bytes = None
        if generate_embedding and user_message:
            try:
                from .rag import RAGService
                embedding_bytes = RAGService.generate_embedding(user_message)
            except Exception as e:
                logger.warning(f"No se pudo generar embedding para episodio: {e}")

        # Calcular importancia
        importance = EpisodicMemoryService._calculate_importance(
            user_message=user_message,
            episode_type=episode_type,
            context=context or {}
        )

        # Clasificar tipo si no se proporcionó
        if not episode_type or episode_type == 'general':
            detected_type, detected_intent = EpisodicMemoryService._classify_episode(
                user_message, assistant_response
            )
            if detected_type != 'general':
                episode_type = detected_type
            if detected_intent:
                intent_detected = detected_intent

        # Sanitizar datos para JSON serialization
        safe_context = _make_json_serializable(context or {})
        safe_rag_context = _make_json_serializable(rag_context_used or {})
        safe_memory_context = _make_json_serializable(memory_context_used or {})

        # Crear el episodio
        try:
            episode = EpisodicMemory.objects.create(
                user=user,
                conversation=conversation,
                user_message=user_message,
                user_message_embedding=embedding_bytes,
                assistant_response=assistant_response,
                timestamp=timezone.now(),
                episode_type=episode_type,
                intent_detected=intent_detected,
                context=safe_context,
                rag_context_used=safe_rag_context,
                memory_context_used=safe_memory_context,
                latency_ms=latency_ms,
                importance_score=importance,
                is_active=True
            )

            logger.info(
                f"Episodio guardado: type={episode_type}, "
                f"importance={importance:.2f}, "
                f"user={user_id}"
            )

            return {
                'id': str(episode.id),
                'episode_type': episode_type,
                'intent_detected': intent_detected,
                'importance_score': importance,
                'timestamp': episode.timestamp.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error al crear episodio en BD: {e}")
            return None

    def get_relevant_episodes(
        self,
        query: str,
        limit: int = 3,
        min_importance: float = 0.0,
        episode_type_filter: Optional[str] = None,
        days_back: Optional[int] = None
    ) -> List[Dict]:
        """
        Busca episodios relevantes para una consulta usando embeddings semánticos.

        Args:
            query: Consulta del usuario
            limit: Número máximo de episodios a retornar
            min_importance: Importancia mínima (0.0 = todos)
            episode_type_filter: Filtrar por tipo de episodio
            days_back: Solo episodios de los últimos N días

        Returns:
            Lista de episodios relevantes con score de similitud
        """
        if not self.user:
            return []

        # Obtener episodios del usuario
        queryset = EpisodicMemory.objects.filter(
            user=self.user,
            is_active=True
        )

        # Filtros
        if episode_type_filter:
            queryset = queryset.filter(episode_type=episode_type_filter)
        if min_importance > 0:
            queryset = queryset.filter(importance_score__gte=min_importance)
        if days_back:
            threshold = timezone.now() - timedelta(days=days_back)
            queryset = queryset.filter(timestamp__gte=threshold)

        # Obtener episodios (máximo 50 para búsqueda)
        episodes = list(queryset.order_by('-timestamp')[:50])

        if not episodes:
            return []

        # Generar embedding de la consulta
        try:
            from .rag import RAGService
            query_embedding_bytes = RAGService.generate_embedding(query)
            if not query_embedding_bytes:
                # Fallback: ordenar por timestamp si no hay embedding
                return EpisodicMemoryService._format_episodes(episodes[:limit])

            query_embedding = np.frombuffer(query_embedding_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Error al generar embedding de consulta: {e}")
            return EpisodicMemoryService._format_episodes(episodes[:limit])

        # Calcular similitud coseno con cada episodio
        scored_episodes = []
        for episode in episodes:
            if not episode.user_message_embedding:
                continue

            try:
                episode_embedding = np.frombuffer(
                    episode.user_message_embedding, dtype=np.float32
                )

                # Normalizar vectores
                query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
                episode_norm = episode_embedding / (np.linalg.norm(episode_embedding) + 1e-10)

                # Similitud coseno
                similarity = float(np.dot(query_norm, episode_norm))

                # Score combinado: 70% similitud semántica + 30% importancia
                combined_score = (similarity * 0.7) + (episode.importance_score * 0.3)

                scored_episodes.append({
                    'episode': episode,
                    'similarity': similarity,
                    'combined_score': combined_score,
                })
            except Exception as e:
                logger.warning(f"Error al calcular similitud para episodio {episode.id}: {e}")
                continue

        # Ordenar por score combinado
        scored_episodes.sort(key=lambda x: x['combined_score'], reverse=True)

        # Tomar los mejores
        top_episodes = scored_episodes[:limit]

        # Si no hay resultados semánticos, hacer fallback a episodios recientes
        # de tipos que contienen información factual del usuario
        if not top_episodes:
            logger.info("Búsqueda semántica sin resultados, usando fallback a episodios factuales recientes")
            factual_types = ['fact_extraction', 'user_preference']
            fallback_qs = EpisodicMemory.objects.filter(
                user=self.user,
                is_active=True,
                episode_type__in=factual_types
            )
            if min_importance > 0:
                fallback_qs = fallback_qs.filter(importance_score__gte=min_importance)
            if days_back:
                fallback_qs = fallback_qs.filter(timestamp__gte=threshold)
            
            fallback_episodes = list(fallback_qs.order_by('-timestamp')[:limit])
            if fallback_episodes:
                return EpisodicMemoryService._format_episodes(fallback_episodes)

        # Formatear respuesta
        result = []
        for item in top_episodes:
            ep = item['episode']
            result.append({
                'id': str(ep.id),
                'type': 'episodic',
                'episode_type': ep.episode_type,
                'intent_detected': ep.intent_detected,
                'user_message': ep.user_message,
                'assistant_response': ep.assistant_response,
                'timestamp': ep.timestamp.isoformat(),
                'similarity_score': round(item['similarity'], 4),
                'combined_score': round(item['combined_score'], 4),
                'importance_score': ep.importance_score,
                'context': ep.context,
                'rag_context_used': ep.rag_context_used,
                'feedback': ep.feedback,
            })

        return result

    @staticmethod
    def get_relevant_episodes_static(
        user_id: str,
        query: str,
        limit: int = 3,
        min_importance: float = 0.0,
        episode_type_filter: Optional[str] = None,
        days_back: Optional[int] = None
    ) -> List[Dict]:
        """
        Versión estática de get_relevant_episodes para usar desde views.
        Crea una instancia internamente.

        Args:
            user_id: ID del usuario (string)
            query: Consulta del usuario
            limit: Número máximo de episodios
            min_importance: Importancia mínima
            episode_type_filter: Filtrar por tipo
            days_back: Solo últimos N días

        Returns:
            Lista de episodios relevantes
        """
        try:
            service = EpisodicMemoryService(user_id=user_id)
            return service.get_relevant_episodes(
                query=query,
                limit=limit,
                min_importance=min_importance,
                episode_type_filter=episode_type_filter,
                days_back=days_back
            )
        except Exception as e:
            logger.error(f"Error en get_relevant_episodes_static: {e}")
            return []

    # =====================================================================
    # MÉTODOS DE CLASIFICACIÓN E IMPORTANCIA
    # =====================================================================

    @staticmethod
    def _classify_episode(user_message: str, assistant_response: str) -> Tuple[str, str]:
        """
        Clasifica el tipo de episodio usando DeepSeek.
        Si falla, usa reglas simples como fallback.

        Returns:
            Tuple (episode_type, intent_detected)
        """
        # Intentar con DeepSeek primero
        try:
            from .llm import LLMService

            system_prompt = """Eres un clasificador de intenciones para un chat inmobiliario.
Analiza el mensaje del usuario y la respuesta del asistente, y determina:

1. TIPO DE EPISODIO (uno de):
   - property_search: Búsqueda de propiedades
   - property_detail: Consulta de detalle de propiedad específica
   - price_inquiry: Consulta de precio
   - matching: Matching oferta-demanda
   - acm_analysis: Análisis Comparativo de Mercado
   - user_preference: El usuario expresa una preferencia
   - fact_extraction: El usuario da información personal
   - general: Consulta general

2. INTENCIÓN DETECTADA (texto corto, ej: "buscar departamento en Cayma",
   "consultar precio", "comparar zonas")

Responde SOLO con JSON: {"episode_type": "...", "intent": "..."}"""

            messages = [
                {"role": "user", "content": f"Usuario: {user_message}\nAsistente: {assistant_response}"}
            ]

            success, _, api_response = LLMService._call_deepseek_api(
                messages=messages,
                system_prompt=system_prompt
            )

            if success and api_response:
                # Asegurar que api_response sea un diccionario antes de llamar a .get()
                if isinstance(api_response, dict):
                    content = api_response.get("content", "")
                else:
                    logger.warning(f"api_response inesperado en classify_episode: type={type(api_response)}")
                    content = ""
                json_match = re.search(r'\{[^}]+\}', content)
                if json_match:
                    data = json.loads(json_match.group(0))
                    episode_type = data.get('episode_type', 'general')
                    intent = data.get('intent', '')
                    return episode_type, intent

        except Exception as e:
            logger.warning(f"Error clasificando episodio con DeepSeek: {e}")

        # Fallback: reglas simples
        return EpisodicMemoryService._classify_with_rules(user_message)

    @staticmethod
    def _classify_with_rules(user_message: str) -> Tuple[str, str]:
        """Clasifica episodio usando reglas simples (fallback)."""
        msg_lower = user_message.lower()

        # Detectar búsqueda de propiedad
        if any(word in msg_lower for word in ['departamento', 'casa', 'terreno', 'local', 'oficina', 'propiedad']):
            # Detectar distrito
            districts = ['cayma', 'yanahuara', 'cercado', 'sachaca', 'miraflores',
                        'cerro colorado', 'paucarpata', 'bustamante', 'mariano melgar']
            found_districts = [d for d in districts if d in msg_lower]
            intent = f"buscar propiedad"
            if found_districts:
                intent += f" en {', '.join(found_districts)}"
            return ('property_search', intent)

        # Detectar consulta de precio
        if any(word in msg_lower for word in ['precio', 'cuánto', 'costo', 'cuanto', 'cuesta', 'presupuesto']):
            return ('price_inquiry', 'consultar precio')

        # Detectar preferencia del usuario
        if any(word in msg_lower for word in ['me gusta', 'prefiero', 'quiero', 'necesito', 'busco']):
            return ('user_preference', 'expresar preferencia')

        # Detectar información personal
        if any(word in msg_lower for word in ['me llamo', 'soy', 'vivo en', 'trabajo en', 'mi nombre']):
            return ('fact_extraction', 'dar información personal')

        return ('general', '')

    @staticmethod
    def _calculate_importance(
        user_message: str,
        episode_type: str,
        context: Dict
    ) -> float:
        """
        Calcula la importancia de un episodio (0.0 a 1.0).

        Factores:
        - Tipo de episodio (property_search, price_inquiry pesan más)
        - Menciones de precio (indica intención de compra)
        - Sentimiento positivo/negativo explícito
        - Longitud del mensaje (mensajes más largos = más interés)
        """
        score = 0.3  # Base

        # Bonus por tipo de episodio
        type_bonus = {
            'property_search': 0.2,
            'property_detail': 0.25,
            'price_inquiry': 0.3,
            'matching': 0.2,
            'acm_analysis': 0.15,
            'user_preference': 0.2,
            'fact_extraction': 0.1,
            'general': 0.0,
        }
        score += type_bonus.get(episode_type, 0.0)

        # Bonus por mención de precio
        msg_lower = user_message.lower()
        if any(word in msg_lower for word in ['precio', 'cuánto', 'costo', 'presupuesto', '$', 'usd', 'soles']):
            score += 0.15

        # Bonus por mención de distrito específico
        districts = ['cayma', 'yanahuara', 'cercado', 'sachaca', 'miraflores',
                    'cerro colorado', 'paucarpata', 'bustamante', 'mariano melgar']
        if any(d in msg_lower for d in districts):
            score += 0.1

        # Bonus por longitud del mensaje (indica interés)
        if len(user_message) > 100:
            score += 0.1
        elif len(user_message) > 50:
            score += 0.05

        # Bonus por sentimiento del contexto
        sentiment = context.get('sentiment', '')
        if sentiment == 'positive':
            score += 0.1
        elif sentiment == 'negative':
            score += 0.05  # También es importante saber qué no le gusta

        # Bonus por acciones del usuario
        user_actions = context.get('user_actions', [])
        if 'click' in user_actions:
            score += 0.15
        if 'save' in user_actions or 'favorite' in user_actions:
            score += 0.2
        if 'share' in user_actions:
            score += 0.15

        return min(max(score, 0.0), 1.0)

    # =====================================================================
    # FEEDBACK
    # =====================================================================

    @staticmethod
    def update_feedback(
        episode_id: uuid.UUID,
        thumbs_up: Optional[bool] = None,
        thumbs_down: Optional[bool] = None,
        user_comment: Optional[str] = None
    ) -> bool:
        """
        Actualiza el feedback de un episodio.

        Args:
            episode_id: ID del episodio
            thumbs_up: True si fue útil
            thumbs_down: True si no fue útil
            user_comment: Comentario opcional del usuario

        Returns:
            True si se actualizó correctamente
        """
        try:
            episode = EpisodicMemory.objects.get(id=episode_id)
            feedback = episode.feedback or {}

            if thumbs_up is not None:
                feedback['thumbs_up'] = thumbs_up
                if thumbs_up:
                    feedback['thumbs_down'] = False
            if thumbs_down is not None:
                feedback['thumbs_down'] = thumbs_down
                if thumbs_down:
                    feedback['thumbs_up'] = False
            if user_comment:
                feedback['user_comment'] = user_comment

            feedback['collected_at'] = timezone.now().isoformat()
            episode.feedback = feedback

            # Si hay thumbs_up, aumentar importancia
            if thumbs_up:
                episode.importance_score = min(episode.importance_score + 0.1, 1.0)
            elif thumbs_down:
                episode.importance_score = max(episode.importance_score - 0.1, 0.0)

            episode.save()
            return True

        except EpisodicMemory.DoesNotExist:
            logger.error(f"Episodio {episode_id} no encontrado para feedback")
            return False
        except Exception as e:
            logger.error(f"Error al actualizar feedback: {e}")
            return False

    # =====================================================================
    # MÉTODOS DE FORMATO
    # =====================================================================

    @staticmethod
    def _format_episodes(episodes: List[EpisodicMemory]) -> List[Dict]:
        """Formatea episodios para respuesta."""
        result = []
        for ep in episodes:
            result.append({
                'id': str(ep.id),
                'type': 'episodic',
                'episode_type': ep.episode_type,
                'intent_detected': ep.intent_detected,
                'user_message': ep.user_message,
                'assistant_response': ep.assistant_response,
                'timestamp': ep.timestamp.isoformat(),
                'similarity_score': 0.0,
                'combined_score': 0.0,
                'importance_score': ep.importance_score,
                'context': ep.context,
                'rag_context_used': ep.rag_context_used,
                'feedback': ep.feedback,
            })
        return result

    @staticmethod
    def format_episodes_for_prompt(episodes: List[Dict]) -> str:
        """
        Formatea episodios relevantes para inyectar en el prompt del LLM.

        Args:
            episodes: Lista de episodios (de get_relevant_episodes)

        Returns:
            Texto formateado para el prompt
        """
        if not episodes:
            return ""

        lines = []
        lines.append("=== INTERACCIONES ANTERIORES RELEVANTES ===")
        lines.append("El usuario tuvo estas interacciones previas que son relevantes para su consulta actual:")
        lines.append("")

        for i, ep in enumerate(episodes, 1):
            timestamp = ep.get('timestamp', '')[:19] if ep.get('timestamp') else ''
            ep_type = ep.get('episode_type', 'general')
            intent = ep.get('intent_detected', '')

            lines.append(f"--- Interacción {i} ({timestamp}) ---")
            lines.append(f"Tipo: {ep_type}")
            if intent:
                lines.append(f"Intención: {intent}")
            lines.append(f"Usuario preguntó: {ep.get('user_message', '')[:200]}")
            lines.append(f"Asistente respondió: {ep.get('assistant_response', '')[:200]}")

            # Agregar contexto de propiedades si existe
            rag_ctx = ep.get('rag_context_used', {})
            if isinstance(rag_ctx, dict):
                docs = rag_ctx.get('documents_retrieved', [])
            elif isinstance(rag_ctx, list):
                docs = rag_ctx
            else:
                docs = []
            if docs:
                titles = [d.get('title', d.get('id', '')) for d in docs[:3]]
                lines.append(f"Propiedades mencionadas: {', '.join(titles)}")

            # Agregar feedback si existe
            feedback = ep.get('feedback', {})
            if feedback.get('thumbs_up'):
                lines.append("→ El usuario calificó esta respuesta como útil")
            elif feedback.get('thumbs_down'):
                lines.append("→ El usuario calificó esta respuesta como no útil")

            lines.append("")

        lines.append("USA esta información para mantener coherencia con interacciones pasadas.")
        lines.append("Si el usuario se refiere a algo que ocurrió antes, usa estos episodios para contextualizar.")
        lines.append("")

        return "\n".join(lines)

    # =====================================================================
    # MANTENIMIENTO
    # =====================================================================

    @staticmethod
    def prune_old_episodes(dry_run: bool = False) -> Dict[str, int]:
        """
        Elimina episodios viejos de baja importancia.

        Args:
            dry_run: Si True, solo cuenta sin eliminar

        Returns:
            Dict con estadísticas de pruning
        """
        threshold_date = timezone.now() - timedelta(days=EpisodicMemoryService.PRUNE_AFTER_DAYS)

        # Episodios viejos Y de baja importancia
        old_low_importance = EpisodicMemory.objects.filter(
            is_active=True,
            timestamp__lt=threshold_date,
            importance_score__lt=EpisodicMemoryService.MIN_IMPORTANCE_TO_KEEP
        )

        # Episodios con feedback negativo (thumbs_down) y viejos
        old_negative_feedback = EpisodicMemory.objects.filter(
            is_active=True,
            timestamp__lt=threshold_date,
            feedback__thumbs_down=True
        )

        stats = {
            'old_low_importance_count': old_low_importance.count(),
            'old_negative_feedback_count': old_negative_feedback.count(),
            'total_to_prune': 0,
            'pruned': 0,
        }

        # Combinar querysets (evitar duplicados)
        to_prune_ids = set()
        for ep in old_low_importance:
            to_prune_ids.add(ep.id)
        for ep in old_negative_feedback:
            to_prune_ids.add(ep.id)

        stats['total_to_prune'] = len(to_prune_ids)

        if not dry_run and to_prune_ids:
            pruned = EpisodicMemory.objects.filter(id__in=list(to_prune_ids)).update(
                is_active=False
            )
            stats['pruned'] = pruned
            logger.info(f"Pruning completado: {pruned} episodios desactivados")

        return stats

    @staticmethod
    def enforce_max_per_user(dry_run: bool = False) -> Dict[str, int]:
        """
        Asegura que ningún usuario exceda MAX_EPISODES_PER_USER.
        Elimina los más antiguos de baja importancia si es necesario.

        Args:
            dry_run: Si True, solo cuenta sin eliminar

        Returns:
            Dict con estadísticas
        """
        from django.db.models import Count

        stats = {
            'users_over_limit': 0,
            'total_removed': 0,
        }

        # Usuarios que exceden el límite
        users_over = (
            EpisodicMemory.objects
            .filter(is_active=True)
            .values('user')
            .annotate(count=Count('id'))
            .filter(count__gt=EpisodicMemoryService.MAX_EPISODES_PER_USER)
        )

        for entry in users_over:
            user_id = entry['user']
            excess = entry['count'] - EpisodicMemoryService.MAX_EPISODES_PER_USER

            stats['users_over_limit'] += 1

            # Obtener episodios a eliminar (los más antiguos de baja importancia)
            to_remove = EpisodicMemory.objects.filter(
                user_id=user_id,
                is_active=True
            ).order_by('importance_score', 'timestamp')[:excess]

            if not dry_run:
                ids = [ep.id for ep in to_remove]
                removed = EpisodicMemory.objects.filter(id__in=ids).update(is_active=False)
                stats['total_removed'] += removed

        return stats
