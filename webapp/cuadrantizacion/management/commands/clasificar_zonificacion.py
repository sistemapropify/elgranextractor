"""
Asigna la zona de uso del plano (PDM) a las propiedades del scraper.

Recorre las propiedades que muestra el mapa (Propify y los portales de
PropiedadesCompetencia), lee el color del plano georreferenciado en la
ubicación de cada una y guarda el resultado en la tabla Zonificacion.

Las filas ya verificadas por una persona no se pisan.

Uso:
    python manage.py clasificar_zonificacion
    python manage.py clasificar_zonificacion --fuentes remax,properati
    python manage.py clasificar_zonificacion --limite 200 --recalcular
"""

from django.core.management.base import BaseCommand

from cuadrantizacion.models import Zonificacion
from cuadrantizacion.zonificacion import asignar_zonificacion, obtener_clasificador

FUENTES_POR_DEFECTO = ('propify', 'remax', 'properati')


class Command(BaseCommand):
    help = 'Asigna la zonificación del PDM a las propiedades del scraper.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fuentes',
            default=','.join(FUENTES_POR_DEFECTO),
            help='Orígenes a procesar, separados por coma (por defecto: propify,remax,properati).',
        )
        parser.add_argument(
            '--limite', type=int, default=0,
            help='Máximo de propiedades a procesar (0 = todas).',
        )
        parser.add_argument(
            '--recalcular', action='store_true',
            help='Recalcula también las filas no verificadas que ya existían.',
        )
        parser.add_argument(
            '--lote', type=int, default=200,
            help='Cada cuántas propiedades informar el avance (por defecto 200).',
        )

    def handle(self, *args, **options):
        from cuadrantizacion import views as vistas

        if obtener_clasificador() is None:
            self.stderr.write(self.style.ERROR(
                'No hay capa de zonificación disponible (revisa la capa raster '
                'y su imagen en static).'
            ))
            return

        fuentes = [
            fuente.strip().casefold()
            for fuente in (options['fuentes'] or '').split(',')
            if fuente.strip()
        ]
        limite = options['limite'] or 0
        lote = max(options['lote'] or 200, 1)

        propiedades = self._recolectar(vistas, fuentes, limite)
        if not propiedades:
            self.stdout.write(self.style.WARNING('No se encontraron propiedades para procesar.'))
            return

        self.stdout.write(f'Propiedades a procesar: {len(propiedades)}')

        creadas = actualizadas = verificadas = sin_zona = 0
        for numero, (fuente, propiedad_id, lat, lng, referencia) in enumerate(propiedades, 1):
            existente = Zonificacion.objects.filter(
                fuente=fuente, propiedad_id=propiedad_id
            ).only('id', 'verificada', 'codigo').first()

            if existente and existente.verificada and not options['recalcular']:
                verificadas += 1
                continue

            fila = asignar_zonificacion(
                fuente=fuente,
                propiedad_id=propiedad_id,
                lat=lat,
                lng=lng,
                propiedad_ref=referencia,
            )
            if fila is None:
                continue
            if existente is None:
                creadas += 1
            else:
                actualizadas += 1
            if not fila.codigo:
                sin_zona += 1

            if numero % lote == 0:
                self.stdout.write(f'  ... {numero}/{len(propiedades)}')

        self.stdout.write(self.style.SUCCESS(
            f'Listo. Nuevas: {creadas} · actualizadas: {actualizadas} · '
            f'verificadas (sin tocar): {verificadas} · sin zona: {sin_zona}'
        ))
        self.stdout.write(
            f'Total en la tabla Zonificacion: {Zonificacion.objects.count()}'
        )

    # ------------------------------------------------------------------
    def _recolectar(self, vistas, fuentes, limite):
        """Junta (fuente, propiedad_id, lat, lng, referencia) de cada origen."""
        resultados = []

        if 'propify' in fuentes:
            try:
                for prop in vistas._available_propify_properties():
                    lat, lng = prop.get('lat'), prop.get('lng')
                    if lat is None or lng is None:
                        continue
                    resultados.append((
                        'propify', str(prop.get('id')), lat, lng,
                        prop.get('code') or prop.get('title') or '',
                    ))
            except Exception as error:  # base Propify inaccesible o sin datos
                self.stderr.write(self.style.WARNING(
                    f'No se pudieron leer propiedades Propify: {error}'
                ))

        portales = [f for f in fuentes if f in {'remax', 'properati'}]
        if portales:
            try:
                for prop in vistas._available_scraped_properties(tuple(portales)):
                    lat, lng = prop.get('lat'), prop.get('lng')
                    if lat is None or lng is None:
                        continue
                    identificador = prop.get('record_id')
                    if identificador is None:
                        identificador = prop.get('id')
                    resultados.append((
                        str(prop.get('source_key') or '').casefold(),
                        str(identificador),
                        lat,
                        lng,
                        prop.get('code') or prop.get('title') or '',
                    ))
            except Exception as error:
                self.stderr.write(self.style.WARNING(
                    f'No se pudieron leer propiedades de portales: {error}'
                ))

        vistos = set()
        unicos = []
        for fila in resultados:
            clave = (fila[0], fila[1])
            if not clave[0] or not clave[1] or clave in vistos:
                continue
            vistos.add(clave)
            unicos.append(fila)
        return unicos[:limite] if limite else unicos
