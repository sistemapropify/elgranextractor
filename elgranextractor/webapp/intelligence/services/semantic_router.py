"""
SemanticSkillRouter — Router semántico de skills usando embeddings E5-large.

Reemplaza el keyword matching de SkillRegistry.find_best_skill() por
clasificación semántica con embeddings y similitud coseno.

Arquitectura:
1. Cada skill tiene N templates (few-shot examples) de consultas reales
2. Los templates se embeddean al iniciar con mode='passage' y se cachean
3. Cuando llega una consulta, se embeddea con mode='query'
4. Se calcula similitud coseno contra todos los templates
5. Se retorna la skill con mayor score si supera el threshold

F1-001: Semantic Skill Router (Phase 1 — Function Calling)
"""

from __future__ import annotations

import logging
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from django.conf import settings

from .rag import RAGService

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RoutingResult:
    """Resultado del routing semántico."""
    skill_name: Optional[str]       # Nombre de la skill detectada (None = RAG puro)
    score: float                    # Mejor score de similitud (0.0 - 1.0)
    threshold: float                # Threshold usado
    accepted: bool                  # True si score >= threshold
    matched_template: str           # Template que hizo match (para debug)
    n_templates_evaluated: int      # Total de templates evaluados
    latency_ms: float               # Tiempo de clasificación
    fallback_used: bool             # True si se usó fallback por keywords
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_log(self) -> Dict[str, Any]:
        """Convierte a dict para logging estructurado."""
        return {
            'skill_name': self.skill_name,
            'score': round(self.score, 4),
            'threshold': self.threshold,
            'accepted': self.accepted,
            'matched_template': self.matched_template[:80] if self.matched_template else '',
            'n_templates': self.n_templates_evaluated,
            'latency_ms': round(self.latency_ms, 2),
            'fallback_used': self.fallback_used,
            'timestamp': self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Skill Templates (Few-Shot Examples)
# ═══════════════════════════════════════════════════════════════════════════════
# Cada skill tiene ejemplos de consultas reales que representan su dominio.
# Mientras más ejemplos, mejor discriminación semántica.
# ═══════════════════════════════════════════════════════════════════════════════

# Templates por defecto — pueden sobreescribirse desde settings
_DEFAULT_SKILL_TEMPLATES: Dict[str, List[str]] = {
    'busqueda_propiedades': [
        # Búsquedas directas
        'busco departamento en Cayma',
        'quiero comprar una casa en Yanahuara',
        'necesito un terreno para construir',
        'busco propiedades en Cerro Colorado',
        'alquiler de departamentos en Sachaca',
        'busco terreno en Zamacola',
        'quiero alquilar un depa en Miraflores',
        'busco casa en venta en Paucarpata',
        'necesito un local comercial en el Cercado',
        'busco oficina en renta en Bustamante',
        'muéstrame departamentos en José Luis Bustamante',
        # Búsquedas con propósito
        'donde puedo construir un colegio',
        'busco terreno para construir una escuela',
        'necesito un local para negocio',
        'quiero un terreno para proyecto de vivienda',
        'busco propiedad para inversion',
        'terreno industrial en la Joya',
        # Búsquedas con características
        'casa con 3 dormitorios en Cayma',
        'departamento amoblado en Yanahuara',
        'terreno de 500 metros en Sachaca',
        'casa con piscina en Cerro Colorado',
        'departamento luminoso en el Cercado',
        'casa amplia con jardin en Bustamante',
        # Búsquedas por precio
        'departamentos hasta 200 mil soles',
        'casas entre 100 y 150 mil dolares',
        'terrenos baratos en Zamacola',
        'propiedades económicas en Paucarpata',
        # Variantes coloquiales (fijar falsos positivos)
        'qué terrenos tienes en Cayma',
        'qué casas tienes en venta',
        'muéstrame las propiedades en cayma',
        'departamento amoblado en Yanahuara en alquiler',
        'muéstrame todos los departamentos disponibles',
    ],
    'resolver_contexto': [
        'muéstrame los que tengan 3 dormitorios',
        'quiero ver más baratos',
        'los que están en la misma zona',
        'enséñame fotos de esa propiedad',
        'solo departamentos',
        'y en Cayma',
        'y en Cerro Colorado',
        'quiero ver opciones más grandes',
        'los que tengan garage',
        'alguna opción con piscina',
        'muéstrame solo los que tienen 2 baños',
        'ordéname por precio',
        'y de todos esos cuales son terrenos',
    ],
    'analizar_mercado': [
        'cómo está el mercado en Cayma',
        'precio promedio de departamentos en Yanahuara',
        'tendencias de precios en Cerro Colorado',
        'comparativa de zonas residenciales',
        'cuál es el mejor distrito para invertir',
        'análisis de mercado en Bustamante',
        'dónde están subiendo los precios',
        'zonas con mayor plusvalía en Arequipa',
        'precio promedio de terrenos en Cayma',
        'comparativa de precios entre Cayma y Yanahuara',
    ],
    'extraer_requerimientos_whatsapp': [
        'tengo un cliente que busca depa en Cayma',
        'me llegó un requerimiento de un terreno',
        'un cliente me pide casa en Yanahuara',
        'necesito procesar este requerimiento',
        'ayúdame a entender lo que busca mi cliente',
        'un cliente está buscando local comercial en Sachaca',
        'me escribieron por WhatsApp buscando departamento',
        'recibí un mensaje de un cliente interesado en terrenos',
        'quiero guardar el requerimiento de un cliente',
        'un cliente me contactó buscando alquiler',
    ],
    '_saludo': [
        'hola',
        'hola cómo estás',
        'buenos días',
        'buenas tardes',
        'buenas noches',
        'qué tal',
    ],
    '_general': [
        'cómo funciona el sistema',
        'quién eres',
        'qué puedes hacer',
        'cómo me puedes ayudar',
        'gracias',
        'muchas gracias',
        'de nada',
        'chau',
        'adiós',
        'hasta luego',
    ],
}

# Templates configurables desde settings
SKILL_TEMPLATES = getattr(
    settings, 'SKILL_TEMPLATES', _DEFAULT_SKILL_TEMPLATES
)


# ═══════════════════════════════════════════════════════════════════════════════
# SemanticSkillRouter
# ═══════════════════════════════════════════════════════════════════════════════


class SemanticSkillRouter:
    """
    Router semántico de skills usando embeddings E5-large.

    Clasifica consultas en lenguaje natural contra templates few-shot
    de cada skill usando similitud coseno en espacio de embeddings.

    Uso:
        router = SemanticSkillRouter()
        result = router.classify("busco departamento en Cayma")
        if result.accepted:
            print(f"Skill: {result.skill_name}, score: {result.score}")
        else:
            print("RAG puro (ninguna skill superó el threshold)")

    Threshold por defecto: 0.45 (configurable via settings.SKILL_ROUTER_THRESHOLD)
    """

    # Threshold de confianza (aumentado de 0.25 a 0.45)
    DEFAULT_THRESHOLD = 0.45

    def __init__(self, threshold: Optional[float] = None):
        """
        Inicializa el router con templates y cache de embeddings.

        Args:
            threshold: Umbral de confianza (default: 0.45)
        """
        self.threshold = threshold or float(
            getattr(settings, 'SKILL_ROUTER_THRESHOLD', self.DEFAULT_THRESHOLD)
        )
        self.templates = SKILL_TEMPLATES

        # Cache de embeddings de templates: {template_hash: embedding_bytes}
        self._template_embeddings: Dict[str, np.ndarray] = {}
        self._template_skill_map: Dict[str, str] = {}  # template_hash -> skill_name

        # Estadísticas
        self._n_classifications = 0
        self._n_accepted = 0
        self._n_fallback = 0

        logger.info(
            f"SemanticSkillRouter inicializado: "
            f"{sum(len(v) for v in self.templates.values())} templates, "
            f"{len(self.templates)} skills, threshold={self.threshold}"
        )

    # ── Inicialización de embeddings ──────────────────────────────────────

    def _compute_template_hash(self, text: str) -> str:
        """Hash MD5 de un template para usar como key en cache."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _get_or_compute_template_embedding(self, template: str) -> Optional[np.ndarray]:
        """
        Obtiene embedding de un template, calculándolo si no está en cache.

        Args:
            template: Texto del template

        Returns:
            Embedding como np.ndarray o None si hay error
        """
        template_hash = self._compute_template_hash(template)

        if template_hash in self._template_embeddings:
            return self._template_embeddings[template_hash]

        try:
            # Los templates se embeddean como 'passage' (son documentos de referencia)
            embedding_bytes = RAGService.generate_embedding(
                template, use_cache=True, mode='passage'
            )
            if embedding_bytes:
                embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                # Normalizar L2 para usar inner product (equivalente a coseno)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                self._template_embeddings[template_hash] = embedding
                return embedding
        except Exception as e:
            logger.error(f"Error al generar embedding para template: {e}")

        return None

    def precompute_all_embeddings(self) -> int:
        """
        Pre-calcula todos los embeddings de templates.
        Se llama al iniciar la aplicación (apps.py).

        Returns:
            Número de templates embeddeados exitosamente
        """
        count = 0
        total = sum(len(v) for v in self.templates.values())

        for skill_name, templates in self.templates.items():
            for template in templates:
                self._template_skill_map[
                    self._compute_template_hash(template)
                ] = skill_name
                embedding = self._get_or_compute_template_embedding(template)
                if embedding is not None:
                    count += 1

        logger.info(
            f"Pre-calculados {count}/{total} embeddings de templates "
            f"para {len(self.templates)} skills"
        )
        return count

    # ── Clasificación ─────────────────────────────────────────────────────

    def classify(self, message: str) -> RoutingResult:
        """
        Clasifica un mensaje de usuario contra templates de skills.

        Estrategia:
        1. Generar embedding del mensaje (mode='query')
        2. Calcular similitud coseno contra todos los templates cacheados
        3. Tomar el mejor score
        4. Si supera threshold, retornar skill
        5. Si no, retornar None (RAG puro)

        Args:
            message: Mensaje del usuario en lenguaje natural

        Returns:
            RoutingResult con la skill detectada (o None) y métricas
        """
        import time
        start = time.time()

        self._n_classifications += 1

        if not message or not message.strip():
            return RoutingResult(
                skill_name=None, score=0.0, threshold=self.threshold,
                accepted=False, matched_template='',
                n_templates_evaluated=0, latency_ms=0.0, fallback_used=False,
            )

        # ── 1. Generar embedding del mensaje ──
        query_embedding_bytes = RAGService.generate_embedding(
            message, use_cache=True, mode='query'
        )

        if not query_embedding_bytes:
            # Fallback a keyword matching si no podemos generar embedding
            logger.warning(
                f"No se pudo generar embedding para mensaje. "
                f"Usando fallback keyword. message='{message[:80]}'"
            )
            return self._keyword_fallback(message, start)

        # Normalizar query embedding
        query_embedding = np.frombuffer(query_embedding_bytes, dtype=np.float32)
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm
        else:
            return self._keyword_fallback(message, start)

        # ── 2. Calcular similitud coseno contra todos los templates ──
        best_score = 0.0
        best_skill = None
        best_template = ''
        n_evaluated = 0

        for template_hash, template_embedding in self._template_embeddings.items():
            n_evaluated += 1
            # Inner product = coseno con vectores normalizados
            score = float(np.dot(query_embedding, template_embedding))

            if score > best_score:
                best_score = score
                best_skill = self._template_skill_map.get(template_hash)
                # Recuperar texto del template (búsqueda inversa)
                for skill_name, templates in self.templates.items():
                    for t in templates:
                        if self._compute_template_hash(t) == template_hash:
                            best_template = t
                            break

        # ── 3. Evaluar contra threshold ──
        # Skills con prefijo '_' son de sistema (saludos, general) → no activan skill
        is_system_skill = best_skill and best_skill.startswith('_')
        accepted = best_score >= self.threshold and not is_system_skill
        elapsed = (time.time() - start) * 1000  # ms

        result = RoutingResult(
            skill_name=best_skill if accepted else None,
            score=best_score,
            threshold=self.threshold,
            accepted=accepted,
            matched_template=best_template,
            n_templates_evaluated=n_evaluated,
            latency_ms=elapsed,
            fallback_used=False,
        )

        if accepted:
            self._n_accepted += 1
            logger.info(
                f"[SemanticRouter] Skill detectada: '{best_skill}' "
                f"(score: {best_score:.4f}, threshold: {self.threshold}, "
                f"latency: {elapsed:.1f}ms)"
            )
        else:
            logger.debug(
                f"[SemanticRouter] Sin skill (score máximo: {best_score:.4f} < "
                f"threshold: {self.threshold}, latency: {elapsed:.1f}ms)"
            )

        return result

    # ── Fallback a keywords ──────────────────────────────────────────────

    def _keyword_fallback(self, message: str, start: float) -> RoutingResult:
        """
        Fallback a keyword matching cuando no hay embedding disponible.

        Útil como respaldo graceful cuando el modelo de embeddings
        no está disponible temporalmente.
        """
        import time
        self._n_fallback += 1

        message_lower = message.lower().strip()

        # Keywords básicas por skill
        keywords: Dict[str, List[str]] = {
            'busqueda_propiedades': [
                'propiedad', 'departamento', 'casa', 'terreno', 'lote',
                'alquiler', 'venta', 'busco', 'quiero', 'necesito',
                'construir', 'inmueble', 'depa',
            ],
            'analizar_mercado': [
                'mercado', 'tendencia', 'precio promedio', 'plusvalía',
                'comparativa', 'análisis', 'inversión',
            ],
        }

        best_score = 0.0
        best_skill = None
        matched_keyword = ''

        for skill_name, skill_keywords in keywords.items():
            for kw in skill_keywords:
                if kw in message_lower:
                    score = len(kw) / len(message_lower) if message_lower else 0
                    # Bonus si la keyword está al inicio
                    if message_lower.startswith(kw):
                        score *= 1.5
                    if score > best_score:
                        best_score = min(score, 0.5)  # Cap a 0.5
                        best_skill = skill_name
                        matched_keyword = kw

        accepted = best_score >= self.threshold
        elapsed = (time.time() - start) * 1000

        logger.warning(
            f"[SemanticRouter] Fallback keyword usado para: '{message[:80]}' "
            f"(score: {best_score:.4f}, skill: {best_skill}, "
            f"keyword: '{matched_keyword}')"
        )

        return RoutingResult(
            skill_name=best_skill if accepted else None,
            score=best_score,
            threshold=self.threshold,
            accepted=accepted,
            matched_template=f"[keyword] {matched_keyword}",
            n_templates_evaluated=sum(len(v) for v in keywords.values()),
            latency_ms=elapsed,
            fallback_used=True,
        )

    # ── Propiedades ──────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        """Estadísticas del router."""
        return {
            'total_classifications': self._n_classifications,
            'accepted': self._n_accepted,
            'fallback_used': self._n_fallback,
            'acceptance_rate': round(
                self._n_accepted / self._n_classifications * 100, 1
            ) if self._n_classifications > 0 else 0,
            'templates_cached': len(self._template_embeddings),
            'total_templates': sum(len(v) for v in self.templates.values()),
            'n_skills': len(self.templates),
            'threshold': self.threshold,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton global
# ═══════════════════════════════════════════════════════════════════════════════

_router_instance: Optional[SemanticSkillRouter] = None


def get_router(threshold: Optional[float] = None) -> SemanticSkillRouter:
    """
    Obtiene instancia singleton del SemanticSkillRouter.

    Args:
        threshold: Threshold opcional (solo se usa en primera inicialización)

    Returns:
        Instancia de SemanticSkillRouter
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticSkillRouter(threshold=threshold)
    return _router_instance


def precompute_router_embeddings() -> int:
    """
    Pre-calcula todos los embeddings de templates.
    Se llama desde apps.py al iniciar Django.

    Returns:
        Número de templates embeddeados
    """
    router = get_router()
    return router.precompute_all_embeddings()
