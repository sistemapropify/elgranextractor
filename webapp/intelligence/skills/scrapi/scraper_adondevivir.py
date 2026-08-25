"""
ScraperAdondevivirSkill ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Skill independiente.

Scrapea propiedades de Adondevivir.com y las guarda en PropiedadesCompetencia.
Reutiliza la lÃƒÆ’Ã‚Â³gica de extracciÃƒÆ’Ã‚Â³n de scrapi/adondevivir_scraper.py.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time as _time
from datetime import datetime
from typing import Any, Dict, Callable

from intelligence.skills.base import BaseSkill, SkillResult
from .db_utils import guardar_propiedades

logger = logging.getLogger(__name__)

# Anti-cuelgue: timeouts y limpieza de locks stale (mismo criterio que REMAX)
CAMOUFOX_LAUNCH_TIMEOUT = int(os.environ.get('CAMOUFOX_LAUNCH_TIMEOUT', '600'))
CAMOUFOX_TOTAL_TIMEOUT = int(os.environ.get('CAMOUFOX_TOTAL_TIMEOUT', '2700'))
LOCK_STALE_SECONDS = int(os.environ.get('CAMOUFOX_LOCK_STALE_SECONDS', '120'))


def _limpiar_locks_stale(profile_dir: str, max_age_s: int = LOCK_STALE_SECONDS) -> None:
    """Borra locks de Firefox/Camoufox viejos de un perfil persistente."""
    try:
        if not os.path.isdir(profile_dir):
            return
        for nombre in ('parent.lock', 'SingletonLock', 'lock', '.parentlock'):
            p = os.path.join(profile_dir, nombre)
            try:
                if os.path.exists(p) and (os.path.getmtime(p) + max_age_s) < _time.time():
                    os.remove(p)
                    print(f'[adondevivir] Lock stale eliminado: {p}')
            except OSError:
                pass
    except Exception:  # noqa: BLE001
        pass


def _ejecutar_scraping(
    max_paginas: int = 0,
    start_page: int = 1,
    progress_callback: Callable[[Dict[str, Any]], bool] | None = None,
    batch_callback: Callable[[list[Dict[str, Any]]], Dict[str, int]] | None = None,
    update_callback: Callable[[list[Dict[str, Any]]], Any] | None = None,
) -> list[Dict[str, Any]]:
    """
    Ejecuta el scraping de Adondevivir y retorna lista de propiedades estandarizadas.
    
    Args:
        max_paginas: MÃƒÆ’Ã‚Â¡ximo de pÃƒÆ’Ã‚Â¡ginas a scrapear. 0 = todas.
    
    Returns:
        Lista de dicts con formato estandarizado listo para guardar en DB.
    """
    # Importar funciones del scraper original
    from scrapi import adondevivir_scraper as adondevivir_source
    from scrapi.adondevivir_scraper import (
        LISTING_URL, GUARDAR_CADA_N_PAGINAS, PROPS_POR_PAGINA,
        estandarizar, extraer_listado, extraer_coordenadas_desde_detalle,
        navegar_con_cloudflare, manejar_sigint,
        mapear_a_formato_remax, subir_imagen_a_blob, obtener_numero_paginas,
        mapear_tipo_schemaorg,
    )
    from camoufox.async_api import AsyncCamoufox
    from scrapi.camoufox_launcher import camoufox_kwargs
    import signal
    import re

    async def _run():
        # La señal de detener pertenece al módulo original y puede quedar en
        # True después de una ejecución interrumpida. Cada job debe arrancar
        # limpio para no detenerse silenciosamente a mitad del listado.
        adondevivir_source.detener = False
        todas_raw = []

        async def emit_progress(**payload):
            if not progress_callback:
                return True
            return await asyncio.to_thread(progress_callback, payload)

        async def extraer_listado_con_limite(page, contexto: str):
            """Evita que un selector del portal deje un job activo sin avance."""
            try:
                return await asyncio.wait_for(extraer_listado(page), timeout=60)
            except TimeoutError as exc:
                raise RuntimeError(
                    f"Adondevivir no terminó de extraer {contexto} en 60 segundos"
                ) from exc

        async def obtener_paginas_con_limite(page):
            try:
                return await asyncio.wait_for(obtener_numero_paginas(page), timeout=45)
            except TimeoutError as exc:
                raise RuntimeError(
                    "Adondevivir no pudo determinar la cantidad de páginas en 45 segundos"
                ) from exc

        def estandarizar_lote(raw_items):
            fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            estandarizadas = []
            for prop in raw_items:
                try:
                    if prop.get("tipo") and not any(
                        palabra in prop["tipo"]
                        for palabra in ["Casa", "Departamento", "Terreno", "Local", "Oficina", "Alojamiento"]
                    ):
                        prop["tipo"] = mapear_tipo_schemaorg(prop["tipo"])
                    mapeada = mapear_a_formato_remax(prop)
                    std = estandarizar(mapeada, fecha_extraccion, "ADondevivir")
                    std["fuente"] = "adondevivir"
                    std["datos_crudos"] = {
                        k: str(v) if not isinstance(v, (dict, list, type(None))) else v
                        for k, v in prop.items()
                    }
                    estandarizadas.append(std)
                except Exception as exc:
                    logger.warning(f"[adondevivir] Error estandarizando: {exc}")
            return estandarizadas
        try:
            signal.signal(signal.SIGINT, manejar_sigint)
        except (ValueError, RuntimeError):
            pass

        t0 = _time.monotonic()
        await emit_progress(
            percent=0,
            processed=0,
            message=(
                "Adondevivir: lanzando navegador seguro "
                f"(timeout {CAMOUFOX_LAUNCH_TIMEOUT}s)"
            ),
        )

        async with AsyncCamoufox(
            **camoufox_kwargs(
                persistent_context=True,
                user_data_dir='./camoufox_session_adondevivir',
            ),
        ) as browser:
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            # FASE 1: Cargar primera pÃƒÆ’Ã‚Â¡gina para obtener total de pÃƒÆ’Ã‚Â¡ginas
            print("=" * 60)
            print("SCRAPER ADONDEVIVIR")
            print("=" * 60)

            await emit_progress(
                percent=1,
                processed=0,
                message="Adondevivir: navegador listo; cargando listado inicial",
            )
            exito = await navegar_con_cloudflare(page, LISTING_URL, timeout=30)
            if not exito:
                print("[!] No se pudo cargar la pÃƒÆ’Ã‚Â¡gina inicial")
                raise RuntimeError("Adondevivir no cargó el listado inicial")

            await emit_progress(
                percent=1,
                processed=0,
                message="Adondevivir: listado inicial cargado; extrayendo propiedades",
            )
            props_pagina1 = await extraer_listado_con_limite(page, "la página 1")
            if not props_pagina1:
                diagnostico = await page.evaluate("""
                    () => ({
                        title: document.title,
                        url: location.href,
                        anchorsDetalle: document.querySelectorAll('a[href*="/propiedades/"]').length,
                        dataToPosting: document.querySelectorAll('[data-to-posting]').length,
                        cardsPorClase: document.querySelectorAll('[class*="posting-card"]').length,
                        texto: (document.body?.innerText || '').slice(0, 180)
                    })
                """)
                resumen = (
                    "Adondevivir: listado sin tarjetas "
                    f"(enlaces={diagnostico.get('anchorsDetalle', 0)}, "
                    f"data-to-posting={diagnostico.get('dataToPosting', 0)}, "
                    f"clases={diagnostico.get('cardsPorClase', 0)})."
                )
                await emit_progress(percent=1, processed=0, message=resumen)
                raise RuntimeError(
                    f"{resumen} Título: {diagnostico.get('title', '')}."
                )
            if start_page <= 1:
                todas_raw.extend(props_pagina1)
            print(f"  [Pagina 1]: {len(props_pagina1)} props")
            await emit_progress(
                percent=2,
                processed=len(todas_raw),
                message=(
                    "Adondevivir: página 1, "
                    f"{len(props_pagina1)} propiedades detectadas"
                ),
            )
            if start_page <= 1 and batch_callback and props_pagina1:
                guardado = await asyncio.to_thread(
                    batch_callback, estandarizar_lote(props_pagina1)
                )
                await emit_progress(
                    percent=2,
                    processed=guardado.get("total", len(todas_raw)),
                    nuevas=guardado.get('nuevas'),
                    actualizadas=guardado.get('actualizadas'),
                    errores=guardado.get('errores'),
                    checkpoint_page=1,
                )

            # Usar el detector robusto del scraper principal.
            total_paginas = await obtener_paginas_con_limite(page)
            print(f"  Total de paginas detectadas: {total_paginas}")
            if not await emit_progress(
                percent=2,
                processed=len(todas_raw),
                message=f"Adondevivir: {total_paginas} paginas detectadas",
            ):
                return todas_raw

            if max_paginas > 0:
                total_paginas = min(total_paginas, max_paginas)

            # Resto de pÃƒÆ’Ã‚Â¡ginas
            for pagina in range(max(2, int(start_page or 1)), total_paginas + 1):
                if adondevivir_source.detener:
                    break

                # Delay aleatorio entre paginas para reducir deteccion de Cloudflare
                delay = random.uniform(2.0, 6.0)
                await asyncio.sleep(delay)

                if not await emit_progress(
                    percent=max(2, int(((pagina - 1) / max(total_paginas, 1)) * 70)),
                    processed=len(todas_raw),
                    message=f"Adondevivir: leyendo pagina {pagina} de {total_paginas}",
                ):
                    break
                url_pagina = f"https://www.adondevivir.com/inmuebles-en-venta-en-arequipa-pagina-{pagina}.html"
                print(f"\n[Pagina {pagina}/{total_paginas}]...")
                exito = await navegar_con_cloudflare(page, url_pagina)
                if not exito:
                    continue
                props = await extraer_listado_con_limite(page, f"la página {pagina}")
                todas_raw.extend(props)
                print(f"  -> {len(props)} props (total: {len(todas_raw)})")
                guardado = None
                if batch_callback and props:
                    guardado = await asyncio.to_thread(
                        batch_callback, estandarizar_lote(props)
                    )
                await emit_progress(
                    percent=max(2, int((pagina / max(total_paginas, 1)) * 70)),
                    processed=(guardado or {}).get('total', len(todas_raw)),
                    nuevas=(guardado or {}).get('nuevas'),
                    actualizadas=(guardado or {}).get('actualizadas'),
                    errores=(guardado or {}).get('errores'),
                    checkpoint_page=pagina,
                    message=(
                        f"Adondevivir: página {pagina}, "
                        f"{len(props)} propiedades detectadas"
                    ),
                )

            # FASE 2: Detalles para coordenadas, tipo e imagen persistida.
            props_a_visitar = [
                p for p in todas_raw
                if not p.get("latitud")
                or not p.get("longitud")
                or not p.get("tipo")
                or not p.get("imagen_url")
                or "blob.core.windows.net" not in str(p.get("imagen_url"))
            ]
            if props_a_visitar and not adondevivir_source.detener:
                print(f"\nFASE 2: Detalles ({len(props_a_visitar)} props)...")
                detalle_pendientes = []
                for i, prop in enumerate(props_a_visitar, 1):
                    if adondevivir_source.detener:
                        break
                    url = prop.get("url", "")
                    if not url:
                        continue
                    if i == 1 or i % 10 == 0:
                        if not await emit_progress(
                            percent=70 + int(((i - 1) / max(len(props_a_visitar), 1)) * 29),
                            processed=len(todas_raw),
                            message=f"Adondevivir: completando detalles {i} de {len(props_a_visitar)}",
                        ):
                            break
                    print(f"  [{i}/{len(props_a_visitar)}] Visitando detalle...")
                    await emit_progress(message=f'Adondevivir: [{i}/{len(props_a_visitar)}] abriendo {url}')
                    lat, lng, tipo_prop, imagen_url = await extraer_coordenadas_desde_detalle(page, url)
                    if lat and lng:
                        prop["latitud"] = lat
                        prop["longitud"] = lng
                    if tipo_prop:
                        prop["tipo"] = tipo_prop
                    imagen_origen = imagen_url or prop.get("imagen_url")
                    if imagen_origen and "blob.core.windows.net" not in str(imagen_origen):
                        imagen_blob = subir_imagen_a_blob(imagen_origen, prop)
                        if imagen_blob:
                            prop["imagen_url"] = imagen_blob
                    elif imagen_origen:
                        prop["imagen_url"] = imagen_origen

                    detalle_pendientes.append(prop)
                    if update_callback and len(detalle_pendientes) >= 10:
                        await asyncio.to_thread(
                            update_callback, estandarizar_lote(detalle_pendientes)
                        )
                        detalle_pendientes.clear()

                if update_callback and detalle_pendientes:
                    await asyncio.to_thread(
                        update_callback, estandarizar_lote(detalle_pendientes)
                    )

            await page.close()

        return estandarizar_lote(todas_raw)

    # Limpiar locks stale del perfil persistente (cuelgues de runs anteriores)
    _limpiar_locks_stale('./camoufox_session_adondevivir')

    # Timeout total: nunca quedarse "activo" indefinidamente
    try:
        return asyncio.run(
            asyncio.wait_for(_run(), timeout=CAMOUFOX_TOTAL_TIMEOUT)
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f'ADONDEVIVIR superó el timeout total de {CAMOUFOX_TOTAL_TIMEOUT}s '
            f'sin terminar. Se canceló para no quedar colgado.'
        )


class ScraperAdondevivirSkill(BaseSkill):
    name = "scraper_adondevivir"
    description = (
        "Scrapea propiedades de Adondevivir.com en Arequipa y las guarda "
        "en la tabla PropiedadesCompetencia."
    )
    category = "custom"
    access_level = 1
    is_active = True

    parameters_schema = {
        'max_paginas': {
            'type': 'integer',
            'description': 'MÃƒÆ’Ã‚Â¡ximo de pÃƒÆ’Ã‚Â¡ginas a scrapear. 0 = todas (default: 0).',
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
                    propiedades_lote, fuente='adondevivir'
                )
                for key in incremental:
                    incremental[key] += int(resultado_lote.get(key, 0) or 0)
                return incremental.copy()

            def actualizar_lote(propiedades_lote):
                return guardar_propiedades(
                    propiedades_lote, fuente='adondevivir'
                )

            propiedades = _ejecutar_scraping(
                max_paginas,
                start_page=start_page,
                progress_callback=progress_callback,
                batch_callback=guardar_lote,
                update_callback=actualizar_lote,
            )

            if not propiedades:
                if int(start_page or 1) > 1:
                    return SkillResult.ok(
                        data={
                            'portal': 'adondevivir',
                            **incremental,
                            'resume_complete': True,
                        },
                        message='Adondevivir: no quedan páginas después del checkpoint.',
                        skill_name=self.name,
                    )
                return SkillResult.error(
                    message=(
                        'Adondevivir no devolvió propiedades. Revise la '
                        'navegación, Cloudflare y los logs de extracción.'
                    ),
                    skill_name=self.name,
                )

            # Persistencia final idempotente para consolidar los Ãºltimos detalles.
            guardar_propiedades(propiedades, fuente='adondevivir')
            resultado = incremental

            return SkillResult.ok(
                data={
                    'portal': 'adondevivir',
                    **resultado,
                },
                message=(
                    f"Adondevivir: {resultado['nuevas']} nuevas, "
                    f"{resultado['actualizadas']} actualizadas, "
                    f"{resultado['errores']} errores / {resultado['total']} total"
                ),
                skill_name=self.name,
            )

        except Exception as e:
            logger.exception(f"[adondevivir] Error en ejecuciÃƒÆ’Ã‚Â³n: {e}")
            return SkillResult.error(
                message=f"Error en scraper Adondevivir: {e}",
                skill_name=self.name,
            )
