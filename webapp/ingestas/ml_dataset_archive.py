"""Verified, private Blob archives for immutable ML cuts, not business history.

Snapshot metadata stays in SQL. Its existing coverage JSON holds the manifest,
so archiving also works when the database has no room for a schema migration.
"""
import gzip
import hashlib
import json
import logging
import tempfile
import time
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)
ARCHIVE_KEY = '_blob_archive'
FORMAT = 'ml-dataset-jsonl-v1'
_last_attempt = 0


class DatasetArchiveError(Exception):
    pass


class AzureDatasetStore:
    """Uses the existing Azure account and a separate, strictly private container."""
    def __init__(self, container=None):
        from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
        from captura.azure_storage import get_blob_service_client
        self.container_name = container or getattr(settings, 'ML_DATASET_ARCHIVE_CONTAINER', 'ml-dataset-archives')
        self.container = get_blob_service_client().get_container_client(self.container_name)
        try:
            properties = self.container.get_container_properties()
        except ResourceNotFoundError:
            try:
                self.container.create_container(public_access=None)
            except ResourceExistsError:
                pass
            properties = self.container.get_container_properties()
        if properties.get('public_access'):
            raise DatasetArchiveError('El contenedor de datasets debe ser privado.')

    def upload(self, key, stream, sha256):
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import ContentSettings
        blob = self.container.get_blob_client(key)
        try:
            blob.upload_blob(stream, overwrite=False, metadata={'sha256': sha256, 'format': FORMAT},
                             content_settings=ContentSettings(content_type='application/gzip'),
                             timeout=60, retry_total=2)
        except ResourceExistsError:
            # A retry after a rolled-back SQL transaction may find its copy.
            # The caller always downloads and verifies it before deleting SQL.
            pass

    def download(self, key, stream):
        self.container.get_blob_client(key).download_blob(timeout=60, retry_total=2).readinto(stream)


def _policy(keep, min_age_days):
    if keep < 2 or min_age_days < 0:
        raise ValueError('Conserva al menos dos cortes y usa una edad no negativa.')


def archive_candidates(keep=5, min_age_days=0):
    from .models import MLDatasetSnapshot, MLTrainingRun
    _policy(keep, min_age_days)
    retained = list(MLDatasetSnapshot.objects.order_by('-pk').values_list('pk', flat=True)[:keep])
    # Keep every experiment's input, including queued/running and rollback models.
    protected = MLTrainingRun.objects.values('dataset_id')
    return MLDatasetSnapshot.objects.exclude(pk__in=retained).exclude(pk__in=protected).filter(
        created_at__lte=timezone.now() - timedelta(days=min_age_days)).order_by('pk')


