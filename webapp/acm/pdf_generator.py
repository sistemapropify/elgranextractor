import io
import json
import os
import logging
import requests
from django.utils import timezone
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image
)
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

C_PRIMARY = '#279896'
C_DARK = '#047d7d'
C_MUTED = '#6b7280'
C_BORDER = '#e0e0e0'
C_BG = '#f4fafa'
C_TEXT = '#1a1a2e'

LOGO_PATH = os.path.join(settings.BASE_DIR, 'acm', 'static', 'acm', 'img', 'LOGO-PROPIFY.png')


def fmt_precio(valor):
    if valor is None: return 'US$ 0.00'
    try: return f"US$ {float(valor):,.2f}"
    except: return 'US$ 0.00'


def fmt_pm2(valor):
    if valor is None: return '---'
    try: return f"US$ {float(valor):,.2f}/m²"
    except: return '---'


def construir_url_mapa(lat, lng, props, radio, api_key, w=800, h=350):
    center = f"{lat},{lng}"
    marks = [f"color:red|label:P|{lat},{lng}"]
    colores = ['blue', 'purple', 'orange', 'brown', 'green']
    for i, p in enumerate(props[:10]):
        pl = p.get('lat') or p.get('latitude')
        pn = p.get('lng') or p.get('longitude')
        if pl is not None and pn is not None:
            marks.append(f"color:{colores[i%len(colores)]}|label:{i+1}|{pl},{pn}")
    params = {'center': center, 'zoom': 15, 'size': f'{w}x{h}', 'maptype': 'roadmap',
              'markers': '|'.join(marks), 'key': api_key}
    return f"https://maps.googleapis.com/maps/api/staticmap?{urlencode(params, doseq=True)}"


