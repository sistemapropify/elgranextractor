"""
Módulo de Pipeline de Vida del Requerimiento.

Calcula las 4 etapas del ciclo de vida de un requerimiento:
1. 📝 Requerimiento — Fecha de creación
2. 🎯 Match — Primer matching ejecutado
3. 📤 Propuesta — Primera propuesta WhatsApp enviada
4. ✅/❌ Decisión — Respuesta del cliente (aceptado/rechazado)

Entre cada etapa, calcula el lapso de tiempo transcurrido.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from django.utils import timezone

from requerimientos.models import Requerimiento
from .models import MatchResult, PropuestaWhatsApp

logger = logging.getLogger(__name__)

STATUS_ACEPTADO = ('interesado', 'visita_agendada', 'cerrada')
STATUS_RECHAZADO = ('rechazado', 'no_interesado')


def _calcular_lapso(desde: Optional[datetime], hasta: Optional[datetime]) -> Optional[Dict[str, Any]]:
    """
    Calcula la diferencia entre dos datetimes y retorna un dict formateado.

    Args:
        desde: Fecha/hora inicial (puede ser None)
        hasta: Fecha/hora final (puede ser None)

    Returns:
        dict con {dias, horas, minutos, display} o None si falta alguna fecha
    """
    if not desde or not hasta:
        return None

    diff = hasta - desde

    if diff.total_seconds() < 0:
        # Si la diferencia es negativa, retornar 0
        diff = timedelta(seconds=0)

    dias = diff.days
    horas = diff.seconds // 3600
    minutos = (diff.seconds % 3600) // 60

    # Formato humano
    if dias > 0:
        if horas > 0:
            display = f"{dias}d {horas}h"
        else:
            display = f"{dias}d"
    elif horas > 0:
        if minutos > 0:
            display = f"{horas}h {minutos}m"
        else:
            display = f"{horas}h"
    else:
        display = f"{minutos}m"

    return {
        'dias': dias,
        'horas': horas,
        'minutos': minutos,
        'display': display,
    }


def _formatear_fecha(dt: Optional[datetime]) -> Optional[str]:
    """Formatea un datetime a string legible 'DD/MM HH:MM'."""
    if not dt:
        return None
    return dt.strftime('%d/%m %H:%M')


def _formatear_fecha_completa(dt: Optional[datetime]) -> Optional[str]:
    """Formatea un datetime a string completo 'DD/MM/AAAA HH:MM'."""
    if not dt:
        return None
    return dt.strftime('%d/%m/%Y %H:%M')


def _obtener_fecha_requerimiento(req: Requerimiento) -> Optional[datetime]:
    """
    Obtiene la mejor fecha disponible del requerimiento.
    Prioriza fecha+hora, luego creado_en.
    """
    if req.fecha:
        if req.hora:
            return datetime.combine(req.fecha, req.hora)
        return datetime.combine(req.fecha, datetime.min.time())
    if req.creado_en:
        return req.creado_en
    return None


def obtener_pipeline_requerimiento(requerimiento_id: int) -> Dict[str, Any]:
    """
    Obtiene el pipeline completo de vida de un requerimiento.

    Args:
        requerimiento_id: ID del requerimiento a analizar

    Returns:
        dict con estructura:
        {
            'requerimiento_id': int,
            'requerimiento_texto': str,
            'etapas': {
                'requerimiento': { ... },
                'match': { ... },
                'propuesta': { ... },
                'decision': { ... },
            },
            'lapso_total': { ... } or None,
            'stats': { ... }
        }
    """
    try:
        req = Requerimiento.objects.get(id=requerimiento_id)
    except Requerimiento.DoesNotExist:
        return {
            'requerimiento_id': requerimiento_id,
            'error': 'Requerimiento no encontrado',
            'etapas': {},
        }

    # ── Etapa 1: Requerimiento ──
    fecha_req = _obtener_fecha_requerimiento(req)
    etapa_req = {
        'tipo': 'requerimiento',
        'label': 'Requerimiento',
        'icono': '📝',
        'fecha': _formatear_fecha_completa(fecha_req) if fecha_req else None,
        'fecha_display': _formatear_fecha(fecha_req) if fecha_req else '—',
        'estado': 'ok' if fecha_req else 'pendiente',
        'detalle': None,
    }

    # ── Etapa 2: Match ──
    fecha_match = None
    mejor_score = None
    total_ejecuciones = 0
    try:
        primer_match = MatchResult.objects.filter(
            requerimiento_id=requerimiento_id
        ).order_by('ejecutado_en').first()

        if primer_match:
            fecha_match = primer_match.ejecutado_en
            mejor_score = float(
                MatchResult.objects.filter(
                    requerimiento_id=requerimiento_id,
                    fase_eliminada__isnull=True,
                ).order_by('-score_total').first().score_total
            ) if MatchResult.objects.filter(
                requerimiento_id=requerimiento_id,
                fase_eliminada__isnull=True,
            ).exists() else None

            total_ejecuciones = MatchResult.objects.filter(
                requerimiento_id=requerimiento_id
            ).values('ejecutado_en').distinct().count()
    except Exception as e:
        logger.warning(f"Error al consultar MatchResult para req #{requerimiento_id}: {e}")

    lapso_req_match = _calcular_lapso(fecha_req, fecha_match)

    etapa_match = {
        'tipo': 'match',
        'label': 'Match',
        'icono': '🎯',
        'fecha': _formatear_fecha_completa(fecha_match) if fecha_match else None,
        'fecha_display': _formatear_fecha(fecha_match) if fecha_match else '—',
        'estado': 'ok' if fecha_match else 'pendiente',
        'lapso_desde_anterior': lapso_req_match,
        'detalle': f"Score: {mejor_score:.0f}%" if mejor_score else None,
    }

    # ── Etapa 3: Propuesta ──
    fecha_propuesta = None
    status_propuesta = None
    total_propuestas = 0
    try:
        primera_propuesta = PropuestaWhatsApp.objects.filter(
            requerimiento_id=requerimiento_id
        ).order_by('enviado_en').first()

        if primera_propuesta:
            fecha_propuesta = primera_propuesta.enviado_en
            status_propuesta = primera_propuesta.status
            total_propuestas = PropuestaWhatsApp.objects.filter(
                requerimiento_id=requerimiento_id
            ).count()
    except Exception as e:
        logger.warning(f"Error al consultar PropuestaWhatsApp para req #{requerimiento_id}: {e}")

    lapso_match_propuesta = _calcular_lapso(fecha_match, fecha_propuesta)
    lapso_total_req_propuesta = _calcular_lapso(fecha_req, fecha_propuesta)

    detalle_propuesta = None
    if status_propuesta:
        nombres_status = dict(PropuestaWhatsApp.Status.choices)
        detalle_propuesta = nombres_status.get(status_propuesta, status_propuesta)

    etapa_propuesta = {
        'tipo': 'propuesta',
        'label': 'Propuesta',
        'icono': '📤',
        'fecha': _formatear_fecha_completa(fecha_propuesta) if fecha_propuesta else None,
        'fecha_display': _formatear_fecha(fecha_propuesta) if fecha_propuesta else '—',
        'estado': 'ok' if fecha_propuesta else ('pendiente' if fecha_match else 'no_aplica'),
        'lapso_desde_anterior': lapso_match_propuesta,
        'lapso_desde_inicio': lapso_total_req_propuesta,
        'detalle': detalle_propuesta,
    }

    # ── Etapa 4: Decisión ──
    fecha_decision = None
    decision_status = None
    detalle_decision = None
    try:
        # Buscar la propuesta más reciente que tenga respondido_en no nulo
        propuesta_con_respuesta = PropuestaWhatsApp.objects.filter(
            requerimiento_id=requerimiento_id,
            respondido_en__isnull=False,
        ).order_by('-respondido_en').first()

        if propuesta_con_respuesta:
            fecha_decision = propuesta_con_respuesta.respondido_en
            st = propuesta_con_respuesta.status

            if st in STATUS_ACEPTADO:
                decision_status = 'aceptado'
                detalle_decision = '✅ Aceptado'
            elif st in STATUS_RECHAZADO:
                decision_status = 'rechazado'
                detalle_decision = '❌ Rechazado'
            else:
                decision_status = 'respondido'
                detalle_decision = f"Respondido: {st}"
    except Exception as e:
        logger.warning(f"Error al consultar decisión para req #{requerimiento_id}: {e}")

    lapso_propuesta_decision = _calcular_lapso(fecha_propuesta, fecha_decision)
    lapso_total_req_decision = _calcular_lapso(fecha_req, fecha_decision)

    if fecha_propuesta and not fecha_decision:
        estado_decision = 'pendiente'
        detalle_decision = 'Esperando respuesta...'
    elif not fecha_propuesta:
        estado_decision = 'no_aplica'
        detalle_decision = 'Sin propuesta enviada'
    else:
        estado_decision = 'ok'

    etapa_decision = {
        'tipo': 'decision',
        'label': 'Decisión',
        'icono': '✅' if decision_status == 'aceptado' else ('❌' if decision_status == 'rechazado' else '⏳'),
        'fecha': _formatear_fecha_completa(fecha_decision) if fecha_decision else None,
        'fecha_display': _formatear_fecha(fecha_decision) if fecha_decision else '—',
        'estado': estado_decision,
        'lapso_desde_anterior': lapso_propuesta_decision,
        'lapso_desde_inicio': lapso_total_req_decision,
        'detalle': detalle_decision,
        'decision': decision_status,
    }

    # ── Lapso total del pipeline completo ──
    lapso_total = _calcular_lapso(fecha_req, fecha_decision)

    # ── Stats ──
    stats = {
        'total_ejecuciones_match': total_ejecuciones,
        'total_propuestas_enviadas': total_propuestas,
        'mejor_score_match': mejor_score,
        'tiene_match': fecha_match is not None,
        'tiene_propuesta': fecha_propuesta is not None,
        'tiene_decision': fecha_decision is not None,
        'decision_final': decision_status,
    }

    # Orden de etapas para el frontend
    etapas_orden = ['requerimiento', 'match', 'propuesta', 'decision']

    return {
        'requerimiento_id': requerimiento_id,
        'requerimiento_texto': req.requerimiento[:200] if req.requerimiento else '',
        'requerimiento_agente': (req.agente or '').replace('\n', ' ').strip(),
        'etapas': {
            'requerimiento': etapa_req,
            'match': etapa_match,
            'propuesta': etapa_propuesta,
            'decision': etapa_decision,
        },
        'etapas_orden': etapas_orden,
        'lapso_total': lapso_total,
        'stats': stats,
    }
