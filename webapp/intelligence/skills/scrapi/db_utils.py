"""Idempotent writes and observations, fenced by the current execution owner."""
import logging
from django.db import transaction
from django.utils import timezone
from scrapi.contracts import ScrapingInterrupted
from scrapi.normalization import validate_row

logger = logging.getLogger(__name__)


def guardar_propiedades(propiedades, fuente, lifecycle_run_id=None, execution_token=None):
    from ingestas.models import PropiedadesCompetencia, ScrapingCandidate, PublicacionFuente
    from ingestas.scraping_store import lock_run, run_counters
    counters = {'total': 0, 'nuevas': 0, 'actualizadas': 0, 'errores': 0}
    seen = set()
    for prop in propiedades:
        key = str(prop.get('id_origen') or '').strip()
        if key in seen:
            continue
        seen.add(key)
        try:
            row = validate_row(prop)
            with transaction.atomic():
                run = lock_run(lifecycle_run_id, execution_token) if lifecycle_run_id else None
                if run and run.portal != fuente:
                    raise ValueError('Portal de la ejecución no coincide con la propiedad')
                candidate = None
                if run:
                    candidate, _ = ScrapingCandidate.objects.get_or_create(run=run, source_id=key,
                        defaults={'raw': row.get('datos_crudos') or {}, 'page': 1})
                fields = {field.name for field in PropiedadesCompetencia._meta.concrete_fields}
                defaults = {k: v for k, v in row.items() if k in fields
                            and k not in {'id', 'fuente', 'id_origen'} and v is not None}
                if run:
                    defaults.update(estado_publicacion='activa', ultima_vez_vista=timezone.now(),
                        fecha_primera_ausencia=None, fecha_retiro_confirmado=None,
                        ausencias_consecutivas=0, ultima_ejecucion_vista=run)
                obj, created = PropiedadesCompetencia.objects.update_or_create(
                    fuente=fuente, id_origen=key, defaults=defaults)
                if run:
                    if obj.primera_vez_vista is None:
                        obj.primera_vez_vista = timezone.now()
                        obj.save(update_fields=['primera_vez_vista'])
                    if run.source_key:
                        PublicacionFuente.objects.update_or_create(source_key=run.source_key, propiedad=obj,
                            defaults={'last_run': run, 'misses': 0, 'state': 'activa',
                                      'first_missing_at': None, 'retired_at': None})
                    candidate.save_outcome = candidate.save_outcome or ('created' if created else 'updated')
                    candidate.raw = row.get('datos_crudos') or candidate.raw
                    candidate.error = str(candidate.raw.get('_detail_error') or '')[:4000]
                    candidate.status = 'error' if candidate.error else 'saved'
                    candidate.save()
                counters['total'] += 1
                counters['nuevas' if created else 'actualizadas'] += 1
        except ScrapingInterrupted:
            raise
        except Exception as exc:
            counters['errores'] += 1
            logger.exception('[%s] persistence.failed: %s', fuente, key)
            if lifecycle_run_id:
                with transaction.atomic():
                    run = lock_run(lifecycle_run_id, execution_token)
                    if key:
                        ScrapingCandidate.objects.update_or_create(run=run, source_id=key,
                            defaults={'status': 'error', 'error': str(exc)[:4000]})
            raise RuntimeError(f'persistence.failed: {fuente}/{key}: {exc}') from exc
    return run_counters(lifecycle_run_id) if lifecycle_run_id else counters


def limpiar_fuente(fuente):
    from ingestas.models import PropiedadesCompetencia
    count, _ = PropiedadesCompetencia.objects.filter(fuente=fuente).delete()
    return count
