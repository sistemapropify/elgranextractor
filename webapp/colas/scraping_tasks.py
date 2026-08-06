"""
Tareas Celery para scraping de portales inmobiliarios.

Lee el estado del ScrapingJob para controlar pausa/reanudar/detención.
Crea ScrapingLog por cada propiedad procesada para el terminal en vivo.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, Any, List

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

# Orden de ejecución por defecto
ORDEN_DEFECTO = ['remax', 'adondevivir', 'properati', 'urbania']


def _resultado_portal_valido(resultado) -> bool:
    """Solo acepta como éxito una extracción que detectó propiedades."""
    data = resultado.data or {}
    return bool(
        resultado.success
        and int(data.get('total', 0) or 0) > 0
    )


def _instanciar_skill(portal: str):
    """Importa dinámicamente la skill del portal y retorna una instancia."""
    skill_map = {
        'remax': 'scraper_remax',
        'adondevivir': 'scraper_adondevivir',
        'properati': 'scraper_properati',
        'urbania': 'scraper_urbania',
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
    ScrapingJob.objects.filter(id=job.id).update(**updates)
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

    job.refresh_from_db()
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
    }
    parametros['resultados_por_portal'] = resultados
    ScrapingJob.objects.filter(id=job.id).update(parametros=parametros)
    job.parametros = parametros


def _crear_log(job, nivel: str, mensaje: str, portal: str = None,
               propiedad_id: str = None) -> int:
    """Crea un ScrapingLog y retorna su ID (para SSE)."""
    from ingestas.models import ScrapingLog
    log = ScrapingLog.log(job, nivel, mensaje, portal, propiedad_id)
    return log.id


def _run_scraping(job_id: int):
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

    portales = (job.parametros or {}).get('portales') or ORDEN_DEFECTO
    job.estado = 'running'
    job.iniciado_en = timezone.now()
    job.save()

    _crear_log(job, 'info', f'🚀 Scraping iniciado con {len(portales)} portales')
    total_portales = len(portales)
    successful_portals = 0
    failed_portals = []

    for idx, portal in enumerate(portales, 1):
        # ── Verificar estado antes de cada portal ──
        job.refresh_from_db()

        if job.estado == 'stopped':
            _crear_log(job, 'info', f'⏹️ Scraping detenido en portal {portal}')
            job.completado_en = timezone.now()
            job.save()
            return

        while job.estado == 'paused':
            _crear_log(job, 'info', f'⏸️  Pausado antes de {portal}')
            time.sleep(2)
            job.refresh_from_db()
            if job.estado == 'stopped':
                job.completado_en = timezone.now()
                job.save()
                return

        # ── Ejecutar scraper ──
        job.portal_actual = portal
        job.progreso = int((idx - 1) / total_portales * 100)
        job.save()

        _crear_log(job, 'info', f'🔍 Iniciando scraper {portal.upper()}...')

        try:
            skill = _instanciar_skill(portal)
            _crear_log(job, 'info', f'⚙️  Ejecutando {portal.upper()}...')
            base_counters = {
                'total_propiedades': job.total_propiedades,
                'procesadas': job.procesadas,
                'nuevas': job.nuevas,
                'actualizadas': job.actualizadas,
                'errores': job.errores,
            }

            def reportar_progreso(payload):
                """Sincroniza progreso interno de la skill y controla cancelación."""
                nonlocal job
                job.refresh_from_db()
                while job.estado == 'paused':
                    time.sleep(2)
                    job.refresh_from_db()
                if job.estado == 'stopped':
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
                    'progreso': overall,
                    'portal_actual': portal,
                }
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
                if checkpoint_page is not None:
                    parametros = dict(job.parametros or {})
                    checkpoints = dict(parametros.get('checkpoints') or {})
                    checkpoints[portal] = max(
                        int(checkpoints.get(portal, 0) or 0),
                        int(checkpoint_page),
                    )
                    parametros['checkpoints'] = checkpoints
                    updates['parametros'] = parametros

                ScrapingJob.objects.filter(id=job.id).update(**updates)

                message = payload.get('message')
                if message:
                    _crear_log(job, 'info', message, portal=portal)
                return True

            # Ejecutar con reintentos controlados. Properati y Adondevivir
            # pueden quedar temporalmente sin respuesta al iniciar Camoufox;
            # el segundo intento usa el mismo checkpoint confirmado.
            max_attempts = 3 if portal == 'properati' else (
                2 if portal == 'adondevivir' else 1
            )
            resultado = None
            for attempt in range(1, max_attempts + 1):
                job.refresh_from_db()
                parametros = dict(job.parametros or {})
                checkpoints = dict(parametros.get('checkpoints') or {})
                start_page = int(checkpoints.get(portal, 0) or 0) + 1
                base_counters = {
                    'total_propiedades': job.total_propiedades,
                    'procesadas': job.procesadas,
                    'nuevas': job.nuevas,
                    'actualizadas': job.actualizadas,
                    'errores': job.errores,
                }
                skill = _instanciar_skill(portal)
                resultado = skill.execute(
                    {'max_paginas': 0, 'start_page': start_page},
                    context={'progress_callback': reportar_progreso},
                )
                if resultado.success:
                    break
                if attempt < max_attempts:
                    terminated = 0
                    if portal == 'adondevivir':
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

            data = resultado.data or {}
            detectadas_portal = int(data.get('total', 0) or 0)
            if _resultado_portal_valido(resultado):
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
            else:
                failed_portals.append(portal)
                if resultado.success:
                    failure_message = (
                        f'{portal.upper()} no detectó ninguna propiedad. '
                        'La extracción vacía no se considera completada.'
                    )
                else:
                    failure_message = resultado.message
                _registrar_resultado_portal(
                    job, portal, 'error', data, failure_message
                )
                _crear_log(
                    job, 'error',
                    f'❌ {portal.upper()} falló: {failure_message}',
                    portal=portal,
                )

        except Exception as e:
            failed_portals.append(portal)
            _registrar_resultado_portal(job, portal, 'error', mensaje=str(e))
            _crear_log(
                job, 'error',
                f'💥 Excepción en {portal.upper()}: {e}',
                portal=portal,
            )
            logger.exception(f"Error en scraper {portal}: {e}")

        job.refresh_from_db()
        if job.estado == 'stopped':
            _crear_log(job, 'info', f'⏹️  Scraping detenido tras {portal}')
            break

    # ── Finalizar ──
    job.refresh_from_db()
    if job.estado != 'stopped':
        if job.total_propiedades <= 0:
            job.estado = 'error'
            job.mensaje_error = (
                'No se detectó ninguna propiedad en los portales seleccionados.'
            )
        elif failed_portals:
            job.estado = 'error'
            job.mensaje_error = (
                'Ejecución parcial: fallaron los portales '
                + ', '.join(sorted(set(failed_portals)))
                + '.'
            )
        elif successful_portals:
            job.estado = 'completed'
        else:
            job.estado = 'error'
            job.mensaje_error = 'Ningún portal terminó correctamente.'
    job.progreso = 100
    job.portal_actual = None
    job.completado_en = timezone.now()
    job.save()

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


@shared_task(bind=True, max_retries=1)
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
