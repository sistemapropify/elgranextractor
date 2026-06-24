"""
Rate Limiter — Control de límites por skill y por usuario.

F3-002: Previene abuso y controla costos operativos.
Soporta almacenamiento en Redis (producción) con fallback a DB/cache local.

Límites por defecto (configurables via settings.RATE_LIMITS):
    - busqueda_propiedades: 30/minuto
    - analizar_mercado: 10/minuto
    - LLM (generación): 20/minuto
    - Embeddings: 100/minuto
"""

from __future__ import annotations

import json
import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Rate Limit Configuration
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_RATE_LIMITS: Dict[str, Tuple[int, int]] = {
    # skill_name: (max_requests, window_seconds)
    'busqueda_propiedades': (30, 60),       # 30 por minuto
    'resolver_contexto': (60, 60),          # 60 por minuto
    'analizar_mercado': (10, 60),           # 10 por minuto
    'reporte_precios_zona': (10, 60),       # 10 por minuto
    'matching_oferta_demanda': (10, 60),    # 10 por minuto
    'llm_generacion': (20, 60),             # 20 por minuto (generación DeepSeek)
    'embedding': (100, 60),                 # 100 por minuto
    'default': (60, 60),                    # 60 por minuto para skills sin config
}

# Límites globales por usuario (independiente de la skill)
GLOBAL_USER_LIMITS: Tuple[int, int] = (200, 60)  # 200 requests totales por minuto


def get_rate_limits() -> Dict[str, Tuple[int, int]]:
    """Obtiene límites desde settings, con fallback a defaults."""
    return getattr(settings, 'RATE_LIMITS', DEFAULT_RATE_LIMITS)


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimitResult
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RateLimitResult:
    """Resultado de una verificación de rate limit."""
    allowed: bool
    remaining: int
    reset_after: int  # segundos hasta que se resetee
    limit: int
    window: int
    retry_after: int = 0  # segundos para esperar si está bloqueado


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimiter
# ═══════════════════════════════════════════════════════════════════════════════


class RateLimiter:
    """
    Rate limiter por skill y usuario.
    
    Usa Django cache framework (Redis en producción, local en desarrollo).
    Los contadores se almacenan como: "ratelimit:{skill}:{user_id}:{window_key}"
    
    Uso:
        limiter = RateLimiter()
        result = limiter.check('busqueda_propiedades', 'user-123')
        if result.allowed:
            limiter.increment('busqueda_propiedades', 'user-123')
            # ejecutar skill
        else:
            # devolver 429 Too Many Requests
    """

    def __init__(self):
        self.limits = get_rate_limits()
        self.cache_prefix = 'ratelimit'

    def _get_cache_key(self, skill: str, user_id: str, window_start: int) -> str:
        """Genera key única para el contador."""
        return f"{self.cache_prefix}:{skill}:{user_id}:{window_start}"

    def _get_window_start(self, window_seconds: int) -> int:
        """Calcula el inicio de la ventana actual."""
        now = int(time.time())
        return now - (now % window_seconds)

    def check(self, skill: str, user_id: str) -> RateLimitResult:
        """
        Verifica si una request está dentro del límite.
        
        Args:
            skill: Nombre de la skill o 'llm_generacion', 'embedding'
            user_id: ID del usuario
            
        Returns:
            RateLimitResult con allowed, remaining, reset_after
        """
        limits = self.limits.get(skill, self.limits['default'])
        max_requests, window = limits
        
        window_start = self._get_window_start(window)
        cache_key = self._get_cache_key(skill, user_id, window_start)
        
        # Obtener contador actual
        current = cache.get(cache_key, 0)
        remaining = max(0, max_requests - current)
        reset_after = window - (int(time.time()) - window_start)
        
        allowed = current < max_requests
        
        # También verificar límite global
        if allowed:
            global_max, global_window = GLOBAL_USER_LIMITS
            global_key = f"{self.cache_prefix}:global:{user_id}:{self._get_window_start(global_window)}"
            global_current = cache.get(global_key, 0)
            allowed = global_current < global_max
        
        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_after=reset_after,
            limit=max_requests,
            window=window,
            retry_after=reset_after if not allowed else 0,
        )

    def increment(self, skill: str, user_id: str) -> int:
        """
        Incrementa el contador para una skill/usuario.
        
        Args:
            skill: Nombre de la skill
            user_id: ID del usuario
            
        Returns:
            Nuevo valor del contador
        """
        limits = self.limits.get(skill, self.limits['default'])
        max_requests, window = limits
        
        window_start = self._get_window_start(window)
        cache_key = self._get_cache_key(skill, user_id, window_start)
        
        # TTL = ventana completa (para limpieza automática)
        ttl = window * 2
        
        try:
            current = cache.get(cache_key, 0)
            current = cache.incr(cache_key)
        except ValueError:
            # Key no existe, crearla
            cache.set(cache_key, 1, ttl)
            current = 1
        
        # Incrementar contador global
        try:
            global_max, global_window = GLOBAL_USER_LIMITS
            global_key = f"{self.cache_prefix}:global:{user_id}:{self._get_window_start(global_window)}"
            try:
                cache.incr(global_key)
            except ValueError:
                cache.set(global_key, 1, global_window * 2)
        except Exception:
            pass
        
        if current >= max_requests:
            logger.warning(
                f"[F3-002] Rate limit excedido: skill={skill}, "
                f"user={user_id}, count={current}, limit={max_requests}"
            )
        
        return current

    def get_remaining(self, skill: str, user_id: str) -> int:
        """Obtiene requests restantes sin incrementar."""
        result = self.check(skill, user_id)
        return result.remaining

    def reset(self, skill: str, user_id: str):
        """Resetea el contador para una skill/usuario."""
        limits = self.limits.get(skill, self.limits['default'])
        _, window = limits
        window_start = self._get_window_start(window)
        cache_key = self._get_cache_key(skill, user_id, window_start)
        cache.delete(cache_key)
        logger.info(f"[F3-002] Rate limit reseteado: skill={skill}, user={user_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[RateLimiter] = None


def get_limiter() -> RateLimiter:
    """Obtiene instancia singleton del RateLimiter."""
    global _instance
    if _instance is None:
        _instance = RateLimiter()
    return _instance


def check_rate_limit(skill: str, user_id: str) -> RateLimitResult:
    """Función de conveniencia para verificar rate limit."""
    return get_limiter().check(skill, user_id)


def increment_rate_limit(skill: str, user_id: str) -> int:
    """Función de conveniencia para incrementar rate limit."""
    return get_limiter().increment(skill, user_id)
