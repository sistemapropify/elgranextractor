"""Explorador 3D de atipicos por distrito: terreno, construida y precio.

Cada casa se lleva a un vector de tres dimensiones normalizadas y se mide que tan
lejos queda del centro del grupo. Las mas lejanas son las que conviene revisar
primero.

Normalizacion: log10 de cada variable (precio y areas son asimetricas: pocas
casas muy caras o muy grandes estiran la escala) y despues z robusto con mediana
y MAD, en vez de media y desviacion. La media y la desviacion las mueven
justamente los atipicos que se quieren encontrar; la mediana no.
"""
import math
from statistics import median

from django.db.models import Count, Q
from django.shortcuts import render

from ingestas.models import PropiedadesCompetencia

TIPO = 'Casa'
OPERACION = 'Venta'
MIN_CASAS = 8
# 0.6745 es el cuantil 75 de la normal: deja el MAD en la misma escala que una
# desviacion estandar, para poder leer la distancia como "sigmas".
ESCALA_MAD = 0.6745
# Corte habitual cuando se trabaja con z robusto y tres dimensiones.
CORTE_ATIPICO = 3.5

CAMPOS = ('id', 'fuente', 'id_origen', 'titulo', 'distrito', 'precio_usd',
          'precio_soles', 'area_terreno', 'area_construida', 'latitud',
          'longitud', 'url', 'estado_publicacion', 'precision_ubicacion')

NUMERICOS = ('precio_usd', 'precio_soles', 'area_terreno', 'area_construida',
             'latitud', 'longitud')

EJES = (('l_terreno', 'Terreno (m²)'), ('l_construida', 'Construida (m²)'),
        ('l_precio', 'Precio (USD)'))


def distritos():
    """Distritos con casas suficientes para que la comparacion tenga sentido."""
    completo = Q(area_terreno__gt=0) & Q(area_construida__gt=0) & Q(precio_usd__gt=0)
    filas = (PropiedadesCompetencia.objects
             .filter(tipo_inmueble=TIPO, tipo_operacion=OPERACION)
             .exclude(distrito__isnull=True).exclude(distrito='')
             .values('distrito')
             .annotate(usables=Count('id', filter=completo))
             .filter(usables__gte=MIN_CASAS)
             .order_by('-usables', 'distrito'))
    return [{'distrito': f['distrito'], 'usables': f['usables']} for f in filas]


def _log10(valor):
    valor = float(valor)
    return math.log10(valor) if valor > 0 else None


def _mediana_y_escala(valores):
    """Mediana y factor para pasar a z robusto. ``None`` si el grupo es plano."""
    mediana = median(valores)
    mad = median([abs(v - mediana) for v in valores])
    return mediana, (ESCALA_MAD / mad if mad > 1e-12 else None)


def analizar(distrito):
    """Casas del distrito con su vector normalizado y su distancia al centro."""
    casas = list(PropiedadesCompetencia.objects
                 .filter(tipo_inmueble=TIPO, tipo_operacion=OPERACION,
                         distrito=distrito, area_terreno__gt=0,
                         area_construida__gt=0, precio_usd__gt=0)
                 .values(*CAMPOS))
    if len(casas) < MIN_CASAS:
        return None

    for casa in casas:
        for campo in NUMERICOS:
            casa[campo] = float(casa[campo]) if casa[campo] is not None else None
        casa['l_terreno'] = _log10(casa['area_terreno'])
        casa['l_construida'] = _log10(casa['area_construida'])
        casa['l_precio'] = _log10(casa['precio_usd'])

    ejes = {}
    for clave, etiqueta in EJES:
        mediana, escala = _mediana_y_escala([c[clave] for c in casas])
        ejes[clave] = {'etiqueta': etiqueta, 'mediana': round(mediana, 4),
                       'valor_central': round(10 ** mediana, 1), 'escala': escala}

    for casa in casas:
        suma = 0.0
        for clave, _ in EJES:
            escala = ejes[clave]['escala']
            z = 0.0 if escala is None else (casa[clave] - ejes[clave]['mediana']) * escala
            casa['z_' + clave[2:]] = round(z, 3)
            suma += z * z
        casa['distancia'] = round(math.sqrt(suma), 3)
        casa['atipica'] = casa['distancia'] > CORTE_ATIPICO
        casa['precio_m2'] = round(casa['precio_usd'] / casa['area_construida'], 1)

    casas.sort(key=lambda c: -c['distancia'])
    return {
        'distrito': distrito,
        'casas': casas,
        'ejes': ejes,
        'total': len(casas),
        'atipicas': sum(1 for c in casas if c['atipica']),
        'corte': CORTE_ATIPICO,
        'min_casas': MIN_CASAS,
    }


def outliers_3d(request):
    """Pagina con el selector de distrito y la nube 3D de casas."""
    distrito = (request.GET.get('distrito') or '').strip()
    datos = analizar(distrito) if distrito else None
    return render(request, 'acm/outliers_3d.html', {
        'distritos': distritos(),
        'distrito': distrito,
        'datos': datos,
        'corte': CORTE_ATIPICO,
        'min_casas': MIN_CASAS,
    })
