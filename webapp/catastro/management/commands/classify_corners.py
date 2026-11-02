import time

from django.core.management.base import BaseCommand, CommandError

from catastro import manual_parks, vector_snapshots
from catastro.corner_detection import detect_corner_lots


class Command(BaseCommand):
    help = (
        'Detect corner lots from block geometry and merge them into the manual '
        'classification layer without removing existing classifications.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--ubigeo',
            action='append',
            dest='ubigeos',
            help='District UBIGEO. Repeat to process selected districts.',
        )
        parser.add_argument(
            '--min-frontage',
            type=float,
            default=3.0,
            help='Minimum metres of contact on each distinct frontage (default: 3).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Write suggestions to R2. Without this flag the command is a dry run.',
        )

    def handle(self, *args, **options):
        minimum = options['min_frontage']
        if minimum <= 0:
            raise CommandError('--min-frontage debe ser mayor que cero.')

        available = {
            source['ubigeo']: source
            for source in vector_snapshots.catalog_sources()
            if source.get('role') == 'snapshot'
            and source.get('layers', {}).get('lotes', {}).get('count')
            and source.get('layers', {}).get('manzanas', {}).get('count')
        }
        requested = sorted(set(options.get('ubigeos') or available))
        unknown = [ubigeo for ubigeo in requested if ubigeo not in available]
        if unknown:
            raise CommandError(
                'No hay vectores de lotes y manzanas para: ' + ', '.join(unknown)
            )

        mode = 'APLICANDO' if options['apply'] else 'SIMULACIÓN'
        self.stdout.write(
            f'{mode}: {len(requested)} distrito(s), frente mínimo {minimum:g} m.'
        )
        total_added = 0
        failures = []
        for ubigeo in requested:
            try:
                for attempt in range(1, 4):
                    try:
                        lots = (
                            vector_snapshots.read_snapshot(ubigeo, 'lotes')
                            .get('features') or []
                        )
                        blocks = (
                            vector_snapshots.read_snapshot(ubigeo, 'manzanas')
                            .get('features') or []
                        )
                        break
                    except Exception:
                        if attempt == 3:
                            raise
                        self.stderr.write(
                            f'{ubigeo}: error leyendo vectores; '
                            f'reintento {attempt}/3 en {attempt * 2}s.'
                        )
                        time.sleep(attempt * 2)
                detected, skipped = detect_corner_lots(
                    lots,
                    blocks,
                    min_frontage_m=minimum,
                )
                current = manual_parks.read(ubigeo)
                # A park parcel is not an ordinary corner lot and is never
                # imported into the street-corner category automatically.
                detected = sorted(set(detected) - set(current['parks']))
                merged = sorted(set(current['corners']) | set(detected))
                added = len(set(merged) - set(current['corners']))
                total_added += added
                self.stdout.write(
                    f'{ubigeo}: {len(lots):,} lotes, {len(blocks):,} manzanas, '
                    f'{len(detected):,} sugerencias, {added:,} nuevas, '
                    f'{len(merged):,} esquinas totales, {skipped:,} omitidas.'
                )
                if options['apply'] and added:
                    manual_parks.save_classifications(
                        ubigeo,
                        {
                            'parks': current['parks'],
                            'corners': merged,
                            'faces_park': current['faces_park'],
                            'colors': current['colors'],
                        },
                        current['token'],
                        actor='clasificacion-automatica-esquinas',
                    )
            except Exception as error:
                failures.append(ubigeo)
                self.stderr.write(
                    self.style.ERROR(f'{ubigeo}: no se pudo procesar: {error}')
                )
        self.stdout.write(self.style.SUCCESS(
            f'Total de esquinas nuevas: {total_added:,}.'
        ))
        if failures:
            raise CommandError(
                'Proceso parcial. Vuelve a ejecutar para: ' + ', '.join(failures)
            )
