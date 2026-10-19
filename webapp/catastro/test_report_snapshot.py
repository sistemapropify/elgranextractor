import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from django.core.cache import cache
from catastro import map_report, report_snapshot
from catastro.storage import StorageError
from catastro.test_map_report import LOT, RECORD, pages

PDF = b'%PDF-test-original'
URL = 'https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistapdf/reporte.php?id='


def document(record=RECORD):
    return {'type': 'cadastral_report_pdf', 'record_id': record,
            'form_number': '1/1', 'source_url': URL + record}


class Cloud:
    def __init__(self):
        self.objects = {}
        self.puts = []

    def _put_verified(self, key, body, content_type):
        self.objects[key] = body
        self.puts.append(key)

    def get(self, key):
        if key not in self.objects:
            raise StorageError('R2 respondió HTTP 404.')
        return self.objects[key], {}


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        cache.clear()
        self.local = self.enterContext(TemporaryDirectory())
        self.remote = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.dict(os.environ, {'CATASTRO_DATA_DIR': self.local}))
        self.cloud = Cloud()
        self.enterContext(patch('catastro.report_snapshot.R2', return_value=self.cloud))
        self.enterContext(patch('scrapi.geollaqta_scraper.pdf_pages', return_value=pages()))

    def mirror(self, record=RECORD, documents=None):
        report_snapshot.save(LOT, document(record), documents or [document(record)], PDF)

    def test_live_success_can_be_read_on_another_server_without_cofopri(self):
        with patch('catastro.map_report.download', return_value=PDF), patch('catastro.map_report.pdf_pages', return_value=pages()):
            original = map_report.report_measurements(LOT, reports=[document()], report_only=True)
        self.assertEqual(len(self.cloud.puts), 3)
        self.assertTrue(self.cloud.puts[-1].endswith('index.json'))
        cache.clear()
        with patch.dict(os.environ, {'CATASTRO_DATA_DIR': self.remote}), patch('catastro.map_report._archived_reports', return_value=None), patch('catastro.map_report.download', side_effect=AssertionError('source offline')):
            restored = map_report.report_measurements(LOT, report_only=True)
        self.assertEqual(restored['metrics'], original['metrics'])
        self.assertNotIn('87654321', json.dumps(restored))
        self.assertFalse((Path(self.local) / 'estado.sqlite3').exists())

    def test_different_unit_reports_stay_separate(self):
        second = RECORD[:-1] + '3'
        documents = [document(), document(second)]
        self.mirror(documents=documents)
        with patch.dict(os.environ, {'CATASTRO_DATA_DIR': self.remote}):
            self.assertIsNone(report_snapshot.read(LOT, second))
            self.assertIsNone(report_snapshot.read(LOT, RECORD[:-1] + '9'))
        self.mirror(second, documents)
        with patch.dict(os.environ, {'CATASTRO_DATA_DIR': self.remote}):
            reports = report_snapshot.read(LOT, second)
        self.assertEqual(len(reports), 2)
        self.assertNotIn('pages', reports[0])
        self.assertIn('pages', reports[1])

    def test_storage_failure_preserves_success_and_next_read_retries_mirror(self):
        with patch.object(self.cloud, '_put_verified', side_effect=StorageError('offline')) as put:
            with patch('catastro.map_report.download', return_value=PDF), patch('catastro.map_report.pdf_pages', return_value=pages()):
                value = map_report.report_measurements(LOT, reports=[document()], report_only=True)
            put.assert_called_once()
        self.assertEqual(value['metrics']['land_area'], '200')
        self.assertEqual(self.cloud.objects, {})
        self.assertIsNotNone(report_snapshot.read(LOT))
        self.assertEqual(len(self.cloud.objects), 3)

    def test_hash_mismatch_and_wrong_lot_are_rejected(self):
        self.mirror()
        pdf_key = next(key for key in self.cloud.objects if key.endswith('.pdf'))
        with patch.dict(os.environ, {'CATASTRO_DATA_DIR': self.remote}):
            self.cloud.objects[pdf_key] = PDF + b'changed'
            self.assertIsNone(report_snapshot.read(LOT))
            self.cloud.objects[pdf_key] = PDF
            wrong = pages()
            wrong[0]['named_fields'][2]['value'] = '999'
            with patch('scrapi.geollaqta_scraper.pdf_pages', return_value=wrong):
                self.assertIsNone(report_snapshot.read(LOT))

    def test_index_is_not_published_if_original_upload_fails(self):
        with patch.object(self.cloud, '_put_verified', side_effect=StorageError('offline')):
            self.mirror()
        self.assertEqual(self.cloud.objects, {})
        self.assertFalse(list(Path(self.local).rglob('*.shared')))

    def test_changed_gallery_retries_if_previous_pdf_was_already_shared(self):
        self.mirror()
        second = RECORD[:-1] + '3'
        with patch.object(self.cloud, '_put_verified', side_effect=StorageError('offline')):
            self.mirror(documents=[document(), document(second)])
        report_snapshot.read(LOT)
        index = json.loads(self.cloud.objects[report_snapshot._prefix(LOT) + 'index.json'])
        self.assertEqual(len(index['reports']), 2)

    def test_archive_reader_does_not_open_the_collectors_sqlite_ledger(self):
        root = Path(self.local) / LOT[:6] / LOT
        root.mkdir(parents=True)
        (root / 'datos.json').write_text(json.dumps({'lot_id':LOT, 'district_ubigeo':LOT[:6],
            'extraction_revision':2, 'reports':[{'type':'cadastral_report_pdf','record_id':RECORD,'pages':pages()}]}))
        with patch('catastro.state.State', side_effect=AssertionError('ledger unavailable')):
            self.assertIsNotNone(map_report._archived_reports(LOT))
        self.assertFalse((Path(self.local) / 'estado.sqlite3').exists())

    def test_unknown_schema_untrusted_source_and_invalid_metadata_are_ignored(self):
        self.mirror()
        prefix = report_snapshot._prefix(LOT)
        for bad in ([], {'schema':1,'lot_id':LOT,'reports':None}, {'schema':99,'lot_id':LOT},
                    {'schema':1,'lot_id':LOT,'reports':[{**document(),'source_url':'https://evil.test/pdf'}]}):
            self.cloud.objects[prefix + 'index.json'] = json.dumps(bad).encode()
            with patch.dict(os.environ, {'CATASTRO_DATA_DIR': self.remote}):
                self.assertIsNone(report_snapshot.read(LOT))

    def test_pdf_copies_are_immutable_and_do_not_replace_full_collector_manifest(self):
        self.mirror()
        digest = hashlib.sha256(PDF).hexdigest()
        self.assertTrue(any(digest in key for key in self.cloud.objects))
        self.assertFalse(any(key.endswith('/datos.json') for key in self.cloud.objects))
        self.assertTrue(all('/map-reports/' in key for key in self.cloud.objects))

    def test_individual_forms_do_not_enter_report_snapshot(self):
        with patch('catastro.map_report.download', return_value=PDF), patch('catastro.map_report.pdf_pages', return_value=pages()):
            individual = {**document(), 'type':'individual_record_pdf',
                          'source_url':URL.replace('reporte.php', 'fichain.php') + RECORD}
            map_report.report_measurements(LOT, reports=[individual])
        self.assertEqual(self.cloud.objects, {})
