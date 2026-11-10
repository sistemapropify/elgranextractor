from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Manual_Sistema_Catastro_Maestro_Arequipa.pdf"
DRONE = ROOT / "tmp" / "pdfs" / "drone_cayma_thumb.jpg"

SNAPSHOT = "2026-11-09 18:56 America/Lima"
REVISION = "8073"
R2_UPLOADED = "3,751"
R2_TOTAL_STATE = "3,764"
R2_COMPLETE = "1,464"
R2_PARTIAL = "2,287"
R2_FAILED = "13"
R2_MISSING_DOCS = "3,107"
ACTIVE_DISTRICT = "Alto Selva Alegre"
ACTIVE_PROCESSED = "105 en la ultima pasada"
ACTIVE_REMAINING = "20,960"
D1_GALLERY_TOTAL = "7,410"
D1_FORMAL_DETAIL = "664"

NAVY = HexColor("#14213D")
BLUE = HexColor("#1F5A94")
CYAN = HexColor("#0B7895")
LIGHT = HexColor("#EEF4F8")
PALE = HexColor("#F6F9FB")
GRID = HexColor("#C7D3DE")
ORANGE = HexColor("#D97706")
RED = HexColor("#B42318")
GREEN = HexColor("#18794E")
MUTED = HexColor("#52606D")


