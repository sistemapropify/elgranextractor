"""
Clasificación de la zonificación (PDM Arequipa 2016-2025) por color del plano.

El plano está georreferenciado (WGS84 / UTM 19S): sus esquinas en longitud y
latitud definen una correspondencia lineal entre coordenadas UTM y píxeles de
la imagen. Con eso, para cada marcador se lee el color del plano en su posición
y se compara contra la paleta de la leyenda impresa, devolviendo el código de
zona (RDM-2, CE, ZRE-CH, ...).

No requiere dependencias nuevas: la proyección UTM está implementada aquí y la
lectura de imagen usa Pillow, que ya es parte del proyecto.
"""

import math
import threading
import time

import numpy as np
from PIL import Image

# ---------------------------------------------------------------- UTM 19S
_A = 6378137.0                      # semieje mayor WGS84
_F = 1 / 298.257223563              # aplanamiento
_E2 = _F * (2 - _F)                 # primera excentricidad al cuadrado
_K0 = 0.9996
_FALSO_ESTE = 500000.0
_FALSO_NORTE = 10000000.0
ZONA_UTM_PDM = 19                   # Arequipa -> zona 19 sur


def lat_lon_a_utm(lat, lon, zona=ZONA_UTM_PDM):
    """Convierte latitud/longitud (WGS84) a UTM (metros). Precisión submétrica."""
    lon0 = math.radians((zona - 1) * 6 - 180 + 3)
    phi = math.radians(lat)
    lam = math.radians(lon)
    ep2 = _E2 / (1 - _E2)
    n = _A / math.sqrt(1 - _E2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = ep2 * math.cos(phi) ** 2
    a = math.cos(phi) * (lam - lon0)

    m = _A * (
        (1 - _E2 / 4 - 3 * _E2 ** 2 / 64 - 5 * _E2 ** 3 / 256) * phi
        - (3 * _E2 / 8 + 3 * _E2 ** 2 / 32 + 45 * _E2 ** 3 / 1024) * math.sin(2 * phi)
        + (15 * _E2 ** 2 / 256 + 45 * _E2 ** 3 / 1024) * math.sin(4 * phi)
        - (35 * _E2 ** 3 / 3072) * math.sin(6 * phi)
    )

    este = _K0 * n * (
        a + (1 - t + c) * a ** 3 / 6
        + (5 - 18 * t + t ** 2 + 72 * c - 58 * ep2) * a ** 5 / 120
    ) + _FALSO_ESTE
    norte = _K0 * (
        m + n * math.tan(phi) * (
            a ** 2 / 2 + (5 - t + 9 * c + 4 * c ** 2) * a ** 4 / 24
            + (61 - 58 * t + 600 * c - 330 * ep2) * a ** 6 / 720
        )
    )
    if lat < 0:
        norte += _FALSO_NORTE
    return este, norte


def georref_desde_esquinas(esquinas, ancho_px, alto_px, zona=ZONA_UTM_PDM):
    """
    Arma la correspondencia UTM -> píxel a partir de las esquinas del plano.

    El plano es un corte UTM "norte arriba", así que la relación es lineal.
    """
    faltantes = [c for c in ('tl', 'tr', 'br', 'bl') if c not in (esquinas or {})]
    if faltantes:
        raise ValueError(f'Faltan esquinas del plano: {", ".join(faltantes)}')
    if not ancho_px or not alto_px:
        raise ValueError('La imagen del plano no tiene dimensiones válidas.')

    este_izq, norte_sup = lat_lon_a_utm(esquinas['tl'][1], esquinas['tl'][0], zona)
    este_der, norte_inf = lat_lon_a_utm(esquinas['br'][1], esquinas['br'][0], zona)

    return {
        'easting_at_x0': este_izq,
        'northing_at_y0': norte_sup,
        'easting_por_px': (este_der - este_izq) / ancho_px,
        'northing_por_px': (norte_sup - norte_inf) / alto_px,
        'zona_utm': zona,
    }


# -------------------------------------------------------------- leyenda PDM
# Paleta oficial tomada de la leyenda del plano (migración 0007 la carga en BD).
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
    ('ZRE-CH', 'Zona de reglamentación especial - Centro histórico', 'Reglamentación especial', '#e0b3b3'),
    ('ZRE-PA', 'Zona de reglamentación especial - Patrimonio agrícola', 'Reglamentación especial', '#739973'),
    ('ZRE-PN', 'Zona de reglamentación especial - Patrimonio natural', 'Reglamentación especial', '#7d4f5a'),
    ('ZRE-PP', 'Zona de reglamentación especial - Patrimonio paisajista', 'Reglamentación especial', '#bb7f85'),
    ('ZRE-RI1', 'Zona de reglamentación especial - Riesgos tipo 1', 'Reglamentación especial', '#aca661'),
    ('ZRE-RI2', 'Zona de reglamentación especial - Riesgos tipo 2', 'Reglamentación especial', '#a6ae48'),
    ('ZRE-RU', 'Zona de reglamentación especial - Renovación urbana', 'Reglamentación especial', '#663849'),
    ('ZAQ', 'Zona arqueológica', 'Otros', '#cecece'),
    ('ZM', 'Zona monumental', 'Otros', '#502936'),
    ('ZRP', 'Zona de reserva paisajista', 'Otros', '#47b368'),
    ('EA', 'Expansión agrícola', 'Otros', '#84dca6'),
    ('ZA', 'Zona agrícola', 'Otros', '#84dca6'),
]


