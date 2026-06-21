"""
Skill para formatear resultados de propiedades en HTML estructurado.
Soporta: carrusel, matriz/tabla, lista numerada.

Pipeline: busqueda_propiedades → formatear_propiedades
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

# URL base de Azure Blob Storage para imágenes de propiedades
# Las imágenes se almacenan como: {AZURE_MEDIA_BASE}/{codigo}.jpg
AZURE_MEDIA_BASE = "https://propifymedia01.blob.core.windows.net/media"


class FormatearPropiedadesSkill(BaseSkill):
    """
    Toma resultados de busqueda_propiedades y los formatea en HTML
    estructurado (carrusel, matriz, lista) para mejor visualización.
    """

    name = "formatear_propiedades"
    description = (
        "Toma resultados de busqueda_propiedades y los muestra en formato "
        "visual: carrusel (tarjetas con foto), matriz (tabla comparativa), "
        "o lista numerada. Pregunta al usuario qué formato prefiere antes de usarlo."
    )
    category = "busqueda"
    access_level = 1
    is_active = True

    parameters_schema = {
        'propiedades': {
            'type': 'array',
            'description': 'Lista de resultados de busqueda_propiedades',
            'required': True,
        },
        'formato': {
            'type': 'string',
            'description': 'Formato de visualización: carrusel, matriz, lista',
            'required': True,
        },
        'campos': {
            'type': 'array',
            'description': 'Campos a incluir. Default: title, price, district_name, property_type_name',
            'required': False,
        },
    }

    # Colores por tipo de propiedad para las tarjetas
    _COLORES_TIPO = {
        'Casa': '#4CAF50',
        'Departamento': '#2196F3',
        'Terreno': '#FF9800',
        'Local Comercial': '#9C27B0',
        'Local': '#9C27B0',
        'Oficina': '#607D8B',
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        if not params:
            return False
        # 'propiedades' es opcional (puede venir de ultima busqueda en metadata)
        if 'formato' not in params or params.get('formato') not in ('carrusel', 'matriz', 'lista'):
            return False
        return True

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        try:
            propiedades = params.get('propiedades', [])
            formato = params.get('formato', 'lista')
            
            # Si no hay propiedades, intentar recuperar del context (follow-up)
            if not propiedades and context and hasattr(context, 'metadata'):
                ultima = context.metadata.get('ultima_busqueda', {}) if isinstance(context.metadata, dict) else {}
                if ultima and ultima.get('resultados'):
                    propiedades = ultima['resultados']
                    logger.info(f"Usando {len(propiedades)} props de ultima busqueda (follow-up)")
            campos = params.get('campos', ['title', 'price', 'district_name', 'property_type_name'])
            max_items = params.get('max_items', 50)

            if len(propiedades) > max_items:
                propiedades = propiedades[:max_items]

            if not propiedades:
                return SkillResult.ok(
                    data={'html': '<p>No hay propiedades para mostrar.</p>', 'total': 0},
                    message="No hay propiedades para mostrar.",
                    skill_name=self.name
                )

            if formato == 'carrusel':
                html = self._generar_carrusel(propiedades, campos)
            elif formato == 'matriz':
                html = self._generar_matriz(propiedades, campos)
            else:
                html = self._generar_lista(propiedades, campos)

            return SkillResult.ok(
                data={
                    'html': html,
                    'total': len(propiedades),
                    'formato': formato,
                },
                message=f"{len(propiedades)} propiedades formateadas en {formato}.",
                metadata={'total': len(propiedades), 'formato': formato},
                skill_name=self.name
            )

        except Exception as e:
            logger.error(f"Error formateando propiedades: {e}", exc_info=True)
            return SkillResult.error(
                message=f"Error al formatear: {str(e)}",
                skill_name=self.name
            )

    def _get_valor(self, field_values: Dict, campo: str) -> str:
        """Obtiene un valor limpio de field_values."""
        val = field_values.get(campo)
        if val is None:
            return ''
        return str(val)

    def _get_precio_formateado(self, fv: Dict) -> str:
        """Formatea precio con moneda."""
        precio = self._get_valor(fv, 'price')
        moneda = self._get_valor(fv, 'currency_name')
        if not precio:
            return ''
        try:
            precio_num = float(precio)
            if precio_num >= 1_000_000:
                precio_str = f"{precio_num/1_000_000:,.2f}M"
            elif precio_num >= 1_000:
                precio_str = f"{precio_num:,.0f}"
            else:
                precio_str = f"{precio_num:,.0f}"
        except (ValueError, TypeError):
            precio_str = precio
        
        if moneda:
            simbolo = 'S/' if moneda.upper() in ('PEN', 'SOLES', 'S/') else '$'
            return f"{simbolo}{precio_str}"
        return f"${precio_str}"

    def _get_color_tipo(self, tipo: str) -> str:
        """Obtiene color según tipo de propiedad."""
        return self._COLORES_TIPO.get(tipo, '#666666')

    def _generar_carrusel(self, propiedades: List[Dict], campos: List[str]) -> str:
        """Genera HTML de carrusel con tarjetas."""
        items_html = []
        for i, prop in enumerate(propiedades):
            fv = prop.get('field_values', {})
            title = self._get_valor(fv, 'title') or f"Propiedad #{prop.get('source_id', '?')}"
            precio = self._get_precio_formateado(fv)
            distrito = self._get_valor(fv, 'district_name')
            tipo = self._get_valor(fv, 'property_type_name')
            color = self._get_color_tipo(tipo)
            code = self._get_valor(fv, 'code')
            desc = self._get_valor(fv, 'description')[:120]

            items_html.append(f"""
            <div class="pf-card">
                <div class="pf-card-img" style="background: linear-gradient(135deg, {color}22, {color}44);">
                    <div class="pf-card-tag" style="background:{color}">{tipo or 'Propiedad'}</div>
                    <div class="pf-card-code">{code}</div>
                    <div class="pf-card-price">{precio}</div>
                </div>
                <div class="pf-card-body">
                    <h4 class="pf-card-title">{title[:80]}</h4>
                    {f'<p class="pf-card-desc">{desc}</p>' if desc else ''}
                    <div class="pf-card-details">
                        {f'<span class="pf-badge pf-badge-location">📍 {distrito}</span>' if distrito else ''}
                        {f'<span class="pf-badge pf-badge-type" style="border-color:{color};color:{color}">{tipo}</span>' if tipo else ''}
                    </div>
                </div>
            </div>""")

        return f"""
        <div class="pf-carousel-container">
            <div class="pf-carousel-header">
                <span class="pf-carousel-count">{len(propiedades)} propiedades</span>
                <div class="pf-carousel-nav">
                    <button class="pf-nav-btn" onclick="pfCarouselScroll(-1)">‹</button>
                    <button class="pf-nav-btn" onclick="pfCarouselScroll(1)">›</button>
                </div>
            </div>
            <div class="pf-carousel-track" id="pf-carousel-track">
                {''.join(items_html)}
            </div>
        </div>
        <style>
            .pf-carousel-container {{ margin: 12px 0; position: relative; }}
            .pf-carousel-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
            .pf-carousel-count {{ font-size: 13px; color: #8b949e; }}
            .pf-carousel-nav {{ display: flex; gap: 6px; }}
            .pf-nav-btn {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 16px; }}
            .pf-nav-btn:hover {{ background: #30363d; }}
            .pf-carousel-track {{ display: flex; gap: 12px; overflow-x: auto; scroll-behavior: smooth; padding: 4px 0 12px; }}
            .pf-carousel-track::-webkit-scrollbar {{ height: 6px; }}
            .pf-carousel-track::-webkit-scrollbar-track {{ background: #161b22; border-radius: 3px; }}
            .pf-carousel-track::-webkit-scrollbar-thumb {{ background: #30363d; border-radius: 3px; }}
            .pf-card {{ flex: 0 0 280px; min-width: 260px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
            .pf-card:hover {{ border-color: #58a6ff; box-shadow: 0 4px 12px rgba(88,166,255,0.15); }}
            .pf-card-img {{ height: 140px; display: flex; flex-direction: column; justify-content: space-between; padding: 10px 12px; position: relative; }}
            .pf-card-tag {{ align-self: flex-start; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; color: #fff; }}
            .pf-card-code {{ font-size: 10px; color: rgba(255,255,255,0.6); }}
            .pf-card-price {{ font-size: 18px; font-weight: 700; color: #fff; text-shadow: 0 1px 3px rgba(0,0,0,0.3); }}
            .pf-card-body {{ padding: 10px 12px 12px; }}
            .pf-card-title {{ margin: 0 0 6px; font-size: 14px; font-weight: 600; color: #c9d1d9; }}
            .pf-card-desc {{ margin: 0 0 8px; font-size: 12px; color: #8b949e; }}
            .pf-card-details {{ display: flex; flex-wrap: wrap; gap: 4px; }}
            .pf-badge {{ font-size: 11px; padding: 2px 8px; border-radius: 10px; }}
            .pf-badge-location {{ background: #1a3a2a; color: #7ee787; }}
            .pf-badge-type {{ background: transparent; border: 1px solid; }}
        </style>
        <script>
        function pfCarouselScroll(dir) {{
            var track = document.getElementById('pf-carousel-track');
            if (track) track.scrollBy({{ left: dir * 300, behavior: 'smooth' }});
        }}
        </script>"""

    def _generar_matriz(self, propiedades: List[Dict], campos: List[str]) -> str:
        """Genera HTML de tabla/matriz comparativa."""
        headers = {
            'title': 'Propiedad',
            'price': 'Precio',
            'district_name': 'Distrito',
            'property_type_name': 'Tipo',
            'operation_type_name': 'Operación',
            'property_status_name': 'Estado',
            'built_area': 'Área',
            'bedrooms': 'Hab.',
        }

        # Mapear nombres de campos a columnas
        col_map = []
        for c in campos:
            h = headers.get(c, c.replace('_', ' ').title())
            col_map.append((c, h))

        rows_html = []
        for i, prop in enumerate(propiedades):
            fv = prop.get('field_values', {})
            cells = []
            for campo, _ in col_map:
                val = ''
                if campo == 'price':
                    val = self._get_precio_formateado(fv)
                elif campo == 'built_area':
                    area = self._get_valor(fv, campo)
                    val = f"{area} m²" if area else ''
                else:
                    val = self._get_valor(fv, campo)
                cells.append(f'<td>{val}</td>')
            rows_html.append(f'<tr>{"".join(cells)}</tr>')

        header_html = ''.join(f'<th>{h}</th>' for _, h in col_map)

        return f"""
        <div class="pf-table-container">
            <div class="pf-table-count">{len(propiedades)} propiedades</div>
            <table class="pf-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{''.join(rows_html)}</tbody>
            </table>
        </div>
        <style>
            .pf-table-container {{ margin: 12px 0; overflow-x: auto; }}
            .pf-table-count {{ font-size: 13px; color: #8b949e; margin-bottom: 8px; }}
            .pf-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
            .pf-table th {{ background: #161b22; color: #8b949e; font-weight: 600; padding: 8px 10px; text-align: left; border-bottom: 2px solid #30363d; white-space: nowrap; }}
            .pf-table td {{ padding: 7px 10px; border-bottom: 1px solid #21262d; color: #c9d1d9; }}
            .pf-table tr:hover td {{ background: #1c2128; }}
            .pf-table tr:nth-child(even) td {{ background: #0d1117; }}
            .pf-table tr:nth-child(even):hover td {{ background: #1c2128; }}
        </style>"""

    def _generar_lista(self, propiedades: List[Dict], campos: List[str]) -> str:
        """Genera HTML de lista numerada."""
        items_html = []
        for i, prop in enumerate(propiedades):
            fv = prop.get('field_values', {})
            title = self._get_valor(fv, 'title') or f"Propiedad #{prop.get('source_id', '?')}"
            precio = self._get_precio_formateado(fv)
            distrito = self._get_valor(fv, 'district_name')
            tipo = self._get_valor(fv, 'property_type_name')
            status = self._get_valor(fv, 'property_status_name')
            desc = self._get_valor(fv, 'description')[:100]

            detalles = []
            if precio:
                detalles.append(f'💰 {precio}')
            if distrito:
                detalles.append(f'📍 {distrito}')
            if tipo:
                detalles.append(f'🏷️ {tipo}')
            if status:
                detalles.append(f'📌 {status}')

            items_html.append(f"""
            <li class="pf-list-item">
                <span class="pf-list-num">{i+1}</span>
                <div class="pf-list-content">
                    <strong class="pf-list-title">{title}</strong>
                    {f'<div class="pf-list-desc">{desc}</div>' if desc else ''}
                    <div class="pf-list-details">{' · '.join(detalles)}</div>
                </div>
            </li>""")

        return f"""
        <ol class="pf-list">
            {''.join(items_html)}
        </ol>
        <style>
            .pf-list {{ list-style: none; counter-reset: item; margin: 8px 0; padding: 0; }}
            .pf-list-item {{ display: flex; gap: 10px; padding: 8px 10px; margin-bottom: 4px; background: #161b22; border: 1px solid #21262d; border-radius: 6px; align-items: flex-start; }}
            .pf-list-item:hover {{ border-color: #30363d; }}
            .pf-list-num {{ flex-shrink: 0; width: 24px; height: 24px; background: #1f6feb; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }}
            .pf-list-content {{ flex: 1; min-width: 0; }}
            .pf-list-title {{ font-size: 14px; color: #c9d1d9; }}
            .pf-list-desc {{ font-size: 12px; color: #8b949e; margin: 2px 0; }}
            .pf-list-details {{ font-size: 12px; color: #8b949e; display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }}
        </style>"""
