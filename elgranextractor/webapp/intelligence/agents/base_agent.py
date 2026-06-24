"""
BaseAgent — Interfaz común para todos los agentes PIL.

F4-001: Define el contrato que todos los agentes deben implementar.
Cada agente tiene run(), validate() y get_metrics().
"""

from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentMetrics:
    """Métricas de ejecución de un agente."""
    def __init__(self):
        self.executions: int = 0
        self.errors: int = 0
        self.total_duration_ms: float = 0.0
        self.last_execution: Optional[float] = None

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / max(self.executions, 1)

    @property
    def error_rate(self) -> float:
        return self.errors / max(self.executions, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'executions': self.executions,
            'errors': self.errors,
            'avg_duration_ms': round(self.avg_duration_ms, 2),
            'error_rate': round(self.error_rate, 4),
        }


class BaseAgent(ABC):
    """
    Clase base para todos los agentes PIL.
    
    Cada agente:
    - Recibe el PILAgentState completo
    - Modifica solo las keys de su responsabilidad
    - Retorna el estado actualizado
    """

    def __init__(self):
        self.metrics = AgentMetrics()
        self.name = self.__class__.__name__

    @abstractmethod
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta la lógica del agente.
        
        Args:
            state: PILAgentState actual
            
        Returns:
            PILAgentState actualizado
        """
        pass

    def validate(self, state: Dict[str, Any]) -> bool:
        """
        Valida que el agente tenga los inputs necesarios.
        
        Args:
            state: PILAgentState actual
            
        Returns:
            True si el agente puede ejecutarse
        """
        return True

    def get_metrics(self) -> AgentMetrics:
        """Retorna métricas de rendimiento del agente."""
        return self.metrics

    def _track_execution(self, func):
        """Decorator para tracking de ejecución."""
        def wrapper(state):
            start = time.time()
            self.metrics.executions += 1
            try:
                result = func(state)
                elapsed = (time.time() - start) * 1000
                self.metrics.total_duration_ms += elapsed
                self.metrics.last_execution = time.time()
                return result
            except Exception as e:
                self.metrics.errors += 1
                logger.error(f"[F4-001] {self.name} error: {e}")
                raise
        return wrapper
