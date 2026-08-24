"""
ScraperRemaxSkill — Skill independiente.

Scrapea propiedades de Remax.pe y las guarda en PropiedadesCompetencia.
Reutiliza la lógica de extracción de scrapi/remax_scraper.py.

Anti-cuelgue: el arranque de Camoufox con perfil persistente puede colgarse
si un run anterior fue matado y dejó locks stale en ./camoufox_session.
Por eso se limpian locks viejos antes de lanzar y se pone un timeout de
arranque + un timeout total (configurables por env):
    CAMOUFOX_LAUNCH_TIMEOUT  (default 600s)
    CAMOUFOX_TOTAL_TIMEOUT   (default 2700s = 45min)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time as _time
from datetime import datetime
from typing import Any, Dict

from intelligence.skills.base import BaseSkill, SkillResult
from .db_utils import guardar_propiedades

logger = logging.getLogger(__name__)

# Timeouts (evitan que el scraper se quede "activo" colgado para siempre)
CAMOUFOX_LAUNCH_TIMEOUT = int(os.environ.get('CAMOUFOX_LAUNCH_TIMEOUT', '600'))
CAMOUFOX_TOTAL_TIMEOUT = int(os.environ.get('CAMOUFOX_TOTAL_TIMEOUT', '2700'))
LOCK_STALE_SECONDS = int(os.environ.get('CAMOUFOX_LOCK_STALE_SECONDS', '120'))


def _limpiar_locks_stale(profile_dir: str, max_age_s: int = LOCK_STALE_SECONDS) -> None:
    """Borra locks de Firefox/Camoufox viejos de un perfil persistente.

    Un run matado (huérfano) deja `parent.lock`/`SingletonLock` y el arranque
    siguiente de Camoufox puede colgarse esperando ese lock. Solo se borran
    locks con más de `max_age_s` segundos de antigüedad para no romper un
    perfil que esté en uso por otro proceso.
    """
    try:
        if not os.path.isdir(profile_dir):
            return
        for nombre in ('parent.lock', 'SingletonLock', 'lock', '.parentlock'):
            p = os.path.join(profile_dir, nombre)
            try:
                if os.path.exists(p) and (os.path.getmtime(p) + max_age_s) < _time.time():
                    os.remove(p)
                    print(f'[remax] Lock stale eliminado: {p}')
            except OSError:
                pass
    except Exception:  # noqa: BLE001
        pass


def _ejecutar_scraping(
    max_paginas: int = 0,
    start_page: int = 1,
    progress_callback=None,
) -> list[Dict[str, Any]]:
    """
    Ejecuta el scraping de Remax y retorna lista de propiedades estandarizadas.

    Args:
        max_paginas: Máximo de páginas a scrapear. 0 = todas.

    Returns:
        Lista de dicts con formato estandarizado listo para guardar en DB.
    """
    def report(payload):
        if not progress_callback:
            return True
        try:
            return progress_callback(payload) is not False
        except Exception:
            logger.exception('[remax] Error reportando progreso')
            return True
    report({'percent': 0, 'message': 'Remax: cargando motor de navegador'})

    # Importar funciones del scraper original (reutilizar, no duplicar)
    from scrapi.remax_scraper import (
        TOTAL_PAGES, GUARDAR_CADA_N_PAGINAS,
        estandarizar, extraer_listado, extraer_detalle,
        navegar_con_cloudflare, manejar_sigint, detener,
    )
    from camoufox.async_api import AsyncCamoufox
    from scrapi.camoufox_launcher import camoufox_kwargs
    import signal

    async def _abrir_navegador():
        # __aenter__ en un await para poder ponerle timeout de arranque.
        # Se reporta CADA etapa del arranque para ver el proceso en vivo
        # (dependencias -> binario -> spawn del navegador). En producción
        # Camoufox va en headless (sin ventana), así que el dashboard es la
        # única forma de ver que está arrancando.
        report({
            'percent': 0,
            'message': 'Remax: verificando dependencias y binario de Camoufox...',
        })
        options = camoufox_kwargs(
            _progress_callback=lambda message: report({
                'percent': 0,
                'message': f'Remax: {message}',
            }),
            persistent_context=True,
            user_data_dir='./camoufox_session',
        )
        report({
            'percent': 0,
            'message': (
                'Remax: binario listo; arrancando el proceso del navegador...'
            ),
        })
        return await AsyncCamoufox(**options).__aenter__()

    async def _run():
        todas_raw = []
        paginas = max_paginas if max_paginas > 0 else TOTAL_PAGES
        try:
            signal.signal(signal.SIGINT, manejar_sigint)
        except (ValueError, RuntimeError):
            pass  # No disponible en hilos secundarios

        t0 = _time.monotonic()
        report({
            'percent': 0,
            'message': (
                f'Remax: lanzando navegador Camoufox '
                f'(timeout {CAMOUFOX_LAUNCH_TIMEOUT}s)...'
            ),
        })
        try:
            browser = await asyncio.wait_for(
                _abrir_navegador(), timeout=CAMOUFOX_LAUNCH_TIMEOUT
            )
        except asyncio.TimeoutError:
            report({
                'message': (
                    f'Remax: ERROR — el navegador no arrancó en '
                    f'{CAMOUFOX_LAUNCH_TIMEOUT}s (perfil bloqueado o colgado). '
                    f'Se limpiaron locks stale de ./camoufox_session. Reintente.'
                ),
            })
            raise RuntimeError(
                f'Camoufox no arrancó en {CAMOUFOX_LAUNCH_TIMEOUT}s para REMAX '
                f'(perfil ./camoufox_session bloqueado o navegador colgado).'
            )

        try:
            report({
                'percent': 1,
                'message': (
                    f'Remax: navegador listo en {int(_time.monotonic() - t0)}s; '
                    f'abriendo listados'
                ),
            })
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            print("=" * 60)
            print(f"SCRAPER REMAX - {paginas} paginas")
            print("=" * 60)

            for n in range(max(1, start_page), paginas + 1):
                if detener:
                    break
                from scrapi.remax_scraper import BASE_URL
                url = BASE_URL.format(n)
                print(f"\n[Pagina {n}/{paginas}]: {url}")
                report({'message': f'Remax: abriendo [Pagina {n}/{paginas}]: {url}'})
                try:
                    await navegar_con_cloudflare(page, url)
                    props = await extraer_listado(page)
                    todas_raw.extend(props)
                    print(f"   -> {len(props)} props (total: {len(todas_raw)})")
                    if not report({
                        'percent': max(2, int((n / paginas) * 45)),
                        'processed': len(todas_raw),
                        'message': (
                            f'Remax: página {n}/{paginas} · '
                            f'{len(todas_raw)} propiedades detectadas'
                        ),
                    }):
                        break
                except Exception as e:
                    print(f"   [ERROR] Pagina {n}: {e}")

            # FASE 2: Detalles para coordenadas
            if todas_raw:
                print(f"\nFASE 2: Detalles ({len(todas_raw)} props)...")
                for i, prop in enumerate(todas_raw):
                    if detener:
                        break
                    distrito = prop.get('Distrito', '')
                    prop_id = prop.get('ID', '')
                    print(f"  [{i+1}/{len(todas_raw)}] ID: {prop_id} - {distrito}")
                    report({'message': f'Remax: [{i+1}/{len(todas_raw)}] ID: {prop_id} - {distrito}'})
                    await extraer_detalle(page, prop)
                    if i == 0 or (i + 1) % 10 == 0 or i + 1 == len(todas_raw):
                        report({
                            'percent': 45 + int(((i + 1) / len(todas_raw)) * 50),
                            'processed': len(todas_raw),
                            'message': (
                                f'Remax: completando detalles {i + 1}/'
                                f'{len(todas_raw)}'
                            ),
                        })
                    await asyncio.sleep(0.5)

            await page.close()
        finally:
            await browser.__aexit__(None, None, None)

        # Estandarizar todas las propiedades
        fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        estandarizadas = []
        for prop in todas_raw:
            try:
                std = estandarizar(prop, fecha_extraccion)
                std['fuente'] = 'remax'
                # Guardar RAW para QA
                raw_copy = {k: v for k, v in prop.items()}
                std['datos_crudos'] = raw_copy
                estandarizadas.append(std)
            except Exception as e:
                logger.warning(f"[remax] Error estandarizando propiedad: {e}")

        return estandarizadas

    # Limpiar locks stale del perfil persistente (cuelgues de runs anteriores)
    _limpiar_locks_stale('./camoufox_session')

    # Timeout total de seguridad: nunca quedarse "activo" indefinidamente
    try:
        return asyncio.run(
            asyncio.wait_for(_run(), timeout=CAMOUFOX_TOTAL_TIMEOUT)
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f'REMAX superó el timeout total de {CAMOUFOX_TOTAL_TIMEOUT}s '
            f'sin terminar. Se canceló para no quedar colgado.'
        )


class ScraperRemaxSkill(BaseSkill):
    name = "scraper_remax"
    description = (
        "Scrapea propiedades de Remax.pe en Arequipa y las guarda "
        "en la tabla PropiedadesCompetencia. Ejecución secuencial por páginas."
    )
    category = "custom"
    access_level = 1
    is_active = True

    parameters_schema = {
        'max_paginas': {
            'type': 'integer',
            'description': 'Máximo de páginas a scrapear. 0 = todas (default: 0).',
            'required': False,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> SkillResult:
        try:
            max_paginas = params.get('max_paginas', 0)
            start_page = params.get('start_page', 1)
            progress_callback = (context or {}).get('progress_callback')
            propiedades = _ejecutar_scraping(
                max_paginas, start_page, progress_callback
            )

            if not propiedades:
                return SkillResult.error(
                    message=(
                        'Remax no devolvió propiedades. Revise la navegación, '
                        'el bloqueo del portal y los logs de extracción.'
                    ),
                    skill_name=self.name,
                )

            resultado = guardar_propiedades(propiedades, fuente='remax')

            return SkillResult.ok(
                data={
                    'portal': 'remax',
                    **resultado,
                },
                message=(
                    f"Remax: {resultado['nuevas']} nuevas, "
                    f"{resultado['actualizadas']} actualizadas, "
                    f"{resultado['errores']} errores / {resultado['total']} total"
                ),
                skill_name=self.name,
            )

        except Exception as e:
            logger.exception(f"[remax] Error en ejecución: {e}")
            return SkillResult.error(
                message=f"Error en scraper Remax: {e}",
                skill_name=self.name,
            )
