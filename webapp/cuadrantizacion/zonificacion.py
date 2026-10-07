"""
Zonificación del PDM: polígonos vectoriales y clasificación de puntos.

Los polígonos se extraen del propio PDF (que los tiene como vectores, no como
imagen), se georreferencian a WGS84 y se sirven como GeoJSON. Clasificar un
marcador es entonces una prueba geométrica —el punto está dentro o fuera del
polígono— en vez de una lectura de color: el resultado no depende del zoom ni
de la resolución, y moverse dentro de una zona nunca cambia la zona asignada.
"""

import json
import math
import threading
import time

# Uso y categoría por código: es la leyenda oficial del plano. La tabla ZonaUso
# puede sobrescribirla (el admin permite corregir colores o descripciones).
LEYENDA_PDM = [
    ('RDB', 'Residencial densidad baja', 'Residencial', '#d2d196'),
    ('RDM-1', 'Residencial densidad media tipo 1', 'Residencial', '#fbfe93'),
    ('RDM-2', 'Residencial densidad media tipo 2', 'Residencial', '#fde41d'),
    ('RDA-1', 'Residencial densidad alta tipo 1', 'Residencial', '#ffb70b'),
    ('RDA-2', 'Residencial densidad alta tipo 2', 'Residencial', '#d6882d'),
    ('I1R', 'Vivienda taller', 'Residencial', '#feffd2'),
    ('CE', 'Comercio especializado', 'Comercio', '#b03130'),
    ('CS', 'Comercio sectorial', 'Comercio', '#ff9d9d'),
    ('CZ', 'Comercio zonal', 'Comercio', '#ff0000'),
    ('CIn', 'Comercio industrial', 'Comercio', '#800200'),
    ('CM', 'Comercio metropolitano', 'Comercio', '#ff615f'),
    ('I-1', 'Industria elemental', 'Industria', '#bc81ce'),
    ('I-2', 'Industria liviana', 'Industria', '#932ab2'),
    ('ZR', 'Zona de recreación', 'Equipamiento', '#1db303'),
    ('EDU', 'Educación', 'Equipamiento', '#3883c0'),
    ('SAL', 'Salud', 'Equipamiento', '#56c4d4'),
    ('OU1', 'Usos especiales tipo 1', 'Equipamiento', '#989898'),
    ('OU2', 'Usos especiales tipo 2', 'Equipamiento', '#4b4b4b'),
    ('ZRE-CH', 'Zona de reglamentación especial - Centro histórico',
     'Reglamentación especial', '#e0b3b3'),
    ('ZRE-PA', 'Zona de reglamentación especial - Patrimonio agrícola',
     'Reglamentación especial', '#739973'),
    ('ZRE-PN', 'Zona de reglamentación especial - Patrimonio natural',
     'Reglamentación especial', '#7d4f5a'),
    ('ZRE-PP', 'Zona de reglamentación especial - Patrimonio paisajista',
     'Reglamentación especial', '#bb7f85'),
    ('ZRE-RI1', 'Zona de reglamentación especial - Riesgos tipo 1',
     'Reglamentación especial', '#aca661'),
    ('ZRE-RI2', 'Zona de reglamentación especial - Riesgos tipo 2',
     'Reglamentación especial', '#a6ae48'),
    ('ZRE-RU', 'Zona de reglamentación especial - Renovación urbana',
     'Reglamentación especial', '#663849'),
    ('ZAQ', 'Zona arqueológica', 'Otros', '#cecece'),
    ('ZM', 'Zona monumental', 'Otros', '#502936'),
    ('ZRP', 'Zona de reserva paisajista', 'Otros', '#47b368'),
    ('EA', 'Expansión agrícola', 'Otros', '#84dca6'),
    ('ZA', 'Zona agrícola', 'Otros', '#84dca6'),
]

M_POR_GRADO_LAT = 110574.0
M_POR_GRADO_LON = 111320.0

# A menos de esta distancia del borde, la zona se marca como aproximada: el
# marcador puede estar a un paso de la zona vecina.
METROS_BORDE = 4.0


def _punto_en_anillo(x, y, anillo):
    """Prueba de punto en polígono por lanzamiento de rayo."""
    dentro = False
    n = len(anillo)
    for i in range(n - 1):
        xi, yi = anillo[i]
        xj, yj = anillo[i + 1]
        if (yi > y) != (yj > y):
            cruce = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < cruce:
                dentro = not dentro
    return dentro


