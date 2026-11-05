"""Capture independent GeoLlaqta lot/block snapshots into private R2."""
from django.core.management.base import BaseCommand, CommandError

from catastro import vector_snapshots


class Command(BaseCommand):
    help = 'Capture independent vector snapshots for a district without creating D1 identities.'

    def add_arguments(self, parser):
        parser.add_argument('--ubigeo', required=True)
        parser.add_argument('--layers', nargs='+', default=['lotes', 'manzanas', 'vias'])
        parser.add_argument('--source', default='pcdpi',
                            choices=['pcdpi', 'wgs84', 'psad56'])
        parser.add_argument('--details', action='store_true',
                            help='Incluye linderos y titulación de predios formalizados.')
        parser.add_argument('--detail-id', action='append', default=[],
                            help='Limita --details a uno o más códigos de predio.')

    def handle(self, *args, **options):
        ubigeo = options['ubigeo']
        try:
            results = vector_snapshots.capture_district(
                ubigeo, options['layers'], source=options['source'],
                include_details=options['details'],
                detail_ids=options['detail_id'],
                progress=lambda layer, done, total: self.stdout.write(
                    '%s %s %s: %s/%s' % (
                        ubigeo, options['source'], layer, done, total)))
        except (ValueError, RuntimeError) as error:
            raise CommandError(str(error)) from error
        for result in results:
            self.stdout.write(self.style.SUCCESS(
                '%s/%s/%s: %s features' % (
                    ubigeo, options['source'], result['layer'],
                    result['features'])))
