"""
ContextManager — Servicio centralizado de contexto activo de búsqueda.

Unifica la lectura/escritura del contexto conversacional para el pipeline
de skills de Propifai. Elimina la duplicación entre SkillExecution.parameters
y conversation.metadata['contexto_activo_busqueda'].

Refactor A — SPEC: plans/spec_tecnica_propifai_intelligence.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ActiveContext — Dataclass normalizada para el contexto de búsqueda
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ActiveContext:
    """
    Contexto activo de búsqueda normalizado.

    Representa los filtros de búsqueda que se heredan entre turnos
    de una conversación. Todos los campos son Optional para permitir
    contextos parciales.

    Uso:
        ctx = ActiveContext(distrito='Cayma', tipo_propiedad='Departamento')
        if not ctx.is_empty():
            params = ctx.to_dict()
    """

    distrito: Optional[str] = None
    tipo_propiedad: Optional[str] = None
    operacion: Optional[str] = None
    precio_min: Optional[float] = None
    precio_max: Optional[float] = None
    habitaciones: Optional[int] = None
    banos: Optional[int] = None
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    condicion: Optional[str] = None
    semantic_query: Optional[str] = None

    # ── Métodos de utilidad ────────────────────────────────────────────────

    def is_empty(self) -> bool:
        """Retorna True si ningún campo tiene valor."""
        return all(v is None for v in self.__dict__.values())

    def merge(self, other: ActiveContext) -> ActiveContext:
        """
        Fusiona dos contextos, priorizando valores no-None del otro.

        Útil para combinar contexto heredado (activo) con parámetros
        nuevos extraídos del mensaje actual.

        Args:
            other: Otro ActiveContext cuyos valores no-None tienen prioridad.

        Returns:
            Nuevo ActiveContext con la fusión de ambos.
        """
        merged = ActiveContext()
        for f in fields(self):
            our_val = getattr(self, f.name)
            other_val = getattr(other, f.name)
            setattr(merged, f.name, other_val if other_val is not None else our_val)
        return merged

    def to_dict(self) -> Dict[str, Any]:
        """Retorna solo los campos con valor no-None como dict."""
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActiveContext:
        """
        Crea un ActiveContext desde un dict, ignorando claves desconocidas.

        Args:
            data: Dict con posibles claves del contexto.

        Returns:
            ActiveContext con los campos que coincidan.
        """
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys and v is not None}
        return cls(**filtered)

    def __str__(self) -> str:
        parts = [f"{k}={v}" for k, v in self.to_dict().items()]
        return f"ActiveContext({', '.join(parts)})" if parts else "ActiveContext(vacío)"


# ═══════════════════════════════════════════════════════════════════════════════
# ContextManager — Servicio centralizado
# ═══════════════════════════════════════════════════════════════════════════════

class ContextManager:
    """
    Servicio centralizado para gestionar el contexto activo de búsqueda.

    Responsabilidades:
    - Leer contexto activo desde SkillExecution o conversation.metadata
    - Guardar contexto activo normalizado
    - Fusionar contexto nuevo con contexto existente
    - Proveer contexto para resolver_contexto

    Elimina la duplicación de fuentes de verdad (M1 del diagnóstico)
    y normaliza nombres de campo (M2 del diagnóstico).
    """

    # Mapeo de nombres de campo normalizados → posibles nombres en field_values
    # Ordenado por probabilidad de ocurrencia (más común primero)
    FIELD_ALIASES: Dict[str, List[str]] = {
        'distrito': ['distrito', 'district', 'district_name', 'zona', 'ubicacion'],
        'tipo_propiedad': [
            'tipo_propiedad', 'property_type', 'property_type_id',
            'tipo', 'type', 'categoria',
        ],
        'operacion': ['operacion', 'operation_type', 'tipo_operacion', 'operation'],
        'precio_min': ['precio_min', 'price_min', 'min_price', 'precio_desde'],
        'precio_max': ['precio_max', 'price_max', 'max_price', 'precio_hasta'],
        'habitaciones': ['habitaciones', 'bedrooms', 'dormitorios', 'cuartos', 'rooms'],
        'banos': ['banos', 'bathrooms', 'banios', 'bano', 'bathroom'],
        'area_min': ['area_min', 'min_area', 'built_area_min', 'area_desde'],
        'area_max': ['area_max', 'max_area', 'total_area_max', 'area_hasta'],
        'condicion': ['condicion', 'condition', 'estado', 'status'],
        'semantic_query': ['semantic_query', 'query', 'busqueda', 'search_query'],
    }

    # ── Lectura ────────────────────────────────────────────────────────────

    @classmethod
    def get_active_context(cls, conversation) -> ActiveContext:
        """
        Obtiene el contexto activo desde la fuente más reciente.

        Estrategia de búsqueda:
        1. SkillExecution — la última ejecución exitosa de busqueda_propiedades
        2. Fallback a conversation.metadata['contexto_activo_busqueda']

        Args:
            conversation: Instancia de Conversation (intelligence.models)

        Returns:
            ActiveContext con los filtros activos o vacío si no hay contexto.
        """
        try:
            # 1. Intentar desde SkillExecution
            from ..models import SkillExecution

            ultima_ejecucion = SkillExecution.objects.filter(
                conversation=conversation,
                skill_name='busqueda_propiedades',
                status='success',
            ).order_by('-executed_at').first()

            if ultima_ejecucion and ultima_ejecucion.parameters:
                params = ultima_ejecucion.parameters
                contexto = cls._normalize_context(params)
                if not contexto.is_empty():
                    logger.info(
                        f"[ContextManager] Contexto recuperado de SkillExecution: {contexto}"
                    )
                    return contexto

            # 2. Fallback a metadata de la conversación
            try:
                conversation.refresh_from_db(fields=['metadata'])
            except Exception:
                pass

            metadata = conversation.metadata or {}
            raw_contexto = metadata.get('contexto_activo_busqueda', {})
            if raw_contexto:
                contexto = cls._normalize_context(raw_contexto)
                if not contexto.is_empty():
                    logger.info(
                        f"[ContextManager] Contexto recuperado de metadata: {contexto}"
                    )
                    return contexto

            return ActiveContext()

        except Exception as e:
            logger.warning(f"[ContextManager] Error al obtener contexto activo: {e}")
            return ActiveContext()

    # ── Escritura ──────────────────────────────────────────────────────────

    @classmethod
    def save_active_context(
        cls, conversation, contexto: ActiveContext
    ) -> None:
        """
        Guarda el contexto activo normalizado en conversation.metadata.

        Args:
            conversation: Instancia de Conversation
            contexto: ActiveContext a guardar (se omite si está vacío)
        """
        if contexto.is_empty():
            return

        try:
            metadata = conversation.metadata or {}
            metadata['contexto_activo_busqueda'] = contexto.to_dict()
            conversation.metadata = metadata
            conversation.save(update_fields=['metadata'])
            logger.info(
                f"[ContextManager] Contexto guardado en metadata: {contexto}"
            )
        except Exception as e:
            logger.warning(
                f"[ContextManager] Error al guardar contexto activo: {e}"
            )

    @classmethod
    def save_raw_context(
        cls, conversation, raw_params: Dict[str, Any]
    ) -> None:
        """
        Guarda un dict raw como contexto activo (normaliza automáticamente).

        Args:
            conversation: Instancia de Conversation
            raw_params: Dict con parámetros sin normalizar
        """
        if not raw_params:
            return
        contexto = cls._normalize_context(raw_params)
        cls.save_active_context(conversation, contexto)

    # ── Normalización ──────────────────────────────────────────────────────

    @classmethod
    def _normalize_context(cls, raw: Dict[str, Any]) -> ActiveContext:
        """
        Normaliza un dict raw a ActiveContext usando FIELD_ALIASES.

        Itera sobre los aliases conocidos y asigna el primer valor
        encontrado al campo normalizado correspondiente.

        Args:
            raw: Dict con posibles nombres de campo no normalizados.

        Returns:
            ActiveContext con los campos normalizados.
        """
        context = ActiveContext()
        for field_name, aliases in cls.FIELD_ALIASES.items():
            for alias in aliases:
                value = raw.get(alias)
                if value is not None:
                    # Intentar convertir tipos básicos
                    try:
                        setattr(context, field_name, cls._cast_value(field_name, value))
                    except (ValueError, TypeError):
                        setattr(context, field_name, value)
                    break
        return context

    @staticmethod
    def _cast_value(field_name: str, value: Any) -> Any:
        """
        Convierte un valor al tipo esperado según el campo.

        Args:
            field_name: Nombre del campo normalizado.
            value: Valor a convertir.

        Returns:
            Valor convertido al tipo apropiado.
        """
        type_map = {
            'precio_min': float,
            'precio_max': float,
            'habitaciones': int,
            'banos': int,
            'area_min': float,
            'area_max': float,
        }
        converter = type_map.get(field_name)
        if converter is not None and value is not None:
            try:
                return converter(value)
            except (ValueError, TypeError):
                return value
        return value

    # ── Utilidad ───────────────────────────────────────────────────────────

    @classmethod
    def has_context(cls, conversation) -> bool:
        """
        Verifica si hay contexto activo disponible.

        Args:
            conversation: Instancia de Conversation

        Returns:
            True si hay contexto activo no vacío.
        """
        return not cls.get_active_context(conversation).is_empty()

    @classmethod
    def clear_context(cls, conversation) -> None:
        """
        Limpia el contexto activo de la conversación.

        Args:
            conversation: Instancia de Conversation
        """
        try:
            metadata = conversation.metadata or {}
            if 'contexto_activo_busqueda' in metadata:
                del metadata['contexto_activo_busqueda']
                conversation.metadata = metadata
                conversation.save(update_fields=['metadata'])
                logger.info("[ContextManager] Contexto activo limpiado")
        except Exception as e:
            logger.warning(f"[ContextManager] Error al limpiar contexto: {e}")
