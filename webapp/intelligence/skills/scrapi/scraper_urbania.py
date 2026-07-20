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
import re
from datetime import datetime
from typing import Any, Dict

from intelligence.skills.base import BaseSkill, SkillResult
from .db_utils import guardar_propiedades

logger = logging.getLogger(__name__)


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


def _ejecutar_scraping(max_paginas: int = 0) -> list[Dict[str, Any]]:
    """
    Ejecuta el scraping de Urbania y retorna lista de propiedades estandarizadas.
    
    Args:
        max_paginas: Máximo de páginas a scrapear. 0 = todas.
    
    Returns:
        Lista de dicts con formato estandarizado listo para guardar en DB.
    """
    from scrapi.urbania_scraper import (
        TOTAL_PAGINAS, GUARDAR_CADA_N_PAGINAS, BASE_PATTERN,
        extraer_listado, extraer_detalle,
        navegar_con_cloudflare, manejar_sigint, detener,
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
            persistent_context=True,
            user_data_dir='./camoufox_session_urbania',
        ) as browser:
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})

            print("=" * 60)
            print(f"SCRAPER URBANIA - {paginas} paginas")
            print("=" * 60)

            for n in range(1, paginas + 1):
                if detener:
                    break
                url = BASE_PATTERN.format(n)
                print(f"\n[Pagina {n}/{paginas}]: {url}")
                try:
                    await navegar_con_cloudflare(page, url)
                    props = await extraer_listado(page)
                    todas_raw.extend(props)
                    print(f"   -> {len(props)} props (total: {len(todas_raw)})")
                except Exception as e:
                    print(f"   [ERROR] Pagina {n}: {e}")

            # FASE 2: Detalles para coordenadas
            if todas_raw and not detener:
                print(f"\nFASE 2: Detalles ({len(todas_raw)} props)...")
                for i, prop in enumerate(todas_raw):
                    if detener:
                        break
                    prop_id = prop.get('ID', '')
                    ubic = prop.get('Ubicacion', '')
                    print(f"  [{i+1}/{len(todas_raw)}] ID: {prop_id} - {ubic}")
                    await extraer_detalle(page, prop)
                    await asyncio.sleep(0.5)

            await page.close()

        # Estandarizar
        fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        estandarizadas = []
        for prop in todas_raw:
            try:
                std = _estandarizar_urbania(prop, fecha_extraccion)
                estandarizadas.append(std)
            except Exception as e:
                logger.warning(f"[urbania] Error estandarizando: {e}")

        return estandarizadas

    return asyncio.run(_run())


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
                    data={'portal': 'urbania', 'total': 0, 'nuevas': 0, 'actualizadas': 0},
                    message='No se encontraron propiedades en Urbania',
                    skill_name=self.name,
                )

            resultado = guardar_propiedades(propiedades, fuente='urbania')

            return SkillResult.ok(
                data={
                    'portal': 'urbania',
                    **resultado,
                },
                message=(
                    f"Urbania: {resultado['nuevas']} nuevas, "
                    f"{resultado['actualizadas']} actualizadas, "
                    f"{resultado['errores']} errores / {resultado['total']} total"
                ),
                skill_name=self.name,
            )

        except Exception as e:
            logger.exception(f"[urbania] Error en ejecución: {e}")
            return SkillResult.error(
                message=f"Error en scraper Urbania: {e}",
                skill_name=self.name,
            )
