"""Extracción de superficies: área de terreno y área construida.

Los portales publican la superficie de dos maneras distintas:

* **campos estructurados** (``Area Terreno`` / ``Area Construida``,
  ``area_total`` / ``area``, ``built_area`` / ``land_area`` …), o
* **dentro de un texto libre** con etiquetas, por ejemplo::

      🏡 ÁREA DE TERRENO: 120 m2
      🏡 ÁREA CONSTRUIDA: 185 m2

Ambas superficies se guardan por separado en ``PropiedadesCompetencia``
(``area_terreno`` y ``area_construida``) porque se usan para cálculos distintos:
en un terreno el precio por m² sale del **área de terreno**, mientras que en una
casa interesa comparar el precio por m² de **terreno** contra el de **construcción**.

Este módulo es autónomo (no importa Django ni ``normalization``) para que lo puedan
usar todos los scrapers sin dependencias cruzadas.
"""

from __future__ import annotations

import math
import re
import unicodedata
from numbers import Number

# ── Etiquetas ──────────────────────────────────────────────────────────────
# Se buscan sobre el texto YA normalizado (minúsculas, sin tildes y con '²'→'2').
# Cada etiqueta lleva la "ventana" de caracteres donde debe aparecer la cifra:
# las etiquetas específicas permiten una ventana amplia y las genéricas una corta,
# para no confundir frases como "terreno apto para 5 casas de 120 m2".
ETIQUETAS_TERRENO = (
    (r'area\s+de\s+terreno\s*:?\s*', 40),
    (r'area\s+del\s+terreno\s*:?\s*', 40),
    (r'area\s+terreno\s*:?\s*', 40),
    (r'superficie\s+de\s+terreno\s*:?\s*', 40),
    (r'\bterreno\s*:?\s*', 16),
)

ETIQUETAS_CONSTRUIDA = (
    (r'area\s+construida\s*:?\s*', 40),
    (r'area\s+de\s+construccion\s*:?\s*', 40),
    (r'area\s+techada\s*:?\s*', 40),
    (r'superficie\s+construida\s*:?\s*', 40),
    (r'\bconstruccion\s*:?\s*', 16),
    (r'\bconstruido\s*:?\s*', 16),
)

# Tras normalizar el texto, 'm²' queda como 'm2'.
PATRON_METROS = r'(\d{1,5}(?:[.,]\d{1,2})?)\s*(?:m2|mts2|mt2|metros\s+cuadrados)'

# Medidas del terreno en formato "frente x fondo" (8.00 X 16.00 = 128 m²).
PATRON_MEDIDAS = r'(\d{1,4}(?:[.,]\d{1,2})?)\s*[x×]\s*(\d{1,4}(?:[.,]\d{1,2})?)'

# Campos estructurados por portal, en orden de prioridad.
CAMPOS_CONSTRUIDA = (
    'Area Construida', 'Área Construida', 'area_construida', 'area_construida_m2',
    'built_area', 'superficie_construida', 'area_techada', 'area', 'Area',
)
CAMPOS_TERRENO = (
    'Area Terreno', 'Área Terreno', 'area_terreno', 'area_de_terreno_m2',
    'land_area', 'superficie_terreno', 'area_total', 'Area Total', 'plot_size',
)
# Campos de texto libre donde puede venir la superficie.
CAMPOS_TEXTO = (
    'Descripcion', 'descripcion', 'description', 'Caracteristicas',
    'caracteristicas', 'Titulo', 'titulo', 'title', 'Observaciones', 'Detalle',
)

CLAVES = ('area_terreno', 'area_construida')


def normalizar_texto(valor) -> str:
    """Minúsculas, sin tildes y con '²' convertido a '2' (para buscar etiquetas)."""
    return ''.join(
        caracter
        for caracter in unicodedata.normalize('NFKD', str(valor or '').lower())
        if not unicodedata.combining(caracter)
    )


def parsear_area(valor) -> float | None:
    """Convierte un valor crudo a m² (float) o ``None`` si no hay número válido.

    Acepta ``120``, ``"120 m2"``, ``"185 m²"``, ``"1.200,50"``, ``"1,200.50"``.
    Un ``0`` se considera "sin dato" (los portales lo usan como vacío).
    """
    if valor is None:
        return None
    if isinstance(valor, Number):
        numero = float(valor)
        return numero if math.isfinite(numero) and numero > 0 else None

    texto = normalizar_texto(valor)
    coincidencia = re.search(r'(\d[\d.,]*)', texto)
    if not coincidencia:
        return None

    crudo = coincidencia.group(1)
    if ',' in crudo and '.' in crudo:
        # Formato español (1.200,50) o inglés (1,200.50): el último separador manda.
        decimal = ',' if crudo.rfind(',') > crudo.rfind('.') else '.'
        miles = '.' if decimal == ',' else ','
        crudo = crudo.replace(miles, '').replace(decimal, '.')
    elif ',' in crudo:
        entero, _, decimales = crudo.partition(',')
        # '1,200' con 3 dígitos es separador de miles, no decimal.
        crudo = f'{entero}{decimales}' if len(decimales) == 3 else f'{entero}.{decimales}'
    elif '.' in crudo:
        entero, _, decimales = crudo.partition('.')
        # '5.795 m2' → 5795 (punto seguido de 3 dígitos = miles).
        if len(decimales) == 3 and entero.isdigit():
            crudo = f'{entero}{decimales}'
    try:
        numero = float(crudo)
    except ValueError:
        return None
    return numero if math.isfinite(numero) and numero > 0 else None


