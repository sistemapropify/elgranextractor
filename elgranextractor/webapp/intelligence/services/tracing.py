"""
Tracing Service — Observabilidad del sistema PIL.

F3-001: Proporciona tracing estructurado con trace_id correlacionado
a través de todos los componentes: router, RAG, nodos LangGraph, DeepSeek.

Arquitectura:
    TraceContext por request → registra decisiones, documentos, nodos
    → se persiste en BD o se exporta como log estructurado
"""

from __future__ import annotations

import json
import uuid
import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RouterDecisionTrace:
    """Traza de una decisión del router semántico."""
    skill_name: Optional[str]
    score: float
    threshold: float
    accepted: bool
    matched_template: str
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class DocumentTrace:
    """Traza de un documento RAG recuperado."""
    document_id: str
    score: float
    collection: str
    source_id: str
    content_preview: str = ''


@dataclass
class NodeTrace:
    """Traza de un nodo del grafo LangGraph ejecutado."""
    node_name: str
    duration_ms: float
    status: str  # 'success', 'error', 'skipped'
    input_summary: str = ''
    output_summary: str = ''
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class DeepSeekTrace:
    """Traza de una interacción con DeepSeek API."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    model: str = 'deepseek-chat'
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# TraceContext
# ═══════════════════════════════════════════════════════════════════════════════


class TraceContext:
    """
    Contexto de tracing para una request completa.
    
    Almacena todas las trazas de una request y permite exportarlas
    como dict para logging estructurado.
    
    Uso:
        trace = TraceContext(user_id='...', conversation_id='...')
        trace.add_router_decision(skill='busqueda', score=0.85, ...)
        trace.add_document(doc_id='123', score=0.92, collection='props')
        trace.add_node('router', duration=150, status='success')
        trace.log_summary()
    """

    def __init__(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        message: Optional[str] = None,
    ):
        self.trace_id = uuid.uuid4().hex[:12]
        self.start_time = time.time()
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.message = message

        # Listas de trazas
        self.router_decisions: List[RouterDecisionTrace] = []
        self.documents: List[DocumentTrace] = []
        self.nodes: List[NodeTrace] = []
        self.deepseek: Optional[DeepSeekTrace] = None

        # Flags
        self.skill_detectada: Optional[str] = None
        self.total_resultados: int = 0
        self.error: Optional[str] = None

    def add_router_decision(
        self,
        skill_name: Optional[str],
        score: float,
        threshold: float,
        accepted: bool,
        matched_template: str = '',
        latency_ms: float = 0.0,
    ):
        """Registra una decisión del router semántico."""
        self.router_decisions.append(RouterDecisionTrace(
            skill_name=skill_name,
            score=score,
            threshold=threshold,
            accepted=accepted,
            matched_template=matched_template,
            latency_ms=latency_ms,
        ))
        self.skill_detectada = skill_name

    def add_document(
        self,
        document_id: str,
        score: float,
        collection: str,
        source_id: str = '',
        content_preview: str = '',
    ):
        """Registra un documento RAG recuperado."""
        self.documents.append(DocumentTrace(
            document_id=document_id,
            score=score,
            collection=collection,
            source_id=source_id,
            content_preview=content_preview[:100],
        ))

    def add_node(
        self,
        node_name: str,
        duration_ms: float,
        status: str,
        input_summary: str = '',
        output_summary: str = '',
        error: Optional[str] = None,
    ):
        """Registra la ejecución de un nodo del grafo."""
        self.nodes.append(NodeTrace(
            node_name=node_name,
            duration_ms=duration_ms,
            status=status,
            input_summary=input_summary[:200],
            output_summary=output_summary[:200],
            error=error,
        ))

    def set_deepseek(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: float = 0.0,
        model: str = 'deepseek-chat',
        error: Optional[str] = None,
    ):
        """Registra una interacción con DeepSeek."""
        self.deepseek = DeepSeekTrace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            model=model,
            error=error,
        )

    @property
    def duration_ms(self) -> float:
        """Tiempo transcurrido desde la creación."""
        return (time.time() - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Exporta el contexto como dict para logging."""
        return {
            'trace_id': self.trace_id,
            'duration_ms': round(self.duration_ms, 2),
            'user_id': self.user_id,
            'conversation_id': self.conversation_id,
            'message_preview': (self.message or '')[:80],
            'skill_detectada': self.skill_detectada,
            'total_resultados': self.total_resultados,
            'n_router_decisions': len(self.router_decisions),
            'n_documents': len(self.documents),
            'n_nodes': len(self.nodes),
            'router_decisions': [asdict(d) for d in self.router_decisions],
            'documents': [
                {
                    'id': d.document_id,
                    'score': round(d.score, 4),
                    'collection': d.collection,
                }
                for d in self.documents[:10]  # Top 10 docs
            ],
            'nodes': [
                {
                    'name': n.node_name,
                    'duration_ms': round(n.duration_ms, 2),
                    'status': n.status,
                }
                for n in self.nodes
            ],
            'deepseek': asdict(self.deepseek) if self.deepseek else None,
            'error': self.error,
            'timestamp': datetime.utcnow().isoformat(),
        }

    def log_summary(self, level: str = 'INFO'):
        """Loggea un resumen del tracing."""
        log_msg = (
            f"[F3-001] Trace {self.trace_id} | "
            f"duration={self.duration_ms:.0f}ms | "
            f"skill={self.skill_detectada or 'N/A'} | "
            f"docs={len(self.documents)} | "
            f"nodes={len(self.nodes)} | "
            f"deepseek_tokens={self.deepseek.total_tokens if self.deepseek else 'N/A'}"
        )
        getattr(logger, level.lower(), logger.info)(log_msg)


# ═══════════════════════════════════════════════════════════════════════════════
# Context Manager (thread-local)
# ═══════════════════════════════════════════════════════════════════════════════

_trace_context: Optional[TraceContext] = None


def get_current_trace() -> Optional[TraceContext]:
    """Obtiene el contexto de tracing actual (thread-local)."""
    global _trace_context
    return _trace_context


def set_current_trace(trace: Optional[TraceContext]):
    """Establece el contexto de tracing actual."""
    global _trace_context
    _trace_context = trace


def create_trace(
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    message: Optional[str] = None,
) -> TraceContext:
    """Crea un nuevo TraceContext y lo establece como actual."""
    trace = TraceContext(
        user_id=user_id,
        conversation_id=conversation_id,
        message=message,
    )
    set_current_trace(trace)
    return trace


def clear_trace():
    """Limpia el contexto de tracing actual."""
    set_current_trace(None)
