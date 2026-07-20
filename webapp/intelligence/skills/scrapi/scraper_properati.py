"""
ScraperProperatiSkill — Skill independiente.

Scrapea propiedades de Properati.com.pe y las guarda en PropiedadesCompetencia.
Reutiliza la lógica de extracción de scrapi/properati_scraper.py.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

from intelligence.skills.base import BaseSkill, SkillResult
from .db_utils import guardar_propiedades

logger = logging.getLogger(__name__)


def _ejecutar_scraping(max_paginas: int = 0) -> list[Dict[str, Any]]:
    """
    Ejecuta el scraping de Properati y retorna lista de propiedades estandarizadas.
    
    Args:
        max_paginas: Máximo de páginas a scrapear. 0 = todas.
    
    Returns:
        Lista de dicts con formato estandarizado listo para guardar en DB.
    """
    from scrapi.properati_scraper import (
        TOTAL_PAGINAS, GUARDAR_CADA_N_PAGINAS, BASE_URL,
        estandarizar, extraer_listado, extraer_detalle,
        navegar_con_cloudflare, manejar_sigint, detener,
        mapear_a_formato_remax,
    )
    from camoufox.async_api import AsyncCamoufox
    import signal

    async def _run():
        todas_raw = []
        paginas = max_paginas if max_paginas > 0 else TOTAL_PAGINAS
        try:
            signal.signal(signal.SIGINT, manejar_sigint)
        except (ValueError, RuntimeError):
            pass

        async with AsyncCamoufox(
            headless=False,
            os='windows',
            humanize=True,
        ) as browser:
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            print("=" * 60)
            print(f"SCRAPER PROPERATI - {paginas} paginas")
            print("=" * 60)

            for n in range(1, paginas + 1):
                if detener:
                    break
                url = BASE_URL if n == 1 else f"{BASE_URL}/{n}"
                print(f"\n[Pagina {n}/{paginas}]: {url}")
                try:
                    await navegar_con_cloudflare(page, url)
                    props = await extraer_listado(page)
                    todas_raw.extend(props)
                    print(f"   -> {len(props)} props (total: {len(todas_raw)})")
                except Exception as e:
                    print(f"   [ERROR] Pagina {n}: {e}")

            # FASE 2: Detalles para coordenadas
            if todas_raw:
                sin_coords = [p for p in todas_raw if not p.get('Coordenadas')]
                if sin_coords:
                    print(f"\nFASE 2: Coordenadas ({len(sin_coords)} props)...")
                    for i, prop in enumerate(sin_coords):
                        if detener:
                            break
                        prop_id = prop.get('ID', '')
                        ubic = prop.get('Ubicacion', '')
                        print(f"  [{i+1}/{len(sin_coords)}] ID: {prop_id} - {ubic}")
                        await extraer_detalle(page, prop)
                        await asyncio.sleep(0.5)

            await page.close()

        # Mapear y estandarizar
        fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        estandarizadas = []
        for prop in todas_raw:
            try:
                mapeada = mapear_a_formato_remax(prop)
                std = estandarizar(mapeada, fecha_extraccion, "Properati")
                std['fuente'] = 'properati'
                std['datos_crudos'] = {k: str(v) if not isinstance(v, (dict, list, type(None))) else v
                                       for k, v in prop.items()}
                estandarizadas.append(std)
            except Exception as e:
                logger.warning(f"[properati] Error estandarizando: {e}")

        return estandarizadas

    return asyncio.run(_run())


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
            propiedades = _ejecutar_scraping(max_paginas)

            if not propiedades:
                return SkillResult.ok(
                    data={'portal': 'properati', 'total': 0, 'nuevas': 0, 'actualizadas': 0},
                    message='No se encontraron propiedades en Properati',
                    skill_name=self.name,
                )

            resultado = guardar_propiedades(propiedades, fuente='properati')

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
            logger.exception(f"[properati] Error en ejecución: {e}")
            return SkillResult.error(
                message=f"Error en scraper Properati: {e}",
                skill_name=self.name,
            )
