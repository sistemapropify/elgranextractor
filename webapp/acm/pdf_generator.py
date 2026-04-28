"""
Generador de PDF para ACM (Análisis Comparativo de Mercado).
Usa ReportLab para generar el PDF del lado del servidor.
Reemplaza la generación client-side con html2pdf.js.
"""
import io
import json
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def formatear_precio(valor):
    """Formatea un número como precio en USD."""
    if valor is None:
        return 'US$ 0.00'
    try:
        return f"US$ {float(valor):,.2f}"
    except (ValueError, TypeError):
        return 'US$ 0.00'


def formatear_precio_m2(valor):
    """Formatea precio por m²."""
    if valor is None:
        return '—'
    try:
        return f"US$ {float(valor):,.2f}/m²"
    except (ValueError, TypeError):
        return '—'


def generar_pdf_acm(acm_link):
    """
    Genera un PDF en memoria con el análisis ACM.
    
    Args:
        acm_link: Instancia de ACMLink con los datos del análisis.
    
    Returns:
        BytesIO con el contenido del PDF.
    """
    buffer = io.BytesIO()
    
    # Configurar documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2*cm,
        leftMargin=2*cm,
        rightMargin=2*cm,
    )
    
    # Colores de la marca
    COLOR_PRIMARY = colors.HexColor('#10b981')      # Verde principal
    COLOR_PRIMARY_DARK = colors.HexColor('#065f46')  # Verde oscuro
    COLOR_PRIMARY_LIGHT = colors.HexColor('#d1fae5') # Verde claro
    COLOR_BG_LIGHT = colors.HexColor('#f0fdf4')      # Fondo verde muy claro
    COLOR_TEXT = colors.HexColor('#1a1a2e')           # Texto principal
    COLOR_TEXT_MUTED = colors.HexColor('#6b7280')     # Texto secundario
    COLOR_BORDER = colors.HexColor('#e5e7eb')         # Borde
    COLOR_WHITE = colors.white
    COLOR_BLUE = colors.HexColor('#2563eb')           # Azul para precios secundarios
    
    # Estilos
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(
        'TituloACM',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=COLOR_PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=2,
        fontName='Helvetica-Bold',
    )
    
    style_subtitle = ParagraphStyle(
        'SubtituloACM',
        parent=styles['Normal'],
        fontSize=14,
        textColor=COLOR_TEXT_MUTED,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    
    style_small = ParagraphStyle(
        'SmallACM',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#999999'),
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    
    style_section_title = ParagraphStyle(
        'SectionTitleACM',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=COLOR_PRIMARY_DARK,
        spaceBefore=12,
        spaceAfter=6,
        fontName='Helvetica-Bold',
    )
    
    style_param_label = ParagraphStyle(
        'ParamLabelACM',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COLOR_TEXT_MUTED,
    )
    
    style_param_value = ParagraphStyle(
        'ParamValueACM',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COLOR_TEXT,
        fontName='Helvetica-Bold',
    )
    
    style_valor_grande = ParagraphStyle(
        'ValorGrandeACM',
        parent=styles['Normal'],
        fontSize=18,
        textColor=COLOR_BLUE,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    
    style_valor_central = ParagraphStyle(
        'ValorCentralACM',
        parent=styles['Normal'],
        fontSize=22,
        textColor=COLOR_WHITE,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    
    style_valor_central_label = ParagraphStyle(
        'ValorCentralLabelACM',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COLOR_WHITE,
        alignment=TA_CENTER,
    )
    
    style_valor_central_small = ParagraphStyle(
        'ValorCentralSmallACM',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#a7f3d0'),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    
    style_table_header = ParagraphStyle(
        'TableHeaderACM',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COLOR_WHITE,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    
    style_table_cell = ParagraphStyle(
        'TableCellACM',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COLOR_TEXT,
    )
    
    style_table_cell_right = ParagraphStyle(
        'TableCellRightACM',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COLOR_TEXT,
        alignment=TA_RIGHT,
    )
    
    style_table_cell_center = ParagraphStyle(
        'TableCellCenterACM',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COLOR_TEXT,
        alignment=TA_CENTER,
    )
    
    style_footer = ParagraphStyle(
        'FooterACM',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#999999'),
        alignment=TA_CENTER,
    )
    
    # Construir elementos del PDF
    elements = []
    
    # ============================================================
    # ENCABEZADO
    # ============================================================
    elements.append(Paragraph('PROPIFAI', style_title))
    elements.append(Paragraph('Análisis Comparativo de Mercado (ACM)', style_subtitle))
    elements.append(Paragraph('Compartido desde Propifai', style_small))
    elements.append(HRFlowable(width="100%", thickness=2, color=COLOR_PRIMARY, spaceAfter=12))
    
    # ============================================================
    # PARÁMETROS DEL ANÁLISIS
    # ============================================================
    # Caja verde claro con borde izquierdo
    params_data = [
        [Paragraph('Parámetros del Análisis', style_section_title)],
    ]
    
    tipo_label = acm_link.tipo_propiedad.capitalize() if acm_link.tipo_propiedad else '—'
    area_label = f"{float(acm_link.area_m2):,.0f} m²" if acm_link.area_m2 else '—'
    if acm_link.es_terreno:
        area_label += ' (terreno)'
    else:
        area_label += ' (construcción)'
    
    usuario_nombre = ''
    if acm_link.user:
        usuario_nombre = acm_link.user.username or str(acm_link.user.id)[:8]
    
    param_table = Table(
        [
            [
                Paragraph(f'<b>Tipo:</b> {tipo_label}', style_param_value),
                Paragraph(f'<b>Área:</b> {area_label}', style_param_value),
            ],
            [
                Paragraph(f'<b>Comparables:</b> {acm_link.num_comparables} propiedades', style_param_value),
                Paragraph(f'<b>Generado por:</b> {usuario_nombre}', style_param_value),
            ],
        ],
        colWidths=[doc.width * 0.45, doc.width * 0.45],
    )
    param_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    # Envolver en una tabla con fondo verde claro
    params_wrapper = Table(
        [[param_table]],
        colWidths=[doc.width],
    )
    params_wrapper.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEBEFORE', (0, 0), (0, 0), 4, COLOR_PRIMARY),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    elements.append(params_wrapper)
    elements.append(Spacer(1, 10))
    
    # ============================================================
    # VALORACIÓN ESTIMADA - 3 TARJETAS
    # ============================================================
    elements.append(Paragraph('Valoración Estimada', style_section_title))
    
    # Obtener valores
    valor_comercial = float(acm_link.valor_comercial) if acm_link.valor_comercial else 0
    precio_sugerido = float(acm_link.precio_venta_sugerido) if acm_link.precio_venta_sugerido else 0
    valor_realizacion = float(acm_link.valor_realizacion) if acm_link.valor_realizacion else 0
    precio_prom_pond = float(acm_link.precio_promedio_ponderado_m2) if acm_link.precio_promedio_ponderado_m2 else 0
    
    # Tarjeta izquierda: Precio Venta Sugerido
    card_width = doc.width / 3 - 4
    
    card1_data = [
        [Paragraph(formatear_precio(precio_sugerido), style_valor_grande)],
        [Paragraph('Precio Venta Sugerido', ParagraphStyle('c1l', parent=style_param_label, alignment=TA_CENTER))],
        [Paragraph('94.99% del comercial', ParagraphStyle('c1s', parent=style_param_label, fontSize=9, textColor=COLOR_PRIMARY, alignment=TA_CENTER))],
    ]
    card1 = Table(card1_data, colWidths=[card_width])
    card1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    
    # Tarjeta central: Valor Comercial (destacada)
    card2_data = [
        [Paragraph('ESTIMACIÓN PARA TU PROPIEDAD', ParagraphStyle('c2h', parent=style_valor_central_label, fontSize=9))],
        [Paragraph(formatear_precio(valor_comercial), style_valor_central)],
        [Paragraph('Valor Comercial (100%)', style_valor_central_label)],
        [Paragraph(f"Precio/m²: {formatear_precio_m2(precio_prom_pond)}", style_valor_central_small)],
    ]
    card2 = Table(card2_data, colWidths=[card_width])
    card2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    
    # Tarjeta derecha: Valor Realización
    card3_data = [
        [Paragraph(formatear_precio(valor_realizacion), style_valor_grande)],
        [Paragraph('Valor Realización Inmediata', ParagraphStyle('c3l', parent=style_param_label, alignment=TA_CENTER))],
        [Paragraph('90.00% del comercial', ParagraphStyle('c3s', parent=style_param_label, fontSize=9, textColor=COLOR_PRIMARY, alignment=TA_CENTER))],
    ]
    card3 = Table(card3_data, colWidths=[card_width])
    card3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    
    # Unir las 3 tarjetas en una fila
    cards_row = Table([[card1, card2, card3]], colWidths=[card_width + 4, card_width + 4, card_width + 4])
    cards_row.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(cards_row)
    elements.append(Spacer(1, 10))
    
    # ============================================================
    # TABLA DE PROPIEDADES COMPARABLES
    # ============================================================
    elements.append(Paragraph('Propiedades Comparables', style_section_title))
    
    # Preparar datos de propiedades
    propiedades = acm_link.propiedades_json
    if isinstance(propiedades, str):
        try:
            propiedades = json.loads(propiedades)
        except (json.JSONDecodeError, TypeError):
            propiedades = []
    
    # Encabezados de tabla
    header_style = style_table_header
    table_data = [
        [
            Paragraph('#', header_style),
            Paragraph('Tipo', header_style),
            Paragraph('Distrito', header_style),
            Paragraph('Precio', header_style),
            Paragraph('US$/m²', header_style),
            Paragraph('Distancia', header_style),
            Paragraph('Fuente', header_style),
        ]
    ]
    
    for i, p in enumerate(propiedades, 1):
        tipo = p.get('tipo', '—')
        distrito = p.get('distrito', '—')
        precio = formatear_precio(p.get('precio'))
        
        precio_m2_val = p.get('precio_m2_final') or p.get('precio_m2')
        if precio_m2_val:
            precio_m2_str = f"US$ {float(precio_m2_val):,.2f}"
        else:
            precio_m2_str = '—'
        
        distancia = p.get('distancia_metros')
        if distancia:
            dist_str = f"{float(distancia):,.0f} m"
        else:
            dist_str = '—'
        
        es_propifai = p.get('es_propify') or p.get('fuente') == 'propifai'
        fuente = 'Propifai' if es_propifai else 'Externo'
        
        # Alternar colores de fila
        bg_color = colors.HexColor('#f9fafb') if i % 2 == 0 else COLOR_WHITE
        
        table_data.append([
            Paragraph(str(i), style_table_cell_center),
            Paragraph(tipo, style_table_cell),
            Paragraph(distrito, style_table_cell),
            Paragraph(precio, style_table_cell_right),
            Paragraph(precio_m2_str, style_table_cell_right),
            Paragraph(dist_str, style_table_cell_right),
            Paragraph(fuente, style_table_cell_center),
        ])
    
    # Crear tabla de propiedades
    col_widths = [0.06 * doc.width, 0.14 * doc.width, 0.18 * doc.width, 0.22 * doc.width, 0.16 * doc.width, 0.14 * doc.width, 0.10 * doc.width]
    
    prop_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    prop_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    # Alternar colores de fila
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            prop_table.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f9fafb')),
            ]))
    
    elements.append(prop_table)
    elements.append(Spacer(1, 10))
    
    # ============================================================
    # ESTADÍSTICAS DE PRECIO POR m²
    # ============================================================
    elements.append(Paragraph('Estadísticas de Precio por m²', style_section_title))
    
    precio_min = float(acm_link.precio_min_m2) if acm_link.precio_min_m2 else 0
    precio_max = float(acm_link.precio_max_m2) if acm_link.precio_max_m2 else 0
    precio_prom = float(acm_link.precio_promedio_m2) if acm_link.precio_promedio_m2 else 0
    
    stats_data = [
        [
            Paragraph(f'<b>Mínimo:</b> {formatear_precio_m2(precio_min)}', style_param_value),
            Paragraph(f'<b>Máximo:</b> {formatear_precio_m2(precio_max)}', style_param_value),
        ],
        [
            Paragraph(f'<b>Promedio simple:</b> {formatear_precio_m2(precio_prom)}', style_param_value),
            Paragraph(f'<b>Promedio ponderado:</b> {formatear_precio_m2(precio_prom_pond)}', style_param_value),
        ],
    ]
    
    stats_table = Table(stats_data, colWidths=[doc.width * 0.45, doc.width * 0.45])
    stats_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    stats_wrapper = Table(
        [[stats_table]],
        colWidths=[doc.width],
    )
    stats_wrapper.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    elements.append(stats_wrapper)
    elements.append(Spacer(1, 20))
    
    # ============================================================
    # FOOTER
    # ============================================================
    elements.append(HRFlowable(width="100%", thickness=2, color=COLOR_PRIMARY, spaceAfter=8))
    elements.append(Paragraph('Propifai — Inteligencia Inmobiliaria', style_footer))
    elements.append(Paragraph('Arequipa, Perú — Este informe es una estimación basada en datos comparables del mercado.', style_footer))
    
    fecha_creacion = acm_link.created_at
    if fecha_creacion:
        fecha_str = fecha_creacion.strftime('%d/%m/%Y')
    else:
        fecha_str = datetime.now().strftime('%d/%m/%Y')
    
    codigo_display = acm_link.codigo or acm_link.short_id
    elements.append(Paragraph(f'{codigo_display} | {fecha_str}', style_footer))
    
    # Generar PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
