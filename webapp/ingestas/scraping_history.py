"""Evidence-backed corrections with a transactional journal and guarded rollback."""
import hashlib
import importlib
import json
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from scrapi.normalization import urbania_row
from .models import PropiedadesCompetencia, ScrapingHistoryRepair

FIELDS = ('precio_soles', 'precio_usd', 'area_m2', 'tipo_inmueble', 'tipo_operacion')
PORTALS = ('urbania', 'remax', 'properati', 'adondevivir', 'facebook_marketplace')


def raw_hash(raw):
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()


def json_value(value):
    return float(value) if isinstance(value, Decimal) else value


def propose(prop):
    raw = prop.datos_crudos or {}
    portal = prop.fuente.lower()
    if not isinstance(raw, dict) or str(raw.get('ID') or raw.get('id') or '') != str(prop.id_origen):
        return None
    if portal == 'urbania':
        row = urbania_row(raw, str(prop.fecha_extraccion))
    elif portal == 'facebook_marketplace':
        from scrapi.facebook_marketplace_scraper import standardize
        row = standardize(raw, str(prop.fecha_extraccion))
    elif portal in PORTALS:
        from scrapi.paged_engine import normalize
        row = normalize(portal, importlib.import_module(f'scrapi.{portal}_scraper'), dict(raw))
    else:
        return None
    changes = {}
    for field in FIELDS:
        old, new = json_value(getattr(prop, field)), row.get(field)
        if new is not None and field in ('precio_soles', 'precio_usd', 'area_m2'):
            model_field = PropiedadesCompetencia._meta.get_field(field)
            decimal_value = Decimal(str(new)).quantize(Decimal('0.01'))
            model_field.run_validators(decimal_value)
            new = float(decimal_value)
        # Unknown values and missing evidence never clear or invent historical data.
        if new is not None and old != new:
            changes[field] = {'before': old, 'after': new}
    if not changes:
        return None
    return {'id': prop.pk, 'id_origen': prop.id_origen, 'source': prop.fuente,
            'normalizer_version': '2', 'changes': changes, 'raw_sha256': raw_hash(raw)}


@transaction.atomic
def apply_plan(proposals, *, apply=False):
    """All-or-nothing; recompute evidence so editing a plan cannot inject values."""
    proposals = list(proposals)
    ids = [p['id'] for p in proposals]
    if len(ids) != len(set(ids)):
        raise ValueError('El plan repite una propiedad.')
    locked = {p.pk: p for p in PropiedadesCompetencia.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
    validated = []
    for proposal in proposals:
        prop = locked.get(proposal['id'])
        current = propose(prop) if prop else None
        if current != proposal:
            raise ValueError(f'Propiedad {proposal["id"]}: datos o evidencia cambiaron; regenerar el plan.')
        validated.append((prop, proposal))
    batch = uuid.uuid4()
    if apply:
        for prop, proposal in validated:
            # Journal and property update commit together; failure rolls back both.
            ScrapingHistoryRepair.objects.create(batch=batch, propiedad=prop,
                source=prop.fuente, source_id=prop.id_origen,
                changes=proposal['changes'], raw_sha256=proposal['raw_sha256'])
            updates = {field: change['after'] for field, change in proposal['changes'].items()}
            PropiedadesCompetencia.objects.filter(pk=prop.pk).update(**updates)
    return {'count': len(validated), 'batch': str(batch) if apply and validated else None, 'applied': apply}


@transaction.atomic
def rollback_batch(batch, *, apply=False):
    # Lock properties first, in the same order as apply, to avoid lock inversion.
    ids = list(ScrapingHistoryRepair.objects.filter(batch=batch).values_list('propiedad_id', flat=True))
    if not ids:
        raise ValueError('Lote de reparación inexistente.')
    props = {p.pk: p for p in PropiedadesCompetencia.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
    entries = list(ScrapingHistoryRepair.objects.select_for_update().filter(batch=batch, rolled_back_at__isnull=True).order_by('propiedad_id'))
    for entry in entries:
        prop = props[entry.propiedad_id]
        if (prop.fuente != entry.source or prop.id_origen != entry.source_id
                or raw_hash(prop.datos_crudos or {}) != entry.raw_sha256
                or any(json_value(getattr(prop, k)) != v['after'] for k, v in entry.changes.items())):
            raise ValueError(f'Propiedad {prop.pk}: actualizada después de la reparación; no se sobrescribirá.')
    if apply:
        for entry in entries:
            PropiedadesCompetencia.objects.filter(pk=entry.propiedad_id).update(
                **{k: v['before'] for k, v in entry.changes.items()})
            entry.rolled_back_at = timezone.now()
            entry.save(update_fields=['rolled_back_at'])
    return {'count': len(entries), 'batch': str(batch), 'applied': apply}
