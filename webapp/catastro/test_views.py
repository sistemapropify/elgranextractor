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
            start.assert_called_once_with('040117',10,None,False)

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
