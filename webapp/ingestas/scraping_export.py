"""Exportación a Excel de la tabla donde se almacenan las propiedades scrapeadas.

La tabla es ``propiedades_competencia`` (modelo ``PropiedadesCompetencia``), el
destino único de los scrapers de portales de competencia (Remax, Adondevivir,
Properati, Urbania, Facebook Marketplace).

Se usa tanto desde la vista web del dashboard de scraping
(``/ingestas/scraping/propiedades/exportar/``) como desde el comando de
gestión ``exportar_propiedades_competencia``.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal

from django.utils import timezone

from .models import PropiedadesCompetencia

# Orden exacto de las columnas del Excel.
CAMPOS_EXPORT = [
    'id',
    'fuente',
    'id_origen',
    'estado_publicacion',
    'tipo_inmueble',
    'tipo_operacion',
    'titulo',
    'precio_usd',
    'precio_soles',
    'area_m2',
    'area_terreno',
    'area_construida',
    'precio_m2_terreno',
    'precio_m2_construida',
    'dormitorios',
    'banos',
    'estacionamientos',
    'distrito',
    'provincia',
    'departamento',
    'direccion_texto',
    'latitud',
    'longitud',
    'precision_ubicacion',
    'antiguedad_anios',
    'agencia_agente',
    'descripcion',
    'amenities',
    'url',
    'imagen_url',
    'fecha_extraccion',
    'primera_vez_vista',
    'ultima_vez_vista',
    'fecha_primera_ausencia',
    'fecha_retiro_confirmado',
    'ausencias_consecutivas',
    'creado_en',
    'actualizado_en',
]

ENCABEZADOS_EXPORT = {
    'id': 'ID',
    'fuente': 'Portal',
    'id_origen': 'ID Origen',
    'estado_publicacion': 'Estado publicación',
    'tipo_inmueble': 'Tipo inmueble',
    'tipo_operacion': 'Tipo operación',
    'titulo': 'Título',
    'precio_usd': 'Precio USD',
    'precio_soles': 'Precio S/.',
    'area_m2': 'Área m²',
    'area_terreno': 'Área terreno (m²)',
    'area_construida': 'Área construida (m²)',
    'precio_m2_terreno': 'Precio/m² terreno',
    'precio_m2_construida': 'Precio/m² construido',
    'dormitorios': 'Dormitorios',
    'banos': 'Baños',
    'estacionamientos': 'Estacionamientos',
    'distrito': 'Distrito',
    'provincia': 'Provincia',
    'departamento': 'Departamento',
    'direccion_texto': 'Dirección',
    'latitud': 'Latitud',
    'longitud': 'Longitud',
    'precision_ubicacion': 'Precisión ubicación',
    'antiguedad_anios': 'Antigüedad (años)',
    'agencia_agente': 'Agencia / Agente',
    'descripcion': 'Descripción',
    'amenities': 'Amenities',
    'url': 'URL',
    'imagen_url': 'URL imagen',
    'fecha_extraccion': 'Fecha extracción',
    'primera_vez_vista': 'Primera vez vista',
    'ultima_vez_vista': 'Última vez vista',
    'fecha_primera_ausencia': 'Primera ausencia',
    'fecha_retiro_confirmado': 'Retiro confirmado',
    'ausencias_consecutivas': 'Ausencias consecutivas',
    'creado_en': 'Creado en',
    'actualizado_en': 'Actualizado en',
}

# Campos con ``choices``: se exporta la etiqueta legible (get_*_display).
CAMPOS_CON_DISPLAY = (
    'estado_publicacion',
    'tipo_inmueble',
    'tipo_operacion',
    'precision_ubicacion',
)

# Campos de fecha/hora: se escriben como datetime y se formatean en la columna.
CAMPOS_FECHA = (
    'fecha_extraccion',
    'primera_vez_vista',
    'ultima_vez_vista',
    'fecha_primera_ausencia',
    'fecha_retiro_confirmado',
    'creado_en',
    'actualizado_en',
)

FORMATO_FECHA = 'dd/mm/yyyy hh:mm'
ANCHO_MAXIMO = 60
ANCHO_MINIMO = 10
TAMANO_LOTE = 500


def filtrar_propiedades(params):
    """Queryset de propiedades scrapeadas con los mismos filtros del dashboard.

    Acepta tanto un ``QueryDict`` (``request.GET``) como un ``dict`` simple
    (usado por el comando de gestión).
    """
    qs = PropiedadesCompetencia.objects.all()

    def limpiar(nombre):
        valor = params.get(nombre)
        return valor.strip() if isinstance(valor, str) else valor

    fuente = limpiar('fuente')
    distrito = limpiar('distrito')
    tipo = limpiar('tipo')
    estado = limpiar('estado')

    if fuente:
        qs = qs.filter(fuente=fuente)
    if distrito:
        qs = qs.filter(distrito__icontains=distrito)
    if tipo:
        qs = qs.filter(tipo_inmueble=tipo)
    if estado:
        qs = qs.filter(estado_publicacion=estado)

    # Las inserciones más recientes siempre aparecen arriba. El ID descendente
    # resuelve de forma estable los lotes que comparten fecha.
    return qs.order_by('-fecha_extraccion', '-id')


def _normalizar_valor(valor):
    """Convierte el valor de un campo a algo que openpyxl pueda escribir."""
    if valor is None:
        return ''
    if isinstance(valor, datetime):
        if timezone.is_aware(valor):
            valor = timezone.localtime(valor)
        return valor.replace(tzinfo=None, microsecond=0)
    if isinstance(valor, date):
        return datetime.combine(valor, time.min)
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, bool) or isinstance(valor, (int, float)):
        return valor
    if isinstance(valor, (list, tuple, set)):
        return ', '.join(str(item) for item in valor)
    if isinstance(valor, dict):
        return json.dumps(valor, ensure_ascii=False, default=str)
    return str(valor)


def _valor_campo(propiedad, campo):
    display = getattr(propiedad, f'get_{campo}_display', None)
    valor = display() if callable(display) else getattr(propiedad, campo, None)
    if campo in CAMPOS_CON_DISPLAY and not valor:
        # Sin valor: se conserva vacío en lugar del texto "None".
        return ''
    return _normalizar_valor(valor)


def construir_libro(propiedades, incluir_crudos=False):
    """Construye el libro openpyxl con la tabla de propiedades scrapeadas.

    ``propiedades`` puede ser cualquier iterable de ``PropiedadesCompetencia``.
    Devuelve una tupla ``(libro, total_filas)``.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = 'Propiedades'

    encabezados = [ENCABEZADOS_EXPORT.get(campo, campo) for campo in CAMPOS_EXPORT]
    ws.append(encabezados)

    relleno = PatternFill('solid', fgColor='1F3B57')
    fuente_encabezado = Font(bold=True, color='FFFFFF')
    for celda in ws[1]:
        celda.fill = relleno
        celda.font = fuente_encabezado
        celda.alignment = Alignment(vertical='center')

    anchos = [max(len(str(texto)) + 2, ANCHO_MINIMO) for texto in encabezados]
    filas_crudas = []
    total = 0

    for propiedad in propiedades:
        fila = []
        for indice, campo in enumerate(CAMPOS_EXPORT):
            valor = _valor_campo(propiedad, campo)
            texto = str(valor)
            if len(texto) + 2 > anchos[indice]:
                anchos[indice] = min(max(len(texto) + 2, ANCHO_MINIMO), ANCHO_MAXIMO)
            fila.append(valor)
        ws.append(fila)
        total += 1

        if incluir_crudos:
            filas_crudas.append([
                propiedad.id,
                propiedad.fuente,
                propiedad.id_origen,
                json.dumps(propiedad.datos_crudos or {}, ensure_ascii=False, default=str),
            ])

    for indice, ancho in enumerate(anchos, start=1):
        letra = get_column_letter(indice)
        ws.column_dimensions[letra].width = min(ancho, ANCHO_MAXIMO)
        if CAMPOS_EXPORT[indice - 1] in CAMPOS_FECHA:
            ws.column_dimensions[letra].number_format = FORMATO_FECHA

    ws.freeze_panes = 'A2'
    if total:
        ws.auto_filter.ref = f'A1:{get_column_letter(len(CAMPOS_EXPORT))}{total + 1}'

    if incluir_crudos:
        ws_crudos = wb.create_sheet('Datos crudos')
        ws_crudos.append(['ID', 'Portal', 'ID Origen', 'Datos crudos (JSON)'])
        for celda in ws_crudos[1]:
            celda.fill = relleno
            celda.font = fuente_encabezado
        for fila in filas_crudas:
            ws_crudos.append(fila)
        ws_crudos.column_dimensions['A'].width = 10
        ws_crudos.column_dimensions['B'].width = 22
        ws_crudos.column_dimensions['C'].width = 28
        ws_crudos.column_dimensions['D'].width = 120
        ws_crudos.freeze_panes = 'A2'

    return wb, total
