"""Capture independent GeoLlaqta lot/block snapshots into private R2."""
from django.core.management.base import BaseCommand, CommandError

from catastro import vector_snapshots


class Command(BaseCommand):
    help = 'Capture independent vector snapshots for a district without creating D1 identities.'

    def add_arguments(self, parser):
        parser.add_argument('--ubigeo', required=True)
        parser.add_argument('--layers', nargs='+', default=['lotes', 'manzanas'])

    def handle(self, *args, **options):
        ubigeo = options['ubigeo']
        try:
            results = vector_snapshots.capture_district(
                ubigeo, options['layers'],
                progress=lambda layer, done, total: self.stdout.write(
                    '%s %s: %s/%s' % (ubigeo, layer, done, total)))
        except (ValueError, RuntimeError) as error:
            raise CommandError(str(error)) from error
        for result in results:
            self.stdout.write(self.style.SUCCESS(
                '%s/%s: %s features' % (ubigeo, result['layer'], result['features'])))
