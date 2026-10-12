import json

from django.core.management.base import BaseCommand, CommandError
from ingestas.ml_dataset_archive import (
    ARCHIVE_KEY, archive_candidates, archive_old_datasets, restore_dataset,
)


class Command(BaseCommand):
    help = 'Archiva cortes ML antiguos en Blob privado. Sin --apply solo muestra el plan.'

    def add_arguments(self, parser):
        parser.add_argument('--keep', type=int, default=5)
        parser.add_argument('--min-age-days', type=int, default=0)
        parser.add_argument('--limit', type=int, default=10)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--restore', type=int, metavar='DATASET_ID')

    def handle(self, *args, **options):
        try:
            if options['limit'] < 1:
                raise ValueError('El límite debe ser positivo.')
            if options['restore']:
                if not options['apply']:
                    self.stdout.write('Para restaurar el dataset en SQL utiliza --restore ID --apply.')
                    return
                result = restore_dataset(options['restore'])
            elif options['apply']:
                result = archive_old_datasets(options['keep'], options['min_age_days'], options['limit'])
            else:
                candidates = [dict(dataset_id=cut.pk, sql_rows=cut.entries.count())
                              for cut in archive_candidates(options['keep'], options['min_age_days'])
                              if not (cut.coverage or {}).get(ARCHIVE_KEY)]
                result = {'dry_run': True, 'eligible_datasets': len(candidates),
                          'eligible_sql_rows': sum(cut['sql_rows'] for cut in candidates),
                          'next_batch': candidates[:options['limit']]}
            self.stdout.write(json.dumps(result))
        except Exception as error:
            raise CommandError('No se completó el archivado/restauración: %s' % type(error).__name__) from error