def _json_line(value):
    return (json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False,
                       sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def _digest(stream):
    stream.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
    stream.seek(0)
    return digest.hexdigest()


def _write_archive(dataset, stream):
    from .models import MLDatasetEntry
    snapshot = {field.attname: getattr(dataset, field.attname) for field in dataset._meta.concrete_fields}
    snapshot['coverage'] = {key: value for key, value in (dataset.coverage or {}).items() if key != ARCHIVE_KEY}
    count = 0
    with gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as compressed:
        compressed.write(_json_line({'format': FORMAT, 'snapshot': snapshot}))
        entries = MLDatasetEntry.objects.filter(dataset=dataset).select_related(
            'observation', 'spatial_assessment').order_by('candidate_id')
        for entry in entries.iterator(chunk_size=200):
            row = {field.attname: getattr(entry, field.attname) for field in entry._meta.concrete_fields}
            row['_observation'] = {'sequence': entry.observation.sequence,
                                   'snapshot': entry.observation.snapshot,
                                   'created_at': entry.observation.created_at.isoformat()}
            row['_spatial_rule'] = entry.spatial_assessment.rule_version if entry.spatial_assessment_id else ''
            compressed.write(_json_line(row))
            count += 1
    size = stream.tell()
    return count, size, _digest(stream)


def _read_archive(stream, dataset, count):
    stream.seek(0)
    with gzip.GzipFile(fileobj=stream, mode='rb') as compressed:
        header = json.loads(compressed.readline())
        snapshot = header.get('snapshot', {})
        if (header.get('format') != FORMAT or snapshot.get('id') != dataset.pk
                or snapshot.get('input_hash') != dataset.input_hash):
            raise DatasetArchiveError('La copia no corresponde al dataset solicitado.')
        seen = 0
        last_candidate = None
        for line in compressed:
            row = json.loads(line)
            candidate = row.get('candidate_id')
            if (row.get('dataset_id') != dataset.pk or not isinstance(candidate, int)
                    or (last_candidate is not None and candidate <= last_candidate)):
                raise DatasetArchiveError('La copia contiene registros inválidos o repetidos.')
            last_candidate = candidate
            seen += 1
            yield row
        if seen != count:
            raise DatasetArchiveError('La cantidad de registros recuperados no coincide.')


def archive_dataset(dataset_id, keep=5, min_age_days=0, store=None):
    from .models import MLDatasetSnapshot, MLDatasetEntry, MLPipelineState
    _policy(keep, min_age_days)
    # Same lock as freeze_dataset: no new cut or concurrent archive can alter
    # which versions are retained while this one is being verified.
    with transaction.atomic():
        MLPipelineState.objects.get_or_create(key='datasets')
        MLPipelineState.objects.select_for_update().get(pk='datasets')
        dataset = MLDatasetSnapshot.objects.select_for_update().get(pk=dataset_id)
        if (dataset.coverage or {}).get(ARCHIVE_KEY):
            return {'dataset_id': dataset_id, 'skipped': 'already_archived'}
        if not archive_candidates(keep, min_age_days).filter(pk=dataset_id).exists():
            return {'dataset_id': dataset_id, 'skipped': 'retained_or_training'}
        store = store or AzureDatasetStore()
        with tempfile.TemporaryFile() as original, tempfile.TemporaryFile() as recovered:
            count, size, sha256 = _write_archive(dataset, original)
            key = 'datasets/%d/%s.jsonl.gz' % (dataset_id, sha256)
            store.upload(key, original, sha256)
            store.download(key, recovered)
            if _digest(recovered) != sha256:
                raise DatasetArchiveError('La copia descargada no coincide; se conservan las filas SQL.')
            # Fully decompress and parse before removing even one row.
            for _ in _read_archive(recovered, dataset, count):
                pass
            removed, _ = MLDatasetEntry.objects.filter(dataset=dataset).delete()
            if removed != count:
                raise DatasetArchiveError('Cambió el dataset durante el archivado; se revierte SQL.')
            coverage = dict(dataset.coverage or {})
            coverage[ARCHIVE_KEY] = {'format': FORMAT, 'container': store.container_name,
                                    'key': key, 'sha256': sha256, 'entries': count,
                                    'compressed_bytes': size, 'verified_at': timezone.now().isoformat()}
            dataset.coverage = coverage
            dataset.save(update_fields=['coverage'])
    logger.info('ml.dataset.archived dataset=%s rows=%s bytes=%s', dataset_id, count, size)
    return {'dataset_id': dataset_id, 'archived_rows': count, 'compressed_bytes': size}


def iter_dataset_entries(dataset, included=None, store=None):
    """Read SQL or an integrity-checked archive without silently returning zero rows."""
    from .models import MLDatasetSnapshot, MLDatasetEntry
    # Callers may hold a model loaded before an archive committed.
    dataset = MLDatasetSnapshot.objects.get(pk=dataset.pk)
    manifest = (dataset.coverage or {}).get(ARCHIVE_KEY)
    if not manifest:
        query = MLDatasetEntry.objects.filter(dataset=dataset)
        if included is not None:
            query = query.filter(included=included)
        found = False
        for entry in query.select_related('observation', 'spatial_assessment').order_by('candidate_id').iterator(chunk_size=200):
            found = True
            yield entry
        if found:
            return
        # An archive may have committed between the metadata read and SELECT.
        dataset.refresh_from_db(fields=['coverage'])
        manifest = (dataset.coverage or {}).get(ARCHIVE_KEY)
        if not manifest:
            return
    store = store or AzureDatasetStore(manifest['container'])
    with tempfile.TemporaryFile() as recovered:
        store.download(manifest['key'], recovered)
        if _digest(recovered) != manifest['sha256']:
            raise DatasetArchiveError('El archivo del dataset no supera la verificación de integridad.')
        # Validate the whole archive first, including its final count/CRC.
        for _ in _read_archive(recovered, dataset, manifest['entries']):
            pass
        for row in _read_archive(recovered, dataset, manifest['entries']):
            if included is not None and row['included'] != included:
                continue
            observation = row.pop('_observation')
            observation['created_at'] = timezone.datetime.fromisoformat(observation['created_at'])
            row['observation'] = SimpleNamespace(**observation)
            row['spatial_assessment'] = SimpleNamespace(rule_version=row.pop('_spatial_rule'))
            row['pk'] = row['id']
            row['target_price_usd'] = Decimal(row['target_price_usd']) if row['target_price_usd'] is not None else None
            yield SimpleNamespace(**row)


def restore_dataset(dataset_id, store=None):
    from .models import MLDatasetSnapshot, MLDatasetEntry, MLPipelineState
    with transaction.atomic():
        MLPipelineState.objects.get_or_create(key='datasets')
        MLPipelineState.objects.select_for_update().get(pk='datasets')
        dataset = MLDatasetSnapshot.objects.select_for_update().get(pk=dataset_id)
        manifest = (dataset.coverage or {}).get(ARCHIVE_KEY)
        if not manifest:
            return {'dataset_id': dataset_id, 'skipped': 'already_in_sql'}
        if MLDatasetEntry.objects.filter(dataset=dataset).exists():
            raise DatasetArchiveError('El dataset archivado tiene filas SQL; no se sobrescriben.')
        fields = [field.attname for field in MLDatasetEntry._meta.concrete_fields]
        batch, restored = [], 0
        for entry in iter_dataset_entries(dataset, store=store):
            batch.append(MLDatasetEntry(**{field: getattr(entry, field) for field in fields}))
            restored += 1
            if len(batch) == 100:
                MLDatasetEntry.objects.bulk_create(batch, batch_size=100)
                batch = []
        if batch:
            MLDatasetEntry.objects.bulk_create(batch, batch_size=100)
        if restored != manifest['entries']:
            raise DatasetArchiveError('Restauración incompleta; se revierte SQL.')
        dataset.coverage = {key: value for key, value in dataset.coverage.items() if key != ARCHIVE_KEY}
        dataset.save(update_fields=['coverage'])
    return {'dataset_id': dataset_id, 'restored_rows': restored}


def archive_old_datasets(keep=5, min_age_days=0, limit=10, store=None):
    if limit < 1:
        raise ValueError('El límite debe ser positivo.')
    results = []
    for dataset in archive_candidates(keep, min_age_days).iterator(chunk_size=50):
        if (dataset.coverage or {}).get(ARCHIVE_KEY):
            continue
        results.append(archive_dataset(dataset.pk, keep, min_age_days, store=store))
        if len(results) >= limit:
            break
    return results


def archive_summary():
    from .models import MLDatasetSnapshot
    keep = getattr(settings, 'ML_DATASET_KEEP_RECENT', 5)
    min_age = getattr(settings, 'ML_DATASET_ARCHIVE_MIN_AGE_DAYS', 0)
    pending = {cut.pk for cut in archive_candidates(keep, min_age)
               if not (cut.coverage or {}).get(ARCHIVE_KEY)}
    archived = [(coverage or {}).get(ARCHIVE_KEY) for coverage in
                MLDatasetSnapshot.objects.values_list('coverage', flat=True)]
    archived = [manifest for manifest in archived if manifest]
    return {'enabled': getattr(settings, 'ML_DATASET_ARCHIVE_ENABLED', False),
            'keep': keep, 'min_age_days': min_age, 'pending': len(pending),
            'archived': len(archived), 'archived_rows': sum(item['entries'] for item in archived),
            'compressed_bytes': sum(item['compressed_bytes'] for item in archived)}


def maybe_archive_datasets():
    """Bounded hourly maintenance; Blob outages do not stop the scraper pipeline."""
    global _last_attempt
    if not getattr(settings, 'ML_DATASET_ARCHIVE_ENABLED', False):
        return []
    now = time.monotonic()
    if _last_attempt and now - _last_attempt < 3600:
        return []
    _last_attempt = now
    try:
        return archive_old_datasets(keep=getattr(settings, 'ML_DATASET_KEEP_RECENT', 5),
                                    min_age_days=getattr(settings, 'ML_DATASET_ARCHIVE_MIN_AGE_DAYS', 0),
                                    limit=10)
    except Exception:
        logger.exception('ml.dataset.archive_failed; filas SQL conservadas para el corte fallido')
        return [{'archive_error': 'No se pudo verificar el archivo; se conserva el corte fallido en SQL.'}]
