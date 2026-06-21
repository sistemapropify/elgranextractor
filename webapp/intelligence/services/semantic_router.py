"""
SemanticSkillRouter — Router semántico de skills usando embeddings E5-large.

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


@dataclass
class RoutingResult:
    """Resultado del routing semántico."""
    skill_name: Optional[str]
    score: float
    threshold: float
    accepted: bool
    matched_template: str
    n_templates_evaluated: int
    latency_ms: float
    fallback_used: bool
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_log(self) -> Dict[str, Any]:
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


_DEFAULT_SKILL_TEMPLATES: Dict[str, List[str]] = {
    'busqueda_propiedades': [
        'busco departamento en Cayma',
        'quiero comprar una casa en Yanahuara',
        'necesito un terreno para construir',
        'donde puedo construir un colegio',
        'busco propiedades en Cerro Colorado',
        'alquiler de departamentos en Sachaca',
        'busco terreno para proyecto de vivienda',
        'casa con 3 dormitorios en Cayma',
        'departamentos hasta 200 mil soles',
        'busco propiedad para inversion',
        'terreno industrial en la Joya',
        'muéstrame departamentos en José Luis Bustamante',
    ],
    'resolver_contexto': [
        'muéstrame los que tengan 3 dormitorios',
        'quiero ver más baratos',
        'los que están en la misma zona',
        'solo departamentos',
        'y en Cayma',
        'y en Cerro Colorado',
        'alguna opción con piscina',
        'ordéname por precio',
    ],
    'analizar_mercado': [
        'cómo está el mercado en Cayma',
        'precio promedio de departamentos en Yanahuara',
        'tendencias de precios en Cerro Colorado',
        'comparativa de zonas residenciales',
        'cuál es el mejor distrito para invertir',
    ],
}

SKILL_TEMPLATES = getattr(settings, 'SKILL_TEMPLATES', _DEFAULT_SKILL_TEMPLATES)


class SemanticSkillRouter:
    """Router semántico de skills usando embeddings E5-large."""

    DEFAULT_THRESHOLD = 0.45

    def __init__(self, threshold: Optional[float] = None):
        self.threshold = threshold or float(
            getattr(settings, 'SKILL_ROUTER_THRESHOLD', self.DEFAULT_THRESHOLD)
        )
        self.templates = SKILL_TEMPLATES
        self._template_embeddings: Dict[str, np.ndarray] = {}
        self._template_skill_map: Dict[str, str] = {}
        self._n_classifications = 0
        self._n_accepted = 0
        self._n_fallback = 0
        logger.info(
            f"SemanticSkillRouter: {sum(len(v) for v in self.templates.values())} templates, "
            f"{len(self.templates)} skills, threshold={self.threshold}"
        )

    def _compute_template_hash(self, text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _get_or_compute_template_embedding(self, template: str) -> Optional[np.ndarray]:
        template_hash = self._compute_template_hash(template)
        if template_hash in self._template_embeddings:
            return self._template_embeddings[template_hash]
        try:
            embedding_bytes = RAGService.generate_embedding(
                template, use_cache=True, mode='passage'
            )
            if embedding_bytes:
                embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                self._template_embeddings[template_hash] = embedding
                return embedding
        except Exception as e:
            logger.error(f"Error al generar embedding para template: {e}")
        return None

    def precompute_all_embeddings(self) -> int:
        count = 0
        for skill_name, templates in self.templates.items():
            for template in templates:
                self._template_skill_map[self._compute_template_hash(template)] = skill_name
                if self._get_or_compute_template_embedding(template) is not None:
                    count += 1
        logger.info(f"Pre-calculados {count} embeddings de templates")
        return count

    def classify(self, message: str) -> RoutingResult:
        import time
        start = time.time()
        self._n_classifications += 1

        if not message or not message.strip():
            return RoutingResult(
                skill_name=None, score=0.0, threshold=self.threshold,
                accepted=False, matched_template='',
                n_templates_evaluated=0, latency_ms=0.0, fallback_used=False,
            )

        query_embedding_bytes = RAGService.generate_embedding(
            message, use_cache=True, mode='query'
        )

        if not query_embedding_bytes:
            return self._keyword_fallback(message, start)

        query_embedding = np.frombuffer(query_embedding_bytes, dtype=np.float32)
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm
        else:
            return self._keyword_fallback(message, start)

        best_score = 0.0
        best_skill = None
        best_template = ''
        n_evaluated = 0

        for template_hash, template_embedding in self._template_embeddings.items():
            n_evaluated += 1
            score = float(np.dot(query_embedding, template_embedding))
            if score > best_score:
                best_score = score
                best_skill = self._template_skill_map.get(template_hash)
                for skill_name, templates in self.templates.items():
                    for t in templates:
                        if self._compute_template_hash(t) == template_hash:
                            best_template = t
                            break

        accepted = best_score >= self.threshold
        elapsed = (time.time() - start) * 1000

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
                f"[SemanticRouter] Skill: '{best_skill}' "
                f"(score: {best_score:.4f}, threshold: {self.threshold}, "
                f"latency: {elapsed:.1f}ms)"
            )
        return result

    def _keyword_fallback(self, message: str, start: float) -> RoutingResult:
        import time
        self._n_fallback += 1
        message_lower = message.lower().strip()
        keywords: Dict[str, List[str]] = {
            'busqueda_propiedades': [
                'propiedad', 'departamento', 'casa', 'terreno', 'busco',
                'alquiler', 'venta', 'construir', 'inmueble',
            ],
            'analizar_mercado': [
                'mercado', 'tendencia', 'precio promedio', 'plusvalía',
            ],
        }
        best_score = 0.0
        best_skill = None
        for skill_name, skill_keywords in keywords.items():
            for kw in skill_keywords:
                if kw in message_lower:
                    score = len(kw) / len(message_lower) if message_lower else 0
                    if message_lower.startswith(kw):
                        score *= 1.5
                    if score > best_score:
                        best_score = min(score, 0.5)
                        best_skill = skill_name
        accepted = best_score >= self.threshold
        elapsed = (time.time() - start) * 1000
        return RoutingResult(
            skill_name=best_skill if accepted else None,
            score=best_score,
            threshold=self.threshold,
            accepted=accepted,
            matched_template=f"[keyword]",
            n_templates_evaluated=sum(len(v) for v in keywords.values()),
            latency_ms=elapsed,
            fallback_used=True,
        )

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            'total_classifications': self._n_classifications,
            'accepted': self._n_accepted,
            'fallback_used': self._n_fallback,
            'templates_cached': len(self._template_embeddings),
            'threshold': self.threshold,
        }


_router_instance: Optional[SemanticSkillRouter] = None


def get_router(threshold: Optional[float] = None) -> SemanticSkillRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticSkillRouter(threshold=threshold)
    return _router_instance


def precompute_router_embeddings() -> int:
    router = get_router()
    return router.precompute_all_embeddings()
