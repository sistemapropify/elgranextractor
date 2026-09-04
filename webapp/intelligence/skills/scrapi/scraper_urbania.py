"""
ScraperUrbaniaSkill — Skill independiente.

Scrapea propiedades de Urbania.pe y las guarda en PropiedadesCompetencia.
Reutiliza la lógica de extracción de scrapi/urbania_scraper.py.
Urbania tiene un formato propio (no usa estandarizar()), por lo que
esta skill incluye su propia función de estandarización.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time as _time
from datetime import datetime
from typing import Any, Callable, Dict

from intelligence.skills.base import BaseSkill, SkillResult
from .db_utils import guardar_propiedades

logger = logging.getLogger(__name__)

# Anti-cuelgue: timeouts (mismo criterio que REMAX). Perfil efímero (sin user_data_dir).
CAMOUFOX_LAUNCH_TIMEOUT = int(os.environ.get('CAMOUFOX_LAUNCH_TIMEOUT', '600'))
CAMOUFOX_TOTAL_TIMEOUT = int(os.environ.get('CAMOUFOX_TOTAL_TIMEOUT', '2700'))


def _estandarizar_urbania(prop: dict, fecha_extraccion: str) -> dict:
    """
    Convierte una propiedad cruda de Urbania al formato estandarizado.

    Urbania no tiene estandarizar() en su scraper original, por lo que
    esta función hace el mapeo directamente.
    """
    # Parsear precio
    precio_texto = (prop.get('Precio') or '').strip()
    precio_usd = None
    precio_soles = None
    if precio_texto:
        # Intentar extraer USD o Soles
        m_usd = re.search(r'US[$]\s*([\d,.]+)', precio_texto)
        m_soles = re.search(r'S/\.?\s*([\d,.]+)', precio_texto)
        if m_usd:
            try:
                precio_usd = float(m_usd.group(1).replace(',', ''))
            except ValueError:
                pass
        if m_soles:
            try:
                precio_soles = float(m_soles.group(1).replace(',', ''))
            except ValueError:
                pass
        if not precio_usd and not precio_soles:
            # Solo número, asumir USD
            solo_num = re.sub(r'[^\d.,]', '', precio_texto).replace(',', '')
            try:
                precio_usd = float(solo_num)
            except ValueError:
                pass

    # Parsear características
    feats = (prop.get('Caracteristicas') or '')
    area = None
    dormitorios = None
    banos = None
    estacionamientos = None

    m_area = re.search(r'(\d+)\s*m²\s*tot', feats)
    m_dorm = re.search(r'(\d+)\s*dorm', feats)
    m_bano = re.search(r'(\d+)\s*bañ', feats)
    m_estac = re.search(r'(\d+)\s*estac', feats)

    if m_area:
        try:
            area = float(m_area.group(1))
        except ValueError:
            pass
    if m_dorm:
        try:
            dormitorios = int(m_dorm.group(1))
        except ValueError:
            pass
    if m_bano:
        try:
            banos = int(m_bano.group(1))
        except ValueError:
            pass
    if m_estac:
        try:
            estacionamientos = int(m_estac.group(1))
        except ValueError:
            pass

    # Parsear ubicación
    ubicacion = (prop.get('Ubicacion') or '').strip()
    distrito = ''
    if ubicacion:
        partes = [p.strip() for p in ubicacion.split(',')]
        distrito = partes[0] if partes else ''

    # Coordenadas
    lat = None
    lng = None
    coords = (prop.get('Coordenadas') or '').strip()
    if coords:
        parts = coords.split(',')
        if len(parts) >= 2:
            try:
                lat = float(parts[0].strip())
                lng = float(parts[1].strip())
            except ValueError:
                pass

    return {
        'fuente': 'urbania',
        'id_origen': str(prop.get('ID', '')).strip(),
        'fecha_extraccion': fecha_extraccion,
        'titulo': (prop.get('Titulo') or '').strip() or None,
        'tipo_inmueble': 'Departamento',  # Urbania scrapea principalmente deptos
        'tipo_operacion': 'Venta',
        'precio_soles': precio_soles,
        'precio_usd': precio_usd,
        'area_m2': area,
        'dormitorios': dormitorios,
        'banos': banos,
        'estacionamientos': estacionamientos,
        'distrito': distrito or None,
        'provincia': 'Arequipa',
        'departamento': 'Arequipa',
        'direccion_texto': ubicacion or None,
        'descripcion': (prop.get('Descripcion') or '').strip() or None,
        'amenities': None,
        'latitud': lat,
        'longitud': lng,
        'url': prop.get('URL Propiedad') or None,
        'imagen_url': prop.get('Imagen URL') or None,
        'antiguedad_anios': None,
        'agencia_agente': None,
        'datos_crudos': {k: str(v) if not isinstance(v, (dict, list, type(None))) else v
                         for k, v in prop.items()},
    }


def _ejecutar_scraping(
    max_paginas: int = 0,
    start_page: int = 1,
    url: str | None = None,
    progress_callback: Callable[[Dict[str, Any]], bool] | None = None,
    batch_callback: Callable[[list[Dict[str, Any]]], Dict[str, int]] | None = None,
) -> list[Dict[str, Any]]:
    """Scrapea Urbania por pagina, persistiendo y reportando cada lote.

    ``url`` opcional: URL del listado de Urbania que el usuario pegó
    (ej. .../venta-de-propiedades-en-arequipa--arequipa?page=1). Si se omite
    se usa ``BASE_PATTERN``. Recorre las páginas hasta que una ya no devuelve
    propiedades (final real del listado).
    """
    from scrapi import urbania_scraper as urbania_source
    from scrapi.urbania_scraper import (
        TOTAL_PAGINAS, BASE_PATTERN, construir_url_pagina,
        extraer_listado, extraer_detalle, navegar_con_cloudflare,
        manejar_sigint,
    )
    from camoufox.async_api import AsyncCamoufox
    from scrapi.camoufox_launcher import camoufox_kwargs
    import signal

    async def _run():
        urbania_source.detener = False
        todas_raw = []
        base_url = (url or "").strip() or BASE_PATTERN
        paginas = max_paginas if max_paginas > 0 else TOTAL_PAGINAS
        pagina_inicial = max(1, min(int(start_page or 1), paginas))

        async def emit_progress(**payload):
            if not progress_callback:
                return True
            return await asyncio.to_thread(progress_callback, payload)

        def estandarizar_lote(raw_items):
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            resultado = []
            for prop in raw_items:
                try:
                    resultado.append(_estandarizar_urbania(prop, fecha))
                except Exception as exc:
                    logger.warning("[urbania] Error estandarizando: %s", exc)
            return resultado

        try:
            signal.signal(signal.SIGINT, manejar_sigint)
        except (ValueError, RuntimeError):
            pass

        t0 = _time.monotonic()
        if not await emit_progress(
            percent=1,
            processed=0,
            message=(
                f'Urbania: lanzando navegador Camoufox '
                f'(timeout {CAMOUFOX_LAUNCH_TIMEOUT}s)'
            ),
        ):
            return []

        browser_options = await asyncio.wait_for(
            asyncio.to_thread(camoufox_kwargs, timeout=120000),
            timeout=180,
        )
        async with AsyncCamoufox(**browser_options) as browser:
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})
            for n in range(pagina_inicial, paginas + 1):
                if urbania_source.detener:
                    break
                if not await emit_progress(
                    percent=int(((n - 1) / max(paginas, 1)) * 99),
                    processed=len(todas_raw),
                    message=f'Urbania: leyendo pagina {n} de {paginas}',
                ):
                    break
                try:
                    await navegar_con_cloudflare(
                        page, construir_url_pagina(base_url, n)
                    )
                    props = await extraer_listado(page)
                    if not props and n > pagina_inicial:
                        # No hay más propiedades: se terminaron las páginas.
                        await emit_progress(
                            processed=len(todas_raw),
                            message=(
                                f'Urbania: sin resultados en la pagina {n}; '
                                f'no hay mas paginas'
                            ),
                        )
                        break
                    total_lote = len(props)
                    completadas = []
                    for indice, prop in enumerate(props, 1):
                        if urbania_source.detener:
                            break
                        await emit_progress(message=f'Urbania: [{indice}/{len(props)}] detalle ID {prop.get("ID", "")} - {prop.get("Distrito", "")}')
                        await extraer_detalle(page, prop)
                        await asyncio.sleep(0.35)
                        completadas.append(prop)
                        if indice == 1 or indice % 10 == 0:
                            if not await emit_progress(
                                percent=int(((n - 1) / max(paginas, 1)) * 99),
                                processed=len(todas_raw) + indice,
                                message=(
                                    f'Urbania: completando detalles de la '
                                    f'pagina {n} ({indice}/{len(props)})'
                                ),
                            ):
                                urbania_source.detener = True
                                break
                    props = completadas
                    todas_raw.extend(props)
                    if batch_callback and props:
                        lote = estandarizar_lote(props)
                        if lote:
                            saved = await asyncio.to_thread(batch_callback, lote)
                            if saved and not await emit_progress(
                                percent=int((n / max(paginas, 1)) * 99),
                                processed=saved.get('total', len(todas_raw)),
                                nuevas=saved.get('nuevas', 0),
                                actualizadas=saved.get('actualizadas', 0),
                                errores=saved.get('errores', 0),
                                checkpoint_page=(n if len(props) == total_lote else None),
                                message=(
                                    f"Urbania: {saved.get('total', 0)} procesadas "
                                    f"({saved.get('nuevas', 0)} nuevas)"
                                ),
                            ):
                                break
                except Exception as exc:
                    raise RuntimeError(
                        f"Urbania fallo en pagina {n}; checkpoint previo conservado"
                    ) from exc
            await page.close()

        estandarizadas = estandarizar_lote(todas_raw)
        await emit_progress(
            percent=99,
            processed=len(estandarizadas),
            message='Urbania: consolidando resultados finales',
        )
        return estandarizadas

    # Timeout total: nunca quedarse "activo" indefinidamente
    try:
        return asyncio.run(
            asyncio.wait_for(_run(), timeout=CAMOUFOX_TOTAL_TIMEOUT)
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f'URBANIA superó el timeout total de {CAMOUFOX_TOTAL_TIMEOUT}s '
            f'sin terminar. Se canceló para no quedar colgado.'
        )

class ScraperUrbaniaSkill(BaseSkill):
    name = "scraper_urbania"
    description = (
        "Scrapea propiedades de Urbania.pe en Arequipa y las guarda "
        "en la tabla PropiedadesCompetencia."
    )
    category = "custom"
    access_level = 1
    is_active = True

    parameters_schema = {
        'url': {
            'type': 'string',
            'description': (
                'URL del listado de Urbania a scrapear (pégalo tal cual del '
                'navegador). Ej: https://urbania.pe/buscar/venta-de-propiedades-'
                'en-arequipa--arequipa?page=1 . Si se omite usa la URL por defecto.'
            ),
            'required': False,
        },
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
            url = params.get('url') or None
            max_paginas = params.get('max_paginas', 0)
            start_page = params.get('start_page', 1)
            progress_callback = (context or {}).get('progress_callback')
            lifecycle_run_id = (context or {}).get('lifecycle_run_id')
            incremental = {'total': 0, 'nuevas': 0, 'actualizadas': 0, 'errores': 0}

            def guardar_lote(propiedades_lote):
                resultado_lote = guardar_propiedades(
                    propiedades_lote,
                    fuente='urbania',
                    lifecycle_run_id=lifecycle_run_id,
                )
                for key in incremental:
                    incremental[key] += int(resultado_lote.get(key, 0) or 0)
                return incremental.copy()

            propiedades = _ejecutar_scraping(
                max_paginas,
                start_page=start_page,
                url=url,
                progress_callback=progress_callback,
                batch_callback=guardar_lote,
            )
            if not propiedades:
                return SkillResult.error(
                    message=(
                        'Urbania no devolvio propiedades. Revise la navegacion, '
                        'el bloqueo del portal y los logs de extraccion.'
                    ),
                    skill_name=self.name,
                )
            guardar_propiedades(
                propiedades,
                fuente='urbania',
                lifecycle_run_id=lifecycle_run_id,
            )
            resultado = incremental
            return SkillResult.ok(
                data={'portal': 'urbania', **resultado},
                message=(
                    f"Urbania: {resultado['nuevas']} nuevas, "
                    f"{resultado['actualizadas']} actualizadas, "
                    f"{resultado['errores']} errores / {resultado['total']} total"
                ),
                skill_name=self.name,
            )
        except Exception as exc:
            logger.exception("[urbania] Error en ejecucion: %s", exc)
            return SkillResult.error(
                message=f"Error en scraper Urbania: {exc}",
                skill_name=self.name,
            )
