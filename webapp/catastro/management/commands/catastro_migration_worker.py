"""Recover interrupted Geollaqta migrations outside the web worker."""
import time

from django.core.management.base import BaseCommand

from catastro import migration_runner
from catastro.master_d1 import Gateway
from catastro.storage import StorageError


class Command(BaseCommand):
    help = 'Resume a stale R2-to-D1 Catastro Master migration.'

    def add_arguments(self, parser):
        parser.add_argument('--ubigeo', default='040126')
        parser.add_argument('--interval', type=int, default=15)
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        ubigeo = str(options['ubigeo'])
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
    def _recover_once(ubigeo):
        gateway = Gateway()
        current = migration_runner.job(gateway, ubigeo)
        status = current.get('status')
        attempts = int(current.get('attempts', 0))
        old_size_error = (
            status == 'error' and
            str(current.get('message', '')).startswith('El archivo supera el límite de lectura.')
        )
        recoverable = (
            status == 'stale' or
            (status == 'error' and attempts < 3 and
             (current.get('retryable') is True or old_size_error))
        )
        if not recoverable:
            return False
        batch_size = int(current.get('batch_size') or 20)
        claimed, value = migration_runner._claim(
            gateway, ubigeo, 'azure-migration-watchdog', batch_size)
        if not claimed:
            return False
        migration_runner._run(
            ubigeo, 'azure-migration-watchdog', batch_size, value['id'])
        return True