def _numero_junto_a_etiqueta(texto_normalizado: str, etiqueta: str, ventana: int) -> float | None:
    """Primer número con unidad que aparece en la ventana posterior a la etiqueta."""
    for coincidencia in re.finditer(etiqueta, texto_normalizado):
        tramo = texto_normalizado[coincidencia.end(): coincidencia.end() + ventana]
        numero = re.search(PATRON_METROS, tramo)
        if numero:
            return parsear_area(numero.group(1))
    return None


def extraer_area_etiquetada(texto, etiquetas) -> float | None:
    """Busca una etiqueta (p. ej. 'area de terreno') y devuelve el m² que la sigue."""
    texto_normalizado = normalizar_texto(texto)
    if not texto_normalizado.strip():
        return None
    for etiqueta, ventana in etiquetas:
        encontrado = _numero_junto_a_etiqueta(texto_normalizado, etiqueta, ventana)
        if encontrado is not None:
            return encontrado
    return None


# Sufijos: hay portales que escriben la cifra ANTES de la palabra
# ("128 m2 totales", "90 m2 construidos").
SUFIJOS_TERRENO = (
    r'm2\s*(?:totales|total)',
    r'm2\s*de\s*terreno',
    r'm2\s*terreno',
)
SUFIJOS_CONSTRUIDA = (
    r'm2\s*(?:construidos|construidas|construida|construido)',
    r'm2\s*(?:techados|techadas|techada|techado)',
)


def _numero_antes_de_sufijo(texto_normalizado: str, sufijos, ventana: int = 28) -> float | None:
    """Último número que aparece justo antes de un sufijo ('128 m2 totales')."""
    for sufijo in sufijos:
        for coincidencia in re.finditer(sufijo, texto_normalizado):
            tramo = texto_normalizado[max(0, coincidencia.start() - ventana): coincidencia.start()]
            numeros = re.findall(r'(\d{1,5}(?:[.,]\d{1,2})?)', tramo)
            if numeros:
                valor = parsear_area(numeros[-1])
                if valor is not None:
                    return valor
    return None


def extraer_areas_de_texto(texto) -> dict:
    """Devuelve ``{'area_terreno': float|None, 'area_construida': float|None}``.

    Reconoce tanto etiquetas previas ("ÁREA DE TERRENO: 120 m2") como sufijos
    ("128 m2 totales" / "90 m2 construidos"). Si el texto trae un único ``m²`` sin
    ninguna pista no se asume que sea la construcción.
    """
    normalizado = normalizar_texto(texto)
    if not normalizado.strip():
        return {'area_terreno': None, 'area_construida': None}
    terreno = extraer_area_etiquetada(normalizado, ETIQUETAS_TERRENO)
    if terreno is None:
        terreno = _numero_antes_de_sufijo(normalizado, SUFIJOS_TERRENO)
    construida = extraer_area_etiquetada(normalizado, ETIQUETAS_CONSTRUIDA)
    if construida is None:
        construida = _numero_antes_de_sufijo(normalizado, SUFIJOS_CONSTRUIDA)
    return {'area_terreno': terreno, 'area_construida': construida}


def _primer_campo(prop: dict, campos) -> float | None:
    for campo in campos:
        valor = parsear_area(prop.get(campo))
        if valor is not None:
            return valor
    return None


def extraer_areas_estructuradas(prop: dict) -> dict:
    """Lee las superficies de los campos estructurados que trae el portal."""
    prop = prop or {}
    return {
        'area_terreno': _primer_campo(prop, CAMPOS_TERRENO),
        'area_construida': _primer_campo(prop, CAMPOS_CONSTRUIDA),
    }


def _texto_disponible(prop: dict) -> str:
    return ' '.join(
        str((prop or {}).get(campo) or '') for campo in CAMPOS_TEXTO
    )


def area_desde_medidas(medidas) -> float | None:
    """'8.00 X 16.00' → 128.0 (frente × fondo = superficie del terreno)."""
    coincidencia = re.search(PATRON_MEDIDAS, normalizar_texto(medidas))
    if not coincidencia:
        return None
    frente = parsear_area(coincidencia.group(1))
    fondo = parsear_area(coincidencia.group(2))
    if frente is None or fondo is None:
        return None
    return round(frente * fondo, 2)


def calcular_areas(prop: dict) -> dict:
    """Superficies de una propiedad: estructuradas primero y texto como respaldo.

    Retorna ``{'area_terreno', 'area_construida', 'area_m2'}`` donde ``area_m2`` es el
    valor principal histórico (construida si existe; si no, terreno).
    """
    datos = extraer_areas_estructuradas(prop)
    # "Medidas: 8.00 X 16.00" describe el terreno (frente x fondo).
    if datos['area_terreno'] is None:
        datos['area_terreno'] = area_desde_medidas((prop or {}).get('Medidas'))
    if any(datos[clave] is None for clave in CLAVES):
        desde_texto = extraer_areas_de_texto(_texto_disponible(prop))
        for clave in CLAVES:
            if datos[clave] is None:
                datos[clave] = desde_texto.get(clave)
    terreno, construida = datos['area_terreno'], datos['area_construida']
    datos['area_m2'] = construida if construida is not None else terreno
    return datos


def calcular_area_m2(prop: dict) -> float | None:
    """Compatibilidad: área principal (construida si hay, si no terreno)."""
    return calcular_areas(prop)['area_m2']
