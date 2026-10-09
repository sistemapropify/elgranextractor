"""Informe PDF del ACM por componentes con la estructura del ACM de Propify.

Reutiliza el mismo logotipo, colores y secciones del informe de referencia
(portada, propiedad sujeto, ubicación, comparables y resultado). El informe no
menciona portales inmobiliarios ni usa sus pines o iconos: toda la identidad
visible es Propify.
"""
from __future__ import annotations

import io
import logging
import math
import os
import re
import time
from datetime import datetime
from functools import lru_cache
from statistics import mean
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

# Paleta Propify (la misma del ACM clásico y del logotipo).
C_PRIMARY = '#279896'
C_DARK = '#047d7d'
C_TEXT = '#1f2933'
C_MUTED = '#6b7280'
C_BAR = '#2f6fb0'
C_LINE = '#f0a02b'

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(HERE, 'static', 'acm', 'img', 'LOGO-PROPIFY.png')

# Se mantiene la misma clave de respaldo que usa el resto del dashboard ACM.
DEFAULT_MAPS_KEY = 'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q'

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')

# Portales que no deben aparecer nunca en el informe ni en sus textos.
_PORTALES = re.compile(
    r'\b(re[\s-]?max|properati|adondevivir|urbania|navent|mercadolibre|'
    r'mercado\s*libre|facebook(?:\s*marketplace)?)\b',
    re.IGNORECASE,
)


def _clean(text, fallback=''):
    """Quita cualquier mención a portales inmobiliarios de un texto libre."""
    value = _PORTALES.sub(' ', str(text or ''))
    value = re.sub(r'\s{2,}', ' ', value).strip(' -·|,;:')
    return value or fallback


def _money(value):
    if value is None:
        return 'Sin dato'
    return f'$ {float(value):,.2f}'


def _number(value, decimals=0, suffix=''):
    if value is None:
        return 'Sin informar'
    return f'{float(value):,.{decimals}f}{suffix}'


def _fecha_larga(value):
    return f'{value.day} de {MESES[value.month - 1]} {value.year}'


def _fecha_corta(value):
    if not value:
        return 'Sin informar'
    if isinstance(value, datetime):
        return f'{value.day} de {MESES[value.month - 1].capitalize()} de {value.year}'
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return 'Sin informar'
    return f'{parsed.day} de {MESES[parsed.month - 1].capitalize()} de {parsed.year}'


def _area(row):
    """Superficie comparable del registro: terreno o construcción."""
    if row.get('kind') == 'Terreno':
        return row.get('land')
    return row.get('built') or row.get('land')


def _unit_price(row):
    price, area = row.get('price'), _area(row)
    if not price or not area:
        return None
    return price / area


@lru_cache(maxsize=1)
def _logo_bytes():
    """Logotipo Propify con la palabra en gris oscuro para fondo blanco.

    El PNG institucional trae el texto en blanco (pensado para fondos de color);
    sobre el papel se recolorea a gris para conservar el mismo logotipo legible.
    """
    try:
        from PIL import Image
        with Image.open(LOGO_PATH) as image:
            image = image.convert('RGBA')
            image.thumbnail((1600, 1600))
            try:
                import numpy as np
                pixels = np.array(image)
                white = (pixels[..., :3] > 225).all(axis=2) & (pixels[..., 3] > 0)
                pixels[white, 0:3] = 70  # conserva el alfa del logotipo original
                image = Image.fromarray(pixels, 'RGBA')
            except ImportError:
                points = image.load()
                for y in range(image.height):
                    for x in range(image.width):
                        red, green, blue, alpha = points[x, y]
                        if alpha and red > 225 and green > 225 and blue > 225:
                            points[x, y] = (70, 70, 70, alpha)
            stream = io.BytesIO()
            image.save(stream, format='PNG')
            return stream.getvalue()
    except Exception:
        logger.warning('ACM PDF: no se pudo preparar el logotipo', exc_info=True)
        try:
            with open(LOGO_PATH, 'rb') as handle:
                return handle.read()
        except OSError:
            return None


