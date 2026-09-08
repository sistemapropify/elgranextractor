import json
from pathlib import Path
from uuid import UUID
from django.core.management.base import BaseCommand, CommandError
from ingestas.scraping_history import apply_plan, rollback_batch


class Command(BaseCommand):
    help = 'Valida/aplica un plan histórico o revierte un lote. Simulación por defecto.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--input')
        group.add_argument('--rollback', type=UUID)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            if options['rollback']:
                result = rollback_batch(options['rollback'], apply=options['apply'])
            else:
                path = Path(options['input'])
                if path.stat().st_size > 10_000_000:
                    raise ValueError('Plan demasiado grande; dividirlo en lotes menores a 10 MB.')
                proposals = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
                if len(proposals) > 1000:
                    raise ValueError('Máximo 1000 propiedades por lote para acotar los bloqueos SQL.')
                result = apply_plan(proposals, apply=options['apply'])
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result))