def generar_pdf_acm(acm_link):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=0.0*cm, bottomMargin=0.5*cm,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()

    s_section = ParagraphStyle('Sec', parent=styles['Heading2'],
        fontSize=12, textColor=colors.HexColor(C_DARK), spaceBefore=3, spaceAfter=2, fontName='Helvetica-Bold')
    s_body = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor(C_TEXT), leading=12)
    s_bold = ParagraphStyle('Bold', parent=s_body, fontName='Helvetica-Bold')
    s_right = ParagraphStyle('R', parent=s_body, alignment=TA_RIGHT)
    s_small = ParagraphStyle('Sml', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor(C_MUTED), alignment=TA_CENTER)
    s_footer = ParagraphStyle('Ftr', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor(C_MUTED), alignment=TA_CENTER)

    elements = [Spacer(1, 0.001*mm)]

    codigo_disp = acm_link.codigo or acm_link.short_id
    fecha_str = acm_link.created_at.strftime('%d/%m/%Y') if acm_link.created_at else timezone.now().strftime('%d/%m/%Y')

    # ---- HEADER: fondo verde oscuro con logo + título ----
    logo_img = None
    try:
        if os.path.exists(LOGO_PATH):
            logo_img = Image(LOGO_PATH, width=3.5*cm, height=1.3*cm)
    except Exception:
        pass

    hdr_style = ParagraphStyle('Hdr', parent=styles['Normal'],
        fontSize=14, textColor=colors.white, fontName='Helvetica-Bold', leading=16)

    if logo_img:
        logo_img._restrictDrawing = False
        hdr = Table(
            [[logo_img, Paragraph(
                f'<b>Análisis Comparativo de Mercado (ACM)</b><br/>'
                f'<font size="7" color="#a7f3d0">{codigo_disp} | {fecha_str}</font>', hdr_style)]],
            colWidths=[4*cm, doc.width - 4*cm]
        )
        hdr.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#047d7d')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(hdr)
    else:
        elements.append(Paragraph('PROPIFY', ParagraphStyle('BT', parent=styles['Heading1'],
            fontSize=22, textColor=colors.HexColor(C_PRIMARY), alignment=TA_CENTER, spaceAfter=1, fontName='Helvetica-Bold')))
        elements.append(Paragraph(f'ACM — {codigo_disp} | {fecha_str}', s_small))

    elements.append(Spacer(1, 2))

    # ---- PARÁMETROS ----
    tipo = acm_link.tipo_propiedad.capitalize() if acm_link.tipo_propiedad else '---'
    area_v = float(acm_link.area_m2) if acm_link.area_m2 else 0
    area_l = f"{area_v:,.0f} m²{' (terreno)' if acm_link.es_terreno else ' (construcción)'}"
    usuario = acm_link.user.username[:20] if acm_link.user and acm_link.user.username else '---'

    pt = Table([
        [Paragraph(f'<b>Tipo:</b> {tipo}', s_body), Paragraph(f'<b>Área:</b> {area_l}', s_body)],
        [Paragraph(f'<b>Comparables:</b> {acm_link.num_comparables} propiedades', s_body),
         Paragraph(f'<b>Usuario:</b> {usuario}', s_body)],
    ], colWidths=[doc.width*0.48, doc.width*0.48])
    pt.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    pw = Table([[pt]], colWidths=[doc.width])
    pw.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(C_BG)),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor(C_PRIMARY)),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(pw)
    elements.append(Spacer(1, 6))

    # ---- VALORACIÓN (3 tarjetas) ----
    elements.append(Paragraph('Valoración Estimada', s_section))

    vc = float(acm_link.valor_comercial) if acm_link.valor_comercial else 0
    ps = float(acm_link.precio_venta_sugerido) if acm_link.precio_venta_sugerido else 0
    vr = float(acm_link.valor_realizacion) if acm_link.valor_realizacion else 0
    pp = float(acm_link.precio_promedio_ponderado_m2) if acm_link.precio_promedio_ponderado_m2 else 0

    cw = doc.width / 3 - 3

    def tarjeta(price, tit, sub, center=False):
        bg_c = colors.HexColor(C_PRIMARY) if center else colors.white
        txt_c = colors.white if center else colors.HexColor(C_PRIMARY)
        st_p = ParagraphStyle('p', parent=styles['Normal'], fontSize=16, textColor=colors.white if center else colors.HexColor(C_PRIMARY), alignment=TA_CENTER, fontName='Helvetica-Bold', leading=18)
        st_t = ParagraphStyle('t', parent=styles['Normal'], fontSize=8.5, textColor=colors.white if center else colors.HexColor(C_MUTED), alignment=TA_CENTER, leading=11)
        st_s = ParagraphStyle('s', parent=styles['Normal'], fontSize=7.5, textColor=colors.white if center else colors.HexColor(C_PRIMARY), alignment=TA_CENTER, leading=9)
        d = [[Paragraph(fmt_precio(price), st_p)], [Paragraph(tit, st_t)]]
        if sub: d.append([Paragraph(sub, st_s)])
        t = Table(d, colWidths=[cw])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_c),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor(C_BORDER) if not center else colors.HexColor(C_DARK)),
        ]))
        return t

    cr = Table([[tarjeta(ps, 'Precio Venta Sugerido', '94.99% del comercial'),
                 tarjeta(vc, 'Valor Comercial (100%)', f'$/m²: {fmt_pm2(pp)}', center=True),
                 tarjeta(vr, 'Valor Realización', '90.00% del comercial')]],
               colWidths=[cw+3, cw+3, cw+3])
    cr.setStyle(TableStyle([('ALIGN', (0,0),(-1,-1),'CENTER'), ('VALIGN', (0,0),(-1,-1),'TOP'),
                            ('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1)]))
    elements.append(cr)
    elements.append(Spacer(1, 8))

    # ---- MAPA ----
    props = acm_link.propiedades_json
    if isinstance(props, str):
        try: props = json.loads(props)
        except: props = []

    api_key = getattr(settings, 'google_maps_api_key', getattr(settings, 'GOOGLE_MAPS_API_KEY', 'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q'))

    lat_c = lng_c = None
    if props:
        lats = [float(p['lat']) for p in props if p.get('lat')]
        lngs = [float(p['lng']) for p in props if p.get('lng')]
        if lats and lngs: lat_c, lng_c = sum(lats)/len(lats), sum(lngs)/len(lngs)

    mapa = None
    if lat_c and lng_c and api_key:
        try:
            url = construir_url_mapa(lat_c, lng_c, props, 500, api_key)
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                from reportlab.lib.utils import ImageReader
                mapa = Image(ImageReader(r.content), width=doc.width, height=doc.width*0.38)
        except Exception as e:
            logger.warning(f"Mapa error: {e}")

    if mapa:
        elements.append(Paragraph('Ubicación de Comparables', s_section))
        mc = Table([[mapa]], colWidths=[doc.width])
        mc.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'), ('BOX',(0,0),(-1,-1),0.5,colors.HexColor(C_BORDER)),
                                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
        elements.append(mc)

    # ---- TARJETAS DE COMPARABLES ----
    elements.append(Paragraph('Propiedades Comparables', s_section))

    for idx, p in enumerate(props):
        pm2 = p.get('precio_m2_final') or p.get('precio_m2') or 0
        dist = float(p.get('distancia_metros', 0))
        fuente = 'Propifai' if p.get('es_propify') or p.get('fuente')=='propifai' else 'Externo'
        habs = p.get('habitaciones', '---')
        banos = p.get('baños', '---')
        area = p.get('metros_construccion') or p.get('metros_terreno') or '---'

        cd = [[
            Paragraph(f'<font size="10" color="{C_PRIMARY}"><b>#{idx+1}</b></font> '
                      f'<font size="10"><b>{p.get("tipo","---")}</b></font>', s_body),
            Paragraph(f'<font size="9" color="{C_DARK}"><b>{fmt_precio(p.get("precio"))}</b></font>', s_right),
        ], [
            Paragraph(
                f'<b>{p.get("distrito","---")}</b> — {area} m² — {fmt_pm2(pm2)} — {dist:,.0f}m'
                f' | {habs} hab {banos} ba | {fuente}',
                ParagraphStyle('Det', parent=s_small, fontSize=7, leading=9, textColor=colors.HexColor(C_MUTED))
            ),
        ]]

        ct = Table(cd, colWidths=[doc.width*0.58, doc.width*0.32])
        ct.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1),
            ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
        ]))

        cw2 = Table([[ct]], colWidths=[doc.width])
        bg_c = colors.HexColor('#f8fafc') if idx%2==0 else colors.white
        cw2.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1), bg_c),
            ('LINEBELOW',(0,0),(-1,0), 0.5, colors.HexColor(C_BORDER)),
            ('LINEBEFORE',(0,0),(0,-1), 2.5, colors.HexColor(C_PRIMARY)),
            ('TOPPADDING',(0,0),(-1,-1), 3),('BOTTOMPADDING',(0,0),(-1,-1), 3),
            ('LEFTPADDING',(0,0),(-1,-1), 5),('RIGHTPADDING',(0,0),(-1,-1), 5),
        ]))
        elements.append(cw2)

    elements.append(Spacer(1, 6))

    # ---- ESTADÍSTICAS ----
    elements.append(Paragraph('Estadísticas de Precio por m²', s_section))

    pmin = float(acm_link.precio_min_m2) if acm_link.precio_min_m2 else 0
    pmax = float(acm_link.precio_max_m2) if acm_link.precio_max_m2 else 0
    prom = float(acm_link.precio_promedio_m2) if acm_link.precio_promedio_m2 else 0

    st = Table([
        [Paragraph('<b>Mínimo:</b>', s_body), Paragraph(fmt_pm2(pmin), s_bold),
         Paragraph('<b>Máximo:</b>', s_body), Paragraph(fmt_pm2(pmax), s_bold)],
        [Paragraph('<b>Promedio:</b>', s_body), Paragraph(fmt_pm2(prom), s_bold),
         Paragraph('<b>Ponderado:</b>', s_body), Paragraph(fmt_pm2(pp), s_bold)],
    ], colWidths=[doc.width*0.12, doc.width*0.30, doc.width*0.12, doc.width*0.30])
    st.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
        ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
    ]))
    sw = Table([[st]], colWidths=[doc.width])
    sw.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(C_BG)),
        ('LINEABOVE',(0,0),(-1,0), 1.5, colors.HexColor(C_PRIMARY)),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
    ]))
    elements.append(sw)
    elements.append(Spacer(1, 12))

    # ---- FOOTER ----
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(C_PRIMARY), spaceAfter=4))
    elements.append(Paragraph('Propify — Inteligencia Inmobiliaria', s_footer))
    elements.append(Paragraph('Arequipa, Perú — Este informe es una estimación basada en datos comparables del mercado.', s_footer))
    elements.append(Paragraph(f'{codigo_disp} | {fecha_str}', s_footer))

    doc.build(elements)
    buffer.seek(0)
    return buffer
