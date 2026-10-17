import collections
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from catastro.parallel import Coordinator, RequestGate, worker_count
from catastro.state import State
from catastro.storage import StorageError
from catastro.test_collector import FakeR2, pdf
from scrapi.geollaqta_scraper import collect, CollectionError, Source, Stopped


class DistrictSource:
    def __init__(self, count=25, barrier=None, delay=.005):
        self.count, self.barrier, self.delay = count, barrier, delay
        self.body = pdf()
        self.active = self.maximum = 0
        self.galleries = collections.Counter()
        self.lock = threading.Lock()
        self.denied = None

    @staticmethod
    def code(number):
        return '040117' + str(number).zfill(8)

    def query(self, **params):
        if params.get('returnIdsOnly'):
            return {'objectIds': list(range(1, self.count + 1))}
        return {'features': [{'attributes': {'OBJECTID': n, 'ID_DIST': '040117', 'ID_LOTE': self.code(n)},
                              'geometry': {'rings': []}}
                             for n in map(int, params['objectIds'].split(','))]}

    def get(self, url, **kwargs):
        gallery = 'vistadetalle' in url
        number = int(parse_qs(urlsplit(url).query)['id_lote'][0][6:]) if gallery else None
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            if gallery:
                self.galleries[number] += 1
        try:
            if gallery and self.barrier and number <= self.barrier.parties:
                self.barrier.wait(timeout=10)
            time.sleep(self.delay)
            if gallery:
                if number == self.denied:
                    raise CollectionError('COFOPRI rechazó la descarga; ejecución detenida.', 403)
                record = '040117201301' + str(number).zfill(7)
                return ('<table><tr><td>1</td><td>1/1</td><td><a href="vistapdf/reporte.php?id=' +
                        record + '">Reporte</a></td></tr></table><img src="https://catastro.cofopri.gob.pe/' +
                        'img_catastro/040117/' + str(number) + '.jpg">').encode()
            return b'\xff\xd8\xffphoto' if url.endswith('.jpg') else self.body
        finally:
            with self.lock:
                self.active -= 1


