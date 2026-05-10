"""
Sistema de métricas y logging estructurado para el sistema de inteligencia.

Proporciona:
- MetricsService: context manager que mide latencia y registra métricas
- StructuredLogger: logging con formato JSON consistente
- Elimina la repetición de `import logging` y `logger = logging.getLogger(__name__)`
"""
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone


# ── Logger base del módulo ─────────────────────────────────────────────────
logger = logging.getLogger(__name__)


class StructuredLogger:
    """
    Logger con formato estructurado para facilitar el análisis.

    Todos los logs incluyen: timestamp, level, module, message,
    y campos adicionales según el contexto.
    """

    @staticmethod
    def _base_extra(extra: Optional[Dict] = None) -> Dict:
        """Construye el diccionario base de metadata."""
        base = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'service': 'intelligence',
        }
        if extra:
            base.update(extra)
        return base

    @classmethod
    def info(cls, message: str, **kwargs):
        """Log informativo con metadata estructurada."""
        logger.info(f"[INTEL] {message}", extra=cls._base_extra(kwargs))

    @classmethod
    def debug(cls, message: str, **kwargs):
        """Log de debug con metadata estructurada."""
        logger.debug(f"[INTEL] {message}", extra=cls._base_extra(kwargs))

    @classmethod
    def warning(cls, message: str, **kwargs):
        """Log de advertencia con metadata estructurada."""
        logger.warning(f"[INTEL] {message}", extra=cls._base_extra(kwargs))

    @classmethod
    def error(cls, message: str, exc_info: bool = False, **kwargs):
        """Log de error con metadata estructurada."""
        logger.error(
            f"[INTEL] {message}",
            exc_info=exc_info,
            extra=cls._base_extra(kwargs),
        )

    @classmethod
    def metric(cls, name: str, value: float, tags: Optional[Dict] = None):
        """
        Registra una métrica numérica.

        Args:
            name: Nombre de la métrica (ej: 'rag.search.latency').
            value: Valor numérico (ej: 0.342 segundos).
            tags: Etiquetas adicionales (ej: {'collection': 'propifai'}).
        """
        extra = cls._base_extra({
            'metric': name,
            'value': value,
            'metric_type': 'gauge',
        })
        if tags:
            extra.update(tags)
        logger.info(f"[METRIC] {name}={value:.4f}", extra=extra)


class MetricsService:
    """
    Servicio de métricas con context manager para medir latencia.

    Uso:
        with MetricsService.timer('rag.search', user_id=user.id) as ctx:
            results = RAGService.search(...)
            ctx.set_tags(collection='propifai', results=len(results))

        # ctx.latency_ms contiene el tiempo transcurrido
        # ctx.metric_name contiene 'rag.search'
    """

    def __init__(self, metric_name: str, **tags):
        self.metric_name = metric_name
        self.tags = tags
        self.start_time: Optional[float] = None
        self.latency_ms: float = 0.0
        self.trace_id: str = uuid.uuid4().hex[:12]

    def set_tags(self, **tags):
        """Agrega etiquetas adicionales a la métrica."""
        self.tags.update(tags)

    def _record(self):
        """Registra la métrica en el log."""
        StructuredLogger.metric(
            self.metric_name,
            self.latency_ms,
            tags={**self.tags, 'trace_id': self.trace_id},
        )

    @classmethod
    @contextmanager
    def timer(cls, metric_name: str, **tags):
        """
        Context manager que mide el tiempo de ejecución.

        Args:
            metric_name: Nombre de la métrica (ej: 'chat.process').
            **tags: Etiquetas iniciales.

        Yields:
            MetricsService instance con .latency_ms al salir.
        """
        ctx = cls(metric_name, **tags)
        ctx.start_time = time.time()
        try:
            yield ctx
        finally:
            ctx.latency_ms = (time.time() - ctx.start_time) * 1000
            ctx._record()

    @classmethod
    def time_function(cls, metric_name: str):
        """
        Decorador para medir tiempo de ejecución de una función.

        Uso:
            @MetricsService.time_function('rag.search')
            def search(query): ...
        """
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                with cls.timer(metric_name) as ctx:
                    return func(*args, **kwargs)
            return wrapper
        return decorator


# ── Singleton de logger estructurado ───────────────────────────────────────
log = StructuredLogger()
