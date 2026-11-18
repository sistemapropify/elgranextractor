"""Recover interrupted Geollaqta migrations outside the web worker."""
import time

from django.core.management.base import BaseCommand

from catastro import migration_runner
from catastro.master_d1 import Gateway
from catastro.storage import StorageError


class Command(BaseCommand):
    help = 'Resume a stale R2-to-D1 Catastro Master migration.'

    def add_arguments(self, parser):
        parser.add_argument('--ubigeo', default=None)
        parser.add_argument('--interval', type=int, default=15)
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        ubigeo = options['ubigeo']
        if ubigeo is not None:
            ubigeo = str(ubigeo)
        interval = max(5, int(options['interval']))
        while True:
            try:
                self._recover_once(ubigeo)
            except StorageError as error:
                self.stderr.write('Catastro migration recovery: ' + str(error))
            if options['once']:
                return
            time.sleep(interval)

    @staticmethod
    def _recover_district(gateway, ubigeo):
        current = migration_runner.job(gateway, ubigeo)
        status = current.get('status')
        attempts = int(current.get('attempts', 0))
        if status == 'done' and not current.get('audit'):
            migration_runner.audit_existing(ubigeo, 'azure-migration-watchdog')
            return True
        old_size_error = (
            status == 'error' and
            str(current.get('message', '')).startswith(
                'El archivo supera el límite de lectura.')
        )
        recoverable = (
            status == 'stale' or
            (status == 'error' and attempts < 3 and
             (current.get('retryable') is True or old_size_error))
        )
        if not recoverable:
            return False
        batch_size = min(
            int(current.get('batch_size') or migration_runner.SAFE_BATCH_SIZE),
            migration_runner.SAFE_BATCH_SIZE,
        )
        claimed, value = migration_runner._claim(
            gateway, ubigeo, 'azure-migration-watchdog', batch_size)
        if not claimed:
            return False
        migration_runner._run(
            ubigeo, 'azure-migration-watchdog', batch_size, value['id'])
        return True

    @classmethod
    def _recover_once(cls, ubigeo=None):
        gateway = Gateway()
        if ubigeo is not None:
            return cls._recover_district(gateway, str(ubigeo))

        # Global migrations are the primary path for "migrar TODOS": if one
        # was interrupted, resume it. While it runs, it owns each district, so
        # the per-district pass below must not race with it.
        global_job = migration_runner.job(gateway, migration_runner.ALL_SCOPE)
        if global_job.get('status') in ('running', 'stale') or (
                global_job.get('status') == 'error'
                and int(global_job.get('attempts', 0)) < 3
                and global_job.get('retryable') is True):
            recovered = migration_runner.recover_global(
                actor='azure-migration-watchdog')
            return bool(recovered.get('recovered'))

        from cuadrantizacion import geollaqta

        advanced = False
        for ubigeo in sorted(geollaqta.DISTRICTS):
            try:
                advanced = cls._recover_district(
                    gateway, str(ubigeo)) or advanced
            except ValueError:
                # No R2 data or an incomplete inventory: leave the district
                # untouched and keep recovering the remaining scopes.
                continue
        return advanced
