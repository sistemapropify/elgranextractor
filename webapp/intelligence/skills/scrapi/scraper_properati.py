"""
ScraperProperatiSkill â€” Skill independiente.

Scrapea propiedades de Properati.com.pe y las guarda en PropiedadesCompetencia.
Reutiliza la lÃ³gica de extracciÃ³n de scrapi/properati_scraper.py.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time as _time
from datetime import datetime
from typing import Any, Callable, Dict

from intelligence.skills.base import BaseSkill, SkillResult
from .db_utils import guardar_propiedades

logger = logging.getLogger(__name__)

# Anti-cuelgue: timeouts (mismo criterio que REMAX). Perfil efímero (sin user_data_dir).
CAMOUFOX_LAUNCH_TIMEOUT = int(os.environ.get('CAMOUFOX_LAUNCH_TIMEOUT', '600'))
CAMOUFOX_TOTAL_TIMEOUT = int(os.environ.get('CAMOUFOX_TOTAL_TIMEOUT', '2700'))


def _ejecutar_scraping(
    max_paginas: int = 0,
    start_page: int = 1,
    progress_callback: Callable[[Dict[str, Any]], bool] | None = None,
    batch_callback: Callable[[list[Dict[str, Any]]], Dict[str, int]] | None = None,
) -> list[Dict[str, Any]]:
    """
    Ejecuta el scraping de Properati y retorna lista de propiedades estandarizadas.
    
    Args:
        max_paginas: MÃ¡ximo de pÃ¡ginas a scrapear. 0 = todas.
    
    Returns:
        Lista de dicts con formato estandarizado listo para guardar en DB.
    """
    from scrapi import properati_scraper as properati_source
    from scrapi.properati_scraper import (
        TOTAL_PAGINAS, GUARDAR_CADA_N_PAGINAS, BASE_URL,
        estandarizar, extraer_listado, extraer_detalle,
        navegar_con_cloudflare, manejar_sigint,
        mapear_a_formato_remax,
    )
    from camoufox.async_api import AsyncCamoufox
    from scrapi.camoufox_launcher import camoufox_kwargs
    import signal

    async def _run():
        # Cada ejecuciÃ³n es independiente. Una seÃ±al de detenciÃ³n anterior no
        # puede cancelar silenciosamente el siguiente trabajo.
        properati_source.detener = False
        todas_raw = []
        paginas = max_paginas if max_paginas > 0 else TOTAL_PAGINAS
        pagina_inicial = max(1, min(int(start_page or 1), paginas))

        async def emit_progress(**payload):
            if not progress_callback:
                return True
            return await asyncio.to_thread(progress_callback, payload)

        def estandarizar_lote(raw_items):
            fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            estandarizadas = []
            for prop in raw_items:
                try:
                    mapeada = mapear_a_formato_remax(prop)
                    std = estandarizar(mapeada, fecha_extraccion, "Properati")
                    std['fuente'] = 'properati'
                    std['datos_crudos'] = {
                        k: str(v) if not isinstance(v, (dict, list, type(None))) else v
                        for k, v in prop.items()
                    }
                    estandarizadas.append(std)
                except Exception as exc:
                    logger.warning("[properati] Error estandarizando: %s", exc)
            return estandarizadas

        try:
            signal.signal(signal.SIGINT, manejar_sigint)
        except (ValueError, RuntimeError):
            pass

        t0 = _time.monotonic()
        if not await emit_progress(
            percent=0,
            processed=0,
            message=(
                f'Properati: lanzando navegador Camoufox '
                f'(timeout {CAMOUFOX_LAUNCH_TIMEOUT}s)'
            ),
        ):
            return []

        async with AsyncCamoufox(
            **camoufox_kwargs(),
        ) as browser:
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            print("=" * 60)
            print(f"SCRAPER PROPERATI - {paginas} paginas")
            print("=" * 60)

            for n in range(pagina_inicial, paginas + 1):
                if properati_source.detener:
                    break
                if not await emit_progress(
                    percent=int(((n - 1) / max(paginas, 1)) * 70),
                    processed=len(todas_raw),
                    message=f'Properati: leyendo pÃ¡gina {n} de {paginas}',
                ):
                    break
                url = BASE_URL if n == 1 else f"{BASE_URL}/{n}"
                print(f"\n[Pagina {n}/{paginas}]: {url}")
                try:
                    await navegar_con_cloudflare(page, url)
                    props = await extraer_listado(page)

                    # Completar cada lote antes de publicarlo en el dashboard.
                    # Antes las coordenadas se buscaban recién después de leer
                    # todas las páginas, por eso la tabla permanecía vacía
                    # durante casi toda la ejecución.
                    for detail_index, prop in enumerate(props, 1):
                        if properati_source.detener:
                            break
                        # Completar tanto coordenadas como imagenes.
                        if (not prop.get('Coordenadas') or '/propiedadesimagenes/' not in str(prop.get('Imagen URL') or '')):
                            await extraer_detalle(page, prop)
                            await asyncio.sleep(0.35)
                        if detail_index == 1 or detail_index % 10 == 0:
                            if not await emit_progress(
                                percent=int(((n - 1) / max(paginas, 1)) * 99),
                                processed=len(todas_raw) + detail_index,
                                message=(
                                    f'Properati: completando coordenadas de la '
                                    f'página {n} ({detail_index}/{len(props)})'
                                ),
                            ):
                                break

                    todas_raw.extend(props)
                    print(f"   -> {len(props)} props (total: {len(todas_raw)})")
                    if batch_callback and props:
                        batch = estandarizar_lote(props)
                        if batch:
                            saved = await asyncio.to_thread(batch_callback, batch)
                            if saved:
                                if not await emit_progress(
                                    percent=int((n / max(paginas, 1)) * 70),
                                    processed=saved.get('total', len(todas_raw)),
                                    nuevas=saved.get('nuevas', 0),
                                    actualizadas=saved.get('actualizadas', 0),
                                    errores=saved.get('errores', 0),
                                    checkpoint_page=n,
                                    message=(
                                        f"Properati: {saved.get('total', 0)} "
                                        f"procesadas ({saved.get('nuevas', 0)} nuevas)"
                                    ),
                                ):
                                    break
                except Exception as e:
                    print(f"   [ERROR] Pagina {n}: {e}")
                    raise RuntimeError(
                        f"Properati fallo en pagina {n}; checkpoint previo conservado"
                    ) from e

            # FASE 2: Reintento de coordenadas o imagenes faltantes
            if todas_raw:
                incompletas = [p for p in todas_raw if not p.get('Coordenadas') or '/propiedadesimagenes/' not in str(p.get('Imagen URL') or '')]
                if incompletas:
                    print(f"\nFASE 2: Detalles pendientes ({len(incompletas)} props)...")
                    for i, prop in enumerate(incompletas):
                        if properati_source.detener:
                            break
                        if not await emit_progress(
                            percent=70 + int((i / max(len(incompletas), 1)) * 29),
                            processed=len(todas_raw),
                            message=(
                                f'Properati: completando detalles '
                                f'{i + 1} de {len(incompletas)}'
                                if i == 0 or (i + 1) % 25 == 0
                                else ''
                            ),
                        ):
                            break
                        prop_id = prop.get('ID', '')
                        ubic = prop.get('Ubicacion', '')
                        print(f"  [{i+1}/{len(incompletas)}] ID: {prop_id} - {ubic}")
                        await emit_progress(message=f'Properati: [{i+1}/{len(incompletas)}] ID: {prop_id} - {ubic}')
                        await extraer_detalle(page, prop)
                        await asyncio.sleep(0.5)

            await page.close()

        estandarizadas = estandarizar_lote(todas_raw)
        await emit_progress(
            percent=99,
            processed=len(estandarizadas),
            message='Properati: consolidando resultados finales',
        )
        return estandarizadas

    # Timeout total: nunca quedarse "activo" indefinidamente
    try:
        return asyncio.run(
            asyncio.wait_for(_run(), timeout=CAMOUFOX_TOTAL_TIMEOUT)
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f'PROPERATI superó el timeout total de {CAMOUFOX_TOTAL_TIMEOUT}s '
            f'sin terminar. Se canceló para no quedar colgado.'
        )


class ScraperProperatiSkill(BaseSkill):
    name = "scraper_properati"
    description = (
        "Scrapea propiedades de Properati.com.pe en Arequipa y las guarda "
        "en la tabla PropiedadesCompetencia."
    )
    category = "custom"
    access_level = 1
    is_active = True

    parameters_schema = {
        'max_paginas': {
            'type': 'integer',
            'description': 'MÃ¡ximo de pÃ¡ginas a scrapear. 0 = todas (default: 0).',
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
            incremental = {
                'total': 0,
                'nuevas': 0,
                'actualizadas': 0,
                'errores': 0,
            }

            def guardar_lote(propiedades_lote):
                resultado_lote = guardar_propiedades(
                    propiedades_lote, fuente='properati'
                )
                for key in incremental:
                    incremental[key] += int(resultado_lote.get(key, 0) or 0)
                return incremental.copy()

            propiedades = _ejecutar_scraping(
                max_paginas,
                start_page=start_page,
                progress_callback=progress_callback,
                batch_callback=guardar_lote,
            )

            if not propiedades:
                return SkillResult.error(
                    message=(
                        'Properati no devolviÃ³ propiedades. La ejecuciÃ³n no se '
                        'considera exitosa; revise navegaciÃ³n, Cloudflare y logs.'
                    ),
                    skill_name=self.name,
                )

            # Segunda pasada: persiste coordenadas y detalles obtenidos despuÃ©s
            # del guardado incremental. Los contadores conservan la primera
            # clasificaciÃ³n nueva/actualizada para no contar dos veces.
            guardar_propiedades(propiedades, fuente='properati')
            resultado = incremental

            return SkillResult.ok(
                data={
                    'portal': 'properati',
                    **resultado,
                },
                message=(
                    f"Properati: {resultado['nuevas']} nuevas, "
                    f"{resultado['actualizadas']} actualizadas, "
                    f"{resultado['errores']} errores / {resultado['total']} total"
                ),
                skill_name=self.name,
            )

        except Exception as e:
            logger.exception(f"[properati] Error en ejecuciÃ³n: {e}")
            return SkillResult.error(
                message=f"Error en scraper Properati: {e}",
                skill_name=self.name,
            )