def _maps_key(static=True):
    try:
        from django.conf import settings
        if static:
            key=getattr(settings,'GOOGLE_MAPS_STATIC_API_KEY','') or os.environ.get('GOOGLE_MAPS_STATIC_API_KEY','')
            if key:return key
        return (getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
                or getattr(settings, 'google_maps_api_key', '')
                or DEFAULT_MAPS_KEY)
    except Exception:
        return DEFAULT_MAPS_KEY


_GEOCODE_CACHE = {}


def _static_map(center, markers, key, size=(640, 420), zoom=15, fetch=True,
                deadline=None):
    """Descarga un mapa estático sin pines de portales (colores genéricos)."""
    if not fetch or not key or not center:
        return None
    if deadline is not None and time.monotonic() > deadline:
        return None
    try:
        import requests
        params = {
            'center': f'{center[0]},{center[1]}', 'zoom': zoom,
            'size': f'{min(size[0],640)}x{min(size[1],640)}', 'scale': 2, 'maptype': 'roadmap',
            'language': 'es', 'key': key,
        }
        if markers:
            params['markers'] = markers
        response = requests.get('https://maps.googleapis.com/maps/api/staticmap',
                                params=params, timeout=6)
        content_type = response.headers.get('Content-Type', '')
        if response.status_code == 200 and response.content and content_type.startswith('image'):
            return response.content
        logger.warning('ACM PDF: mapa no disponible (HTTP %s). Comprueba Maps Static API y su clave de servidor.', response.status_code)
    except Exception:
        logger.warning('ACM PDF: no se pudo descargar el mapa', exc_info=True)
    return None


def _reverse_geocode(lat, lng, key, fetch=True):
    """Dirección legible para la portada; cae a coordenadas si no hay servicio."""
    if fetch and key:
        try:
            import requests
            response = requests.get(
                'https://maps.googleapis.com/maps/api/geocode/json',
                params={'latlng': f'{lat},{lng}', 'key': key, 'language': 'es'},
                timeout=6,
            )
            payload = response.json()
            if payload.get('status') == 'OK' and payload.get('results'):
                address = payload['results'][0].get('formatted_address')
                if address:
                    return _clean(address)
        except Exception:
            logger.warning('ACM PDF: no se pudo resolver la dirección', exc_info=True)
    return f'{lat:.5f}, {lng:.5f}'


def _zona_text(lat, lng, key, fetch=True):
    """Dirección de la zona, memorizada para no repetir consultas idénticas."""
    cache_key = (round(lat, 6), round(lng, 6), bool(fetch))
    if cache_key not in _GEOCODE_CACHE:
        _GEOCODE_CACHE[cache_key] = _reverse_geocode(lat, lng, key, fetch)
    return _GEOCODE_CACHE[cache_key]


