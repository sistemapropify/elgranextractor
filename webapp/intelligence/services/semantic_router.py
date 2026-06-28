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
    user_context: Optional[Dict[str, Any]] = None  # Contexto del usuario (rol, level, domains)
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
    # ── NUEVAS SKILLS DEL SISTEMA EXPERTO MULTI-ROL ──
    'metricas_globales': [
        'cómo van las ventas este mes',
        'cuántas propiedades se vendieron este mes',
        'dame los KPIs del mes',
        'resumen ejecutivo de ventas',
        'cuál es el rendimiento del mes',
        'métricas globales del sistema',
        'cómo le está yendo a la empresa',
        'reporte de ventas semanal',
        'cuántos matches se generaron hoy',
        'estadísticas generales de la plataforma',
    ],
    'reporte_ventas': [
        'genera un reporte de ventas',
        'cuánto se ha vendido esta semana',
        'ventas del último trimestre',
        'comparativa de ventas mes a mes',
        'reporte detallado de transacciones',
        'cuántas propiedades se vendieron en junio',
        'ventas por distrito este mes',
        'evolución de ventas en el año',
    ],
    'analisis_rendimiento': [
        'cómo está el rendimiento de la plataforma',
        'análisis de rendimiento de agentes',
        'qué agente vendió más este mes',
        'ranking de agentes por ventas',
        'rendimiento comparativo entre agentes',
        'quién está generando más matches',
        'top agentes del mes',
    ],
    'consultar_normativa': [
        'qué dice la ley sobre alquileres',
        'normativa de zonificación comercial',
        'requisitos legales para alquilar',
        'cuál es la ley de inquilinato en Perú',
        'normas de construcción en Arequipa',
        'qué dice el reglamento de propiedad horizontal',
        'aspectos legales de un contrato de alquiler',
        'consulta la normativa peruana de bienes raíces',
        'derechos del inquilino según la ley',
        'marco legal para compra venta de inmuebles',
    ],
    'revisar_contrato': [
        'revisa este contrato de alquiler',
        'analiza las cláusulas de este contrato',
        'el contrato tiene alguna cláusula abusiva',
        'revisión legal de contrato de compraventa',
        'verifica este acuerdo de arrendamiento',
        'qué dice este contrato en la cláusula de penalidades',
        'revisa aspectos legales de este documento',
    ],
    'aspectos_legales': [
        'qué aspectos legales debo considerar',
        'consejos legales para comprar propiedad',
        'qué papeles necesita una propiedad en venta',
        'documentación necesaria para transferir',
        'aspectos notariales de la compra',
        'qué impuestos se pagan al comprar inmueble',
        'costos legales de una transacción inmobiliaria',
    ],
    'campanas_activas': [
        'qué campañas de Facebook están activas',
        'cómo están rindiendo los anuncios',
        'muéstrame las campañas de marketing activas',
        'estado de las campañas publicitarias',
        'campañas de Meta Ads en ejecución',
        'qué anuncios están corriendo ahora',
        'inversión actual en campañas digitales',
    ],
    'leads_generados': [
        'cuántos leads generamos este mes',
        'leads de las campañas de Facebook',
        'qué campaña está generando más leads',
        'calidad de los leads de marketing',
        'conversión de leads a clientes',
        'costo por lead en las campañas activas',
        'leads por distrito y campaña',
    ],
    'metricas_marketing': [
        'métricas de marketing del mes',
        'rendimiento de las campañas publicitarias',
        'ROI de las campañas de Meta Ads',
        'estadísticas de Facebook Ads',
        'alcance e impresiones de los anuncios',
        'clic y conversiones de campañas',
        'costo por resultado en publicidad',
    ],
    'mis_propiedades': [
        'qué propiedades tengo asignadas',
        'muéstrame mis propiedades',
        'cuáles son mis propiedades en cartera',
        'lista de mis propiedades activas',
        'propiedades que tengo a mi cargo',
        'ver mi portafolio de propiedades',
        'mis inmuebles publicados',
    ],
    'mis_requerimientos': [
        'qué requerimientos tengo pendientes',
        'muéstrame mis clientes buscando propiedad',
        'requerimientos que he registrado',
        'mis leads activos',
        'clientes que me han contactado',
        'lista de mis requerimientos',
    ],
    'mis_matches': [
        'qué matches tengo pendientes',
        'muéstrame mis matches',
        'cruza mis propiedades con requerimientos',
        'tengo matches nuevos',
        'propiedades que match con mis clientes',
        'clientes compatibles con mis propiedades',
        'ver mis matches del día',
    ],
    'portafolio_agente': [
        'qué propiedades tiene Valery',
        'portafolio del agente Juan Pérez',
        'cuántas propiedades tiene cada agente',
        'propiedades a cargo de María',
        'portafolio de propiedades por agente',
        'qué agentes tienen más propiedades',
        'distribución de propiedades entre agentes',
    ],
    'analizar_oportunidad': [
        'analiza esta propiedad como inversión',
        'es buena oportunidad esta propiedad',
        'qué rentabilidad tiene esta propiedad',
        'análisis de inversión para este inmueble',
        'conviene comprar esta propiedad',
        'potencial de plusvalía de esta zona',
        'evaluación de oportunidad inmobiliaria',
    ],
    'equipo_a_cargo': [
        'cómo está mi equipo',
        'qué agentes tengo a cargo',
        'rendimiento de mi equipo',
        'mis agentes están cumpliendo metas',
        'estado del equipo de ventas',
        'reporte de mi equipo de agentes',
    ],
    'desempeño_agentes': [
        'cómo están rindiendo los agentes',
        'desempeño del equipo comercial',
        'qué agente necesita apoyo',
        'evaluación de rendimiento de agentes',
        'métricas de desempeño del equipo',
        'agentes con bajo rendimiento este mes',
        'top y bottom agentes del período',
    ],
    'reporte_equipo': [
        'genera reporte del equipo',
        'reporte de gestión de agentes',
        'informe mensual del equipo',
        'resumen de actividad del equipo',
        'reporte consolidado de agentes',
        'estadísticas del equipo de ventas',
    ],
    'logs_sistema': [
        'muéstrame los logs del sistema',
        'logs de actividad reciente',
        'historial de eventos del sistema',
        'bitácora de operaciones',
        'registro de accesos al sistema',
        'logs de ejecución de skills',
        'actividad del sistema de inteligencia',
    ],
    'errores_recientes': [
        'hubo errores en el sistema',
        'errores recientes en la plataforma',
        'fallos en ejecución de skills',
        'errores de conexión con DeepSeek',
        'excepciones en el sistema',
        'problemas técnicos reportados',
        'tracebacks y errores de hoy',
    ],
    'estado_servicios': [
        'cómo está funcionando el sistema',
        'estado de los servicios',
        'servicios activos y su estado',
        'health check del sistema',
        'qué servicios están caídos',
        'monitoreo de servicios en tiempo real',
        'estado de celery y redis',
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
        Pre-calcula todos los embeddings de templates usando batch encoding.

        SPEC-014: Reemplaza el loop secuencial (78 llamadas individuales)
        por UNA sola llamada batch a RAGService.generate_embeddings_batch().
        Reduce de ~4s a ~300ms.

        Returns:
            Número de templates embeddeados exitosamente
        """
        import time
        start = time.time()

        total = sum(len(v) for v in self.templates.values())

        # Construir listas paralelas para batch encoding
        all_templates: List[str] = []
        all_hashes: List[str] = []
        all_skill_names: List[str] = []

        for skill_name, templates in self.templates.items():
            for template in templates:
                template_hash = self._compute_template_hash(template)
                self._template_skill_map[template_hash] = skill_name
                all_templates.append(template)
                all_hashes.append(template_hash)
                all_skill_names.append(skill_name)

        # Batch encoding: UNA llamada en lugar de N llamadas individuales
        embeddings = RAGService.generate_embeddings_batch(
            all_templates, mode='passage', batch_size=32
        )

        count = 0
        for i, emb in enumerate(embeddings):
            if emb is not None:
                self._template_embeddings[all_hashes[i]] = emb
                count += 1
            else:
                # Fallback individual para templates que fallaron
                embedding = self._get_or_compute_template_embedding(all_templates[i])
                if embedding is not None:
                    self._template_embeddings[all_hashes[i]] = embedding
                    count += 1

        elapsed = (time.time() - start) * 1000
        logger.info(
            f"Pre-calculados {count}/{total} embeddings de templates "
            f"para {len(self.templates)} skills "
            f"en {elapsed:.0f}ms (batch encoding)"
        )
        return count

    # ── Clasificación ─────────────────────────────────────────────────────

    def classify(self, message: str, user_context: Optional[Dict[str, Any]] = None) -> RoutingResult:
        """
        Clasifica un mensaje de usuario contra templates de skills.

        Estrategia (SPEC v2.0 - Sistema Experto Multi-Rol):
        1. Generar embedding del mensaje (mode='query')
        2. Calcular similitud coseno contra TODOS los templates (sin filtrar por rol)
        3. Tomar el mejor score
        4. Si supera threshold, retornar skill
        5. Si no, retornar None (RAG puro)
        6. user_context se incluye en el resultado para que el SkillOrchestrator
           verifique permisos después (no se filtra aquí)

        Args:
            message: Mensaje del usuario en lenguaje natural
            user_context: Dict opcional con datos del usuario (rol, level, domains).
                          NO se usa para filtrar, solo se propaga al resultado.

        Returns:
            RoutingResult con la skill detectada (o None), métricas y user_context
        """
        import time
        start = time.time()

        self._n_classifications += 1

        if not message or not message.strip():
            return RoutingResult(
                skill_name=None, score=0.0, threshold=self.threshold,
                accepted=False, matched_template='',
                n_templates_evaluated=0, latency_ms=0.0, fallback_used=False,
                user_context=user_context,
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
            return self._keyword_fallback(message, start, user_context)

        # Normalizar query embedding
        query_embedding = np.frombuffer(query_embedding_bytes, dtype=np.float32)
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm
        else:
            return self._keyword_fallback(message, start, user_context)

        # ── 2. Calcular similitud coseno contra todos los templates ──
        # SPEC v2.0: NO filtrar por rol. Usar TODOS los templates.
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
            user_context=user_context,
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

    def _keyword_fallback(self, message: str, start: float,
                          user_context: Optional[Dict[str, Any]] = None) -> RoutingResult:
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
            user_context=user_context,
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
    
        # ── Multi-Skill Orchestration (SPEC v2.1) ────────────────────────────
    
        # Conectores que indican consulta compuesta
        _MULTI_CONNECTORS = [
            ' y ', ' además ', ' también ', ' y además ', ' y luego ',
            ' y también ', ' , ', ';',
        ]
    
        # Verbos que indican acción independiente
        _MULTI_VERBS = [
            'muestra', 'muestrame', 'busca', 'analiza', 'compara',
            'listame', 'dime', 'quiero ver', 'necesito',
        ]
    
        def _es_consulta_compuesta(self, query: str) -> bool:
            """Detecta si una consulta requiere múltiples skills."""
            if not query:
                return False
            q = query.lower().strip()
    
            # 1. Detectar conectores compuestos
            for conn in self._MULTI_CONNECTORS:
                if conn in q:
                    return True
    
            # 2. Detectar múltiples verbos de acción
            verbos_encontrados = 0
            for v in self._MULTI_VERBS:
                if v in q:
                    verbos_encontrados += 1
                    if verbos_encontrados >= 2:
                        return True
    
            return False
    
        def _descomponer_consulta(self, query: str) -> List[str]:
            """
            Descompone una consulta compuesta en sub-consultas usando heurísticas.
    
            OPCIÓN A (por defecto): Reglas heurísticas rápidas
            OPCIÓN B: Fallback a LLM si la heurística no es suficiente
            """
            q = query.strip()
    
            # Intentar dividir por conectores principales
            for conn in [' y además ', ' y también ', ' y luego ', ' y ']:
                if conn in q.lower():
                    parts = q.lower().split(conn, 1)  # Solo primera división
                    if len(parts) == 2 and len(parts[0]) > 5 and len(parts[1]) > 5:
                        return [parts[0].strip(), parts[1].strip()]
    
            # Dividir por punto y coma
            if ';' in q:
                parts = [p.strip() for p in q.split(';') if len(p.strip()) > 5]
                if len(parts) >= 2:
                    return parts
    
            # Dividir por coma si hay verbos múltiples
            if ',' in q:
                verbos_en_primera = sum(1 for v in self._MULTI_VERBS if v in q.split(',')[0])
                if verbos_en_primera >= 1:
                    parts = [p.strip() for p in q.split(',') if len(p.strip()) > 5]
                    if len(parts) >= 2:
                        return parts
    
            # No se pudo descomponer — retornar la consulta completa
            return [q]
    
        def classify_multi(
            self,
            message: str,
            user_context: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """
            Clasifica una consulta que puede requerir múltiples skills.
    
            SPEC v2.1 — Multi-Skill Orchestration:
            Detecta consultas compuestas, las descompone en sub-consultas,
            clasifica cada una independientemente, y construye un plan
            de ejecución con dependencias.
    
            Args:
                message: Mensaje del usuario en lenguaje natural
                user_context: Contexto del usuario (rol, level, domains)
    
            Returns:
                Dict con plan de ejecución:
                {
                    'is_multi': bool,
                    'execution_mode': 'sequential' | 'parallel',
                    'skills': [
                        {
                            'skill': str,
                            'order': int,
                            'params': dict,
                            'depends_on': Optional[str],
                            'sub_query': str,
                            'score': float,
                        }
                    ],
                    'original_query': str
                }
            """
            # Paso 1: Detectar si es consulta compuesta
            if not self._es_consulta_compuesta(message):
                # Consulta simple: clasificar normalmente
                result = self.classify(message, user_context)
                return {
                    'is_multi': False,
                    'execution_mode': 'single',
                    'skills': [{
                        'skill': result.skill_name,
                        'order': 1,
                        'params': {},
                        'depends_on': None,
                        'sub_query': message,
                        'score': result.score,
                    }] if result.accepted else [],
                    'original_query': message,
                }
    
            # Paso 2: Descomponer en sub-consultas
            sub_queries = self._descomponer_consulta(message)
    
            # Paso 3: Clasificar cada sub-consulta
            skills_plan = []
            for i, sub_q in enumerate(sub_queries):
                result = self.classify(sub_q, user_context)
                if result.accepted and result.skill_name:
                    skills_plan.append({
                        'skill': result.skill_name,
                        'order': i + 1,
                        'params': {'semantic_query': sub_q},
                        'depends_on': None,  # Se determina después
                        'sub_query': sub_q,
                        'score': result.score,
                    })
    
            # Paso 4: Determinar modo de ejecución y dependencias
            if len(skills_plan) <= 1:
                # Solo una skill válida
                return {
                    'is_multi': False,
                    'execution_mode': 'single',
                    'skills': skills_plan,
                    'original_query': message,
                }
    
            # Detectar si hay dependencias entre skills
            # Regla: si hay skills del mismo tipo (busqueda+analisis) → secuencial
            categories_used = set()
            for s in skills_plan:
                skill_obj = None
                try:
                    from .registry import SkillRegistry
                    skill_obj = SkillRegistry().get_by_name(s['skill'])
                except Exception:
                    pass
                cat = getattr(skill_obj, 'category', 'custom') if skill_obj else 'custom'
                categories_used.add(cat)
    
            # Si todas son reportes → paralelo
            # Si hay mix de búsqueda + análisis → secuencial
            has_search = any(
                getattr(SkillRegistry().get_by_name(s['skill']), 'category', '') == 'busqueda'
                for s in skills_plan
            ) if skills_plan else False
    
            has_analysis = any(
                getattr(SkillRegistry().get_by_name(s['skill']), 'category', '') == 'reporte'
                for s in skills_plan
            ) if skills_plan else False
    
            if has_search and has_analysis:
                # Modo secuencial: búsqueda genera datos para análisis
                execution_mode = 'sequential'
                # El primer skill de búsqueda no depende de nadie
                # Los skills de análisis dependen del último de búsqueda
                last_search = None
                for s in skills_plan:
                    skill_obj = SkillRegistry().get_by_name(s['skill'])
                    cat = getattr(skill_obj, 'category', '') if skill_obj else ''
                    if cat == 'busqueda':
                        last_search = s['skill']
                    elif cat == 'reporte' and last_search:
                        s['depends_on'] = last_search
            else:
                # Skills independientes → paralelo
                execution_mode = 'parallel'
    
            logger.info(
                f"[SemanticRouter] Multi-skill detectado: "
                f"{len(skills_plan)} skills, modo={execution_mode}, "
                f"skills={[s['skill'] for s in skills_plan]}"
            )
    
            return {
                'is_multi': True,
                'execution_mode': execution_mode,
                'skills': skills_plan,
                'original_query': message,
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
