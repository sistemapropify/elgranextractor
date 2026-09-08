import json
import socket
from django.core.management.base import BaseCommand, CommandError
from ingestas.scraping_health import worker_health


class Command(BaseCommand):
    help = 'Salud del worker de este host; código de salida no cero cuando no está listo.'

    def add_arguments(self, parser):
        parser.add_argument('--any-worker', action='store_true')

    def handle(self, *args, **options):
        health = worker_health(None if options['any_worker'] else socket.gethostname()[:128])
        self.stdout.write(json.dumps(health))
        if not health['ready']:
            raise CommandError('worker.unavailable')