def _bar_chart(labels, values, average):
    """Gráfico de barras con la línea del precio promedio (estilo de referencia)."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        figure, axis = plt.subplots(figsize=(7.6, 4.1), dpi=160)
        positions = list(range(len(values)))
        axis.bar(positions, values, width=.62, color=C_BAR, label='Comparables', zorder=2)
        axis.axhline(average, color=C_LINE, linewidth=2.6, label='Promedio', zorder=3)
        axis.plot(positions, [average] * len(values), 'o', color=C_LINE,
                  markersize=6, zorder=4)
        axis.set_ylim(0, max(values + [average]) * 1.18)
        axis.set_xticks(positions)
        axis.set_xticklabels(labels, fontsize=8, color='#666666')
        axis.grid(axis='y', color='#e8e8e8', linewidth=.8)
        axis.set_axisbelow(True)
        for side in ('top', 'right'):
            axis.spines[side].set_visible(False)
        for side in ('left', 'bottom'):
            axis.spines[side].set_color('#cccccc')
        axis.tick_params(colors='#666666', labelsize=8)
        axis.legend(loc='upper center', bbox_to_anchor=(.5, 1.14), ncol=2,
                    frameon=False, fontsize=8)
        figure.tight_layout()
        stream = io.BytesIO()
        figure.savefig(stream, format='png')
        plt.close(figure)
        return stream.getvalue()
    except Exception:
        logger.warning('ACM PDF: no se pudo dibujar el gráfico', exc_info=True)
        return None


def _croquis(center, points, radius):
    """Croquis referencial sin servicios externos: sujeto, comparables y radio.

    Se usa solo si el mapa de calles no está disponible, para no dejar la
    ubicación vacía. No incluye marcas ni pines de ningún portal.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle

        lat0, lng0 = center

        def to_xy(lat, lng):
            return ((lng - lng0) * 111320 * math.cos(math.radians(lat0)),
                    (lat - lat0) * 110540)

        figure, axis = plt.subplots(figsize=(7.4, 4.7), dpi=160)
        axis.add_patch(Circle((0, 0), radius, fill=False, linestyle='--',
                              linewidth=1.1, edgecolor='#9fb8c8', zorder=1))
        offsets = []
        for index, (lat, lng) in enumerate(points):
            x, y = to_xy(lat, lng)
            offsets.append((x, y))
            axis.plot([x], [y], marker='o', markersize=9, color='#d64545', zorder=3)
            axis.annotate(str(index + 1), (x, y), color='white', fontsize=7,
                          ha='center', va='center', zorder=4)
        axis.plot([0], [0], marker='D', markersize=11, color=C_DARK, zorder=5)
        axis.annotate('P', (0, 0), color='white', fontsize=7.5,
                      ha='center', va='center', zorder=6)
        extent = max([radius, 60] + [max(abs(x), abs(y)) for x, y in offsets]) * 1.18
        axis.set_xlim(-extent, extent)
        axis.set_ylim(-extent, extent)
        axis.set_aspect('equal')
        axis.set_xlabel('metros (este)', fontsize=8, color='#666666')
        axis.set_ylabel('metros (norte)', fontsize=8, color='#666666')
        axis.tick_params(labelsize=7, colors='#777777')
        axis.grid(color='#e6ecef', linewidth=.8)
        axis.set_axisbelow(True)
        for side in ('top', 'right'):
            axis.spines[side].set_visible(False)
        for side in ('left', 'bottom'):
            axis.spines[side].set_color('#cccccc')
        figure.tight_layout()
        stream = io.BytesIO()
        figure.savefig(stream, format='png')
        plt.close(figure)
        return stream.getvalue()
    except Exception:
        logger.warning('ACM PDF: no se pudo dibujar el croquis', exc_info=True)
        return None

def _selection(records, result, excluded):
    """Comparables que sustentan el resultado del ACM."""
    excluded = set(excluded or ())
    by_id = {row['id']: row for row in records}
    used_ids = []
    for row_id in list(result.get('land_ids', [])) + list(result.get('house_ids', [])):
        if row_id in by_id and row_id not in excluded and row_id not in used_ids:
            used_ids.append(row_id)
    if result.get('model') == 'components':
        recommended = [detail['id'] for detail in result.get('breakdown', [])
                       if detail.get('usable')]
        used_ids = ([row_id for row_id in used_ids if by_id[row_id]['kind'] != 'Casa']
                    + [row_id for row_id in recommended
                       if row_id in by_id and row_id not in excluded])
    return [by_id[row_id] for row_id in used_ids]