pdfmetrics.registerFont(TTFont("Manual", r"C:\Windows\Fonts\arial.ttf"))
pdfmetrics.registerFont(TTFont("Manual-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
pdfmetrics.registerFontFamily("Manual", normal="Manual", bold="Manual-Bold")


try:
    BASE = getSampleStyleSheet()
except Exception:
    BASE = None

STYLES = {
    "title": ParagraphStyle(
        "title", fontName="Manual-Bold", fontSize=28, leading=34,
        textColor=colors.white, spaceAfter=10),
    "subtitle": ParagraphStyle(
        "subtitle", fontName="Manual", fontSize=12, leading=18,
        textColor=HexColor("#DDEAF2")),
    "h1": ParagraphStyle(
        "h1", fontName="Manual-Bold", fontSize=20, leading=25,
        textColor=NAVY, spaceBefore=4, spaceAfter=10),
    "h2": ParagraphStyle(
        "h2", fontName="Manual-Bold", fontSize=14, leading=18,
        textColor=BLUE, spaceBefore=12, spaceAfter=6),
    "h3": ParagraphStyle(
        "h3", fontName="Manual-Bold", fontSize=10.5, leading=14,
        textColor=CYAN, spaceBefore=8, spaceAfter=3),
    "body": ParagraphStyle(
        "body", fontName="Manual", fontSize=8.8, leading=13.2,
        textColor=HexColor("#202A34"), spaceAfter=5),
    "small": ParagraphStyle(
        "small", fontName="Manual", fontSize=7.4, leading=10.5,
        textColor=MUTED, spaceAfter=3),
    "bullet": ParagraphStyle(
        "bullet", fontName="Manual", fontSize=8.5, leading=12.5,
        leftIndent=12, firstLineIndent=-7, bulletIndent=2,
        textColor=HexColor("#202A34"), spaceAfter=3),
    "table": ParagraphStyle(
        "table", fontName="Manual", fontSize=6.4, leading=8.2,
        textColor=HexColor("#202A34")),
    "table_small": ParagraphStyle(
        "table_small", fontName="Manual", fontSize=5.8, leading=7.3,
        textColor=HexColor("#202A34")),
    "table_head": ParagraphStyle(
        "table_head", fontName="Manual-Bold", fontSize=6.2, leading=8,
        textColor=colors.white),
    "caption": ParagraphStyle(
        "caption", fontName="Manual", fontSize=7.3, leading=10,
        textColor=MUTED, alignment=TA_CENTER, spaceBefore=3, spaceAfter=6),
    "cover_note": ParagraphStyle(
        "cover_note", fontName="Manual", fontSize=9, leading=13,
        textColor=NAVY),
    "callout": ParagraphStyle(
        "callout", fontName="Manual", fontSize=8.4, leading=12.5,
        textColor=NAVY, spaceAfter=0),
    "code": ParagraphStyle(
        "code", fontName="Courier", fontSize=6.8, leading=9.4,
        textColor=HexColor("#1D2935")),
}


def p(text, style="body"):
    return Paragraph(text, STYLES[style])


def bullet(text):
    return Paragraph(text, STYLES["bullet"], bulletText="•")


def e(value):
    return escape(str(value))


def callout(title, text, tone=BLUE):
    table = Table(
        [[Paragraph("<b>" + e(title) + "</b><br/>" + text, STYLES["callout"])]],
        colWidths=[174 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.7, tone),
        ("LINEBEFORE", (0, 0), (0, -1), 4, tone),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def section(title, subtitle=None):
    items = [PageBreak(), p(e(title), "h1")]
    if subtitle:
        items.append(p(e(subtitle), "small"))
        items.append(Spacer(1, 4))
    return items


def header_row(values):
    return [Paragraph(e(value), STYLES["table_head"]) for value in values]


def data_table(headers, rows, widths, small=False, alignments=None):
    body = [header_row(headers)]
    style = STYLES["table_small" if small else "table"]
    for row in rows:
        body.append([
            Paragraph(e(value), style) if not isinstance(value, Paragraph) else value
            for value in row
        ])
    table = Table(body, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    for index in range(1, len(body)):
        if index % 2 == 0:
            commands.append(("BACKGROUND", (0, index), (-1, index), PALE))
    if alignments:
        for column, alignment in alignments.items():
            commands.append(("ALIGN", (column, 1), (column, -1), alignment))
    table.setStyle(TableStyle(commands))
    return table


class SystemFlow(Flowable):
    def __init__(self):
        super().__init__()
        self.width = 174 * mm
        self.height = 78 * mm

    def draw(self):
        c = self.canv
        labels = [
            ("1. FUENTES", "GeoLlaqta / COFOPRI\nArcGIS, galerias, reportes"),
            ("2. CAPTURA", "Valida, descarga y conserva\nestado reanudable"),
            ("3. R2", "Originales, manifiestos,\nvectores e imagenes"),
            ("4. D1", "Entidades normalizadas,\ncampos, relaciones y auditoria"),
            ("5. APLICACIONES", "Catastro Maestro, ACM,\nfichas, mapas y planos"),
        ]
        box_w = 68
        box_h = 48
        gap = 12
        y = 18
        for index, (title, detail) in enumerate(labels):
            x = 4 + index * (box_w + gap)
            fill = LIGHT if index < 4 else HexColor("#E8F3EC")
            c.setFillColor(fill)
            c.setStrokeColor(BLUE if index < 4 else GREEN)
            c.roundRect(x, y, box_w, box_h, 6, fill=1, stroke=1)
            c.setFillColor(NAVY)
            c.setFont("Manual-Bold", 7)
            c.drawString(x + 6, y + 35, title)
            c.setFont("Manual", 5.8)
            for line_index, line in enumerate(detail.split("\n")):
                c.drawString(x + 6, y + 24 - line_index * 9, line)
            if index < 4:
                c.setStrokeColor(ORANGE)
                c.setLineWidth(1.2)
                c.line(x + box_w + 2, y + 24, x + box_w + gap - 2, y + 24)
                c.line(x + box_w + gap - 5, y + 27, x + box_w + gap - 2, y + 24)
                c.line(x + box_w + gap - 5, y + 21, x + box_w + gap - 2, y + 24)
        c.setFillColor(MUTED)
        c.setFont("Manual", 6.2)
        c.drawString(4, 6, "R2 conserva originales y copias inmutables; D1 es la fuente de verdad normalizada para todas las aplicaciones.")


class ManualTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=16 * mm,
            title="Manual completo del Sistema Catastro Maestro",
            author="Prometeo / ACM",
            subject="Arquitectura, flujo, PCDPI, R2, D1, imágenes y datos",
            **kwargs,
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="main",
        )
        self.addPageTemplates([
            PageTemplate(id="body", frames=[frame], onPage=self._page)
        ])

    def _page(self, canvas, doc):
        if doc.page == 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.35)
        canvas.line(18 * mm, 12.5 * mm, 192 * mm, 12.5 * mm)
        canvas.setFont("Manual", 6.7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 8.7 * mm, "Manual integral - Catastro Maestro Arequipa")
        canvas.drawRightString(192 * mm, 8.7 * mm, "Pagina %d" % doc.page)
        canvas.restoreState()


class Cover(Flowable):
    def __init__(self):
        super().__init__()
        self.width = 174 * mm
        self.height = 245 * mm

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.rect(0, 122 * mm, self.width, 123 * mm, fill=1, stroke=0)
        c.setFillColor(CYAN)
        c.rect(0, 118 * mm, self.width, 4 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Manual-Bold", 11)
        c.drawString(12 * mm, 221 * mm, "PROMETEO / ACM")
        c.setFont("Manual-Bold", 28)
        c.drawString(12 * mm, 184 * mm, "Sistema Catastro")
        c.drawString(12 * mm, 168 * mm, "Maestro Arequipa")
        c.setFont("Manual", 12)
        c.setFillColor(HexColor("#DDEAF2"))
        c.drawString(12 * mm, 151 * mm, "Manual integral de arquitectura, datos y flujo")
        c.drawString(12 * mm, 144 * mm, "PCDPI, GeoLlaqta, R2, D1, expedientes y fotogramas")
        c.setFillColor(colors.white)
        c.roundRect(12 * mm, 40 * mm, 150 * mm, 62 * mm, 7, fill=0, stroke=1)
        c.setFillColor(NAVY)
        c.setFont("Manual-Bold", 10)
        c.drawString(18 * mm, 90 * mm, "Corte documental")
        c.setFont("Manual", 8.6)
        c.drawString(18 * mm, 80 * mm, SNAPSHOT)
        c.drawString(18 * mm, 70 * mm, "Fuente de verdad publicada: D1")
        c.drawString(18 * mm, 60 * mm, "Archivo original e inmutable: R2")
        c.drawString(18 * mm, 50 * mm, "Datos vectoriales D1: 263,375 entidades de lote")
        c.setFont("Manual", 7.8)
        c.setFillColor(MUTED)
        c.drawString(12 * mm, 18 * mm, "Documento generado desde el codigo y los objetos reales del sistema.")


def cover():
    return [
        Cover(),
        Spacer(1, 1),
    ]


def toc():
    entries = [
        ("1", "Resumen ejecutivo"),
        ("2", "Glosario: que es cada pieza"),
        ("3", "Arquitectura y flujo completo"),
        ("4", "PCDPI en detalle"),
        ("5", "Formalizacion y sistemas de referencia"),
        ("6", "R2: objetos, rutas y campos"),
        ("7", "D1: tablas y diccionario de campos"),
        ("8", "Expedientes, galerias y documentos"),
        ("9", "Fotogramas, ortofotos, raster y Georreferenciacion"),
        ("10", "Flujo de actualizacion y publicacion"),
        ("11", "Inventario actual por distrito"),
        ("12", "Estado de migracion y lecturas correctas"),
        ("13", "Seguridad, integridad y auditoria"),
        ("14", "Limitaciones y datos que no deben inventarse"),
        ("15", "Apendices: campos y rutas de referencia"),
    ]
    rows = [[number, title] for number, title in entries]
    return [
        PageBreak(),
        p("Contenido", "h1"),
        data_table(["No.", "Seccion"], rows, [16 * mm, 150 * mm]),
        Spacer(1, 7),
        callout(
            "Correccion documental importante",
            "R2 si almacena copias vectoriales. Conserva snapshots comprimidos de lotes, "
            "manzanas y vias bajo <b>geollaqta/vectores/</b>, ademas de expedientes en "
            "<b>geollaqta/[ubigeo]/[lote]/</b>, fichas formalizadas y parches raster. "
            "La afirmacion anterior de que R2 solo guardaba expedientes era incompleta.",
            ORANGE,
        ),
    ]


def executive():
    rows = [
        ["Lotes vectoriales en D1", "263,375 entidades de lote con geometria"],
        ["Manzanas vectoriales en D1", "22,841"],
        ["Vias vectoriales en D1", "28,189"],
        ["Lotes publicados en la capa PCDPI", "95,649 en 10 distritos"],
        ["Registros de formalizacion", "162,487 en 28 distritos"],
        ["Lotes con galeria vinculada en D1", "7,410"],
        ["Fichas formales importadas en D1", "664"],
        ["Lotes con archivos en R2", "3,751"],
        ["Lotes R2 completos", "1,464"],
        ["Lotes R2 parciales", "2,287"],
        ["Distrito en captura documental", "Alto Selva Alegre"],
    ]
    return [
        *section("1. Resumen ejecutivo", "Que contiene el sistema y como se interpreta el inventario."),
        data_table(["Indicador", "Valor"], rows, [58 * mm, 108 * mm]),
        Spacer(1, 6),
        p(
            "El sistema separa cuatro responsabilidades. <b>GeoLlaqta/COFOPRI</b> es la fuente externa. "
            "<b>R2</b> conserva originales, snapshots vectoriales, expedientes y parches de imagen. "
            "<b>D1</b> conserva la informacion normalizada y las relaciones que consultan las aplicaciones. "
            "Los <b>consumidores</b> -Catastro Maestro, ACM, fichas y mapas- leen D1 y no deben depender de "
            "consultas a pedido a GeoLlaqta.", "body"),
        callout(
            "Lectura correcta de los 263,375",
            "Es el total de entidades de lote almacenadas en D1. No debe interpretarse automaticamente "
            "como 263,375 parcelas fisicas unicas: una parcela puede estar representada por la capa "
            "PCDPI y por formalizacion. D1 conserva ambas procedencias; la deduplicacion geometrica "
            "es una conciliacion separada.",
            RED,
        ),
        Spacer(1, 6),
        p(
            "Datos aportados por cada nivel: la geometria y ubicacion provienen de los snapshots vectoriales; "
            "las medidas documentales se extraen de reportes PDF y del servicio de formalizacion; los titulares, "
            "observaciones, fotografias y documentos dependen de la galeria publicada por COFOPRI.", "body"),
    ]


def glossary():
    rows = [
        ["GeoLlaqta", "Portal publico de COFOPRI que reune mapas, fichas, reportes PDF, fotografias y servicios oficiales."],
        ["COFOPRI", "Organismo de Formalizacion de la Propiedad Informal. Es la autoridad de origen de estos datos."],
        ["PCDPI", "Capa ArcGIS oficial llamada <b>Catastro Urbano PCDPI</b>. Es una coleccion vectorial de lotes urbanos; no es una ortofoto ni un PDF."],
        ["PCDPI - contenido", "Geometria de lotes y atributos como ID_LOTE, sector, manzana, lote, areas, niveles, unidades, uso, CUC y anio catastral."],
        ["Formalizacion", "Cartografia de predios formalizados en servicios WGS84 y PSAD56, con reporte oficial por RPU."],
        ["D1", "Base maestra Cloudflare D1. Fuente de verdad normalizada que consumen las aplicaciones."],
        ["R2", "Almacen privado de objetos compatible con S3. Guarda originales, manifiestos, snapshots vectoriales y raster."],
        ["Manifiesto", "JSON <b>datos.json</b> que describe un lote, sus archivos, hashes, reportes y faltantes."],
        ["SHA-256", "Huella criptografica que permite comprobar que un archivo no cambio."],
        ["PCDPI / PSAD56", "PSAD56 es un datum antiguo (EPSG:4248). ArcGIS entrega la consulta reproyectada a EPSG:4326."],
        ["WGS84", "Sistema geografico EPSG:4326 usado por Google Maps, D1 y la geometria publicada."],
        ["Raster", "Imagen compuesta por pixeles. Una fotografia aerea, ortofoto o plano escaneado puede ser raster."],
        ["Vector", "Geometria definida por coordenadas: punto, linea o poligono. Un lote es normalmente un poligono."],
        ["LoD", "Nivel de detalle de geometria, datos o imagen."],
    ]
    return [
        *section("2. Glosario: que es cada pieza"),
        data_table(["Concepto", "Definicion"], rows, [34 * mm, 132 * mm]),
        Spacer(1, 7),
        callout(
            "PCDPI en una frase",
            "<b>PCDPI no es una imagen.</b> Es la capa vectorial de Catastro Urbano PCDPI publicada por "
            "COFOPRI. Las fichas y fotografias se obtienen aparte desde la galeria GeoLlaqta y los reportes "
            "PDF oficiales.",
            BLUE,
        ),
    ]


def architecture():
    rows = [
        ["Aplicacion", "Consume"],
        ["Catastro Maestro", "D1: entidades, atributos, geometria, relaciones, medios y procedencia."],
        ["ACM", "D1 para fichas y lotes; R2 solo mediante rutas controladas para servir el original."],
        ["Visor de planos", "D1: versiones, metadatos, observaciones y geometria revisada."],
        ["Panel de captura", "Estado local, R2 y D1; muestra progreso y permite reanudar."],
        ["Mapa raster", "D1: versiones raster; R2: bytes de imagen verificados por SHA-256."],
    ]
    return [
        *section("3. Arquitectura y flujo completo", "Desde la fuente externa hasta cada pantalla."),
        SystemFlow(),
        Spacer(1, 6),
        data_table(["Componente", "Responsabilidad"], rows, [36 * mm, 130 * mm]),
        Spacer(1, 7),
        p("Flujo de un lote PCDPI", "h2"),
        bullet("<b>Descubrimiento:</b> el recolector consulta el inventario ArcGIS del distrito y obtiene los OBJECTID."),
        bullet("<b>Atributos:</b> consulta en lotes de 100 los campos configurados y recibe geometria en EPSG:4326."),
        bullet("<b>Galeria:</b> descarga <b>vistadetalle.php?id_lote=...</b>, que contiene enlaces a fichas, reportes y fotos."),
        bullet("<b>Conservacion:</b> descarga los PDFs, HTML y JPG; crea <b>datos.json</b> y una copia inmutable <b>datos-[sha].json</b>."),
        bullet("<b>R2:</b> sube cada objeto y guarda su SHA-256 y tamano en el ledger local."),
        bullet("<b>Normalizacion:</b> el manifiesto se convierte en entidades, atributos, titulares, linderos, actos y medios."),
        bullet("<b>D1:</b> registra una version inmutable, contribuciones por campo, identidades, selecciones y journal de auditoria."),
        bullet("<b>Publicacion:</b> ACM, Catastro Maestro y fichas leen la misma identidad D1 y obtienen los medios por clave R2."),
        Spacer(1, 6),
        p("Regla de oro", "h2"),
        callout(
            "R2 y D1 no duplican el mismo papel",
            "<b>R2</b> conserva bytes y objetos originales. <b>D1</b> conserva el modelo consultable y la procedencia. "
            "La verdad funcional para mapas y fichas es D1; R2 evita depender de GeoLlaqta y permite recuperar el original.",
            GREEN,
        ),
    ]


def pcdpi():
    fields = [
        ["OBJECTID", "Identificador interno ArcGIS."],
        ["COD_LOTE / COD_MZNA / COD_SECT", "Codigos cortos de lote, manzana y sector."],
        ["ID_LOTE", "Codigo catastral principal; se usa en la galeria GeoLlaqta."],
        ["ID_MZNA", "Identificador de manzana."],
        ["HAB_URBANA / MZNA_MUNI / LOTE_MUNI", "Habilitacion urbana y numeracion municipal."],
        ["NRO_UNIDADES / NIVELES", "Unidades y niveles, cuando existen."],
        ["ZONIFICACION / ESTRUCTURACION", "Clasificacion urbanistica."],
        ["MEP / ECS / ECC", "Indicadores tecnicos y de estado de servicios."],
        ["AGUA / LUZ / TELEFONO / DESAGUE", "Disponibilidad de servicios."],
        ["AREA_TER / AREA_CON", "Areas de terreno y construccion publicadas por PCDPI. Pueden ser nulas."],
        ["AREA_GRAFICA", "Area calculada desde la geometria de la fuente."],
        ["ID_PUEBLO_TIT / ID_PREDIO_RPU", "Identificadores de pueblo y predio formal."],
        ["ID_PLANO / ANIO_CAT / CUC", "Plano, anio de catastro y Codigo Unico Catastral."],
        ["FECH_TRAN / CODI_USER", "Fecha de transferencia y usuario de carga."],
        ["SHAPE", "Geometria poligonal del lote."],
        ["SHAPE.AREA / SHAPE.LEN", "Area y longitud geometricas calculadas por ArcGIS."],
    ]
    return [
        *section("4. PCDPI en detalle", "Catastro Urbano PCDPI: servicio vectorial oficial, no una fotografia."),
        p(
            "El servicio oficial declarado es <b>Catastro Urbano PCDPI</b>, con referencia espacial "
            "EPSG:4326. La capa <b>Lotes</b> es la capa 10. Sus atributos describen el lote y su "
            "geometria; no contienen los bytes de las fichas.", "body"),
        data_table(["Campo PCDPI", "Significado"], fields, [62 * mm, 104 * mm]),
        Spacer(1, 7),
        p("Cobertura PCDPI en Arequipa", "h2"),
        p(
            "La capa publica lotes en 10 distritos de Arequipa y suma <b>95,649</b> registros de lote. "
            "En los otros 19 distritos el servicio devuelve cero. Esos distritos pueden seguir teniendo "
            "vectores y reportes de formalizacion, pero no una galeria PCDPI por lote.", "body"),
        callout(
            "Que se puede obtener desde PCDPI",
            "Geometria y atributos del lote. Para titulares, PDFs, fotografia y observaciones, el sistema "
            "debe abrir la galeria GeoLlaqta enlazada por ID_LOTE. La capa PCDPI por si sola no entrega esos archivos.",
            ORANGE,
        ),
    ]


def formalization():
    rows = [
        ["Fuente", "CRS de origen", "Uso"],
        ["FORMALIZACION_WGS84", "EPSG:4326", "Predios formalizados ya en coordenadas WGS84."],
        ["FORMALIZACION_PSAD56", "EPSG:4248", "Predios formalizados en datum PSAD56; ArcGIS los entrega reproyectados a EPSG:4326."],
        ["reporte/lote.php + ws_cofopri", "WGS84 en salida", "Reporte oficial por RPU: ubicacion, titulo, areas y linderos."],
    ]
    return [
        *section("5. Formalizacion y sistemas de referencia", "Que datos aporta y como se evita mezclar datums."),
        data_table(["Fuente", "CRS", "Funcion"], rows, [50 * mm, 35 * mm, 81 * mm]),
        Spacer(1, 6),
        bullet("PSAD56 y WGS84 se consultan por separado y se deduplican por RPU al combinarse en la migracion."),
        bullet("El servicio ArcGIS devuelve geometria en EPSG:4326, pero la procedencia conserva el CRS original."),
        bullet("El reporte por RPU aporta urbanizacion, area de terreno, frente, derecha, izquierda, fondo, colindancias y estado del titulo."),
        bullet("Si el endpoint no publica area construida o numero de unidades, el sistema deja el valor vacio. No lo inventa."),
        p("Estructura del JSON formalizado", "h2"),
        p(
            "Ruta: <b>geollaqta/formalizacion/[ubigeo]/[source]/[RPU].json</b>. "
            "Ejemplo real: <b>geollaqta/formalizacion/040101/psad56/P06081968.json</b>, 1,793 bytes.", "body"),
        data_table(
            ["Grupo", "Campos"],
            [
                ["Identidad", "source, source_name, ID_PREDIO_RPU, OBJECTID, FORMALIZATION_DETAIL_STATUS"],
                ["Ubicacion", "FI_CODPRE, CODPJV, MZNA, LOTE, EDI_PISO, EDI_DPTO, NOMPJV, SECTOR, DISTRITO, PROVINCIA"],
                ["Titulo", "FECHA_TITULO, ESTADO_TITULO, FI_EST_REGIS, TIPOADJU, OBSERVACION, ULTIMA_ACTUALIZACION"],
                ["Medidas", "PM_AREPRE, PM_LTEFRE, PM_LTEDER, PM_LTEIZQ, PM_LTEFON"],
                ["Colindancias", "FC_FRENTE, FC_DERECHA, FC_IZQUIERDA, FC_FONDO"],
                ["Uso", "TIPO_USO, FI_TIPUSO, TIPO_PREDIO, TT_CODIGO, ESTADO, SITUACION"],
            ],
            [35 * mm, 131 * mm],
        ),
        Spacer(1, 6),
        callout(
            "Ejemplo real verificado",
            "P06081968: area 789.12 m2; frente 33 m; derecha 32.04 m; izquierda 29.50 m; fondo 20.50 m; "
            "titulo inscrito el 18/03/2000; urbanizacion Asentamiento Humano Misericordia Senor.",
            GREEN,
        ),
    ]


def r2_section():
    key_rows = [
        ["geollaqta/[ubigeo]/[ID_LOTE]/datos.json", "Manifiesto mutable de acceso rapido para el lote."],
        [".../datos-[sha256].json", "Copia inmutable del manifiesto."],
        [".../detalle-[sha].html", "HTML original de la galeria GeoLlaqta."],
        [".../reporte-[record].pdf", "Reporte catastral oficial."],
        [".../ficha-[record].pdf", "Ficha individual, bienes comunes, actividad economica u otra ficha publicada."],
        [".../[lote]-[sha].jpg", "Fotografia de fachada."],
        ["geollaqta/formalizacion/[ubigeo]/[source]/[RPU].json", "Respuesta normalizada del reporte formalizado."],
        ["geollaqta/vectores/index.json", "Indice de todos los snapshots vectoriales."],
        ["geollaqta/vectores/[ubigeo]/[capa].part-NNNN.json.gz", "Snapshot PCDPI comprimido, hasta 4,000 features por parte."],
        ["geollaqta/vectores/[ubigeo]/[source]/[capa]...", "Snapshots PSAD56 o WGS84."],
        ["geollaqta/maestro/raster/[sha].jpg|png", "Imagen de dron o parche raster verificado."],
        ["geollaqta/maestro/derivados/...", "Derivados vectoriales o assets generados desde originales."],
    ]
    object_rows = [
        ["02032032-77b54c0c5aeaa530.jpg", "42,833", "Fotografia de fachada"],
        ["datos-4c356a....json", "290,660", "Manifiesto inmutable"],
        ["datos.json", "290,660", "Manifiesto de acceso"],
        ["detalle-4825d6....html", "6,816", "HTML original"],
        ["ficha-0401292013030004245-....pdf", "6,231", "Ficha de actividad economica"],
        ["reporte-0401292013010039224-....pdf", "46,123", "Reporte catastral"],
    ]
    return [
        *section("6. R2: objetos, rutas y campos", "El archivo privado de originales, vectores y raster."),
        callout(
            "R2 si contiene vectores",
            "Los snapshots vectoriales existen en R2 como JSON gzip por partes. El indice real contiene "
            "204 snapshots de lotes, manzanas y vias para distintas fuentes y distritos.",
            BLUE,
        ),
        Spacer(1, 6),
        data_table(["Prefijo / ruta", "Contenido"], key_rows, [79 * mm, 87 * mm], small=True),
        Spacer(1, 7),
        p("Ejemplo real: lote 04012902032032", "h2"),
        data_table(["Objeto", "Bytes", "Tipo"], object_rows, [78 * mm, 24 * mm, 64 * mm], small=True),
        Spacer(1, 5),
        p(
            "El manifiesto declara <b>lot_id</b>, <b>district_ubigeo</b>, <b>source_url</b>, "
            "<b>retrieved_at</b>, <b>feature</b>, <b>artifacts</b>, <b>reports</b> y <b>missing</b>. "
            "Cada artifact contiene <b>type</b>, <b>filename</b>, <b>source_url</b>, <b>bytes</b> y <b>sha256</b>; "
            "los PDFs agregan <b>record_id</b>, <b>document_name</b> y <b>form_number</b>.", "body"),
        p("Ejemplo real de snapshot vectorial", "h2"),
        p(
            "Alto Selva Alegre PCDPI: <b>24,705 lotes</b> distribuidos en 7 partes comprimidas. "
            "La primera mide 327,020 bytes y contiene 4,000 features; el total descomprimido declarado "
            "es 12,468,697 bytes. Manzanas: 1,700 features. El objeto se valida con el SHA-256 guardado en el indice.",
            "body"),
    ]


def d1_section():
    tables = [
        ["sources", "Fuente y distrito al que pertenece."],
        ["versions", "Version inmutable, fecha, CRS, georreferenciacion, original y payload."],
        ["entities", "Entidad maestra: lote, manzana, via, edificacion u otra."],
        ["identities", "Relacion entre un identificador de fuente y la entidad maestra."],
        ["contributions", "Valor de cada campo por version y su evidencia."],
        ["selections", "Campo ganador actualmente publicado para cada entidad."],
        ["current_attributes", "Tabla plana consultable con todos los campos actuales."],
        ["people", "Titulares y personas."],
        ["relationships", "Relaciones de propiedad y otras relaciones."],
        ["media", "Punteros R2 a PDFs, fotos, HTML y manifiestos."],
        ["boundary_segments", "Frente, derecha, izquierda, fondo, longitud y evidencia."],
        ["registral_acts", "Datos registrales y de titulacion."],
        ["external_identifiers", "RPU, CUC y otros identificadores externos."],
        ["addresses", "Direcciones estructuradas y geocodificacion."],
        ["property_observations", "Observaciones documentales por campo."],
        ["zones / environment_features", "Zonas y footprints de raster u otros elementos."],
        ["coverage_records", "Cobertura declarada por ubigeo y dataset."],
        ["journal", "Auditoria de cada revision."],
        ["plan_workspace / plan_notes", "Revision de planos y notas."],
        ["catalog_review_status/events", "Revision y trazabilidad de catalogos."],
    ]
    groups = [
        ["Identificacion", "country_code, ubigeo, postal_code, department, province, district, zone, sector"],
        ["Lote y ubicacion", "urbanization, block, lot, building, entrance, floor, unit"],
        ["Direccion", "address, address_block, address_lot, street_type, street_name, municipal_number"],
        ["Registro", "condition, registry_office, registry_entry_type, notary_name, notary_kardex, deed_date, registry_folios, registry_seat, property_registration_date"],
        ["Construccion registral", "construction_declaration, construction_registration_seat, construction_registration_date"],
        ["Identificadores", "cuc, cadastral_reference, registry_entry_number"],
        ["Uso", "cadastral_use, observed_use, zoning, use_category, business_category, business_subcategory, ciiu_code, ciiu_version, commercial_name"],
        ["Areas", "land_area, built_area, geometric_land_area, gis_land_area, gis_built_area"],
        ["Perimetro", "front, back, left, right, perimeter"],
        ["Construccion y espacios", "bedrooms, bathrooms, half_bathrooms, parking_spaces, floors, units"],
        ["Indicadores espaciales", "is_corner, is_through, faces_park"],
    ]
    coverage = [
        ["Area de terreno", "152,100", "Documental o SIG; no toda es medida oficial."],
        ["Area construida", "5,501", "Documental o SIG."],
        ["Frente", "536", "Campo actual; hay 645 lotes con cuatro segmentos documentales."],
        ["Derecha", "418", "Campo actual."],
        ["Izquierda", "411", "Campo actual."],
        ["Fondo", "504", "Campo actual."],
        ["Cuatro linderos actuales", "302", "Solo 302 lotes tienen los cuatro campos simultaneamente."],
        ["Perimetro total", "0", "La columna existe, pero ningun lote tiene aun el total persistido."],
        ["Urbanizacion", "664", "Solo se ha importado la formalizacion detallada actual."],
        ["Uso catastral", "148,601", "Proviene principalmente de vectores."],
        ["Pisos / unidades", "77,797 / 3,435", "Cobertura parcial."],
        ["Esquina", "0", "La columna existe, pero no hay valores migrados."],
        ["Frente a parque", "0", "La columna existe, pero no hay valores migrados."],
    ]
    return [
        *section("7. D1: tablas y diccionario de campos", "Modelo normalizado, procedencia y campos actuales."),
        p(
            "D1 usa una tabla maestra de entidades y tablas relacionadas. Cada aporte de una fuente queda "
            "en <b>contributions</b>; <b>selections</b> decide que contribucion esta activa. Por eso un campo "
            "puede reemplazarse o auditarse sin borrar la version original.", "body"),
        data_table(["Tabla D1", "Funcion"], tables, [48 * mm, 118 * mm], small=True),
        Spacer(1, 7),
        p("Campos de current_attributes", "h2"),
        data_table(["Grupo", "Campos principales"], groups, [33 * mm, 133 * mm]),
        Spacer(1, 7),
        KeepTogether([
            p("Completitud actual de campos en D1", "h2"),
            data_table(
                ["Campo o grupo", "Lotes con dato", "Lectura"],
                coverage, [43 * mm, 25 * mm, 98 * mm], small=True),
            Spacer(1, 6),
            callout(
                "Procedencia por campo",
                "Cuando la ficha muestra un area, una fecha o un titular, D1 puede recuperar la version, "
                "archivo, pagina, campo original, SHA-256 y fuente que produjeron ese valor. Esto permite "
                "distinguir dato documental, dato SIG y dato calculado.",
                GREEN,
            ),
        ]),
    ]


def records_and_gallery():
    rows = [
        ["REPORTE CATASTRAL", "PDF del reporte completo; contiene ubicacion, titulares, areas, uso y linderos."],
        ["FICHA INDIVIDUAL", "PDF con el detalle registral/catastral individual de la unidad."],
        ["FICHA BIENES COMUNES", "PDF de areas y bienes comunes."],
        ["FICHA ACTIVIDAD ECONOMICA", "PDF de actividad registrada."],
        ["Otra ficha fichaXXX.php", "Se conserva si el portal la publica y la URL es segura."],
        ["Fotografia de fachada", "JPG/PNG desde img_catastro."],
    ]
    media_fields = [
        ["id", "Identificador del medio."],
        ["entity_id", "Lote, unidad u otra entidad a la que pertenece."],
        ["kind", "facade_image, interior_image, cadastral_report_pdf, individual_record_pdf, etc."],
        ["object_key", "Ruta exacta del archivo en R2."],
        ["sha256", "Huella de integridad del archivo."],
        ["observed_at", "Fecha de observacion."],
        ["source_version", "Version D1 que aporto el medio."],
        ["details_json", "Documento, pagina, registro, URL y otros detalles."],
    ]
    owner_fields = [
        ["people.name", "Nombre o razon social del titular."],
        ["people.document_type", "Tipo de documento."],
        ["people.document_number", "Numero de documento."],
        ["relationships.person_id", "Vinculo entre unidad/lote y persona."],
        ["relationships.kind", "Por ejemplo titular_segun_documento."],
        ["relationships.details_json", "Participacion, condicion, pagina y fila de origen."],
    ]
    return [
        *section("8. Expedientes, galerias y documentos", "Que hay dentro de una galeria y como llega a R2 y D1."),
        data_table(["Tipo publicado", "Uso"], rows, [54 * mm, 112 * mm]),
        Spacer(1, 7),
        p("Donde se almacenan fotografias y documentos", "h2"),
        p(
            "D1 no guarda los bytes de la foto dentro de una columna. Guarda una fila en "
            "<b>media</b> con el tipo, la clave R2, el SHA-256 y la entidad relacionada. "
            "Los bytes viven en R2.", "body"),
        data_table(["Columna de media", "Funcion"], media_fields, [38 * mm, 128 * mm], small=True),
        Spacer(1, 5),
        callout(
            "Fotos de interior",
            "La tabla admite <b>interior_image</b>, pero la galeria GeoLlaqta no publica "
            "fotos de interior y actualmente D1 tiene <b>0</b> medios de ese tipo. "
            "Solo pueden agregarse con otro origen o una carga controlada. No deben confundirse "
            "con las fotos de anuncios inmobiliarios de otras aplicaciones.",
            ORANGE,
        ),
        Spacer(1, 5),
        data_table(
            ["Medio actual en D1", "Lotes cubiertos"],
            [
                ["Foto de fachada", "6,657"],
                ["Reporte catastral PDF", "7,403"],
                ["Ficha individual PDF", "2,647"],
                ["HTML original", "7,435"],
                ["Manifiesto", "7,435"],
                ["Foto interior", "0"],
            ],
            [70 * mm, 104 * mm],
        ),
        Spacer(1, 7),
        p("Donde se almacenan los propietarios", "h2"),
        data_table(["Campo", "Funcion"], owner_fields, [46 * mm, 120 * mm], small=True),
        Spacer(1, 4),
        p(
            "La cadena real es <b>lote</b> -> <b>unidad_en_lote</b> -> <b>titular_segun_documento</b> "
            "-> <b>people</b>. Actualmente hay 6,834 lotes con al menos un titular, 8,278 filas de "
            "personas y 16,155 relaciones de titularidad. Una fila contiene el valor literal "
            "NNN NNN NNN de la fuente y debe tratarse como placeholder, no como propietario real.",
            "body"),
        Spacer(1, 7),
        p("Ejemplo real del lote 04012902032032", "h2"),
        bullet("Reporte catastral 0401292013010039224, 46,123 bytes."),
        bullet("Ficha de actividad economica 0401292013030004245, 6,231 bytes."),
        bullet("Fotografia de fachada 02032032, 42,833 bytes."),
        bullet("Ficha individual solicitada por el HTML, pero COFOPRI respondio HTTP 500; se registra como faltante, no se inventa."),
        p(
            "El manifiesto de este lote pesa 290,660 bytes porque conserva los textos y tablas extraidas "
            "de los PDFs, ademas de la lista de archivos. El manifiesto no es la ficha: es el indice "
            "auditable que permite reconstruir que se descargo y que falto.", "body"),
        p("Cobertura documental actual por distrito", "h2"),
        data_table(
            [
                "Distrito", "Lotes", "Con titular", "Con fachada",
                "Con reporte PDF", "Con ficha individual PDF",
            ],
            [
                ["Alto Selva Alegre", "43,814", "1,963", "1,989", "2,198", "1,137"],
                ["Yanahuara", "10,480", "4,870", "4,672", "5,210", "1,510"],
                ["Jose Luis Bustamante y Rivero", "27,720", "1", "1", "1", "0"],
                ["Arequipa Cercado", "698", "0", "0", "0", "0"],
                ["Los otros 25 distritos", "180,663", "0", "0", "0", "0"],
            ],
            [
                48 * mm, 21 * mm, 23 * mm, 23 * mm, 29 * mm, 30 * mm,
            ],
            small=True,
            alignments={1: "RIGHT", 2: "RIGHT", 3: "RIGHT", 4: "RIGHT", 5: "RIGHT"},
        ),
        Spacer(1, 6),
        callout(
            "Diferencia entre fuente y archivo",
            "El HTML de la galeria es un documento de origen. El PDF es el documento oficial. El JSON es "
            "el manifiesto tecnico. D1 guarda datos normalizados y referencias; R2 conserva los tres tipos de archivo.",
            BLUE,
        ),
    ]


def frames_and_rasters():
    metadata = [
        ["format", "JPEG o PNG."],
        ["center", "Latitud y longitud del centro de la imagen."],
        ["captured_at", "Fecha y hora EXIF."],
        ["camera", "Modelo de camara registrado por EXIF."],
        ["product", "Producto detectado, por ejemplo DJI Mini 4 Pro."],
        ["image_width / image_height", "Dimensiones en pixeles."],
        ["relative_altitude_m", "Altitud relativa leida desde XMP."],
        ["gimbal_yaw_deg / pitch", "Orientacion del gimbal."],
        ["initial_width_m / height_m", "Huella inicial estimada."],
        ["initial_rotation_deg", "Rotacion inicial."],
        ["source_filename", "Nombre original del archivo."],
    ]
    state = [
        ["center", "Centro final de la huella."],
        ["width_m / height_m", "Dimensiones finales en metros."],
        ["rotation_deg", "Rotacion final."],
        ["opacity", "Opacidad final."],
        ["visible", "Determina si el parche se muestra."],
        ["locked", "Solo los parches bloqueados se publican a todos los consumidores."],
    ]
    story = [
        *section("9. Fotogramas, ortofotos, raster y georreferenciacion", "Que usa el sistema y que no procesa automaticamente."),
        p("Definiciones", "h2"),
        bullet("<b>Fotograma:</b> una imagen individual capturada por el sensor en un instante. Es el archivo que la camara escribio, normalmente con EXIF, GPS, altitud y orientacion."),
        bullet("<b>Ortofoto:</b> imagen corregida por perspectiva, relieve, lente y orientacion para que cada pixel represente una posicion terrestre cercana a una proyeccion ortogonal."),
        bullet("<b>Mosaico:</b> union georreferenciada de varias ortofotos o imagenes en una sola capa."),
        bullet("<b>Parche raster:</b> imagen rectangular colocada dentro de una huella WGS84 sobre el mapa base."),
        p("Que hace realmente el sistema", "h2"),
        bullet("Acepta JPEG/PNG de hasta 12 MB y 50 megapixeles."),
        bullet("Lee EXIF GPS, fecha, camara, altitud relativa y orientacion del gimbal."),
        bullet("Calcula una huella rectangular inicial usando altitud y campo visual; para DJI Mini 4 Pro usa 73.7 grados horizontales."),
        bullet("Permite mover el centro, cambiar ancho, alto, rotacion y opacidad hasta encajar con manzanas y lotes."),
        bullet("Solo publica el parche cuando esta bloqueado y visible; fuera de su huella permanece Google Maps."),
        bullet("<b>No hace:</b> estructura desde movimiento, union automatica de fotogramas, correccion de relieve, calibracion de lente completa o generacion de ortofoto."),
        callout(
            "Uso correcto de un fotograma",
            "Un fotograma puede cargarse como parche para inspeccion visual o referencia temporal, pero "
            "no debe tratarse automaticamente como una ortofoto exacta. Para comparar lotes y medir "
            "desplazamientos con precision conviene usar una ortofoto o mosaico ya rectificado y ajustar "
            "la huella contra puntos de control.",
            ORANGE,
        ),
        Spacer(1, 5),
        p("Ejemplo real almacenado en D1 y R2", "h2"),
    ]
    if DRONE.exists():
        image = Image(str(DRONE), width=165 * mm, height=93 * mm)
        story.append(image)
        story.append(p("Fotograma real de Cayma, 22/10/2026, DJI Mini 4 Pro, 4032 x 2268 px, altitud relativa 100.3 m. Imagen reducida para este documento.", "caption"))
    story.extend([
        KeepTogether([p("Metadatos del fotograma", "h2"), data_table(
            ["Metadato raster", "Significado"], metadata, [52 * mm, 114 * mm],
            small=True)]),
        Spacer(1, 5),
        data_table(["Estado calibrado", "Significado"], state, [52 * mm, 114 * mm], small=True),
        Spacer(1, 5),
        p(
            "En el ejemplo, la huella final es 130.201 m x 73.242 m, rotacion 346.9 grados, "
            "centro -16.385468556 / -71.5476705806 y estado locked=true, visible=true. "
            "La imagen original esta en <b>geollaqta/maestro/raster/2aa19ece...jpg</b> y mide 7,282,688 bytes.",
            "body"),
    ])
    return story


def update_flow():
    steps = [
        ["1", "Origen", "Descubrir inventario, descargar originales y validar HTTP, formato y limites."],
        ["2", "Manifiesto", "Registrar URL, hash, bytes, documentos, faltantes y datos extraidos."],
        ["3", "R2", "Subir archivos con PUT y verificar HEAD/hash; conservar version inmutable."],
        ["4", "Normalizacion", "Separar geometria, atributos, personas, medios, linderos y actos."],
        ["5", "D1", "Registrar version, contribuciones, identidades, selecciones y journal."],
        ["6", "Lectura", "ACM y mapas consultan D1; el endpoint de medios devuelve el objeto R2 validado."],
        ["7", "Reintento", "El ledger marca pendientes; un fallo de red no borra lo ya archivado."],
        ["8", "Auditoria", "Comparar cobertura de origen, hashes, entidades, campos y archivos."],
    ]
    return [
        *section("10. Flujo de actualizacion y publicacion", "Que ocurre desde una descarga hasta una ficha visible."),
        data_table(["Paso", "Etapa", "Resultado"], steps, [12 * mm, 35 * mm, 119 * mm]),
        Spacer(1, 7),
        p("Estados de un lote", "h2"),
        bullet("<b>failed:</b> no se pudo descargar o archivar el lote."),
        bullet("<b>partial:</b> el manifiesto fue archivado, pero falta al menos un documento o foto."),
        bullet("<b>complete:</b> los documentos publicados por la galeria fueron archivados."),
        bullet("<b>uploaded=1:</b> los objetos fueron verificados en R2."),
        bullet("<b>master_status=normalized_d1:</b> la ficha se puede servir desde D1."),
        p(
            "La captura es reanudable. El estado local guarda trabajos, hashes, objetos y faltantes; "
            "si se interrumpe, vuelve a consultar el inventario y omite lo ya verificado.", "body"),
    ]


DISTRICTS = [
    ("Arequipa (Cercado)", 698, 93, 1200, 0, 698, 0, 663),
    ("Alto Selva Alegre", 43814, 3128, 1689, 24705, 19109, 2169, 0),
    ("Cayma", 14850, 1472, 1963, 0, 14850, 0, 0),
    ("Cerro Colorado", 38546, 2842, 3751, 15636, 22910, 0, 0),
    ("Characato", 2305, 373, 617, 343, 1962, 0, 1),
    ("Chiguata", 1731, 340, 421, 0, 1731, 0, 0),
    ("Jacobo Hunter", 8076, 754, 1167, 0, 8076, 0, 0),
    ("La Joya", 8529, 836, 1085, 0, 8529, 0, 0),
    ("Mariano Melgar", 26246, 2104, 2112, 15493, 10753, 0, 0),
    ("Miraflores", 8749, 605, 980, 0, 8749, 0, 0),
    ("Mollebaya", 232, 73, 43, 0, 232, 0, 0),
    ("Paucarpata", 14852, 1923, 2683, 973, 13879, 0, 0),
    ("Pocsi", 554, 117, 129, 0, 554, 0, 0),
    ("Polobaya", 771, 227, 277, 0, 771, 0, 0),
    ("Quequena", 902, 116, 112, 0, 902, 0, 0),
    ("Sabandia", 908, 154, 180, 0, 908, 0, 0),
    ("Sachaca", 9165, 1057, 1248, 4838, 4327, 0, 0),
    ("San Juan de Siguas", 256, 51, 76, 0, 256, 0, 0),
    ("San Juan de Tarucani", 423, 113, 159, 0, 423, 0, 0),
    ("Santa Isabel de Siguas", 110, 41, 58, 0, 110, 0, 0),
    ("Santa Rita de Siguas", 818, 61, 59, 0, 818, 0, 0),
    ("Socabaya", 10511, 917, 1194, 114, 10397, 0, 0),
    ("Tiabaya", 2247, 296, 514, 0, 2247, 0, 0),
    ("Uchumayo", 4081, 478, 614, 0, 4081, 0, 0),
    ("Vitor", 851, 120, 245, 0, 851, 0, 0),
    ("Yanahuara", 10480, 425, 782, 5240, 0, 5240, 0),
    ("Yarabamba", 767, 142, 193, 0, 767, 0, 0),
    ("Yura", 24183, 2167, 2257, 7750, 16433, 0, 0),
    ("Jose Luis Bustamante y Rivero", 27720, 1816, 2381, 20557, 7163, 1, 0),
]


def district_inventory():
    rows = []
    for name, lots, blocks, roads, pcdpi, formal, gallery, detail in DISTRICTS:
        rows.append([
            name, f"{lots:,}", f"{blocks:,}", f"{roads:,}",
            f"{pcdpi:,}" if pcdpi else "-",
            f"{formal:,}" if formal else "-",
            f"{gallery:,}" if gallery else "-",
            f"{detail:,}" if detail else "-",
        ])
    rows.append([
        "TOTAL", "263,375", "22,841", "28,189",
        "95,649", "162,487", "7,410", "664",
    ])
    return [
        *section("11. Inventario actual por distrito", "Lotes, manzanas, vias y disponibilidad documental."),
        p(
            "Las columnas PCDPI y formalizacion cuentan registros de cada fuente; pueden superponerse. "
            "Galería D1 indica lotes PCDPI ya vinculados a un manifiesto documental. Ficha formal D1 indica "
            "reportes formales ya importados.", "small"),
        data_table(
            [
                "Distrito", "Lotes D1", "Manz.", "Vias",
                "PCDPI", "Formal.", "Gal. D1", "Ficha D1",
            ],
            rows,
            [
                48 * mm, 18 * mm, 14 * mm, 14 * mm,
                18 * mm, 18 * mm, 18 * mm, 16 * mm,
            ],
            small=True,
            alignments={1: "RIGHT", 2: "RIGHT", 3: "RIGHT", 4: "RIGHT", 5: "RIGHT", 6: "RIGHT", 7: "RIGHT"},
        ),
        Spacer(1, 5),
        callout(
            "Sobre las vias",
            "Los 29 distritos tienen al menos una capa vectorial de vias y el total D1 es 28,189. "
            "Solo siete distritos tienen ejes viales de PCDPI. En los demas, las vias provienen de "
            "formalizacion PSAD56 o WGS84. Que existan vias no garantiza que cada tramo oficial este completo.",
            BLUE,
        ),
    ]


def status_and_limits():
    status_rows = [
        ["Lotes con archivos R2", R2_UPLOADED],
        ["Estado local total", R2_TOTAL_STATE],
        ["R2 completos", R2_COMPLETE],
        ["R2 parciales", R2_PARTIAL],
        ["R2 fallidos/pendientes", R2_FAILED],
        ["Documentos faltantes declarados", R2_MISSING_DOCS],
        ["Galeria vinculada D1", D1_GALLERY_TOTAL],
        ["Fichas formales D1", D1_FORMAL_DETAIL],
        ["Revision D1", REVISION],
        ["Distrito actual", ACTIVE_DISTRICT],
        ["Procesados en ultima pasada", ACTIVE_PROCESSED],
        ["Pendientes del distrito", ACTIVE_REMAINING],
    ]
    limits = [
        ["PCDPI no cubre los 29 distritos", "Solo 10 distritos publican lotes en esa capa. Los demas dependen de formalizacion y otras fuentes."],
        ["PCDPI puede tener AREA_TER/AREA_CON nulos", "El reporte PDF o la formalizacion pueden completar el dato. No debe inferirse como documental."],
        ["La formalizacion no publica todos los campos", "No siempre existen area construida, unidades o titulares. Se dejan como Sin dato."],
        ["PDFs pueden responder HTTP 500/404", "Se conserva el manifiesto, se documenta el faltante y se reintenta cuando corresponde."],
        ["Una foto no es una ortofoto", "El sistema ajusta una huella rectangular; no ejecuta fotogrametria automatica."],
        ["Entidades D1 pueden duplicar parcelas entre fuentes", "PCDPI y formalizacion se conservan con procedencia separada; requieren conciliacion geometrica."],
        ["Las cifras operativas cambian", "El apendice de estado es una fotografia con fecha; el ledger y D1 son la referencia vigente."],
    ]
    return [
        *section("12. Estado de migracion y lecturas correctas", "Corte documental y limites que deben respetarse."),
        data_table(["Indicador", "Valor al corte"], status_rows, [85 * mm, 81 * mm]),
        Spacer(1, 7),
        p("Limitaciones y valores que no deben inventarse", "h2"),
        data_table(["Limitacion", "Regla"], limits, [58 * mm, 108 * mm], small=True),
        Spacer(1, 6),
        callout(
            "Como leer la ficha maestra",
            "Un lote puede mostrar geometria desde D1 y, al mismo tiempo, indicar que un PDF o una "
            "fotografia no esta publicada. Eso no es una contradiccion: el lote existe, pero el "
            "documento de origen falta o no fue publicado por COFOPRI.",
            ORANGE,
        ),
    ]


def security():
    rows = [
        ["Credenciales", "R2 usa firma AWS4-HMAC-SHA256 y credenciales privadas fuera del codigo."],
        ["Integridad", "Cada objeto se compara con SHA-256 y tamano antes de publicarse."],
        ["Origen permitido", "El recolector acepta solo dominios oficiales configurados y bloquea redirecciones no confiables."],
        ["Version inmutable", "El payload original de D1 y el manifiesto R2 no se sobrescriben; los cambios crean versiones."],
        ["Procedencia", "Cada contribucion conserva version, archivo, campo, pagina y evidencia."],
        ["Auditoria", "journal registra revision, actor, fecha y alcance del cambio."],
        ["Limites", "PDFs hasta 20 MB; imagenes raster hasta 12 MB y 50 megapixeles."],
        ["Reintentos", "Errores de transporte se reintentan; accesos denegados o datos invalidos se registran."],
    ]
    return [
        *section("13. Seguridad, integridad y auditoria"),
        data_table(["Control", "Implementacion"], rows, [40 * mm, 126 * mm]),
        Spacer(1, 7),
        p(
            "La regla central es no modificar el original para corregir una presentacion. Si una "
            "version nueva cambia un campo, se agrega una contribucion y se actualiza la seleccion; "
            "la version anterior permanece disponible para auditoria y reversion.", "body"),
    ]


def appendices():
    formal_fields = [
        ["FI_CODPRE", "Codigo de predio/reporte."],
        ["CODPJV / PJ_CODPJV", "Codigos de pueblo joven o pueblo titulado."],
        ["MZNA / LOTE", "Manzana y lote oficiales."],
        ["EDI_PISO / EDI_DPTO", "Piso y departamento/unidad."],
        ["NOMPJV", "Nombre de pueblo, urbanizacion o asentamiento."],
        ["SECTOR", "Sector del predio."],
        ["DPTO / PROV / DISTRITO", "Ubicacion administrativa."],
        ["TIPO_PUEBLO / TIPO_PREDIO", "Clasificacion del pueblo y del predio."],
        ["TIPO_USO / FI_TIPUSO", "Uso publicado."],
        ["ESTADO / SITUACION", "Estado administrativo del registro."],
        ["FECHA_TITULO / ESTADO_TITULO", "Fecha y estado de titulacion."],
        ["FI_EST_REGIS / FI_ORIGEN", "Estado registral y origen."],
        ["PM_AREPRE", "Area de terreno del reporte."],
        ["PM_LTEFRE / DER / IZQ / FON", "Medidas perimetricas oficiales."],
        ["FC_FRENTE / DER / IZQ / FONDO", "Colindancias oficiales."],
        ["OBSERVACION", "Observacion textual de la fuente."],
        ["ULTIMA_ACTUALIZACION", "Fecha de ultima actualizacion."],
    ]
    return [
        *section("14. Apendices: campos y rutas de referencia"),
        p("A. Campos clave del reporte formalizado", "h2"),
        data_table(["Campo", "Significado"], formal_fields, [52 * mm, 114 * mm], small=True),
        Spacer(1, 7),
        p("B. Respuesta de integridad del sistema", "h2"),
        bullet("<b>Que existe en la fuente:</b> se consulta el catalogo o servicio y se guarda fecha de consulta."),
        bullet("<b>Que fue descargado:</b> artifacts con URL, tamano y hash."),
        bullet("<b>Que fue archivado:</b> objetos R2 verificados."),
        bullet("<b>Que fue normalizado:</b> versiones, contribuciones y selecciones D1."),
        bullet("<b>Que se muestra:</b> current_attributes, relationships, media y boundary_segments."),
        bullet("<b>Que falto:</b> missing y d1_import_failures, con estado y motivo."),
        Spacer(1, 7),
        callout(
            "Definicion operativa de fuente de verdad",
            "D1 es la fuente de verdad para consultas y publicacion. R2 es el respaldo de los originales "
            "y de los snapshots. GeoLlaqta es el origen externo. Una copia local o un cache temporal nunca "
            "debe reemplazar a D1 en las aplicaciones de produccion.",
            GREEN,
        ),
        Spacer(1, 10),
        p("Documento preparado para revision tecnica y operativa del sistema.", "small"),
        p("Corte de datos: " + SNAPSHOT, "small"),
    ]


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = ManualTemplate(str(OUTPUT))
    story = []
    story.extend(cover())
    story.extend(toc())
    story.extend(executive())
    story.extend(glossary())
    story.extend(architecture())
    story.extend(pcdpi())
    story.extend(formalization())
    story.extend(r2_section())
    story.extend(d1_section())
    story.extend(records_and_gallery())
    story.extend(frames_and_rasters())
    story.extend(update_flow())
    story.extend(district_inventory())
    story.extend(status_and_limits())
    story.extend(security())
    story.extend(appendices())
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
