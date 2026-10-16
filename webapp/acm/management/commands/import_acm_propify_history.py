"""Import an explicitly verified ownership mapping; dry run is the default."""
import hashlib
import json
import uuid
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from acm.access import database
from acm.access_models import ACMPortalAnalysis
from acm.components_engine import parameters
from acm.models import ACMLink


class Command(BaseCommand):
    help = 'Revisa/importa historial por componentes usando una correspondencia verificada de IDs.'

    def add_arguments(self, parser):
        parser.add_argument('--mapping', required=True, help='JSON: [{"prometeo_user_id": "UUID", "propify_user_id": "ID"}].')
        parser.add_argument('--apply', action='store_true', help='Importar los registros revisados; sin esta opción solo cuenta.')

    def handle(self, *args, **options):
        try:
            items = json.loads(Path(options['mapping']).read_text(encoding='utf-8'))
            if not isinstance(items, list):
                raise ValueError
            mappings = [(str(uuid.UUID(str(item['prometeo_user_id']))), str(int(item['propify_user_id']))) for item in items]
            if len({source for source, _ in mappings}) != len(mappings) or any(int(target) <= 0 for _, target in mappings):
                raise ValueError
        except (OSError, ValueError, TypeError, KeyError):
            raise CommandError('El archivo debe contener correspondencias únicas de UUID Prometeo a ID Propify positivo.')
        # Validate every destination before writing anything. Do not infer identity from names/emails.
        for _, target in mappings:
            with connections['propifai'].cursor() as cursor:
                cursor.execute('SELECT id FROM [dbo].[user] WHERE id=%s AND is_active=1', [target])
                if cursor.fetchone() is None:
                    raise CommandError('Una cuenta Propify de destino no existe o está inactiva.')
        ready = pending = created = 0
        with transaction.atomic(using=database()):
            for source, target in mappings:
                for old in ACMLink.objects.filter(user_id=source).iterator(chunk_size=100):
                    if old.metodo != 'componentes' or not isinstance(old.parametros_json, dict) or not old.parametros_json or not isinstance(old.resultado_json, dict) or not old.resultado_json.get('new'):
                        pending += 1
                        continue
                    try:
                        parameters(old.parametros_json)
                    except (ValueError, TypeError, OverflowError):
                        pending += 1
                        continue
                    snapshot = {'params': old.parametros_json, 'records': old.propiedades_json,
                                'result': old.resultado_json,
                                'excluded': old.resultado_json.get('excluded_ids', []),
                                'legacy_id': str(old.id)}
                    ready += 1
                    fingerprint = hashlib.sha256(('legacy:' + str(old.id)).encode()).hexdigest()
                    existing = ACMPortalAnalysis.objects.using(database()).filter(fingerprint=fingerprint).first()
                    if existing and existing.owner_id != target:
                        raise CommandError('Un análisis ya está vinculado a otra cuenta. No se reasigna automáticamente.')
                    if options['apply'] and existing is None:
                        row = ACMPortalAnalysis.objects.using(database()).create(owner_id=target, fingerprint=fingerprint, snapshot=snapshot)
                        ACMPortalAnalysis.objects.using(database()).filter(pk=row.pk).update(created_at=old.created_at)
                        created += 1
        self.stdout.write(f'Revisables: {ready}. Conservados sin importar por evidencia incompleta/clásica: {pending}. Importados: {created}.')
        if not options['apply']:
            self.stdout.write('Simulación: no se modificó el historial. Revisa las correspondencias antes de usar --apply.')
