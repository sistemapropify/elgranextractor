import io
import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from ingestas.ml_dataset_archive import (
    ARCHIVE_KEY, AzureDatasetStore, DatasetArchiveError, archive_candidates, archive_dataset,
    archive_old_datasets, archive_summary, iter_dataset_entries, restore_dataset,
)
from ingestas.ml_dataset_views import dataset_export
from ingestas.ml_training import _rows
from ingestas.models import (
    MLCandidate, MLDatasetEntry, MLDatasetSnapshot, MLObservation,
    MLTrainingRun, PropiedadesCompetencia,
)
from ingestas.tests.test_ml_candidates import valid


class MemoryBlobStore:
    container_name = 'private-test-archives'

    def __init__(self):
        self.blobs = {}

    def upload(self, key, stream, sha256):
        self.blobs.setdefault(key, stream.read())

    def download(self, key, stream):
        stream.write(self.blobs[key])


class AzureStoreTests(SimpleTestCase):
    def test_public_container_is_rejected(self):
        container = MagicMock()
        container.get_container_properties.return_value = {'public_access': 'blob'}
        client = MagicMock()
        client.get_container_client.return_value = container
        with patch('captura.azure_storage.get_blob_service_client', return_value=client):
            with self.assertRaises(DatasetArchiveError):
                AzureDatasetStore()
        container.create_container.assert_not_called()

    def test_missing_container_is_created_private(self):
        from azure.core.exceptions import ResourceNotFoundError
        container = MagicMock()
        container.get_container_properties.side_effect = [ResourceNotFoundError('missing'), {'public_access': None}]
        client = MagicMock()
        client.get_container_client.return_value = container
        with patch('captura.azure_storage.get_blob_service_client', return_value=client):
            AzureDatasetStore()
        container.create_container.assert_called_once_with(public_access=None)

    def test_sdk_upload_is_immutable_and_download_reads_entire_stream(self):
        container = MagicMock()
        container.get_container_properties.return_value = {'public_access': None}
        client = MagicMock()
        client.get_container_client.return_value = container
        with patch('captura.azure_storage.get_blob_service_client', return_value=client):
            store = AzureDatasetStore()
        stream = io.BytesIO(b'compressed-data')
        store.upload('dataset.gz', stream, 'f' * 64)
        kwargs = container.get_blob_client.return_value.upload_blob.call_args.kwargs
        self.assertFalse(kwargs['overwrite'])
        self.assertEqual(kwargs['metadata']['sha256'], 'f' * 64)
        store.download('dataset.gz', stream)
        container.get_blob_client.return_value.download_blob.return_value.readinto.assert_called_once_with(stream)


