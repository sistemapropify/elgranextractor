"""
ScraperAdondevivirSkill — Skill independiente.

Scrapea propiedades de Adondevivir.com y las guarda en PropiedadesCompetencia.
Reutiliza la lógica de extracción de scrapi/adondevivir_scraper.py.
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
    Ejecuta el scraping de Adondevivir y retorna lista de propiedades estandarizadas.
    
    Args:
        max_paginas: Máximo de páginas a scrapear. 0 = todas.
    
    Returns:
        Lista de dicts con formato estandarizado listo para guardar en DB.
    """
    # Importar funciones del scraper original
    from scrapi.adondevivir_scraper import (
        LISTING_URL, GUARDAR_CADA_N_PAGINAS, PROPS_POR_PAGINA,
        estandarizar, extraer_listado, extraer_coordenadas_desde_detalle,
        navegar_con_cloudflare, manejar_sigint, detener,
        mapear_a_formato_remax,
    )
    from camoufox.async_api import AsyncCamoufox
    import signal
    import re

    async def _run():
        todas_raw = []
        try:
            signal.signal(signal.SIGINT, manejar_sigint)
        except (ValueError, RuntimeError):
            pass

        async with AsyncCamoufox(
            headless=False,
            os='windows',
            humanize=True,
            persistent_context=True,
            user_data_dir='./camoufox_session_adondevivir',
        ) as browser:
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            # FASE 1: Cargar primera página para obtener total de páginas
            print("=" * 60)
            print("SCRAPER ADONDEVIVIR")
            print("=" * 60)

            exito = await navegar_con_cloudflare(page, LISTING_URL, timeout=30)
            if not exito:
                print("[!] No se pudo cargar la página inicial")
                return []

            props_pagina1 = await extraer_listado(page)
            todas_raw.extend(props_pagina1)
            print(f"  [Pagina 1]: {len(props_pagina1)} props")

            # Determinar total de páginas desde el HTML
            total_paginas = 1
            try:
                html = await page.content()
                pag_match = re.search(r'de\s+(\d+)\s+resultados', html)
                if pag_match:
                    total_results = int(pag_match.group(1))
                    total_paginas = max(1, (total_results + PROPS_POR_PAGINA - 1) // PROPS_POR_PAGINA)
                    print(f"  Resultados totales: {total_results} -> {total_paginas} páginas")
            except Exception:
                pass

            if max_paginas > 0:
                total_paginas = min(total_paginas, max_paginas)

            # Resto de páginas
            for pagina in range(2, total_paginas + 1):
                if detener:
                    break
                url_pagina = f"https://www.adondevivir.com/inmuebles-en-venta-en-arequipa-pagina-{pagina}.html"
                print(f"\n[Pagina {pagina}/{total_paginas}]...")
                exito = await navegar_con_cloudflare(page, url_pagina, timeout=30)
                if not exito:
                    continue
                props = await extraer_listado(page)
                todas_raw.extend(props)
                print(f"  -> {len(props)} props (total: {len(todas_raw)})")

            # FASE 2: Detalles para coordenadas
            props_a_visitar = [p for p in todas_raw
                              if not p.get("latitud") or not p.get("longitud")
                              or not p.get("tipo")]
            if props_a_visitar and not detener:
                print(f"\nFASE 2: Detalles ({len(props_a_visitar)} props)...")
                for i, prop in enumerate(props_a_visitar, 1):
                    if detener:
                        break
                    url = prop.get("url", "")
                    if not url:
                        continue
                    print(f"  [{i}/{len(props_a_visitar)}] Visitando detalle...")
                    lat, lng, tipo_prop = await extraer_coordenadas_desde_detalle(page, url)
                    if lat and lng:
                        prop["latitud"] = lat
                        prop["longitud"] = lng
                    if tipo_prop:
                        prop["tipo"] = tipo_prop

            await page.close()

        # Post-procesamiento: mapear y estandarizar
        from scrapi.adondevivir_scraper import mapear_tipo_schemaorg
        for prop in todas_raw:
            if prop.get("tipo") and not any(
                palabra in prop["tipo"]
                for palabra in ["Casa", "Departamento", "Terreno", "Local", "Oficina", "Alojamiento"]
            ):
                prop["tipo"] = mapear_tipo_schemaorg(prop["tipo"])

        fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        estandarizadas = []
        for prop in todas_raw:
            try:
                # Primero mapear al formato REMAX, luego estandarizar
                mapeada = mapear_a_formato_remax(prop)
                std = estandarizar(mapeada, fecha_extraccion, "ADondevivir")
                std['fuente'] = 'adondevivir'
                std['datos_crudos'] = {k: str(v) if not isinstance(v, (dict, list, type(None))) else v
                                       for k, v in prop.items()}
                estandarizadas.append(std)
            except Exception as e:
                logger.warning(f"[adondevivir] Error estandarizando: {e}")

        return estandarizadas

    return asyncio.run(_run())


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
                    data={'portal': 'adondevivir', 'total': 0, 'nuevas': 0, 'actualizadas': 0},
                    message='No se encontraron propiedades en Adondevivir',
                    skill_name=self.name,
                )

            resultado = guardar_propiedades(propiedades, fuente='adondevivir')

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
            logger.exception(f"[adondevivir] Error en ejecución: {e}")
            return SkillResult.error(
                message=f"Error en scraper Adondevivir: {e}",
                skill_name=self.name,
            )
