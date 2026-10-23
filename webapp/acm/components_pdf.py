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
    return f'$ {float(value):,.0f}'


def _number(value, decimals=0, suffix=''):
    if value is None:
        return 'Sin informar'
    return f'{float(value):,.0f}{suffix}'


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
            image = image.crop(image.getbbox())
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


def _property_photo(url, deadline=None):
    if not url or (deadline is not None and time.monotonic() >= deadline):
        return None
    try:
        from .portal_views import load_photo_bytes
        return load_photo_bytes(url)
    except Exception:
        logger.info('ACM PDF: fotografía no disponible; se conserva el informe.')
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
    """Teal price-per-square-metre bars with the adopted average line."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        if not values:return None
        canvas=Image.new('RGB',(1000,490),'white');draw=ImageDraw.Draw(canvas)
        def font(size):
            for path in ('arial.ttf','DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
                try:return ImageFont.truetype(path,size)
                except OSError:pass
            return ImageFont.load_default(size=size)
        left,right,top,bottom=28,972,34,389
        maximum=max(max(values),average,1)*1.18
        for i in range(1,5):
            y=bottom-(bottom-top)*i/4
            draw.line((left,y,right,y),fill='#edf3f3',width=2)
        step=(right-left)/len(values);bar=min(step*.62,130)
        for i,value in enumerate(values):
            x=left+step*(i+.5);y=bottom-(bottom-top)*value/maximum
            for py in range(int(y),bottom+1):
                f=(py-y)/max(1,bottom-y)
                color=tuple(int(a+(b-a)*f) for a,b in zip((213,239,239),(0,143,145)))
                draw.line((x-bar/2,py,x+bar/2,py),fill=color,width=1)
            draw.text((x,bottom+17),str(labels[i]),font=font(23),fill='#475569',anchor='mt')
            draw.text((x,bottom+49),f'$ {value:,.0f}',font=font(20),fill='#475569',anchor='mt')
        y=bottom-(bottom-top)*average/maximum
        draw.line((left,y,right,y),fill='#334155',width=3)
        for i in range(len(values)):
            x=left+step*(i+.5);draw.ellipse((x-4,y-4,x+4,y+4),fill='#334155')
        stream=io.BytesIO();canvas.save(stream,format='PNG');return stream.getvalue()
    except Exception:
        logger.warning('ACM PDF: no se pudo dibujar el gráfico',exc_info=True)
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
    """Portrait client report following the supplied Propify visual reference."""
    from .client_report import prepare_report, age, RESULT_LABELS
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import SimpleDocTemplate, Image, KeepInFrame, Paragraph, Spacer, Table, TableStyle
    data = prepare_report(params, records, result, excluded, generated_at, user, fetch_images)
    teal = colors.HexColor('#008f91')
    dark = colors.HexColor('#243238')
    muted = colors.HexColor('#66757a')
    width = 519
    styles = {
        'title': ParagraphStyle('client_title', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=teal, alignment=TA_CENTER),
        'section': ParagraphStyle('client_section', fontName='Helvetica-Bold', fontSize=13, leading=17, textColor=teal, spaceBefore=10, spaceAfter=7),
        'body': ParagraphStyle('client_body', fontName='Helvetica', fontSize=9, leading=12, textColor=dark),
        'small': ParagraphStyle('client_small', fontName='Helvetica', fontSize=7.3, leading=9.6, textColor=dark),
        'label': ParagraphStyle('client_label', fontName='Helvetica', fontSize=7, leading=9, textColor=muted),
        'bold': ParagraphStyle('client_bold', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=dark),
        'center': ParagraphStyle('client_center', fontName='Helvetica', fontSize=8, leading=11, textColor=muted, alignment=TA_CENTER),
    }
    def para(text, style='body'):
        return Paragraph(escape(str(text)), styles[style])
    def table(rows, widths, padding=0):
        t=Table(rows,colWidths=widths,hAlign='LEFT')
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),padding),
            ('RIGHTPADDING',(0,0),(-1,-1),padding),('TOPPADDING',(0,0),(-1,-1),padding),('BOTTOMPADDING',(0,0),(-1,-1),padding)]))
        return t
    def photo(image,w,h,placeholder='Sin fotografía disponible'):
        if image:
            try:
                iw,ih=ImageReader(io.BytesIO(image)).getSize()
                scale=min(w/iw,h/ih)
                pic=Image(io.BytesIO(image),width=iw*scale,height=ih*scale)
                box=Table([[pic]],colWidths=[w],rowHeights=[h])
                box.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
                return box
            except Exception:
                pass
        box=Table([[para(placeholder,'center')]],colWidths=[w],rowHeights=[h])
        box.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f0f7f7')),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        return box
    story=[]
    logo=photo(data['logo'],103,33,'Propify')
    author=[para('Preparado por:','label'),para(data['author'],'small')]
    header=table([[logo,author]],[365,154]);story.extend([header,Spacer(1,12),para('Análisis comparativo de mercado','title'),Spacer(1,3),para('Información aproximada al '+_fecha_larga(data['date']),'center'),Spacer(1,17)])
    facts=table([[para('Área de terreno','label'),para('Área construida','label'),para('Antigüedad','label')],
                 [para(_number(params.get('land'),2,' m²') if params.get('land') else 'No aplica','bold'),
                  para(_number(params.get('built'),2,' m²') if params.get('built') else 'No aplica','bold'),para(age(params.get('age')),'bold')]], [88,88,103])
    detail=[para('Ubicación','label'),para(data['address']),Spacer(1,7),para('Tipo de propiedad','label'),para(params.get('property_type','Casa'),'bold')]
    hero=table([[detail,facts]],[240,279])
    story.append(hero)
    story.append(para('Ubicación de las propiedades','section'))
    map_content=[photo(data['map'],245,142,'Mapa no disponible'),para('P  Propiedad sujeto  ·  Números: propiedades seleccionadas','label')]
    if data['croquis']:map_content.append(para('Croquis referencial de distancias; no representa un mapa de calles.','label'))
    chart_content=[para('PRECIO PROMEDIO DE VENTA POR M2','label'),para(_money(data['average'])+' /m²','bold'),photo(data['chart'],250,129,'Sin valores unitarios disponibles')]
    story.append(table([[map_content,chart_content]],[262,257]))
    for heading,rows in data['groups']:
        story.append(para(heading,'section'))
        columns=5
        cell_width=(width-8*(columns-1))/columns
        for offset in range(0,len(rows),columns):
            cards=[]
            for row in rows[offset:offset+columns]:
                n=data['rows'].index(row)+1
                card=[photo(data['photos'].get(row['id']),cell_width,46),Spacer(1,4),para(str(n)+'. '+_clean(row.get('kind'),'Inmueble'),'small')]
                card.extend([para('Terreno '+_number(row.get('land'),2,' m²')+' · Construcción '+_number(row.get('built'),2,' m²'),'small'),
                             para('Antigüedad: '+age(row.get('age')),'small'),
                             para(_clean(row.get('district') or row.get('title'),'Sin ubicación informada'),'small')])
                rental='alquil' in str(row.get('operation','')).lower()
                card.extend([para('Precio de alquiler mensual' if rental else 'Precio de venta','label'),para(_money(row.get('price')),'small'),
                             para(_money(_unit_price(row))+' /m²'+(' al mes' if rental else ''),'small')])
                cards.append(card)
            cards.extend(['']*(columns-len(cards)))
            cells=[];widths=[]
            for i,card in enumerate(cards):
                if i:cells.append('');widths.append(8)
                cells.append(card);widths.append(cell_width)
            story.extend([table([cells],widths),Spacer(1,5)])
    result_blocks=[para('Resultados','section')]
    if data['values']:
        values=[]
        for label,key in RESULT_LABELS:
            values.append([para(label,'label'),para(_money(data['values'][key]),'bold')])
        values_table=table(values,[168,100],padding=5)
        values_table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6f5f5'))]))
        result_blocks.append(table([[para(data['summary']),values_table]],[245,274]))
    else:
        result_blocks.append(para('No se obtuvo una estimación final porque faltaron comparables aptos.'))
    story.extend(result_blocks)
    pdm = data.get('pdm')
    if pdm:
        story.append(para('Zona de uso PDM','section'))
        story.append(para(
            f"{pdm['codigo']} · {pdm['nombre']} · {pdm['categoria']} · "
            f"Uso analizado: {pdm['property_type']}", 'bold'))
        if pdm['rows']:
            story.append(para('Parámetros normativos','label'))
            typologies = pdm['typologies'] or ['Parámetros']
            label_width = 118
            value_width = (width - label_width) / max(1, len(typologies))
            pdm_rows = [[para('Parámetro', 'label'),
                         *[para(value, 'label') for value in typologies]]]
            for item in pdm['rows']:
                values = list(item['values'])
                values += ['Sin informar'] * (len(typologies) - len(values))
                pdm_rows.append([para(item['label'], 'small'),
                                 *[para(value, 'small') for value in values]])
            pdm_table = Table(
                pdm_rows,
                colWidths=[label_width] + [value_width] * len(typologies),
                repeatRows=1,
                hAlign='LEFT',
            )
            pdm_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6f5f5')),
                ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#cfdfdf')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(pdm_table)
        if pdm['compatible_uses']:
            story.append(para('Usos compatibles: ' + pdm['compatible_uses'], 'small'))
        for note in pdm['notes']:
            story.append(para(note, 'label'))
    if data['notes']:
        story.append(para('Justificación u observaciones','section'))
        for line in data['notes'].split('\n'):
            story.append(para(line) if line else Spacer(1,6))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFillColor(teal);canvas.rect(0,0,A4[0],9,fill=1,stroke=0)
        canvas.setFont('Helvetica',8);canvas.setFillColor(muted)
        canvas.drawCentredString(A4[0]/2,21,'www.propify.pe')
        canvas.drawRightString(A4[0]-38,21,str(doc.page));canvas.restoreState()
    stream=io.BytesIO()
    doc=SimpleDocTemplate(stream,pagesize=A4,leftMargin=38,rightMargin=38,topMargin=29,bottomMargin=37,
                          title='Análisis comparativo de mercado',author=data['author'],subject='ACM Propify')
    doc.build([KeepInFrame(width-12,A4[1]-29-37-12,story,mode='shrink')],onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()
