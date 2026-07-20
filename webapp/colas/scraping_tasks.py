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


def _actualizar_contadores(job, resultado: Dict[str, int]):
    """Actualiza contadores del job con el resultado de un scraper."""
    job.procesadas += resultado.get('total', 0)
    job.nuevas += resultado.get('nuevas', 0)
    job.actualizadas += resultado.get('actualizadas', 0)
    job.errores += resultado.get('errores', 0)
    job.save()


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

    portales = job.parametros.get('portales', ORDEN_DEFECTO)
    job.estado = 'running'
    job.iniciado_en = timezone.now()
    job.save()

    _crear_log(job, 'info', f'🚀 Scraping iniciado con {len(portales)} portales')
    total_portales = len(portales)

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

            # Ejecutar el scraper
            resultado = skill.execute({'max_paginas': 0})

            if resultado.success:
                data = resultado.data or {}
                _actualizar_contadores(job, data)
                _crear_log(
                    job, 'success',
                    f'✅ {portal.upper()} completado: '
                    f'{data.get("nuevas", 0)} nuevas, '
                    f'{data.get("actualizadas", 0)} actualizadas, '
                    f'{data.get("errores", 0)} errores',
                    portal=portal,
                )
            else:
                _crear_log(
                    job, 'error',
                    f'❌ {portal.upper()} falló: {resultado.message}',
                    portal=portal,
                )
                job.errores += 1

        except Exception as e:
            _crear_log(
                job, 'error',
                f'💥 Excepción en {portal.upper()}: {e}',
                portal=portal,
            )
            job.errores += 1
            logger.exception(f"Error en scraper {portal}: {e}")

        job.refresh_from_db()
        if job.estado == 'stopped':
            _crear_log(job, 'info', f'⏹️  Scraping detenido tras {portal}')
            break

    # ── Finalizar ──
    job.refresh_from_db()
    if job.estado != 'stopped':
        job.estado = 'completed'
    job.progreso = 100
    job.portal_actual = None
    job.completado_en = timezone.now()
    job.save()

    resumen = (
        f'🎯 Scraping completado: {job.nuevas} nuevas, '
        f'{job.actualizadas} actualizadas, {job.errores} errores'
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