class ParallelCollectorTests(unittest.TestCase):
    def test_ten_lots_overlap_but_pdf_ledger_and_callbacks_stay_on_coordinator(self):
        owner = threading.get_ident()
        source = DistrictSource(23, threading.Barrier(10))
        cloud = FakeR2()
        parse_threads, control_threads = [], []
        from scrapi.geollaqta_scraper import pdf_pages
        def parse(body):
            parse_threads.append(threading.get_ident())
            return pdf_pages(body)
        def checkpoint():
            control_threads.append(threading.get_ident())
        with tempfile.TemporaryDirectory() as tmp, patch('scrapi.geollaqta_scraper.pdf_pages', side_effect=parse):
            result = collect('040117', root=tmp, source=source, r2=cloud, workers=10,
                             checkpoint=checkpoint, progress=lambda data: checkpoint())
            self.assertTrue(result['complete'])
            self.assertEqual((result['processed'], result['uploaded'], result['remaining_objects']), (23, 23, 0))
            self.assertEqual(source.maximum, 10)
            state = State(tmp)
            self.assertEqual(state.snapshot()['totals']['uploaded'], 23)
            for key, digest, size in state.db.execute('SELECT * FROM uploads'):
                body = cloud.objects[key][0]
                self.assertEqual((hashlib.sha256(body).hexdigest(), len(body)), (digest, size))
            state.close()
        self.assertEqual(set(parse_threads), {owner})
        self.assertEqual(len(parse_threads), 23)
        self.assertEqual(set(control_threads), {owner})

    def test_pause_resume_skips_every_completed_lot_even_when_completion_is_out_of_order(self):
        source, cloud = DistrictSource(24, delay=.015), FakeR2()
        def progress(data):
            if data['processed'] >= 3:
                raise Stopped('pause requested')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Stopped):
                collect('040117', root=tmp, source=source, r2=cloud, workers=10, progress=progress)
            state = State(tmp)
            completed = {row['object_id'] for row in state.db.execute('SELECT * FROM lots WHERE uploaded=1')}
            state.close()
            self.assertGreaterEqual(len(completed), 3)
            self.assertLess(len(completed), 24)
            before = source.galleries.copy()
            resumed = collect('040117', root=tmp, source=source, r2=cloud, workers=4)
            self.assertTrue(resumed['complete'])
            self.assertEqual(resumed['skipped'], len(completed))
            for number in completed:
                self.assertEqual(source.galleries[number], before[number])

    def test_access_denied_stops_scheduling_and_retains_truthful_inventory(self):
        source, cloud = DistrictSource(50, delay=.01), FakeR2()
        source.denied = 1
        with tempfile.TemporaryDirectory() as tmp:
            result = collect('040117', root=tmp, source=source, r2=cloud, workers=4)
            self.assertFalse(result['complete'])
            self.assertGreater(result['failed'], 0)
            self.assertEqual(result['stop_reason'], 'source_or_storage_error')
            self.assertLess(len(source.galleries), 50)
            state = State(tmp)
            totals = state.snapshot()['totals']
            self.assertEqual(result['uploaded'], totals['uploaded'])
            self.assertEqual(result['remaining_objects'], 50 - totals['uploaded'])
            state.close()

    def test_upload_failure_is_retryable_and_new_files_are_not_deleted(self):
        source = DistrictSource(6)
        class BrokenCloud(FakeR2):
            broken = True
            def put_verified(self, key, body, mime):
                if self.broken and '/'+source.code(1)+'/' in key:
                    raise StorageError('R2 no disponible.')
                return super().put_verified(key, body, mime)
        cloud = BrokenCloud()
        with tempfile.TemporaryDirectory() as tmp:
            result = collect('040117', root=tmp, source=source, r2=cloud, workers=4, keep_local=False)
            self.assertFalse(result['complete'])
            self.assertTrue((Path(tmp)/'040117'/source.code(1)/'datos.json').exists())
            state = State(tmp)
            self.assertEqual(state.lot(source.code(1))['uploaded'], 0)
            state.close()
            before = source.galleries[1]
            cloud.broken = False
            result = collect('040117', root=tmp, source=source, r2=cloud, workers=4, keep_local=False)
            self.assertTrue(result['complete'])
            self.assertEqual(source.galleries[1], before)

    def test_legacy_byte_budget_remains_exact_and_sequential(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = collect('040117', root=tmp, source=DistrictSource(3), r2=FakeR2(),
                             workers=10, budget=100)
            self.assertEqual(result['workers'], 1)
            self.assertFalse(result['complete'])

    def test_invalid_worker_counts_are_rejected_before_opening_a_ledger(self):
        for value in (0, 11, -1, True, 2.5, 'bad'):
            with self.subTest(value=value), patch('scrapi.geollaqta_scraper.State') as state:
                with self.assertRaises(ValueError):
                    collect('040117', workers=value)
                state.assert_not_called()


class ParallelControlTests(unittest.TestCase):
    def test_global_spacing_and_shared_cooldown(self):
        now = [100.]
        gate = RequestGate(clock=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0]+seconds))
        gate.wait(lambda: None)
        gate.wait(lambda: None)
        self.assertAlmostEqual(now[0], 101.)
        gate.defer(8)
        gate.wait(lambda: None)
        self.assertAlmostEqual(now[0], 109.)

    @patch('scrapi.geollaqta_scraper.time.sleep')
    def test_retry_after_on_429_pauses_the_shared_gate(self, sleep):
        gate = Mock()
        source = Source(gate=gate)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'gallery'
        source.opener.open = Mock(side_effect=[HTTPError('https://catastro.cofopri.gob.pe/', 429,
                                                        'busy', {'Retry-After':'7'}, None), response])
        self.assertEqual(source.get('https://catastro.cofopri.gob.pe/'), b'gallery')
        gate.defer.assert_called_once_with(7.)
        self.assertEqual(gate.wait.call_count, 2)

    def test_coordinator_propagates_actual_timeouts_instead_of_waiting_forever(self):
        coordinator = Coordinator(lambda: None)
        def timeout():
            raise TimeoutError('actual timeout')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(coordinator.call, timeout)
            while not future.done():
                coordinator.service(timeout=.01)
            with self.assertRaises(TimeoutError):
                future.result()

    def test_existing_jobs_upgrade_to_one_worker_and_new_jobs_remember_requested_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = State(tmp)
            old = state.create_job('040117', 0, workers=1)
            state.close()
            con = sqlite3.connect(str(Path(tmp)/'estado.sqlite3'))
            con.execute('ALTER TABLE jobs DROP COLUMN workers');con.commit();con.close()
            state = State(tmp)
            self.assertEqual(state.job(old)['workers'], 1)
            state.update_job(old, status='stopped')
            new = state.create_job('040117', 0, workers=10)
            self.assertEqual(state.job(new)['workers'], 10)
            state.close()
        with patch.dict(os.environ, {'CATASTRO_MAX_WORKERS':'4'}):
            self.assertEqual(worker_count(), 4)
