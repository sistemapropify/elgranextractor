"""
Skill Cache.

Sistema de cache inteligente para skills con backend Redis y fallback local.
Optimiza rendimiento y reduce carga en skills costosas.
"""
from __future__ import annotations

import time
import json
import hashlib
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field

redis = None
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@dataclass
class CacheEntry:
    """Entrada de cache con metadata."""
    key: str
    data: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: Optional[int] = None

    def is_expired(self) -> bool:
        """Verifica si la entrada ha expirado."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        """Actualiza timestamp de acceso."""
        self.accessed_at = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a dict para serialización."""
        return {
            'key': self.key,
            'data': self.data,
            'created_at': self.created_at,
            'accessed_at': self.accessed_at,
            'access_count': self.access_count,
            'ttl': self.ttl,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Crea instancia desde dict."""
        return cls(**data)


class SkillCache:
    """
    Cache inteligente para resultados de skills.

    Características:
    - Backend Redis con fallback local
    - TTL configurable por skill
    - Invalidación por patrones
    - Métricas de rendimiento
    - Serialización automática de SkillResult
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        local_cache_size: int = 1000,
        default_ttl: int = 3600,
        enable_local_fallback: bool = True
    ):
        """
        Inicializa el cache.

        Args:
            redis_url: URL de conexión a Redis
            local_cache_size: Tamaño máximo del cache local
            default_ttl: TTL por defecto en segundos
            enable_local_fallback: Habilitar cache local como fallback
        """
        self.redis_url = redis_url
        self.local_cache_size = local_cache_size
        self.default_ttl = default_ttl
        self.enable_local_fallback = enable_local_fallback

        # Cache local como dict de CacheEntry
        self._local_cache: Dict[str, CacheEntry] = {}

        # Conexión Redis
        self._redis_client: Optional[redis.Redis] = None
        self._redis_available = False

        # Estadísticas
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'redis_errors': 0,
        }

        # Inicializar Redis
        self._init_redis()

    def _init_redis(self) -> None:
        """Inicializa conexión a Redis."""
        from ..services.metrics import log
        if not REDIS_AVAILABLE:
            log.warning("Redis no disponible, usando solo cache local")
            return

        try:
            self._redis_client = redis.from_url(self.redis_url)
            # Test de conexión
            self._redis_client.ping()
            self._redis_available = True
            log.info("Redis conectado exitosamente")
        except Exception as e:
            log.warning(f"Error conectando a Redis: {e}")
            self._redis_available = False
            if self._redis_client:
                self._redis_client.close()
                self._redis_client = None

    def get(self, key: str) -> Optional[SkillResult]:
        """
        Obtiene un resultado del cache.

        Args:
            key: Clave del cache

        Returns:
            SkillResult o None si no existe o expiró
        """
        from ..services.metrics import log
        # Intentar Redis primero
        if self._redis_available:
            try:
                result = self._get_from_redis(key)
                if result is not None:
                    self._stats['hits'] += 1
                    return result
            except Exception as e:
                log.warning(f"Error obteniendo de Redis: {e}")
                self._stats['redis_errors'] += 1

        # Fallback a cache local
        if self.enable_local_fallback:
            result = self._get_from_local(key)
            if result is not None:
                self._stats['hits'] += 1
                return result

        self._stats['misses'] += 1
        return None

    def set(self, key: str, value: SkillResult, ttl: Optional[int] = None) -> None:
        """
        Almacena un resultado en cache.

        Args:
            key: Clave del cache
            value: SkillResult a cachear
            ttl: TTL en segundos (usa default si None)
        """
        if ttl is None:
            ttl = self.default_ttl

        # Solo cachear resultados exitosos
        if not value.success:
            return

        # Serializar SkillResult
        data = self._serialize_result(value)

        # Almacenar en Redis
        from ..services.metrics import log
        if self._redis_available:
            try:
                self._set_in_redis(key, data, ttl)
            except Exception as e:
                log.warning(f"Error almacenando en Redis: {e}")
                self._stats['redis_errors'] += 1

        # Almacenar en cache local
        if self.enable_local_fallback:
            self._set_in_local(key, data, ttl)

        self._stats['sets'] += 1

    def delete(self, key: str) -> bool:
        """
        Elimina una clave del cache.

        Args:
            key: Clave a eliminar

        Returns:
            True si se eliminó, False si no existía
        """
        from ..services.metrics import log
        deleted = False

        # Eliminar de Redis
        if self._redis_available:
            try:
                if self._redis_client and self._redis_client.delete(key):
                    deleted = True
            except Exception as e:
                log.warning(f"Error eliminando de Redis: {e}")
                self._stats['redis_errors'] += 1

        # Eliminar de cache local
        if self.enable_local_fallback and key in self._local_cache:
            del self._local_cache[key]
            deleted = True

        if deleted:
            self._stats['deletes'] += 1

        return deleted

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalida todas las claves que coinciden con un patrón.

        Args:
            pattern: Patrón glob (ej: "skill:math:*")

        Returns:
            Número de claves invalidadas
        """
        invalidated = 0

        # Invalidar en Redis
        from ..services.metrics import log
        if self._redis_available and self._redis_client:
            try:
                keys = self._redis_client.keys(pattern)
                if keys:
                    invalidated += self._redis_client.delete(*keys)
            except Exception as e:
                log.warning(f"Error invalidando patrón en Redis: {e}")
                self._stats['redis_errors'] += 1

        # Invalidar en cache local
        if self.enable_local_fallback:
            keys_to_delete = [
                key for key in self._local_cache.keys()
                if self._matches_pattern(key, pattern)
            ]
            for key in keys_to_delete:
                del self._local_cache[key]
                invalidated += 1

        return invalidated

    def clear(self) -> None:
        """Limpia todo el cache."""
        # Limpiar Redis
        from ..services.metrics import log
        if self._redis_available and self._redis_client:
            try:
                self._redis_client.flushdb()
            except Exception as e:
                log.warning(f"Error limpiando Redis: {e}")
                self._stats['redis_errors'] += 1

        # Limpiar cache local
        self._local_cache.clear()

        from ..services.metrics import log
        log.info("Cache limpiado completamente")

    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del cache.

        Returns:
            Dict con estadísticas
        """
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests) if total_requests > 0 else 0

        return {
            'redis_available': self._redis_available,
            'local_cache_enabled': self.enable_local_fallback,
            'local_cache_size': len(self._local_cache),
            'local_cache_max_size': self.local_cache_size,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'sets': self._stats['sets'],
            'deletes': self._stats['deletes'],
            'redis_errors': self._stats['redis_errors'],
            'hit_rate': round(hit_rate, 3),
            'total_requests': total_requests,
        }

    def _get_from_redis(self, key: str) -> Optional[SkillResult]:
        """Obtiene dato de Redis."""
        from ..services.metrics import log
        if not self._redis_client:
            return None

        data = self._redis_client.get(key)
        if data:
            try:
                parsed = json.loads(data)
                return self._deserialize_result(parsed)
            except Exception as e:
                log.warning(f"Error deserializando dato de Redis: {e}")
                # Eliminar dato corrupto
                self._redis_client.delete(key)

        return None

    def _set_in_redis(self, key: str, data: Dict[str, Any], ttl: int) -> None:
        """Almacena dato en Redis."""
        if not self._redis_client:
            return

        json_data = json.dumps(data)
        self._redis_client.setex(key, ttl, json_data)

    def _get_from_local(self, key: str) -> Optional[SkillResult]:
        """Obtiene dato del cache local."""
        entry = self._local_cache.get(key)
        if entry and not entry.is_expired():
            entry.touch()
            return self._deserialize_result(entry.data)
        elif entry and entry.is_expired():
            # Eliminar entrada expirada
            del self._local_cache[key]

        return None

    def _set_in_local(self, key: str, data: Dict[str, Any], ttl: int) -> None:
        """Almacena dato en cache local."""
        # Limpiar entradas expiradas si es necesario
        self._cleanup_local_cache()

        entry = CacheEntry(key=key, data=data, ttl=ttl)
        self._local_cache[key] = entry

    def _cleanup_local_cache(self) -> None:
        """Limpia entradas expiradas del cache local."""
        expired_keys = [
            key for key, entry in self._local_cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._local_cache[key]

        # Si aún está lleno, eliminar entradas menos accedidas
        if len(self._local_cache) >= self.local_cache_size:
            # Ordenar por último acceso y eliminar las más viejas
            sorted_entries = sorted(
                self._local_cache.items(),
                key=lambda x: (x[1].accessed_at, x[1].access_count)
            )
            keys_to_remove = len(self._local_cache) - self.local_cache_size + 10  # Remover 10 extra
            for key, _ in sorted_entries[:keys_to_remove]:
                del self._local_cache[key]

    def _serialize_result(self, result: SkillResult) -> Dict[str, Any]:
        """Serializa SkillResult para almacenamiento."""
        return {
            'success': result.success,
            'data': result.data,
            'error_message': result.error_message,
            'metadata': result.metadata,
        }

    def _deserialize_result(self, data: Dict[str, Any]) -> 'SkillResult':
        """Deserializa SkillResult desde almacenamiento."""
        from ..services.skill_base import SkillResult
        return SkillResult(
            success=data['success'],
            data=data.get('data'),
            error_message=data.get('error_message'),
            metadata=data.get('metadata', {}),
        )

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Verifica si una clave coincide con un patrón glob simple."""
        # Implementación simple de glob matching
        # Para producción, usar fnmatch o similar
        import fnmatch
        return fnmatch.fnmatch(key, pattern)

    def __del__(self):
        """Cleanup al destruir la instancia."""
        if self._redis_client:
            try:
                self._redis_client.close()
            except:
                pass