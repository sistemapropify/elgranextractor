"""Reprocess archived evidence; simulation by default, never opens portal pages."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from ingestas.models import PropiedadesCompetencia, RevisionPropiedadScraping
from scrapi.building_features import apply_features, preserve_features


class Command(BaseCommand):
    help = 'Reprocesa cocheras y ascensor desde los datos guardados. Simula salvo --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Guardar los cambios; por defecto solo simula.')
        parser.add_argument('--database', default='default')
        parser.add_argument('--portal', choices=['remax', 'properati', 'adondevivir', 'urbania', 'facebook_marketplace'])
        parser.add_argument('--after-id', type=int, default=0, help='Reanudar después de este ID.')
        parser.add_argument('--batch-size', type=int, default=100)
        parser.add_argument('--limit', type=int, help='Opcional, solo para acotar una comprobación.')
        parser.add_argument('--cursor-file', type=Path, help='Guardar el cursor confirmado al aplicar; reanuda en la siguiente ejecución.')

    def handle(self, *args, **options):
        size, after = options['batch_size'], options['after_id']
        if not 1 <= size <= 500 or after < 0 or (options['limit'] is not None and options['limit'] < 1):
            raise CommandError('Tamaño de lote, límite o ID de reanudación inválido.')
        alias, portal = options['database'], options.get('portal')
        cursor_path = options.get('cursor_file')
        scope = {'database': alias, 'portal': portal}
        if cursor_path and cursor_path.exists():
            try:
                cursor = json.loads(cursor_path.read_text(encoding='utf-8'))
                if cursor.get('scope') != scope:
                    raise ValueError()
                after = max(after, int(cursor['after_id']))
            except (ValueError, KeyError, TypeError):
                raise CommandError('El cursor no corresponde a este portal y base de datos.')
        scanned = changed = 0
        while options['limit'] is None or scanned < options['limit']:
            take = size if options['limit'] is None else min(size, options['limit'] - scanned)
            query = PropiedadesCompetencia.objects.using(alias).filter(
                pk__gt=after, tipo_inmueble__in=['Casa', 'Departamento', 'Oficina'])
            if portal:
                query = query.filter(fuente__iexact=portal)
            ids = list(query.order_by('pk').values_list('pk', flat=True)[:take])
            if not ids:
                break
            for pk in ids:
                with transaction.atomic(using=alias):
                    records = PropiedadesCompetencia.objects.using(alias)
                    if options['apply']:
                        records = records.select_for_update()
                    p = records.get(pk=pk)
                    review = RevisionPropiedadScraping.objects.using(alias).filter(propiedad_id=pk).first()
                    protected = set(review.campos_protegidos) if review else set()
                    old_raw = p.datos_crudos if isinstance(p.datos_crudos, dict) else {}
                    row = apply_features({'tipo_inmueble': p.tipo_inmueble, 'descripcion': p.descripcion,
                        'estacionamientos': p.estacionamientos, 'datos_crudos': old_raw, 'amenities': p.amenities,
                        'fecha_extraccion': p.fecha_extraccion})
                    raw = preserve_features(row['datos_crudos'], old_raw, protected,
                        kind=p.tipo_inmueble, description=p.descripcion, count=p.estacionamientos, amenities=p.amenities)
                    count = row['estacionamientos']
                    if count is None or {'estacionamientos', 'tiene_cochera', 'tipos_cochera'} & protected:
                        count = p.estacionamientos
                    different = raw != old_raw or count != p.estacionamientos
                    if different:
                        changed += 1
                        if options['apply']:
                            p.datos_crudos, p.estacionamientos = raw, count
                            p.save(using=alias, update_fields=['datos_crudos', 'estacionamientos'])
                scanned += 1
                after = pk
            if options['apply'] and cursor_path:
                cursor_path.parent.mkdir(parents=True, exist_ok=True)
                temp = cursor_path.with_name(cursor_path.name + '.tmp')
                temp.write_text(json.dumps({'scope': scope, 'after_id': after}), encoding='utf-8')
                temp.replace(cursor_path)
            self.stdout.write(json.dumps({'mode': 'apply' if options['apply'] else 'simulation',
                'scanned': scanned, 'changed': changed, 'after_id': after}, ensure_ascii=False))
        self.stdout.write(self.style.SUCCESS(f'{scanned} revisadas; {changed} con cambios; último ID {after}. '
            + ('Cambios guardados.' if options['apply'] else 'Simulación: no se modificaron datos.')))
