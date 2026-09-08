"""Read-only, evidence-backed proposals for historical numeric corrections."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from ingestas.models import PropiedadesCompetencia
from ingestas.scraping_history import PORTALS, propose


class Command(BaseCommand):
    help = 'Exporta correcciones verificables desde datos crudos. No modifica SQL.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)
        parser.add_argument('--portal', choices=PORTALS, default='urbania')
        parser.add_argument('--after-id', type=int, default=0)
        parser.add_argument('--limit', type=int, choices=range(1, 1001), default=1000, metavar='1..1000')

    def handle(self, *args, **options):
        count = skipped = 0
        last_id = options['after_id']
        with Path(options['output']).open('x', encoding='utf-8') as output:
            query = PropiedadesCompetencia.objects.filter(fuente__iexact=options['portal'], pk__gt=last_id).order_by('pk')
            for prop in query.iterator(chunk_size=500):
                last_id = prop.pk
                try:
                    proposal = propose(prop)
                except (ValueError, TypeError, KeyError, ValidationError):
                    skipped += 1
                    continue
                if proposal:
                    output.write(json.dumps(proposal, ensure_ascii=False) + '\n')
                    count += 1
                    if count == options['limit']:
                        break
        self.stdout.write(f'{count} propuestas; {skipped} registros inválidos. Continuar con --after-id {last_id}. No se modificó SQL.')
