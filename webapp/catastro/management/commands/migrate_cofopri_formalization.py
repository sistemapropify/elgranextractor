"""Migrate archived WGS84/PSAD56 lots to D1 through MasterStore."""
from django.core.management.base import BaseCommand, CommandError

from catastro import cofopri_vector_migration, source_manager
from cuadrantizacion.geollaqta import DISTRICTS


class Command(BaseCommand):
    help = 'Migrate deduplicated formalization vectors using MasterStore.'

    def add_arguments(self, parser):
        parser.add_argument('--ubigeo', action='append', required=True)
        parser.add_argument('--batch-size', type=int, default=100)
        parser.add_argument('--limit', type=int)

    def handle(self, *args, **options):
        if not 20 <= options['batch_size'] <= 200:
            raise CommandError('batch-size debe estar entre 20 y 200.')
        for ubigeo in options['ubigeo']:
            if ubigeo not in DISTRICTS:
                raise CommandError('UBIGEO no disponible: ' + ubigeo)
            try:
                store = source_manager.store()
                result = cofopri_vector_migration.migrate_district(
                    store, ubigeo, DISTRICTS[ubigeo]['name'],
                    options['batch_size'], options['limit'],
                    progress=lambda item: self.stdout.write(
                        '%s: %s/%s, faltan %s' % (
                            ubigeo, item['processed'],
                            item['total'], item['remaining'])))
            except Exception as error:
                raise CommandError(str(error)) from error
            self.stdout.write(self.style.SUCCESS(
                '%s: %s unique lots, %s batches' % (
                    ubigeo, result['unique_formalization_lots'],
                    len(result['batches']))))
