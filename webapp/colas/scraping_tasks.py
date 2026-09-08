"""
Tareas Celery para scraping de portales inmobiliarios.

Lee el estado del ScrapingJob para controlar pausa/reanudar/detención.
Crea ScrapingLog por cada propiedad procesada para el terminal en vivo.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from functools import wraps
from datetime import datetime
from typing import Dict, Any, List

from celery import shared_task
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)


def _keep_windows_awake(function):
    """Evita suspensión, hibernación y apagado de pantalla durante el job.

    SetThreadExecutionState afecta únicamente al hilo del scraper y se revierte
    siempre al finalizar, incluso cuando hay una excepción.
    """
    @wraps(function)
    def wrapped(*args, **kwargs):
        keep_awake = False
        if os.name == 'nt':
            try:
                import ctypes
                flags = 0x80000000 | 0x00000001 | 0x00000002
                keep_awake = bool(
                    ctypes.windll.kernel32.SetThreadExecutionState(flags)
                )
            except (AttributeError, OSError):
                keep_awake = False
        try:
            return function(*args, **kwargs)
        finally:
            if keep_awake:
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
                except (AttributeError, OSError):
                    pass

    return wrapped

# Orden de ejecución por defecto
ORDEN_DEFECTO = [
    'remax', 'adondevivir', 'properati', 'urbania',
    'facebook_marketplace',
]

# El límite global de Celery (5 min) no es apropiado para navegadores. Cada
# skill mantiene su propio timeout y checkpoint; este margen permite que el
# timeout interno cierre Camoufox y reintente limpiamente.
SCRAPING_TASK_SOFT_TIME_LIMIT = int(
    os.environ.get('SCRAPING_TASK_SOFT_TIME_LIMIT', '6900')
)
SCRAPING_TASK_TIME_LIMIT = int(
    os.environ.get('SCRAPING_TASK_TIME_LIMIT', '7200')
)


def _error_camoufox_no_reintentable(resultado) -> bool:
    """Detecta fallos permanentes del host que un reintento no puede reparar."""
    message = str(getattr(resultado, 'message', '') or '').lower()
    permanent_markers = (
        'camoufoxsystemdependencyerror',
        'faltan dependencias linux',
        'libgtk-3.so.0',
        'libx11-xcb.so.1',
        'libasound.so.2',
        'facebook_auth_required',
        'facebook_session_invalid',
        'xpcomglueload error',
        "couldn't load xpcom",
    )
    return any(marker in message for marker in permanent_markers)


def _mensaje_error_camoufox_no_reintentable(resultado) -> str:
    """Explica el fallo permanente sin confundir autenticacion con librerias."""
    message = str(getattr(resultado, 'message', '') or '').lower()
    if 'facebook_auth_required' in message:
        return (
            'Facebook Marketplace requiere una sesion autenticada. '
            'Configure FACEBOOK_MARKETPLACE_COOKIES_JSON o renueve la sesion '
            'persistente; no se reintentara sin credenciales.'
        )
    if 'facebook_session_invalid' in message:
        return (
            'La sesion configurada para Facebook Marketplace no es valida. '
            'Renueve FACEBOOK_MARKETPLACE_COOKIES_JSON.'
        )
    return (
        'Camoufox no se reintentara: faltan dependencias nativas '
        'en el servidor.'
    )


def _resultado_portal_valido(resultado) -> bool:
    """Solo acepta como éxito una extracción que detectó propiedades."""
    data = resultado.data or {}
    return bool(
        resultado.success
        and data.get('discovery', {}).get('complete') is True
        and not int(data.get('errores', 0) or 0)
        and not int(data.get('pending', 0) or 0)
        and (
            int(data.get('total', 0) or 0) > 0
            or bool(data.get('resume_complete'))
        )
    )


def _instanciar_skill(portal: str):
    """Importa dinámicamente la skill del portal y retorna una instancia."""
    skill_map = {
        'remax': 'scraper_remax',
        'adondevivir': 'scraper_adondevivir',
        'properati': 'scraper_properati',
        'urbania': 'scraper_urbania',
        'facebook_marketplace': 'scraper_facebook_marketplace',
    }
    skill_name = skill_map.get(portal)
    if not skill_name:
        raise ValueError(f"Portal no soportado: {portal}")

    module_path = f"intelligence.skills.scrapi.{skill_name}"
    import importlib
    module = importlib.import_module(module_path)
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        # Buscar clases cuyo nombre empiece con 'Scraper' y termine con 'Skill'
        if isinstance(attr, type) and attr_name.startswith('Scraper') and attr_name.endswith('Skill'):
            return attr()
    raise ValueError(f"No se encontró skill para {portal}")


def _actualizar_contadores(
    job,
    resultado: Dict[str, int],
    base_counters: Dict[str, int] | None = None,
):
    """
    Consolida el resultado de un portal sin duplicar los avances en vivo.

    ``total_propiedades`` representa las propiedades detectadas y
    ``procesadas`` las propiedades ya clasificadas como nuevas, existentes
    o con error.
    """
    from ingestas.models import ScrapingJob

    if base_counters is None:
        job.refresh_from_db()
        base_counters = {
            'total_propiedades': job.total_propiedades,
            'procesadas': job.procesadas,
            'nuevas': job.nuevas,
            'actualizadas': job.actualizadas,
            'errores': job.errores,
        }

    total = int(resultado.get('total', 0) or 0)
    updates = {
        'total_propiedades': base_counters['total_propiedades'] + total,
        'procesadas': base_counters['procesadas'] + total,
        'nuevas': base_counters['nuevas']
        + int(resultado.get('nuevas', 0) or 0),
        'actualizadas': base_counters['actualizadas']
        + int(resultado.get('actualizadas', 0) or 0),
        'errores': base_counters['errores']
        + int(resultado.get('errores', 0) or 0),
    }
    ScrapingJob.objects.filter(id=job.id, execution_token=job.execution_token).update(**updates)
    job.refresh_from_db()


def _registrar_resultado_portal(
    job,
    portal: str,
    estado: str,
    resultado: Dict[str, int] | None = None,
    mensaje: str = '',
):
    """Persiste en el propio job el desglose y estado de cada portal."""
    from ingestas.models import ScrapingJob

    expected_token = job.execution_token
    job.refresh_from_db()
    if job.execution_token != expected_token:
        from scrapi.contracts import ScrapingInterrupted
        raise ScrapingInterrupted('execution.owner_lost: resultado de un ejecutor reemplazado')
    parametros = dict(job.parametros or {})
    resultados = dict(parametros.get('resultados_por_portal') or {})
    data = resultado or {}
    resultados[portal] = {
        'estado': estado,
        'detectadas': int(data.get('total', 0) or 0),
        'nuevas': int(data.get('nuevas', 0) or 0),
        'actualizadas': int(data.get('actualizadas', 0) or 0),
        'errores': int(data.get('errores', 0) or 0),
        'mensaje': str(mensaje or '')[:500],
        'discovery': data.get('discovery') or {},
        'source': (parametros.get('sources') or {}).get(portal) or {},
    }
    parametros['resultados_por_portal'] = resultados
    ScrapingJob.objects.filter(id=job.id, execution_token=expected_token).update(parametros=parametros)
    job.parametros = parametros


def _crear_log(job, nivel: str, mensaje: str, portal: str = None,
               propiedad_id: str = None, evento='message', contexto=None) -> int:
    """Crea un ScrapingLog y retorna su ID (para SSE)."""
    from ingestas.models import ScrapingLog
    from scrapi.telemetry import sanitize
    log = ScrapingLog.log(job, nivel, sanitize(mensaje), portal, propiedad_id,
                         evento=evento, contexto=sanitize(contexto or {}))
    return log.id


def _start_portal_heartbeat(
    job_id: int,
    portal: str,
    execution_token,
    interval: int = 30,
):
    """Mantiene una evidencia persistente de que el portal sigue vivo.

    El watchdog usa los logs recientes para distinguir un proceso lento de
    uno huérfano, por lo que el heartbeat no puede ser solo una consulta.
    """
    from ingestas.models import ScrapingJob

    stop_event = threading.Event()

    def beat():
        close_old_connections()
        try:
            while not stop_event.wait(interval):
                job = ScrapingJob.objects.filter(id=job_id).first()
                if (
                    not job
                    or job.estado not in ('running', 'paused')
                    or job.execution_token != execution_token
                ):
                    return
                _crear_log(
                    job,
                    'debug',
                    f'{portal.title()}: proceso activo; esperando el siguiente avance',
                    portal=portal,
                )
                from datetime import timedelta
                now = timezone.now()
                ScrapingJob.objects.filter(id=job_id, execution_token=execution_token,
                    estado__in=['running', 'paused'], lease_expires_at__gt=now).update(
                    heartbeat_at=now, lease_expires_at=now + timedelta(seconds=180))
        finally:
            close_old_connections()

    heartbeat = threading.Thread(
        target=beat,
        daemon=True,
        name=f'scraping-heartbeat-{job_id}-{portal}',
    )
    heartbeat.start()
    return stop_event, heartbeat

def _release_for_shutdown(job_id, token):
    """Fence this process immediately while preserving its durable pending work."""
    from ingestas.models import ScrapingJob
    from django.db import transaction
    with transaction.atomic():
        job = ScrapingJob.objects.select_for_update().get(pk=job_id)
        if job.execution_token != token or job.estado not in ('running', 'paused'):
            return
        job.estado = 'idle' if job.estado == 'running' else 'paused'
        job.execution_token = None
        job.lease_expires_at = None
        job.save(update_fields=['estado', 'execution_token', 'lease_expires_at'])
        _crear_log(job, 'warning', 'Worker detenido; candidatos y checkpoint conservados para continuar.',
                   portal=job.portal_actual, evento='worker.stopping')


@_keep_windows_awake
def _run_scraping(job_id: int, stop_event=None):
    """
    Lógica principal de scraping. Llamada desde Celery task o desde threading.
    
    Args:
        job_id: ID del ScrapingJob.
    """
    from ingestas.models import ScrapingJob

    try:
        job = ScrapingJob.objects.get(id=job_id)
    except ScrapingJob.DoesNotExist:
        logger.error(f"ScrapingJob {job_id} no encontrado")
        return

    # Claim compare-and-swap: solo un ejecutor puede mover idle -> running.
    # Un segundo despacho del mismo job termina antes de abrir Camoufox.
    execution_token = uuid.uuid4()
    from datetime import timedelta
    lease_start = timezone.now()
    claimed = ScrapingJob.objects.filter(
        id=job_id, estado='idle'
    ).update(
        estado='running',
        iniciado_en=timezone.now(),
        execution_token=execution_token,
        heartbeat_at=lease_start,
        lease_expires_at=lease_start + timedelta(seconds=180),
    )
    if claimed != 1:
        logger.warning(
            "ScrapingJob #%s ignorado: ya fue reclamado (estado=%s)",
            job_id,
            job.estado,
        )
        return

    job.refresh_from_db()
    def shutdown_requested():
        if stop_event and stop_event.is_set():
            _release_for_shutdown(job_id, execution_token)
            return True
        return False

    if shutdown_requested():
        return
    portales = (job.parametros or {}).get('portales') or ORDEN_DEFECTO
    if (job.parametros or {}).get('mode') == 'preview':
        from ingestas.scraping_preview import run_preview
        run_preview(job, execution_token, stop_event=stop_event)
        return

    _crear_log(
        job,
        'info',
        f"🚀 Trabajo #{job.id} · Portales seleccionados ({len(portales)}): {', '.join(portales)}",
    )
    if os.name == 'nt':
        _crear_log(
            job,
            'info',
            '🛡️ Protección activa: Windows no suspenderá ni hibernará '
            'mientras este scraping esté ejecutándose.',
        )
    total_portales = len(portales)
    successful_portals = 0
    failed_portals = []

    for idx, portal in enumerate(portales, 1):
        if shutdown_requested():
            return
        portal_run = None
        # ── Verificar estado antes de cada portal ──
        job.refresh_from_db()

        # Al reanudar un job parcial, no repetir portales que ya finalizaron.
        resultados_previos = dict(
            (job.parametros or {}).get('resultados_por_portal') or {}
        )
        if (resultados_previos.get(portal) or {}).get('estado') == 'completed':
            successful_portals += 1
            _crear_log(
                job,
                'info',
                f'↪️ {portal.upper()} ya estaba completado; se conserva y se omite.',
                portal=portal,
            )
            continue

        if job.execution_token != execution_token:
            logger.info(
                'ScrapingJob #%s: ejecución reemplazada; proceso anterior finaliza.',
                job.id,
            )
            return

        if job.estado == 'stopped':
            _crear_log(job, 'info', f'⏹️ Scraping detenido en portal {portal}')
            job.completado_en = timezone.now()
            job.save()
            return

        while job.estado == 'paused':
            if shutdown_requested():
                return
            _crear_log(job, 'info', f'⏸️  Pausado antes de {portal}')
            time.sleep(2)
            job.refresh_from_db()
            if job.estado == 'stopped':
                job.completado_en = timezone.now()
                job.save()
                return

        if job.estado != 'running' or job.execution_token != execution_token:
            return

        # ── Ejecutar scraper ──
        job.portal_actual = portal
        job.progreso = int((idx - 1) / total_portales * 100)
        updated = ScrapingJob.objects.filter(
            id=job.id,
            estado='running',
            execution_token=execution_token,
        ).update(portal_actual=portal, progreso=job.progreso)
        if updated != 1:
            return
        job.refresh_from_db()

        _crear_log(job, 'info', f'🔍 Iniciando scraper {portal.upper()}...')

        try:
            from ingestas.lifecycle import (
                fail_portal_run,
                finalize_portal_run,
                start_or_resume_portal_run,
            )

            portal_run = start_or_resume_portal_run(job, portal)
            from scrapi.telemetry import runtime_context
            _crear_log(job, 'info', f'{portal}: configuración de esta ejecución', portal=portal,
                evento='source.snapshot', contexto={'run_id': portal_run.pk,
                    'source': portal_run.source_config, **runtime_context()})
            from ingestas.scraping_store import record_progress, resume_state, run_counters
            existing = run_counters(portal_run.id)
            skill = _instanciar_skill(portal)
            _crear_log(job, 'info', f'⚙️  Ejecutando {portal.upper()}...')
            base_counters = {
                'total_propiedades': max(0, job.total_propiedades - existing['total']),
                'procesadas': max(0, job.procesadas - existing['total']),
                'nuevas': max(0, job.nuevas - existing['nuevas']),
                'actualizadas': max(0, job.actualizadas - existing['actualizadas']),
                'errores': max(0, job.errores - existing['errores']),
            }

            def reportar_progreso(payload):
                """Sincroniza progreso interno de la skill y controla cancelación."""
                nonlocal job
                if shutdown_requested():
                    return False
                job.refresh_from_db()
                while job.estado == 'paused':
                    if shutdown_requested():
                        return False
                    time.sleep(2)
                    job.refresh_from_db()
                if (
                    job.estado != 'running'
                    or job.execution_token != execution_token
                ):
                    return False

                portal_progress = max(
                    0, min(100, int(payload.get('percent', 0) or 0))
                )
                overall = int(
                    ((idx - 1) + (portal_progress / 100))
                    / total_portales
                    * 100
                )
                updates = {
                    'portal_actual': portal,
                }
                if payload.get('percent') is not None:
                    updates['progreso'] = max(job.progreso, overall)
                if any(key in payload for key in ('candidate_batch', 'candidate_error', 'candidate_excluded', 'discovery', 'checkpoint_page')):
                    record_progress(portal_run.id, payload, execution_token)
                if payload.get('processed') is not None:
                    processed = int(payload['processed'])
                    updates['procesadas'] = base_counters['procesadas'] + processed
                    updates['total_propiedades'] = (
                        base_counters['total_propiedades'] + processed
                    )
                for counter in ('nuevas', 'actualizadas', 'errores'):
                    if payload.get(counter) is not None:
                        updates[counter] = (
                            base_counters[counter] + int(payload[counter])
                        )
                checkpoint_page = payload.get('checkpoint_page')
                resume_item_ids = payload.get('resume_item_ids')
                if checkpoint_page is not None or resume_item_ids is not None:
                    parametros = dict(job.parametros or {})
                    if checkpoint_page is not None:
                        checkpoints = dict(parametros.get('checkpoints') or {})
                        checkpoints[portal] = max(
                            int(checkpoints.get(portal, 0) or 0),
                            int(checkpoint_page),
                        )
                        parametros['checkpoints'] = checkpoints
                    if resume_item_ids is not None:
                        clean_ids = []
                        seen_ids = set()
                        raw_ids = (
                            resume_item_ids
                            if isinstance(resume_item_ids, (list, tuple))
                            else []
                        )
                        for raw_id in raw_ids:
                            item_id = str(raw_id or '').strip()
                            if not item_id.isdigit() or item_id in seen_ids:
                                continue
                            seen_ids.add(item_id)
                            clean_ids.append(item_id)
                        resume_queues = dict(
                            parametros.get('resume_queues') or {}
                        )
                        resume_queues[portal] = clean_ids
                        parametros['resume_queues'] = resume_queues
                    updates['parametros'] = parametros

                updated = ScrapingJob.objects.filter(
                    id=job.id,
                    estado='running',
                    execution_token=execution_token,
                ).update(**updates)
                if updated != 1:
                    return False

                message = payload.get('message')
                if message:
                    context_data = {key: value for key, value in payload.items()
                                    if key not in ('message', 'candidate_batch', 'resume_item_ids')}
                    context_data.update(run_id=portal_run.id, execution_token=str(execution_token))
                    _crear_log(job, payload.get('level', 'info'), message, portal=portal,
                               propiedad_id=payload.get('property_id'),
                               evento=payload.get('event', 'message'), contexto=context_data)
                return True

            # Ejecutar con reintentos controlados. Properati y Adondevivir
            # pueden quedar temporalmente sin respuesta al iniciar Camoufox;
            # el segundo intento usa el mismo checkpoint confirmado.
            max_attempts = 3 if portal == 'properati' else (
                2 if portal in ('adondevivir', 'urbania', 'facebook_marketplace') else 1
            )
            resultado = None
            for attempt in range(1, max_attempts + 1):
                if shutdown_requested():
                    return
                job.refresh_from_db()
                parametros = dict(job.parametros or {})
                checkpoints = dict(parametros.get('checkpoints') or {})
                start_page = int(checkpoints.get(portal, 0) or 0) + 1
                resume_queues = dict(parametros.get('resume_queues') or {})
                skill = _instanciar_skill(portal)
                heartbeat_stop, heartbeat_thread = _start_portal_heartbeat(
                    job.id, portal, execution_token
                )
                try:
                    resultado = skill.execute(
                        {
                            'max_paginas': 0,
                            'start_page': start_page,
                            'resume_item_ids': resume_queues.get(portal),
                            'source_url': portal_run.source_config['source_url'],
                            'resume_state': resume_state(portal_run),
                            'max_items': (parametros.get('limits') or {}).get('max_items', 1500),
                        },
                        context={
                            'progress_callback': reportar_progreso,
                            'lifecycle_run_id': portal_run.id,
                            'execution_token': execution_token,
                        },
                    )
                finally:
                    heartbeat_stop.set()
                    heartbeat_thread.join(timeout=2)
                job.refresh_from_db()
                if (
                    job.estado != 'running'
                    or job.execution_token != execution_token
                ):
                    if job.execution_token == execution_token:
                        fail_portal_run(
                            portal_run,
                            'La ejecución fue detenida antes de completar el portal.',
                            status='incomplete',
                            execution_token=execution_token,
                        )
                    return
                pending_details = int(run_counters(portal_run.id).get('pending', 0))
                if resultado.success and not pending_details:
                    break
                if _error_camoufox_no_reintentable(resultado):
                    _crear_log(
                        job, 'error',
                        _mensaje_error_camoufox_no_reintentable(resultado),
                        portal=portal,
                    )
                    break
                if attempt < max_attempts:
                    terminated = 0
                    if portal in ('adondevivir', 'urbania', 'facebook_marketplace'):
                        # Un arranque de contexto persistente que venció su
                        # timeout puede dejar Camoufox vivo y el perfil
                        # bloqueado. Antes de reintentar liberamos únicamente
                        # los perfiles del scraper.
                        from ingestas.views import _terminate_scraping_browsers
                        terminated = _terminate_scraping_browsers()
                    job.refresh_from_db()
                    checkpoints = dict((job.parametros or {}).get('checkpoints') or {})
                    resume_page = int(checkpoints.get(portal, 0) or 0) + 1
                    _crear_log(
                        job, 'warning',
                        f'Camoufox fallo; reintento {attempt + 1}/{max_attempts} '
                        f'desde la pagina {resume_page}. '
                        + (
                            f'Se cerraron {terminated} proceso(s) Camoufox '
                            'huérfano(s).'
                            if terminated else
                            'Perfil Camoufox liberado antes del reintento.'
                        ),
                        portal=portal,
                    )
                    time.sleep(min(5 * attempt, 15))

            data = dict(resultado.data or {})
            data.update(run_counters(portal_run.id))
            resultado.data = data
            detectadas_portal = int(data.get('total', 0) or 0)
            if _resultado_portal_valido(resultado):
                save_errors = int(data.get('errores', 0) or 0)
                if save_errors:
                    lifecycle_result = {
                        'reliable': False,
                        'baseline': False,
                        'seen': 0,
                        'possible': 0,
                        'retired': 0,
                        'reason': (
                            f'La ejecución reportó {save_errors} error(es); '
                            'no se evaluaron ausencias.'
                        ),
                    }
                    fail_portal_run(
                        portal_run,
                        lifecycle_result['reason'],
                        status='incomplete',
                        execution_token=execution_token,
                    )
                else:
                    record_progress(portal_run.id, {'discovery': data['discovery']}, execution_token)
                    lifecycle_result = finalize_portal_run(portal_run, execution_token=execution_token)
                successful_portals += 1
                _actualizar_contadores(job, data, base_counters)
                _registrar_resultado_portal(
                    job, portal, 'completed', data, resultado.message
                )
                _crear_log(
                    job, 'success',
                    f'✅ {portal.upper()} completado: '
                    f'{detectadas_portal} detectadas, '
                    f'{data.get("nuevas", 0)} nuevas, '
                    f'{data.get("actualizadas", 0)} actualizadas, '
                    f'{data.get("errores", 0)} errores',
                    portal=portal,
                )
                if lifecycle_result['baseline']:
                    _crear_log(
                        job,
                        'info',
                        f'📍 {portal.upper()}: línea base creada con '
                        f'{lifecycle_result["seen"]} publicaciones; todavía '
                        'no se evaluaron desapariciones.',
                        portal=portal,
                    )
                elif lifecycle_result['reliable']:
                    _crear_log(
                        job,
                        'info',
                        f'📊 {portal.upper()}: ciclo de vida actualizado · '
                        f'{lifecycle_result["possible"]} posibles retiradas · '
                        f'{lifecycle_result["retired"]} retiros confirmados.',
                        portal=portal,
                    )
                else:
                    _crear_log(
                        job,
                        'warning',
                        f'⚠️ {portal.upper()}: {lifecycle_result["reason"]}',
                        portal=portal,
                    )
            else:
                failed_portals.append(portal)
                if resultado.success:
                    failure_message = (f'{portal.upper()}: recorrido incompleto · '
                        f'{(data.get("discovery") or {}).get("stop_reason", "unknown")} · '
                        f'{data.get("total", 0)} guardadas. No se evaluaron ausencias.')
                else:
                    failure_message = resultado.message
                _actualizar_contadores(job, data, base_counters)
                fail_portal_run(portal_run, failure_message, status='incomplete', execution_token=execution_token)
                _registrar_resultado_portal(
                    job, portal, 'incomplete', data, failure_message
                )
                _crear_log(
                    job, 'error',
                    f'❌ {portal.upper()} falló: {failure_message}',
                    portal=portal,
                )

        except Exception as e:
            job.refresh_from_db()
            if job.estado != 'running' or job.execution_token != execution_token:
                return
            if portal_run is not None:
                from ingestas.lifecycle import fail_portal_run
                fail_portal_run(portal_run, str(e), status='error', execution_token=execution_token)
            failed_portals.append(portal)
            _registrar_resultado_portal(job, portal, 'error', mensaje=str(e))
            _crear_log(
                job, 'error',
                f'💥 Excepción en {portal.upper()}: {e}',
                portal=portal,
            )
            logger.exception(f"Error en scraper {portal}: {e}")

        job.refresh_from_db()
        if (
            job.estado != 'running'
            or job.execution_token != execution_token
        ):
            _crear_log(job, 'info', f'⏹️  Scraping detenido tras {portal}')
            return

    # ── Finalizar ──
    job.refresh_from_db()
    if job.estado != 'running' or job.execution_token != execution_token:
        return
    if job.total_propiedades <= 0:
        final_state = 'error'
        final_error = 'No se detectó ninguna propiedad en los portales seleccionados.'
    elif failed_portals:
        final_state = 'error'
        final_error = (
            'Ejecución parcial: fallaron los portales '
            + ', '.join(sorted(set(failed_portals)))
            + '.'
        )
    elif successful_portals:
        final_state = 'completed'
        final_error = None
    else:
        final_state = 'error'
        final_error = 'Ningún portal terminó correctamente.'
    finalized = ScrapingJob.objects.filter(
        id=job.id,
        estado='running',
        execution_token=execution_token,
    ).update(
        estado=final_state,
        execution_token=None,
        mensaje_error=final_error,
        progreso=100,
        portal_actual=None,
        completado_en=timezone.now(),
    )
    if finalized != 1:
        return
    job.refresh_from_db()

    resumen = (
        f'🎯 Scraping completado: {job.total_propiedades} detectadas, '
        f'{job.nuevas} nuevas, '
        f'{job.actualizadas} actualizadas, {job.errores} errores'
        if job.estado == 'completed'
        else (
            f'❌ Scraping finalizado con error: '
            f'{job.total_propiedades} detectadas, {job.nuevas} nuevas, '
            f'{job.actualizadas} actualizadas, {job.errores} errores'
        )
    )
    _crear_log(job, 'success' if job.estado == 'completed' else 'info', resumen)
    logger.info(f"ScrapingJob #{job_id}: {resumen}")


@shared_task(
    bind=True,
    max_retries=1,
    soft_time_limit=SCRAPING_TASK_SOFT_TIME_LIMIT,
    time_limit=SCRAPING_TASK_TIME_LIMIT,
)
def scraping_task(self, job_id: int):
    """
    Versión Celery de _run_scraping.
    """
    _run_scraping(job_id)


def scraping_task_run(job_id: int):
    """
    Versión threading de _run_scraping (sin Celery).
    Útil para desarrollo local.
    """
    _run_scraping(job_id)