def _rgb(hexa):
    return np.array([int(hexa[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.int32)


class ClasificadorZonificacion:
    """Lee el color del plano georreferenciado en la posición de cada marcador."""

    VENTANA = 7
    # Lado de la ventana de muestreo medido en metros: así el clasificador se
    # comporta igual si se cambia la resolución de la capa.
    VENTANA_METROS = 64.0
    TOLERANCIA = 20.0
    TOLERANCIA_GRIS = 12.0
    TOLERANCIA_EXACTA = 6.0
    VOTOS_MINIMOS_EXACTOS = 4
    FRACCION_MINIMA_EXACTOS = 0.06
    COBERTURA_MINIMA = 0.28
    COBERTURA_ALTA = 0.55

    def __init__(self, ruta_imagen, esquinas, paleta=None):
        self.ruta = str(ruta_imagen)
        with Image.open(self.ruta) as im:
            rgb = im.convert('RGB')
            self.ancho, self.alto = rgb.size
            self.pixeles = np.asarray(rgb)
        self.georref = georref_desde_esquinas(esquinas, self.ancho, self.alto)
        self.paleta = []
        for codigo, nombre, categoria, hexa in (paleta or LEYENDA_PDM):
            color = _rgb(hexa)
            self.paleta.append({
                'codigo': codigo,
                'nombre': nombre,
                'categoria': categoria,
                'color': hexa,
                'rgb': color,
                # Los grises se confunden con el terreno del mapa base: se exige
                # coincidencia más estricta para no inventar zonas.
                'gris': bool(int(color.max() - color.min()) <= 10),
            })

    # ------------------------------------------------------------------
    def pixel_de(self, lat, lon):
        """Devuelve la coordenada (x, y) del punto dentro de la imagen."""
        este, norte = lat_lon_a_utm(lat, lon, self.georref.get('zona_utm', ZONA_UTM_PDM))
        x = (este - self.georref['easting_at_x0']) / self.georref['easting_por_px']
        y = (self.georref['northing_at_y0'] - norte) / self.georref['northing_por_px']
        return x, y

    def dentro(self, x, y):
        return 0 <= x < self.ancho and 0 <= y < self.alto

    def metros_por_pixel(self):
        return (
            abs(self.georref['easting_por_px'])
            + abs(self.georref['northing_por_px'])
        ) / 2

    def ventana_en_pixeles(self):
        """Ventana de muestreo de ~64 m, siempre impar y de al menos 3 px."""
        lado = int(round(self.VENTANA_METROS / self.metros_por_pixel()))
        lado = max(3, lado)
        return lado if lado % 2 else lado + 1

    def votos_minimos_exactos(self, ventana):
        return max(
            self.VOTOS_MINIMOS_EXACTOS,
            int(round(self.FRACCION_MINIMA_EXACTOS * ventana * ventana)),
        )

    def clasificar(self, lat, lon, **kwargs):
        """
        Devuelve la zona del punto (o None si no se puede determinar).

        Ver `clasificar_pixel` para el detalle del algoritmo.
        """
        try:
            x, y = self.pixel_de(float(lat), float(lon))
        except (TypeError, ValueError):
            return None
        return self.clasificar_pixel(x, y, **kwargs)

    def clasificar_pixel(self, x, y, ventana=None, tolerancia=None,
                         cobertura_minima=None, permitir_aproximado=True):
        """
        Resuelve la zona leyendo el plano alrededor del píxel indicado.

        Primero busca una zona "llena": la mayoría del vecindario debe coincidir
        con un color de la leyenda. Si eso falla —calles, etiquetas, manzanas
        sueltas o polígonos muy pequeños— reintenta con una coincidencia casi
        exacta del color de relleno, que en este plano es inequívoca.
        """
        if not self.dentro(x, y):
            return None

        ventana = ventana or self.ventana_en_pixeles()
        tolerancia = tolerancia or self.TOLERANCIA
        cobertura_minima = cobertura_minima if cobertura_minima is not None else self.COBERTURA_MINIMA

        mitad = ventana // 2
        xi, yi = int(round(x)), int(round(y))
        x0, x1 = max(0, xi - mitad), min(self.ancho, xi + mitad + 1)
        y0, y1 = max(0, yi - mitad), min(self.alto, yi + mitad + 1)
        bloque = self.pixeles[y0:y1, x0:x1, :3].reshape(-1, 3).astype(np.int32)
        if not len(bloque):
            return None

        total = len(bloque)
        candidatos = []
        for item in self.paleta:
            limite = self.TOLERANCIA_GRIS if item['gris'] else tolerancia
            distancias = np.sqrt(
                ((bloque - item['rgb']) ** 2).sum(axis=1).astype(np.float64)
            )
            coinciden = distancias <= limite
            votos = int(coinciden.sum())
            if votos:
                candidatos.append((
                    votos,
                    float(distancias[coinciden].mean()),
                    item,
                ))
        candidatos.sort(key=lambda c: (-c[0], c[1]))

        aproximado = False
        if candidatos and (candidatos[0][0] / total) >= cobertura_minima:
            votos, distancia, item = candidatos[0]
        elif permitir_aproximado:
            # Segundo intento: color de relleno casi exacto (el plano usa los
            # colores de la leyenda sin degradado, así que una coincidencia
            # exacta es evidencia suficiente aunque el polígono sea pequeño).
            votos, distancia, item = 0, 0.0, None
            for candidato in self.paleta:
                # Los grises se parecen al terreno del mapa base: no se aceptan
                # por coincidencia exacta, solo por zona llena.
                if candidato['gris']:
                    continue
                distancias = np.sqrt(
                    ((bloque - candidato['rgb']) ** 2).sum(axis=1).astype(np.float64)
                )
                coinciden = distancias <= self.TOLERANCIA_EXACTA
                cuenta = int(coinciden.sum())
                if cuenta < self.votos_minimos_exactos(ventana):
                    continue
                promedio = float(distancias[coinciden].mean())
                if votos == 0 or cuenta > votos or (cuenta == votos and promedio < distancia):
                    votos, distancia, item = cuenta, promedio, candidato
            if item is None:
                return None
            aproximado = True
        else:
            return None

        cobertura = votos / total

        # Empate técnico entre dos colores muy parecidos (p. ej. EA y ZA): se
        # prefiere el que tenga menor distancia promedio.
        if len(candidatos) > 1:
            votos2, dist2, item2 = candidatos[1]
            if votos2 == votos and dist2 < distancia - 1:
                votos, distancia, item = votos2, dist2, item2

        return {
            'codigo': item['codigo'],
            'uso': item['nombre'],
            'categoria': item['categoria'],
            'color': item['color'],
            'cobertura': round(cobertura, 3),
            'confianza': (
                'baja' if aproximado
                else ('alta' if cobertura >= self.COBERTURA_ALTA else 'media')
            ),
            'aproximado': aproximado,
            'distancia_color': round(distancia, 1),
            'px': [round(x, 1), round(y, 1)],
        }

    def clasificar_lote(self, puntos):
        """Clasifica una lista de (lat, lon) manteniendo el orden."""
        return [self.clasificar(lat, lon) for lat, lon in puntos]

    def color_mas_cercano_pixel(self, x, y, ventana=None):
        """
        Diagnóstico: el color de la leyenda más parecido alrededor del píxel.

        Sirve para explicar por qué un punto quedó sin zona (por ejemplo, si el
        vecindario es casi todo terreno o si está pegado al borde de un polígono).
        """
        if not self.dentro(x, y):
            return None
        ventana = ventana or self.ventana_en_pixeles()
        mitad = ventana // 2
        xi, yi = int(round(x)), int(round(y))
        x0, x1 = max(0, xi - mitad), min(self.ancho, xi + mitad + 1)
        y0, y1 = max(0, yi - mitad), min(self.alto, yi + mitad + 1)
        bloque = self.pixeles[y0:y1, x0:x1, :3].reshape(-1, 3).astype(np.int32)
        if not len(bloque):
            return None
        mejor = None
        for item in self.paleta:
            distancias = np.sqrt(
                ((bloque - item['rgb']) ** 2).sum(axis=1).astype(np.float64)
            )
            promedio = float(distancias.mean())
            if mejor is None or promedio < mejor[0]:
                mejor = (promedio, item)
        return {
            'codigo': mejor[1]['codigo'],
            'nombre': mejor[1]['nombre'],
            'distancia_promedio': round(mejor[0], 1),
        }


# --------------------------------------------------------------- caché
_cache = {'clasificador': None, 'momento': 0.0, 'clave': None}
_lock = threading.Lock()
VIDA_CACHE_SEGUNDOS = 300


def invalidar_cache():
    """Fuerza a reconstruir el clasificador en la próxima consulta."""
    with _lock:
        _cache['clasificador'] = None
        _cache['momento'] = 0.0
        _cache['clave'] = None


def _ruta_local_de(imagen_url):
    """Resuelve la ruta física de la imagen de la capa (static o media)."""
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from pathlib import Path

    if not imagen_url:
        return None
    if imagen_url.startswith(('http://', 'https://')):
        return None  # una imagen remota no se puede muestrear en local

    relativa = imagen_url[len('/static/'):] if imagen_url.startswith('/static/') else imagen_url
    relativa = relativa.lstrip('/')

    encontrada = finders.find(relativa)
    if encontrada:
        return encontrada

    base_dir = getattr(settings, 'BASE_DIR', None)
    static_root = getattr(settings, 'STATIC_ROOT', None)
    candidatos = [
        Path(static_root) / relativa if static_root else None,
        Path(base_dir) / 'static' / relativa if base_dir else None,
    ]
    for candidato in candidatos:
        if candidato and candidato.exists():
            return str(candidato)
    return None


def obtener_clasificador():
    """
    Devuelve el clasificador de la capa de zonificación activa (cacheado).

    Se apoya en la primera capa raster activa que tenga esquinas cargadas y una
    imagen local accesible.
    """
    from .models import CapaRasterMapa

    ahora = time.time()
    with _lock:
        vigente = (
            _cache['clasificador'] is not None
            and (ahora - _cache['momento']) < VIDA_CACHE_SEGUNDOS
        )
        if vigente:
            return _cache['clasificador']

        capa = (
            CapaRasterMapa.objects.filter(activo=True)
            .exclude(esquinas={})
            .order_by('orden', 'id')
            .first()
        )
        if not capa:
            return None

        ruta = _ruta_local_de(capa.imagen_url)
        if not ruta:
            return None

        paleta = None
        try:
            from .models import ZonaUso
            filas = list(ZonaUso.objects.filter(activo=True).order_by('orden', 'codigo'))
            if filas:
                paleta = [(z.codigo, z.nombre, z.categoria, z.color) for z in filas]
        except Exception:
            paleta = None

        clasificador = ClasificadorZonificacion(ruta, capa.esquinas, paleta)
        _cache.update({'clasificador': clasificador, 'momento': ahora, 'clave': capa.id})
        return clasificador


def clasificar_punto(lat, lon):
    """Atajo: clasifica un punto con la capa activa. Devuelve None si no aplica."""
    clasificador = obtener_clasificador()
    if clasificador is None:
        return None
    return clasificador.clasificar(lat, lon)


# ------------------------------------------------- asignación persistida

def asignar_zonificacion(fuente, propiedad_id, lat, lng, propiedad_ref=None, forzar=False):
    """
    Calcula la zona de una propiedad y la guarda en la tabla Zonificacion.

    Reglas:
    * Si la fila está verificada por una persona, no se pisa el código: la
      verificación humana manda sobre el cálculo por color.
    * Si no está verificada, se recalcula y se actualizan coordenadas y zona.
    * Si no existe, se crea.
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
    """
    Marca (o desmarca) que una persona confirmó la zona de una propiedad.

    Si la fila todavía no existe, se calcula la zona antes de guardar.
    """
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
    """
    Devuelve las filas ya guardadas para una lista de (fuente, propiedad_id).
    """
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
