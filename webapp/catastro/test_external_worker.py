import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from django.test import SimpleTestCase, Client
from catastro.external_worker import Control, run_once, ControlError
from catastro.jobs import start_job
from catastro.state import State
from catastro.test_collector import FakeSource, FakeR2, LOT
from scrapi.geollaqta_scraper import Stopped

TOKEN = 'private-test-worker-token-with-at-least-32-characters'


class ExternalWorkerTests(SimpleTestCase):
    def setUp(self):
        self.render_patch = patch('django.template.base.Template._render',lambda template,context:template.nodelist.render(context))
        self.render_patch.start()
        self.server = tempfile.TemporaryDirectory()
        self.worker = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ,{'CATASTRO_DATA_DIR':self.server.name,'CATASTRO_EXECUTION_MODE':'external','CATASTRO_WORKER_TOKEN':TOKEN})
        self.environment.start()
        self.client = Client(enforce_csrf_checks=True)

    def tearDown(self):
        self.render_patch.stop()
        self.environment.stop()
        self.server.cleanup();self.worker.cleanup()

    def post(self, path, data=None, token=TOKEN, lease=''):
        return self.client.post('/catastro/api/worker/'+path+'/',data=json.dumps(data or {}),content_type='application/json',HTTP_AUTHORIZATION='Bearer '+token,HTTP_X_CATASTRO_LEASE=lease)

    def queued(self):
        state=State();job=state.create_job('040117',0,executor='external');state.close();return job

    def control(self):
        case=self
        class TestControl:
            def call(self, action,payload=None,job=None,lease=None):
                response=case.post('claim' if job is None else job+'/'+action,payload,lease=lease or '')
                if response.status_code==409:raise Stopped('lease lost')
                if response.status_code!=200:raise ControlError('control error '+str(response.status_code))
                return response.json()
        return TestControl()

    def test_private_token_required_and_browser_csrf_exemption_is_scoped(self):
        self.assertEqual(self.post('claim',token='wrong').status_code,403)
        self.assertEqual(self.client.get('/catastro/api/worker/claim/').status_code,405)
        with patch.dict(os.environ,{'CATASTRO_EXECUTION_MODE':'server'}):
            self.assertEqual(self.post('claim').status_code,403)
        self.assertEqual(self.post('claim').status_code,200)
        self.assertEqual(self.client.post('/catastro/api/start/',data='{}',content_type='application/json').status_code,403)

    def test_external_start_waits_without_launching_server_process_and_keeps_queue(self):
        with patch('catastro.jobs.credentials'),patch('catastro.jobs.subprocess.Popen') as spawn:
            job=start_job('040102')
            spawn.assert_not_called()
        state=State();state.db.execute('UPDATE jobs SET heartbeat=0 WHERE id=?',(job,));state.db.commit()
        self.assertEqual(state.snapshot()['jobs'][0]['status'],'queued')
        with self.assertRaises(ValueError):state.create_job('040126',0)
        state.close()

    def test_one_claim_and_lease_protection_and_no_secret_in_status(self):
        job=self.queued();claim=self.post('claim').json()
        self.assertEqual(claim['job']['id'],job)
        self.assertEqual(claim['job']['workers'],10)
        self.assertIsNone(self.post('claim').json()['job'])
        self.assertEqual(self.post(job+'/heartbeat',lease='wrong').status_code,409)
        self.assertEqual(self.post(job+'/heartbeat',lease=claim['lease']).status_code,200)
        state=State();self.assertNotIn('lease',state.snapshot()['jobs'][0]);state.close()

    def test_real_collector_protocol_uploads_documents_and_syncs_dashboard(self):
        job=self.queued();source=FakeSource();cloud=FakeR2()
        result=run_once(self.control(),self.worker.name,source,cloud)
        self.assertEqual((result['processed'],result['uploaded']),(1,1))
        state=State();self.assertEqual(state.job(job)['status'],'completed')
        self.assertEqual(state.lot(LOT)['uploaded'],1)
        self.assertGreater(state.upload_bytes(),0)
        self.assertEqual(state.job(job)['source_objects'],1);state.close()
        self.assertIn('geollaqta/040117/'+LOT+'/datos.json',cloud.objects)
        self.assertFalse((Path(self.server.name)/'040117'/LOT).exists())
        self.assertFalse(list(Path(self.worker.name).rglob('*.pdf')))
        again=self.queued();source.gets.clear()
        second=run_once(self.control(),self.worker.name,source,cloud)
        self.assertEqual(second['processed'],0);self.assertEqual(source.gets,[])

    def test_ten_parallel_lots_sync_to_dashboard_and_resume_without_redownload(self):
        import threading
        from catastro.test_parallel import DistrictSource
        source, cloud = DistrictSource(12, threading.Barrier(10)), FakeR2()
        job = self.queued()
        result = run_once(self.control(), self.worker.name, source, cloud)
        self.assertEqual(result['workers'], 10)
        self.assertEqual(source.maximum, 10)
        state = State()
        self.assertEqual(state.job(job)['processed'], 12)
        self.assertEqual(state.job(job)['remaining_objects'], 0)
        self.assertEqual(state.snapshot('040117')['totals']['uploaded'], 12)
        state.close()
        before = source.galleries.copy()
        self.queued()
        resumed = run_once(self.control(), self.worker.name, source, cloud)
        self.assertEqual(resumed['processed'], 0)
        self.assertEqual(source.galleries, before)

    def test_stop_is_obeyed_before_any_source_download(self):
        job=self.queued();original=self.control();source=FakeSource()
        class StopAfterClaim:
            def call(this,action,payload=None,job_id=None,lease=None):
                result=original.call(action,payload,job_id,lease)
                if action=='claim':
                    state=State();state.update_job(job,stop=1);state.close()
                return result
        result=run_once(StopAfterClaim(),self.worker.name,source,FakeR2())
        self.assertTrue(result['stopped']);self.assertFalse(source.gets)
        state=State();self.assertEqual(state.job(job)['status'],'stopped');state.close()

    def test_cross_district_rows_and_bad_uploads_are_rejected_without_writes(self):
        job=self.queued();lease=self.post('claim').json()['lease']
        row={'lot_id':'04012607041014','ubigeo':'040126','status':'complete','object_id':1,'uploaded':1,'missing':0,'reports':1,'photos':1,'bytes':100}
        self.assertEqual(self.post(job+'/lot',{'lot':row},lease=lease).status_code,400)
        row.update(lot_id=LOT,ubigeo='040117')
        self.assertEqual(self.post(job+'/lot',{'lot':row,'uploads':[{'object_key':'geollaqta/other/file','sha256':'a'*64,'bytes':1}]},lease=lease).status_code,400)
        state=State();self.assertIsNone(state.lot(LOT));state.close()

    def test_pending_local_upload_is_reconciled_after_lost_acknowledgement(self):
        cloud=FakeR2();source=FakeSource()
        from scrapi.geollaqta_scraper import collect
        collect('040117',root=self.worker.name,source=source,r2=cloud,keep_local=False)
        job=self.queued();source.gets.clear()
        result=run_once(self.control(),self.worker.name,source,cloud)
        self.assertEqual(result['processed'],0);self.assertEqual(source.gets,[])
        state=State();self.assertTrue(state.lot(LOT)['uploaded']);state.close()

    def test_fresh_worker_retries_only_missing_document_using_originals_in_r2(self):
        cloud=FakeR2();source=FakeSource();self.queued()
        run_once(self.control(),self.worker.name,source,cloud)
        state=State();state.create_job('040117',0,retry_missing=True,executor='external');state.close()
        source.missing=False;source.gets.clear()
        with tempfile.TemporaryDirectory() as fresh:
            result=run_once(self.control(),fresh,source,cloud)
        self.assertTrue(result['complete'])
        self.assertEqual(len(source.gets),1)
        self.assertIn('fichain.php',source.gets[0])

    def test_resume_inventory_is_paginated_and_single_lot_scope_is_preserved(self):
        state=State()
        for i in range(501):
            state.save_lot('040117'+str(i).zfill(8),'040117',status='partial',uploaded=1,commit=False)
        state.db.commit();state.close()
        job=self.queued();lease=self.post('claim').json()['lease']
        first=self.post(job+'/seed',lease=lease).json()
        second=self.post(job+'/seed',{'after':first['next_after']},lease=lease).json()
        self.assertEqual((len(first['lots']),len(second['lots'])),(500,1))
        self.assertNotEqual(first['lots'][-1]['lot_id'],second['lots'][0]['lot_id'])
        self.assertIsNone(second['next_after'])
        self.post(job+'/finish',{'status':'completed'},lease=lease)
        state=State();job=state.create_job('040117',0,lot_id='04011700000001',executor='external');state.close()
        lease=self.post('claim').json()['lease']
        only=self.post(job+'/seed',lease=lease).json()
        self.assertEqual([r['lot_id'] for r in only['lots']],['04011700000001'])

    def test_control_only_sends_token_to_configured_https_host_or_localhost(self):
        for url in ['https://evil.example','http://acm.propifai.com','https://user@acm.propifai.com','https://acm.propifai.com/path']:
            with self.assertRaises(ValueError):Control(url,TOKEN)
        Control('https://acm.propifai.com',TOKEN);Control('http://127.0.0.1:8000',TOKEN)

    def test_azure_service_waits_without_claiming_or_failing_job_then_resumes(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('collector_cli_test',Path(__file__).resolve().parents[2]/'scripts/catastro_worker.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        job=self.queued();control=self.control()
        with patch.object(module,'source_available',return_value=False):
            self.assertIsNone(module.service_once(control,self.worker.name))
        state=State();self.assertEqual(state.job(job)['status'],'queued')
        self.assertIn('automáticamente',state.job(job)['message'])
        self.assertEqual(state.db.execute('SELECT source_status FROM collector_presence').fetchone()[0],'unavailable');state.close()
        with patch.object(module,'source_available',return_value=True),patch.object(module,'run_once',side_effect=lambda c,r:run_once(c,r,FakeSource(),FakeR2())):
            result=module.service_once(control,self.worker.name)
        self.assertEqual(result['uploaded'],1)
        state=State();self.assertEqual(state.job(job)['status'],'completed');state.close()

    def test_azure_service_does_not_probe_cofopri_without_pending_work(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('collector_cli_idle_test',Path(__file__).resolve().parents[2]/'scripts/catastro_worker.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with patch.object(module,'source_available') as probe:
            self.assertIsNone(module.service_once(self.control(),self.worker.name))
            probe.assert_not_called()

    def test_session_middleware_exemption_only_covers_private_collector_actions(self):
        import importlib.util
        import sys
        from types import SimpleNamespace
        spec=importlib.util.spec_from_file_location('intelligence._collector_middleware_test',Path(__file__).resolve().parents[1]/'intelligence/middleware.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'intelligence.authentication':SimpleNamespace(get_authenticated_user=lambda request:None)}):
            spec.loader.exec_module(module)
        middleware=module.AuthenticationMiddleware(lambda request:None)
        self.assertTrue(middleware._is_public_path('/catastro/api/worker/claim/'))
        self.assertTrue(middleware._is_public_path('/catastro/api/worker/'+'a'*32+'/heartbeat/'))
        self.assertFalse(middleware._is_public_path('/catastro/api/start/'))
        self.assertFalse(middleware._is_public_path('/catastro/api/status/'))
        self.assertFalse(middleware._is_public_path('/catastro/api/worker/other-action/'))