def _distancia_a_anillo(x, y, anillo, m_lon, m_lat):
    """Distancia en metros del punto al borde del polígono."""
    menor = float('inf')
    n = len(anillo)
    for i in range(n - 1):
        x1, y1 = anillo[i]
        x2, y2 = anillo[i + 1]
        px, py = (x - x1) * m_lon, (y - y1) * m_lat
        vx, vy = (x2 - x1) * m_lon, (y2 - y1) * m_lat
        largo = vx * vx + vy * vy
        t = 0.0 if largo == 0 else max(0.0, min(1.0, (px * vx + py * vy) / largo))
        dx, dy = px - t * vx, py - t * vy
        distancia = math.hypot(dx, dy)
        if distancia < menor:
            menor = distancia
    return menor


class ClasificadorZonificacion:
    """Resuelve la zona de un punto contra los polígonos del plano."""

    def __init__(self, ruta_geojson, leyenda=None):
        self.ruta = str(ruta_geojson)
        with open(self.ruta, encoding='utf-8') as archivo:
            datos = json.load(archivo)

        self.leyenda = {}
        for fila in (leyenda or LEYENDA_PDM):
            codigo, nombre, categoria, color = fila[:4]
            parametros = fila[4] if len(fila) > 4 else {}
            self.leyenda[codigo] = {
                'nombre': nombre, 'categoria': categoria, 'color': color,
                'parametros': parametros or {},
            }

        self.poligonos = []
        for indice, feature in enumerate(datos.get('features', [])):
            geometria = feature.get('geometry') or {}
            if geometria.get('type') != 'Polygon':
                continue
            anillo = (geometria.get('coordinates') or [[]])[0]
            if len(anillo) < 3:
                continue
            propiedades = feature.get('properties') or {}
            codigo = propiedades.get('codigo') or ''
            if not codigo:
                continue
            xs = [p[0] for p in anillo]
            ys = [p[1] for p in anillo]
            self.poligonos.append({
                'codigo': codigo,
                'color': propiedades.get('color') or '',
                'orden': propiedades.get('orden', indice),
                'anillo': anillo,
                'bbox': (min(xs), min(ys), max(xs), max(ys)),
            })
        # El orden del PDF es el de dibujo: el último tapa a los anteriores.
        self.poligonos.sort(key=lambda p: p['orden'])

    def clasificar(self, lat, lon):
        """Zona del punto, o None si no cae en ningún polígono del plano."""
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None

        m_lon = M_POR_GRADO_LON * math.cos(math.radians(lat))
        m_lat = M_POR_GRADO_LAT

        elegido = None
        for poligono in self.poligonos:
            x0, y0, x1, y1 = poligono['bbox']
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            if _punto_en_anillo(lon, lat, poligono['anillo']):
                elegido = poligono  # el último que contiene al punto es el visible

        if elegido is None:
            return None

        informacion = self.leyenda.get(elegido['codigo'], {})
        distancia = _distancia_a_anillo(
            lon, lat, elegido['anillo'], m_lon, m_lat
        )
        cerca = distancia < METROS_BORDE
        return {
            'codigo': elegido['codigo'],
            'uso': informacion.get('nombre') or elegido['codigo'],
            'categoria': informacion.get('categoria') or '',
            'color': informacion.get('color') or elegido['color'],
            'parametros': informacion.get('parametros') or {},
            # Se conserva la forma de la respuesta anterior para no tocar a los
            # consumidores; ahora la cobertura es geométrica, no de color.
            'cobertura': 1.0,
            'confianza': 'media' if cerca else 'alta',
            'aproximado': cerca,
            'distancia_borde_m': round(distancia, 1),
        }


# --------------------------------------------------------------- caché
_cache = {'clasificador': None, 'momento': 0.0}
_lock = threading.Lock()
VIDA_CACHE_SEGUNDOS = 300


def invalidar_cache():
    """Fuerza a reconstruir el clasificador en la próxima consulta."""
    with _lock:
        _cache['clasificador'] = None
        _cache['momento'] = 0.0


def _ruta_local_de(url):
    """Resuelve la ruta física del GeoJSON (static o media)."""
    from pathlib import Path

    from django.conf import settings
    from django.contrib.staticfiles import finders

    if not url:
        return None
    if url.startswith(('http://', 'https://')):
        return None  # un archivo remoto no se puede leer en local

    relativa = url[len('/static/'):] if url.startswith('/static/') else url
    relativa = relativa.split('?')[0].lstrip('/')

    encontrada = finders.find(relativa)
    if encontrada:
        return encontrada

    base_dir = getattr(settings, 'BASE_DIR', None)
    static_root = getattr(settings, 'STATIC_ROOT', None)
    for candidato in (
        Path(static_root) / relativa if static_root else None,
        Path(base_dir) / 'static' / relativa if base_dir else None,
    ):
        if candidato and candidato.exists():
            return str(candidato)
    return None