def build_acm_pdf(params, records, result, excluded=(), generated_at=None,
                  user=None, fetch_images=True):
    """Construye el informe PDF (A4) con la identidad de Propify."""
    from .report_selection import report_records, report_values
    records=report_records(params,records,excluded)
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                    PageBreak, PageTemplate, Paragraph, Spacer,
                                    Table, TableStyle)

    generated_at = generated_at or datetime.now()
    new = result.get('new')
    used = _selection(records, result, excluded)
    target_kind = params.get('property_type', 'Casa')
    excluded_set = set() if 'report_ids' in params else set(excluded or ())
    # Comparables completos del tipo analizado: la evidencia de mercado del informe.
    market = sorted(
        (row for row in records
         if row['kind'] == target_kind and not row.get('issues')
         and row['id'] not in excluded_set),
        key=lambda row: row.get('distance') or 0,
    )
    market_ids = {row['id'] for row in market}
    used_ids = {row['id'] for row in used}
    # Registros del tipo analizado que no entraron al cálculo (solo referencia).
    reference = [row for row in records
                 if row['kind'] == target_kind and row['id'] not in used_ids
                 and row['id'] not in market_ids and row['id'] not in excluded_set]
    key = _maps_key()
    deadline = time.monotonic() + 45 if fetch_images else None
    location_maps={}
    if fetch_images:
        def location_image(row):
            return row['id'],_static_map((row['lat'],row['lng']),[f'color:red|{row["lat"]},{row["lng"]}'],key,size=(320,240),zoom=16,deadline=deadline)
        with ThreadPoolExecutor(max_workers=4) as pool:
            location_maps=dict(pool.map(location_image,records))

    styles = {
        'band': ParagraphStyle('band', fontName='Helvetica-Bold', fontSize=23,
                               leading=27, textColor=colors.white, alignment=TA_CENTER),
        'section': ParagraphStyle('section', fontName='Helvetica-Bold', fontSize=17,
                                  leading=20, textColor=colors.HexColor(C_DARK),
                                  alignment=TA_CENTER, spaceBefore=2, spaceAfter=6),
        'center': ParagraphStyle('center', fontName='Helvetica', fontSize=10,
                                 leading=13, textColor=colors.HexColor(C_TEXT),
                                 alignment=TA_CENTER),
        'center_small': ParagraphStyle('center_small', fontName='Helvetica',
                                       fontSize=8.7, leading=11.5,
                                       textColor=colors.HexColor(C_TEXT),
                                       alignment=TA_CENTER),
        'center_bold': ParagraphStyle('center_bold', fontName='Helvetica-Bold',
                                      fontSize=11, leading=14,
                                      textColor=colors.HexColor(C_DARK),
                                      alignment=TA_CENTER),
        'label': ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=9.2,
                                leading=12.5, textColor=colors.HexColor(C_TEXT)),
        'value': ParagraphStyle('value', fontName='Helvetica', fontSize=10,
                                leading=13, textColor=colors.HexColor(C_TEXT)),
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10.5,
                               leading=15, textColor=colors.HexColor(C_TEXT),
                               alignment=TA_JUSTIFY),
        'result_label': ParagraphStyle('result_label', fontName='Helvetica-Bold',
                                       fontSize=11.5, leading=15,
                                       textColor=colors.HexColor(C_TEXT)),
        'result_value': ParagraphStyle('result_value', fontName='Helvetica-Bold',
                                       fontSize=12.5, leading=15,
                                       textColor=colors.HexColor(C_DARK),
                                       alignment=TA_RIGHT),
    }

    page_width, page_height = A4
    margin = 20 * mm
    width = page_width - 2 * margin
    logo = _logo_bytes()

    def decorate(canvas, doc):
        canvas.saveState()
        if logo:
            try:
                reader = ImageReader(io.BytesIO(logo))
                logo_width, logo_height = reader.getSize()
                draw_width = 40 * mm
                canvas.drawImage(reader, margin, page_height - 20 * mm,
                                 width=draw_width,
                                 height=draw_width * logo_height / logo_width,
                                 mask='auto')
            except Exception:
                logger.warning('ACM PDF: no se pudo dibujar el logotipo', exc_info=True)
        canvas.setStrokeColor(colors.HexColor(C_PRIMARY))
        canvas.setLineWidth(1.6)
        canvas.line(margin, 16 * mm, page_width - margin, 16 * mm)
        canvas.setFillColor(colors.HexColor(C_MUTED))
        canvas.setFont('Helvetica', 8)
        canvas.drawString(margin, 12 * mm,
                          f'{_fecha_larga(generated_at)} (La Información es Aproximada)')
        canvas.restoreState()

    def centered(flowable, space=6):
        return Table([[flowable]], colWidths=[width],
                     style=TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                       ('TOPPADDING', (0, 0), (-1, -1), space),
                                       ('BOTTOMPADDING', (0, 0), (-1, -1), space),
                                       ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                       ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))

    def zona():
        return escape(_zona_text(params['lat'], params['lng'], _maps_key(static=False), fetch_images))

    def squared(text, style):
        """Párrafo con el cuadro teal de la referencia (sin glifos de símbolos)."""
        box = Table([['']], colWidths=[3 * mm], rowHeights=[3 * mm])
        box.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(C_PRIMARY)),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                 ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                 ('TOPPADDING', (0, 0), (-1, -1), 0),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
        row = Table([[box, Paragraph(text, style)]],
                    colWidths=[7 * mm, width - 7 * mm])
        row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                 ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                 ('TOPPADDING', (0, 0), (-1, -1), 3),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
        return row

    story = []

    # ---------------------------------------------------------------- Portada
    story.append(Spacer(1, 14 * mm))
    banner = Table([[Paragraph('ANÁLISIS COMPARATIVO<br/>DE MERCADO', styles['band'])]],
                   colWidths=[width])
    banner.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(C_PRIMARY)),
                                ('TOPPADDING', (0, 0), (-1, -1), 16),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
                                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 10)]))
    story.append(banner)
    story.append(Spacer(1, 12 * mm))

    subject_center = (params['lat'], params['lng'])
    used_points = [(row['lat'], row['lng']) for row in (records if 'report_ids' in params else used)]
    cover_markers = [f'color:0x047d7d|label:P|{params["lat"]},{params["lng"]}']
    cover_image = _static_map(subject_center, cover_markers, key, size=(700, 460),
                              zoom=16, fetch=fetch_images, deadline=deadline)
    if not cover_image:
        cover_image = _croquis(subject_center, [], params['radius'])
    if cover_image:
        iw,ih=ImageReader(io.BytesIO(cover_image)).getSize()
        image = Image(io.BytesIO(cover_image), width=120 * mm,
                      height=120 * mm * ih / iw)
        image.hAlign = 'CENTER'
        story.append(image)
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(zona(), styles['center_bold']))
    story.append(Spacer(1, 10 * mm))
    author = _clean(getattr(user, 'get_full_name', lambda: '')() or
                    getattr(user, 'username', '') or '', 'Propify')
    story.append(Paragraph(f'Preparado Por {escape(author)}', styles['center_bold']))
    story.append(PageBreak())

    # ------------------------------------------------------ Propiedad sujeto
    story.append(Paragraph('PROPIEDAD SUJETO', styles['section']))
    story.append(centered(Paragraph(f'<b>ZONA :</b> {zona()}', styles['center'])))
    story.append(Spacer(1, 6 * mm))
    areas = Table([[
        Paragraph(f'<b>ÁREA TERRENO :</b> {_number(params.get("land"), 2, " m²") if params.get("land") else "No aplica"}', styles['center_small']),
        Paragraph(f'<b>ÁREA CONSTRUIDA :</b> {_number(params.get("built"), 2, " m²") if params.get("built") else "No aplica"}', styles['center_small']),
        Paragraph('<b>ANTIGÜEDAD :</b> Sin informar', styles['center_small']),
    ]], colWidths=[width / 3] * 3)
    areas.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    story.append(areas)
    story.append(Spacer(1, 12 * mm))

    chart_rows = market or used
    unit_rows = [(row, _unit_price(row)) for row in chart_rows]
    unit_rows = [(row, unit) for row, unit in unit_rows if unit]
    average = mean([unit for _, unit in unit_rows]) if unit_rows else None
    story.append(Paragraph('PRECIO PROMEDIO DE VENTA POR M2', styles['section']))
    story.append(centered(Paragraph(_money(average), styles['center_bold'])))
    if unit_rows:
        labels = [f'{index + 1}. {_money(unit)}' for index, (_, unit) in enumerate(unit_rows)]
        chart = _bar_chart(labels, [unit for _, unit in unit_rows], average)
        if chart:
            image = Image(io.BytesIO(chart), width=155 * mm,
                          height=155 * mm * 4.1 / 7.6)
            image.hAlign = 'CENTER'
            story.append(Spacer(1, 4 * mm))
            story.append(image)
    story.append(PageBreak())

    # ------------------------------------------------------------ Ubicación
    story.append(Paragraph('UBICACIÓN DE LAS PROPIEDADES', styles['section']))
    markers = [f'color:0x047d7d|label:P|{params["lat"]},{params["lng"]}']
    map_rows=records if 'report_ids' in params else used
    numbered = [row for row in map_rows if row['kind'] != 'Terreno'][:9]
    for index, row in enumerate(numbered):
        markers.append(f'color:red|label:{index + 1}|{row["lat"]},{row["lng"]}')
    others = [row for row in map_rows if row not in numbered]
    if others:
        markers.append('size:mid|color:blue|' + '|'.join(f'{row["lat"]},{row["lng"]}' for row in others))
    map_image = _static_map(subject_center, markers, key, size=(640, 500), zoom=15,
                            fetch=fetch_images, deadline=deadline)
    croquis_fallback = not map_image
    if croquis_fallback:
        map_image = _croquis(subject_center, used_points, params['radius'])
    if map_image:
        iw,ih=ImageReader(io.BytesIO(map_image)).getSize()
        image = Image(io.BytesIO(map_image), width=width, height=width * ih / iw)
        image.hAlign = 'CENTER'
        story.append(image)
        if croquis_fallback:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(
                'Croquis referencial de distancias: no representa un mapa de calles.',
                styles['center_small']))
    story.append(Spacer(1, 8 * mm))
    story.append(squared(f'<b>Propiedad Sujeto :</b> {zona()}', styles['value']))
    story.append(squared(f'<b>Propiedades Comparables :</b> ' +
                         (f'{len(records)} propiedades seleccionadas para el informe' if 'report_ids' in params else f'{len(used)} propiedades usadas en la estimación'), styles['value']))
    story.append(PageBreak())

    # --------------------------------------------------------- Comparables
    def comparable_block(row, thumb):
        address = (_clean(row.get('district') or '')
                   or _clean(row.get('title') or '', 'Sin dirección'))
        facts = [
            ('ÁREA TERRENO', _number(row.get('land'), 2, ' m²')),
            ('ÁREA CONSTRUIDA', _number(row.get('built'), 2, ' m²')),
            ('PRECIO', _money(row.get('price'))),
            ('PRECIO M2', _money(_unit_price(row))),
            ('FECHA DE PUBLICACIÓN', _fecha_corta(row.get('first_seen') or row.get('last_seen'))),
        ]
        facts_table = Table(
            [[Paragraph(f'<b>{label} :</b>', styles['label']),
              Paragraph(value, styles['value'])] for label, value in facts],
            colWidths=[47 * mm, width - 68 * mm - 47 * mm] if thumb
            else [47 * mm, width - 47 * mm],
        )
        facts_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        if thumb:
            left = Image(io.BytesIO(thumb), width=64 * mm,
                         height=64 * mm * 240 / 320)
            body = Table([[left, facts_table]], colWidths=[68 * mm, width - 68 * mm])
        else:
            body = Table([[facts_table]], colWidths=[width])
        body.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                  ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                  ('RIGHTPADDING', (0, 0), (0, 0), 6)]))
        return KeepTogether([
            Spacer(1, 5 * mm),
            centered(Paragraph(f'<b>DIRECCIÓN :</b> {escape(address)}', styles['center']), 2),
            Spacer(1, 3 * mm),
            body,
        ])

    def comparable_section(title, rows, limit):
        if not rows:
            return
        story.append(Paragraph(title, styles['section']))
        for index, row in enumerate(rows if 'report_ids' in params else rows[:limit]):
            thumb=location_maps.get(row['id'])
            if fetch_images and not thumb:
                thumb=_croquis((params['lat'],params['lng']),[(row['lat'],row['lng'])],params['radius'])
            story.append(comparable_block(row, thumb))
        story.append(PageBreak())

    comparable_section('COMPARABLES EN VENTA', market or used, 6)
    if target_kind != 'Terreno':
        comparable_section('TERRENOS DE REFERENCIA',
                           [row for row in used if row['kind'] == 'Terreno'], 4)
    comparable_section('COMPARABLES DE REFERENCIA', reference, 6)

    # ------------------------------------------------------------- Resultado
    story.append(Paragraph('RESULTADO', styles['section']))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        'El resultado de la estimación de valor de mercado de su propiedad es precisa y '
        'se ha realizado teniendo en consideración lo siguiente:', styles['body']))
    story.append(Spacer(1, 4 * mm))
    for text in (
        'Se ha realizado el estudio con comparables listados (otras propiedades), de '
        'similares características a la suya, que se encuentren ubicadas en su sector.',
        'Para identificar los comparables, se considera la cercanía y características '
        'específicas en la propiedad.',
        'El precio sugerido se ha calculado para obtener un precio de Venta óptimo en un '
        'tiempo razonable.',
    ):
        story.append(squared(text, styles['body']))
    story.append(Spacer(1, 8 * mm))
    if new:
        values = report_values(params,result)
        result_table = Table([
            [Paragraph('VALOR DE SALIDA AL MERCADO', styles['result_label']),
             Paragraph(_money(values['market_entry']), styles['result_value'])],
            [Paragraph('VALOR COMERCIAL', styles['result_label']),
             Paragraph(_money(values['commercial']), styles['result_value'])],
            [Paragraph('VALOR DE REALIZACIÓN INMEDIATA', styles['result_label']),
             Paragraph(_money(values['immediate']), styles['result_value'])],
        ], colWidths=[width * .58, width * .42])
        result_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(result_table)
        story.append(Spacer(1, 10 * mm))
    else:
        story.append(Paragraph(
            'No se obtuvo una estimación final porque faltaron comparables aptos para '
            'completar el método.', styles['body']))
        story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        'El precio puede ajustarse de acuerdo a su gusto, pero hay que tener en cuenta el '
        'efecto en las ofertas que recibirá y la cantidad de días que su propiedad '
        'permanecerá en el mercado.', styles['body']))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        'Un precio justo es la mejor manera de aumentar el interés de los compradores. '
        'Estoy a su disposición para atender a sus consultas.', styles['body']))

    buffer = io.BytesIO()
    document = BaseDocTemplate(
        buffer, pagesize=A4, leftMargin=margin, rightMargin=margin,
        topMargin=30 * mm, bottomMargin=22 * mm,
        title='Análisis comparativo de mercado',
        author=_clean(getattr(user, 'username', '') or '', 'Propify'),
        subject='ACM Propify',
    )
    frame = Frame(margin, 22 * mm, width, page_height - 30 * mm - 22 * mm, id='body')
    document.addPageTemplates([PageTemplate(id='acm', frames=[frame], onPage=decorate)])
    document.build(story)
    return buffer.getvalue()
