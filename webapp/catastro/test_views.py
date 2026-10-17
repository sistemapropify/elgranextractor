import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client,TestCase

from catastro.state import State


class DashboardTests(TestCase):
    def setUp(self):
        # Django 5's test-only template signal uses a copy protocol incompatible
        # with Python 3.14. Render normally; assertions use actual response HTML.
        self.template_patch = patch('django.template.base.Template._render', lambda template, context: template.nodelist.render(context))
        self.template_patch.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.environment = patch.dict('os.environ', {'CATASTRO_DATA_DIR':self.tmp.name})
        self.environment.start()
        self.admin = get_user_model().objects.create_user(username='admin',is_staff=True)
        self.user = get_user_model().objects.create_user(username='viewer')

    def tearDown(self):
        self.template_patch.stop()
        self.environment.stop()
        self.tmp.cleanup()

    def test_anonymous_and_non_admin_cannot_read_archive(self):
        self.assertEqual(self.client.get('/catastro/api/status/').status_code,401)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/catastro/').status_code,403)
        self.assertEqual(self.client.get('/catastro/archivos/04011713059004/datos.json/').status_code,403)

    def test_dashboard_renders_navigation_and_actual_assets(self):
        self.client.force_login(self.admin)
        response=self.client.get('/catastro/')
        self.assertContains(response,'Dashboard catastral')
        self.assertContains(response,'catastro-dashboard.js')
        self.assertContains(response,'catastro-dashboard.css')
        self.assertContains(response,'040117')
        self.assertContains(response,'Descargar distrito completo')
        self.assertNotContains(response,'Predios por descarga')
        self.assertContains(response,'id="collection-workers"')
        self.assertContains(response,'value="10" selected')
        self.assertContains(response,'Pausar descarga')

    def test_post_requires_csrf_and_does_not_allow_get_to_launch(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/catastro/api/start/').status_code,405)
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        with patch('catastro.views.start_job') as start:
            response=client.post('/catastro/api/start/',data=json.dumps({'ubigeo':'040117'}),content_type='application/json')
            self.assertEqual(response.status_code,403)
            start.assert_not_called()

    def test_archived_files_are_private_and_not_arbitrary_paths(self):
        code='04011713059004'
        state=State(self.tmp.name)
        state.save_lot(code,'040117',status='complete')
        state.close()
        folder=Path(self.tmp.name)/'040117'/code
        folder.mkdir(parents=True)
        (folder/'datos.json').write_text(json.dumps({'artifacts':[{'filename':'ficha-example.pdf','type':'cadastral_form_pdf'}]}))
        (folder/'ficha-example.pdf').write_bytes(b'%PDF-test')
        self.client.force_login(self.admin)
        response=self.client.get('/catastro/archivos/'+code+'/ficha-example.pdf/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertEqual(response['Content-Type'],'application/pdf')
        response.close()
        self.assertEqual(self.client.get('/catastro/archivos/'+code+'/unlisted.pdf/').status_code,404)

    def test_start_uses_shared_job_and_no_credential_parameters(self):
        self.client.force_login(self.admin)
        with patch('catastro.views.start_job',return_value='example-job') as start:
            response=self.client.post('/catastro/api/start/',data=json.dumps({'ubigeo':'040117','limit':10,'credentials':'ignored'}),content_type='application/json')
            self.assertEqual(response.status_code,202)
            start.assert_called_once_with('040117',10,None,False,workers=None)

    def test_default_request_downloads_whole_district_without_a_limit(self):
        self.client.force_login(self.admin)
        with patch('catastro.views.start_job',return_value='district-job') as start:
            response=self.client.post('/catastro/api/start/',data=json.dumps({'ubigeo':'040117'}),content_type='application/json')
            self.assertEqual(response.status_code,202)
            start.assert_called_once_with('040117',None,None,False,workers=None)

    def test_selected_parallelism_is_persisted_and_out_of_range_requests_do_not_launch(self):
        self.client.force_login(self.admin)
        with patch('catastro.jobs.credentials'), patch('catastro.jobs.subprocess.Popen') as spawn:
            spawn.return_value.pid = 123
            response = self.client.post('/catastro/api/start/', data=json.dumps({'ubigeo':'040117','workers':4}), content_type='application/json')
            self.assertEqual(response.status_code, 202)
            state = State(self.tmp.name)
            job = state.job(response.json()['job_id'])
            self.assertEqual(job['workers'], 4)
            state.update_job(job['id'], status='stopped')
            state.close()
            spawn.reset_mock()
            for workers in (0, 11, True, 2.5):
                response = self.client.post('/catastro/api/start/', data=json.dumps({'ubigeo':'040117','workers':workers}), content_type='application/json')
                self.assertEqual(response.status_code, 400)
            spawn.assert_not_called()

    def test_r2_only_property_and_original_can_be_read_without_azure_copies(self):
        import fitz
        code='04011713059004'
        state=State(self.tmp.name);state.save_lot(code,'040117',status='complete',uploaded=1);state.close()
        data={'lot_id':code,'district_ubigeo':'040117','reports':[],'missing':[],
              'artifacts':[{'filename':'ficha-example.pdf','type':'cadastral_form_pdf','document_name':'FICHA INDIVIDUAL','form_number':'1/1'}]}
        pdf=fitz.open();page=pdf.new_page();page.draw_rect((20,20,200,100));original=pdf.tobytes();pdf.close()
        def remote_get(key):
            return (json.dumps(data).encode() if key.endswith('datos.json') else original),{}
        self.client.force_login(self.admin)
        with patch('catastro.views.R2') as cloud:
            cloud.return_value.get.side_effect=remote_get
            self.assertContains(self.client.get('/catastro/lotes/'+code+'/'),'FICHA INDIVIDUAL')
            response=self.client.get('/catastro/archivos/'+code+'/ficha-example.pdf/')
            self.assertEqual(response.status_code,200)
            self.assertEqual(b''.join(response.streaming_content),original)
            response.close()
            page_response=self.client.get('/catastro/paginas/'+code+'/ficha-example.pdf/1/')
            self.assertEqual(page_response.status_code,200)
            self.assertTrue(page_response.content.startswith(b'\x89PNG'))
            data['lot_id']='04011713059005'
            self.assertEqual(self.client.get('/catastro/lotes/'+code+'/').status_code,502)

    def test_original_page_returns_lines_as_private_png(self):
        import fitz
        code='04011713059004'
        state=State(self.tmp.name);state.save_lot(code,'040117',status='complete');state.close()
        folder=Path(self.tmp.name)/'040117'/code;folder.mkdir(parents=True)
        (folder/'datos.json').write_text(json.dumps({'artifacts':[{'filename':'ficha-example.pdf','type':'cadastral_form_pdf'}]}))
        doc=fitz.open();page=doc.new_page();page.draw_rect((20,20,200,100));page.insert_text((30,40),'CAMPO | VALOR');doc.save(folder/'ficha-example.pdf');doc.close()
        url='/catastro/paginas/'+code+'/ficha-example.pdf/1/'
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.admin)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertEqual(self.client.get('/catastro/paginas/'+code+'/ficha-example.pdf/2/').status_code,404)