def _paleta_desde_bd():
    try:
        from .models import ZonaUso
        filas = list(ZonaUso.objects.filter(activo=True).order_by('orden', 'codigo'))
        if filas:
            return [
                (z.codigo, z.nombre, z.categoria, z.color, z.parametros or {})
                for z in filas
            ]
    except Exception:
        pass
    return None


def obtener_clasificador():
    """Clasificador de la capa vectorial activa (cacheado)."""
    from .models import CapaVectorialMapa

    ahora = time.time()
    with _lock:
        if (
            _cache['clasificador'] is not None
            and (ahora - _cache['momento']) < VIDA_CACHE_SEGUNDOS
        ):
            return _cache['clasificador']

        capa = (
            CapaVectorialMapa.objects.filter(activo=True)
            .exclude(geojson_url='')
            .order_by('orden', 'id')
            .first()
        )
        ruta = _ruta_local_de(capa.geojson_url) if capa else None
        if not ruta:
            ultima = (
                'cuadrantizacion/capas/zonificacion_pdm_poligonos.geojson'
            )
            ruta = _ruta_local_de(ultima)
        if not ruta:
            return None

        clasificador = ClasificadorZonificacion(ruta, _paleta_desde_bd())
        _cache.update({'clasificador': clasificador, 'momento': ahora})
        return clasificador


def clasificar_punto(lat, lon):
    """Atajo: clasifica un punto con la capa activa."""
    clasificador = obtener_clasificador()
    if clasificador is None:
        return None
    return clasificador.clasificar(lat, lon)


# ------------------------------------------------- asignación persistida

def asignar_zonificacion(fuente, propiedad_id, lat, lng, propiedad_ref=None, forzar=False):
    """
    Calcula la zona de una propiedad y la guarda en la tabla Zonificacion.

    Si la fila está verificada por una persona, no se pisa el código.
    """
    from .models import Zonificacion

    fuente = str(fuente or '').strip().casefold()
    propiedad_id = str(propiedad_id or '').strip()
    if not fuente or not propiedad_id:
        return None

    fila = Zonificacion.objects.filter(
        fuente=fuente, propiedad_id=propiedad_id
    ).first()
    if fila and fila.verificada and not forzar:
        return fila

    zona = None
    if lat is not None and lng is not None:
        try:
            zona = clasificar_punto(float(lat), float(lng))
        except (TypeError, ValueError):
            zona = None

    if fila is None:
        fila = Zonificacion(fuente=fuente, propiedad_id=propiedad_id)

    if propiedad_ref:
        fila.propiedad_ref = str(propiedad_ref)[:200]
    if lat is not None and lng is not None:
        try:
            fila.latitud = float(lat)
            fila.longitud = float(lng)
        except (TypeError, ValueError):
            pass

    if zona:
        fila.codigo = zona.get('codigo') or ''
        fila.nombre = zona.get('uso') or ''
        fila.categoria = zona.get('categoria') or ''
        fila.color = zona.get('color') or ''
        fila.cobertura = zona.get('cobertura')
        fila.confianza = zona.get('confianza') or ''
        fila.origen_calculo = 'automatico'
    else:
        fila.codigo = ''
        fila.nombre = ''
        fila.categoria = ''
        fila.color = ''
        fila.cobertura = None
        fila.confianza = ''

    fila.save()
    return fila


def guardar_verificacion(fuente, propiedad_id, verificada, usuario=None,
                         observacion=None, lat=None, lng=None, propiedad_ref=None):
    """Marca (o desmarca) la verificación humana de la zona de una propiedad."""
    from django.utils import timezone

    fila = asignar_zonificacion(
        fuente, propiedad_id, lat, lng, propiedad_ref=propiedad_ref
    )
    if fila is None:
        return None

    fila.verificada = bool(verificada)
    if fila.verificada:
        fila.verificada_por = (str(usuario)[:150] if usuario else None)
        fila.fecha_verificacion = timezone.now()
    else:
        fila.verificada_por = None
        fila.fecha_verificacion = None
    if observacion is not None:
        fila.observacion = str(observacion).strip() or None
    fila.save()
    return fila


def zonificaciones_guardadas(pares):
    """Filas ya guardadas para una lista de (fuente, propiedad_id)."""
    from .models import Zonificacion

    indice = {}
    normalizados = []
    for fuente, propiedad_id in pares:
        clave = (str(fuente or '').strip().casefold(), str(propiedad_id or '').strip())
        if clave[0] and clave[1]:
            normalizados.append(clave)
    if not normalizados:
        return indice

    consulta = Zonificacion.objects.none()
    for fuente, propiedad_id in normalizados:
        consulta = consulta | Zonificacion.objects.filter(
            fuente=fuente, propiedad_id=propiedad_id
        )
    for fila in consulta:
        indice[(fila.fuente, fila.propiedad_id)] = fila
    return indice
