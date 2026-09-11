"""Recalcula precision_ubicacion de las propiedades de Properati ya guardadas.

Lee la ficha de cada aviso y aplica la regla real del portal:
  - aviso 'El anunciante prefiere no mostrar la dirección exacta' (o
    visibility: approximate)  -> aproximada
  - sin ese aviso y con coordenada -> exacta
  - sin datos -> desconocida
"""
import re
import time
import urllib.request

from django.core.management.base import BaseCommand
from django.db.models import Q

from ingestas.models import PropiedadesCompetencia
from scrapi.properati_scraper import (
    _precision_ubicacion_desde_html,
    extraer_coordenadas_desde_html,
)

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
      '(KHTML, like Gecko) Version/17.0 Safari/605.1.15')
HEADERS = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-PE,es;q=0.9,en;q=0.8',
    'Accept-Encoding': 'identity',
}


class Command(BaseCommand):
    help = 'Recalcula precision_ubicacion de Properati leyendo la ficha de cada aviso.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0,
                            help='Máximo de propiedades a procesar (0 = todas).')
        parser.add_argument('--solo-vacios', action='store_true',
                            help='Solo las que están en desconocida o sin coordenadas.')
        parser.add_argument('--sleep', type=float, default=0.8,
                            help='Pausa entre peticiones (segundos).')

    def handle(self, *args, **options):
        qs = PropiedadesCompetencia.objects.filter(
            fuente='properati', url__isnull=False).exclude(url='')
        if options['solo_vacios']:
            qs = qs.filter(Q(precision_ubicacion='desconocida') | Q(latitud__isnull=True))
        qs = qs.order_by('-id')
        if options['limit']:
            qs = qs[:options['limit']]

        ok = err = cambiadas = 0
        for r in qs:
            try:
                req = urllib.request.Request(r.url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=40) as resp:
                    html = resp.read().decode('utf-8', errors='replace')
            except Exception as exc:
                err += 1
                self.stderr.write(f'ERR {r.id_origen}: {exc}')
                continue

            lat, lng = extraer_coordenadas_desde_html(html)
            updates = {}
            if lat is not None and lng is not None and r.latitud is None:
                updates['latitud'] = lat
                updates['longitud'] = lng
                updates['coordenadas'] = f'{lat},{lng}'

            precision = _precision_ubicacion_desde_html(html)
            if precision == 'desconocida' and re.search(
                    r'prefiere no mostrar la direcci[oó]n exacta', html, re.IGNORECASE):
                precision = 'aproximada'
            if precision == 'desconocida' and (r.latitud is not None or 'latitud' in updates):
                precision = 'exacta'
            if precision != r.precision_ubicacion:
                updates['precision_ubicacion'] = precision

            if updates:
                PropiedadesCompetencia.objects.filter(pk=r.pk).update(**updates)
                cambiadas += 1
            ok += 1
            time.sleep(options['sleep'])

        self.stdout.write(self.style.SUCCESS(
            f'Listo: {ok} procesadas, {cambiadas} actualizadas, {err} errores.'))
