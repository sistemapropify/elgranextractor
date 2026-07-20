"""
ScraperRemaxSkill — Skill independiente.

Scrapea propiedades de Remax.pe y las guarda en PropiedadesCompetencia.
Reutiliza la lógica de extracción de scrapi/remax_scraper.py.
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
    Ejecuta el scraping de Remax y retorna lista de propiedades estandarizadas.
    
    Args:
        max_paginas: Máximo de páginas a scrapear. 0 = todas.
    
    Returns:
        Lista de dicts con formato estandarizado listo para guardar en DB.
    """
    # Importar funciones del scraper original (reutilizar, no duplicar)
    from scrapi.remax_scraper import (
        TOTAL_PAGES, GUARDAR_CADA_N_PAGINAS,
        estandarizar, extraer_listado, extraer_detalle,
        navegar_con_cloudflare, manejar_sigint, detener,
    )
    from camoufox.async_api import AsyncCamoufox
    import signal

    async def _run():
        todas_raw = []
        paginas = max_paginas if max_paginas > 0 else TOTAL_PAGES
        try:
            signal.signal(signal.SIGINT, manejar_sigint)
        except (ValueError, RuntimeError):
            pass  # No disponible en hilos secundarios

        async with AsyncCamoufox(
            headless=False,
            os='windows',
            humanize=True,
            persistent_context=True,
            user_data_dir='./camoufox_session',
        ) as browser:
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            print("=" * 60)
            print(f"SCRAPER REMAX - {paginas} paginas")
            print("=" * 60)

            for n in range(1, paginas + 1):
                if detener:
                    break
                from scrapi.remax_scraper import BASE_URL
                url = BASE_URL.format(n)
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
                print(f"\nFASE 2: Detalles ({len(todas_raw)} props)...")
                for i, prop in enumerate(todas_raw):
                    if detener:
                        break
                    distrito = prop.get('Distrito', '')
                    prop_id = prop.get('ID', '')
                    print(f"  [{i+1}/{len(todas_raw)}] ID: {prop_id} - {distrito}")
                    await extraer_detalle(page, prop)
                    await asyncio.sleep(0.5)

            await page.close()

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

    return asyncio.run(_run())


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
            propiedades = _ejecutar_scraping(max_paginas)

            if not propiedades:
                return SkillResult.ok(
                    data={'portal': 'remax', 'total': 0, 'nuevas': 0, 'actualizadas': 0},
                    message='No se encontraron propiedades en Remax',
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