class DatasetArchiveTests(TestCase):
    def setUp(self):
        self.store = MemoryBlobStore()
        self.prop = PropiedadesCompetencia.objects.create(**valid())
        self.obs, _ = MLObservation.objects.get_or_create(
            propiedad=self.prop, sequence=1, defaults={
                'content_hash': 'a' * 64, 'rule_version': 'test',
                'snapshot': {'first_seen': '2026-01-01', 'descripcion': 'Información original'},
            })
        self.candidate, _ = MLCandidate.objects.get_or_create(propiedad=self.prop, defaults={'latest': self.obs})
        self.cuts = [self.cut() for _ in range(7)]
        self.old = self.cuts[0]
        self.original_entry = self.old.entries.get()

    def cut(self, included=True):
        dataset = MLDatasetSnapshot.objects.create(criteria_version='test', spatial_rule_version='test',
            identity_rule_version='test', input_hash='f' * 64, catalog_hash='a' * 64,
            total=1, included=int(included), coverage={'by_type': {'Casa': int(included)}})
        MLDatasetSnapshot.objects.filter(pk=dataset.pk).update(created_at=timezone.now() - timedelta(days=30))
        dataset.refresh_from_db()
        MLDatasetEntry.objects.create(dataset=dataset, candidate=self.candidate, observation=self.obs,
            included=included, reason='Oferta válida', reason_code='included.offer',
            identity_group_hash='group-a', target_price_usd=Decimal('300000.00'),
            features={'tipo_inmueble': 'Casa', 'tipo_operacion': 'Venta', 'fuente': 'remax',
                      'area_terreno': 200, 'area_construida': 240, 'url': 'https://example.test/anuncio',
                      'antiguedad_anios': 0, 'distrito': 'Cayma'})
        return dataset

    def archive(self, dataset=None):
        return archive_dataset((dataset or self.old).pk, store=self.store)

    def test_latest_five_and_every_training_status_are_protected(self):
        for status in ('queued', 'running', 'completed', 'failed'):
            with self.subTest(status=status):
                run = MLTrainingRun.objects.create(dataset=self.old, property_type='Casa',
                                                   algorithm='test', code_version='test', status=status)
                self.assertEqual(self.archive()['skipped'], 'retained_or_training')
                self.assertTrue(self.old.entries.exists())
                run.delete()
        for cut in self.cuts[-5:]:
            self.assertEqual(self.archive(cut)['skipped'], 'retained_or_training')
        self.assertFalse(self.store.blobs)

    def test_recent_age_protected_even_outside_latest_five(self):
        MLDatasetSnapshot.objects.filter(pk=self.old.pk).update(created_at=timezone.now())
        self.assertEqual(archive_dataset(self.old.pk, min_age_days=7, store=self.store)['skipped'], 'retained_or_training')
        self.assertFalse(self.store.blobs)

    def test_archive_keeps_metadata_and_observations_but_moves_entries(self):
        before_observations = MLObservation.objects.count()
        result = self.archive()
        self.assertEqual(result['archived_rows'], 1)
        self.old.refresh_from_db()
        self.assertEqual(self.old.total, 1)
        self.assertEqual(self.old.status, 'ready')
        self.assertEqual(self.old.coverage['by_type'], {'Casa': 1})
        self.assertEqual(MLObservation.objects.count(), before_observations)
        self.assertTrue(PropiedadesCompetencia.objects.filter(pk=self.prop.pk).exists())
        self.assertFalse(self.old.entries.exists())
        manifest = self.old.coverage[ARCHIVE_KEY]
        self.assertEqual(manifest['container'], self.store.container_name)
        self.assertEqual(len(manifest['sha256']), 64)
        self.assertEqual(manifest['entries'], 1)
        self.assertTrue(manifest['key'].endswith('.jsonl.gz'))

    def test_reads_stale_dataset_instance_from_archive_and_preserves_zero_age(self):
        before = list(iter_dataset_entries(self.old))[0]
        self.archive()
        after = list(iter_dataset_entries(self.old, store=self.store))[0]
        for field in MLDatasetEntry._meta.concrete_fields:
            self.assertEqual(getattr(before, field.attname), getattr(after, field.attname))
        self.assertEqual(after.features['antiguedad_anios'], 0)
        self.assertEqual(after.observation.sequence, self.obs.sequence)
        self.assertEqual(after.observation.snapshot, self.obs.snapshot)

    def test_restores_sql_rows_with_original_ids_and_keeps_blob_backup(self):
        self.archive()
        result = restore_dataset(self.old.pk, store=self.store)
        self.assertEqual(result['restored_rows'], 1)
        self.assertEqual(self.old.entries.get().pk, self.original_entry.pk)
        self.old.refresh_from_db()
        self.assertNotIn(ARCHIVE_KEY, self.old.coverage)
        self.assertEqual(len(self.store.blobs), 1)
        self.assertEqual(restore_dataset(self.old.pk)['skipped'], 'already_in_sql')

    def test_archive_retry_does_not_upload_or_remove_twice(self):
        self.archive()
        self.assertEqual(self.archive()['skipped'], 'already_archived')
        self.assertEqual(len(self.store.blobs), 1)

    def test_upload_failure_keeps_sql_and_no_manifest(self):
        with patch.object(self.store, 'upload', side_effect=OSError('upload unavailable')):
            with self.assertRaises(OSError):
                self.archive()
        self.assertTrue(self.old.entries.exists())
        self.old.refresh_from_db()
        self.assertNotIn(ARCHIVE_KEY, self.old.coverage)

    def test_download_failure_keeps_sql_and_retries_existing_blob(self):
        with patch.object(self.store, 'download', side_effect=OSError('download unavailable')):
            with self.assertRaises(OSError):
                self.archive()
        self.assertTrue(self.old.entries.exists())
        self.assertEqual(len(self.store.blobs), 1)
        self.assertEqual(self.archive()['archived_rows'], 1)
        self.assertEqual(len(self.store.blobs), 1)

    def test_corrupt_copy_never_deletes_sql_rows(self):
        with patch.object(self.store, 'download', side_effect=lambda key, out: out.write(b'corrupt')):
            with self.assertRaises(DatasetArchiveError):
                self.archive()
        self.assertTrue(self.old.entries.exists())
        self.old.refresh_from_db()
        self.assertNotIn(ARCHIVE_KEY, self.old.coverage)

    def test_manifest_save_failure_rolls_back_sql_deletion(self):
        with patch.object(MLDatasetSnapshot, 'save', side_effect=RuntimeError('db write failed')):
            with self.assertRaises(RuntimeError):
                self.archive()
        self.assertTrue(self.old.entries.exists())
        self.old.refresh_from_db()
        self.assertNotIn(ARCHIVE_KEY, self.old.coverage)
        self.assertEqual(self.archive()['archived_rows'], 1)

    def test_corrupt_archived_read_and_restore_raise_without_partial_sql(self):
        self.archive()
        key = next(iter(self.store.blobs))
        self.store.blobs[key] = self.store.blobs[key][:-5]
        with self.assertRaises(DatasetArchiveError):
            list(iter_dataset_entries(self.old, store=self.store))
        with self.assertRaises(DatasetArchiveError):
            restore_dataset(self.old.pk, store=self.store)
        self.assertFalse(self.old.entries.exists())

    def test_csv_download_identical_after_archiving_and_training_reader_works(self):
        request = RequestFactory().get('/export.csv')
        request.current_user = SimpleNamespace(is_authenticated=True, is_active=True)
        with patch('ingestas.ml_dataset_views.schema_ready', return_value=True):
            before = dataset_export(request, self.old.pk).content
            original_rows = _rows(self.old, 'Casa')
            self.archive()
            with patch('ingestas.ml_dataset_archive.AzureDatasetStore', return_value=self.store):
                after = dataset_export(request, self.old.pk).content
                archived_rows = _rows(self.old, 'Casa')
        self.assertEqual(before, after)
        self.assertEqual(original_rows, archived_rows)

    def test_excluded_records_preserved_in_archive(self):
        self.old.entries.update(included=False, target_price_usd=None, reason='Falta superficie')
        self.archive()
        self.assertEqual(len(list(iter_dataset_entries(self.old, included=False, store=self.store))), 1)
        self.assertEqual(list(iter_dataset_entries(self.old, included=True, store=self.store)), [])

    def test_csv_unavailable_blob_returns_503_instead_of_empty_download(self):
        self.archive()
        request = RequestFactory().get('/export.csv')
        request.current_user = SimpleNamespace(is_authenticated=True, is_active=True)
        with patch('ingestas.ml_dataset_views.schema_ready', return_value=True), \
                patch('ingestas.ml_dataset_archive.AzureDatasetStore', side_effect=OSError('offline')), \
                self.assertLogs('ingestas.ml_dataset_views', level='ERROR'):
            response = dataset_export(request, self.old.pk)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('Content-Disposition', response)

    def test_anonymous_csv_does_not_access_sql_or_blob(self):
        with patch('ingestas.ml_dataset_views.schema_ready') as ready:
            response = dataset_export(RequestFactory().get('/export.csv'), self.old.pk)
        self.assertEqual(response.status_code, 401)
        ready.assert_not_called()

    def test_command_dry_run_does_not_contact_azure_or_modify_sql(self):
        output = io.StringIO()
        with patch('ingestas.ml_dataset_archive.AzureDatasetStore') as azure:
            call_command('archive_ml_datasets', stdout=output)
        azure.assert_not_called()
        plan = json.loads(output.getvalue())
        self.assertTrue(plan['dry_run'])
        self.assertEqual(plan['eligible_datasets'], 2)
        self.assertEqual(plan['eligible_sql_rows'], 2)
        self.assertEqual(MLDatasetEntry.objects.count(), 7)

    def test_batch_limit_and_summary(self):
        result = archive_old_datasets(limit=1, store=self.store)
        self.assertEqual(len(result), 1)
        summary = archive_summary()
        self.assertEqual(summary['archived'], 1)
        self.assertEqual(summary['archived_rows'], 1)
        self.assertEqual(summary['pending'], 1)

    def test_invalid_policy_cannot_archive_current_or_previous_snapshot(self):
        for keep, age in ((0, 0), (1, 0), (5, -1)):
            with self.assertRaises(ValueError):
                archive_candidates(keep=keep, min_age_days=age)
        with self.assertRaises(ValueError):
            archive_old_datasets(limit=0)

    @override_settings(ML_DATASET_ARCHIVE_ENABLED=False)
    def test_disabled_maintenance_never_connects_blob(self):
        from ingestas.ml_dataset_archive import maybe_archive_datasets
        with patch('ingestas.ml_dataset_archive.AzureDatasetStore') as azure:
            self.assertEqual(maybe_archive_datasets(), [])
        azure.assert_not_called()

    @override_settings(ML_DATASET_ARCHIVE_ENABLED=True)
    def test_maintenance_failure_is_contained(self):
        from ingestas import ml_dataset_archive as module
        with patch.object(module, '_last_attempt', 0), patch.object(module, 'archive_old_datasets', side_effect=OSError('offline')), \
                self.assertLogs('ingestas.ml_dataset_archive', level='ERROR'):
            self.assertIn('archive_error', module.maybe_archive_datasets()[0])
            self.assertEqual(module.maybe_archive_datasets(), [])
