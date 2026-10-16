import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, SimpleTestCase

from . import cad_reader as cad

READY = bool(importlib.util.find_spec('ezdxf') and importlib.util.find_spec('pyproj'))


class CadStatusTests(SimpleTestCase):
    def test_transient_windows_lock_preserves_previous_json_and_retries(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            cad.write_status(folder,status='running',message='Anterior')
            original=Path.replace
            attempts=[]
            def replace(source,target):
                attempts.append(source)
                if len(attempts)<3:
                    self.assertEqual(json.loads((folder/'estado.json').read_text())['message'],'Anterior')
                    raise PermissionError(5,'Acceso denegado')
                return original(source,target)
            with patch.object(Path,'replace',replace),patch.object(cad.time,'sleep') as sleep:
                cad.write_status(folder,message='Actualizado')
            self.assertEqual(len(attempts),3)
            self.assertEqual(sleep.call_count,2)
            self.assertEqual(json.loads((folder/'estado.json').read_text())['message'],'Actualizado')
            self.assertEqual(list(folder.glob('*.tmp')),[])

    def test_persistent_lock_is_bounded_and_does_not_destroy_last_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            cad.write_status(folder,status='running',message='Conservado')
            with patch.object(Path,'replace',side_effect=PermissionError(5,'Acceso denegado')) as replace,patch.object(cad.time,'sleep'):
                with self.assertRaises(PermissionError):cad.write_status(folder,message='Otro')
            self.assertEqual(replace.call_count,8)
            self.assertEqual(json.loads((folder/'estado.json').read_text())['message'],'Conservado')
            self.assertEqual(list(folder.glob('*.tmp')),[])


@skipUnless(READY, 'Install requirements-cad.txt for CAD tests')
class CadGeometryTests(SimpleTestCase):
    def setUp(self):
        import ezdxf
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        environment = patch.dict(os.environ, {'CATASTRO_DATA_DIR':self.temporary.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.job = uuid.uuid4().hex
        self.folder = cad.directory(self.job)
        self.folder.mkdir(parents=True)
        document = ezdxf.new('R2018')
        document.units = 6
        document.layers.new('LOTES', dxfattribs={'color': 3})
        document.layers.new('ROTULOS', dxfattribs={'color': 2})
        m = document.modelspace()
        m.add_lwpolyline([(230000,8185000),(230020,8185000),(230020,8185030),(230000,8185030)],
                         close=True, dxfattribs={'layer':'LOTES'})
        m.add_text('Texto <literal>', dxfattribs={'layer':'ROTULOS', 'insert':(230005,8185015)})
        block = document.blocks.new('LOTE_BLOQUE')
        block.add_lwpolyline([(0,0),(10,0),(10,10),(0,10)], close=True)
        m.add_blockref('LOTE_BLOQUE',(230050,8185000),dxfattribs={'layer':'LOTES'})
        hatch = m.add_hatch(dxfattribs={'layer':'LOTES'})
        hatch.paths.add_polyline_path([(230100,8185000),(230120,8185000),(230120,8185020),(230100,8185020)],is_closed=True,flags=1)
        hatch.paths.add_polyline_path([(230105,8185005),(230110,8185005),(230110,8185010),(230105,8185010)],is_closed=True,flags=0)
        document.saveas(self.folder/'converted.dxf')
        data = cad.read_dxf(self.folder)
        cad.write_status(self.folder, id=self.job, status='completed', **data)

    def test_layers_blocks_text_and_hatch_holes_are_preserved(self):
        state = cad.status(self.job)
        self.assertEqual(state['drawable'], 4)
        self.assertEqual(state['unsupported'], {})
        lots = cad.features(self.job,'LOTES')
        self.assertFalse(lots['georeferenced'])
        self.assertEqual(len(lots['features']),3)
        hatch = next(f for f in lots['features'] if f['properties']['entidad_cad']=='HATCH')
        self.assertEqual(len(hatch['geometry']['coordinates']),2)
        block = next(f for f in lots['features'] if f['properties']['bloque_origen'])
        self.assertEqual(block['geometry']['coordinates'][0][0],[230050,8185000])
        text = cad.features(self.job,'ROTULOS')['features'][0]
        self.assertEqual(text['properties']['texto'],'Texto <literal>')

    def test_projection_is_explicit_and_original_geometry_is_not_changed(self):
        raw = cad.features(self.job,'LOTES')['features'][0]['geometry']['coordinates'][0][0]
        projected = cad.features(self.job,'LOTES',crs='EPSG:32719')
        point = projected['features'][0]['geometry']['coordinates'][0][0]
        self.assertTrue(projected['georeferenced'])
        self.assertTrue(-74 < point[0] < -69)
        self.assertTrue(-19 < point[1] < -14)
        self.assertEqual(cad.features(self.job,'LOTES')['features'][0]['geometry']['coordinates'][0][0],raw)

    def test_unknown_layer_crs_and_traversal_are_rejected(self):
        for kwargs in ({'layer':'missing'},{'layer':'LOTES','crs':'+proj=anything'},{'layer':'LOTES','offset':-1}):
            with self.assertRaises(ValueError):cad.features(self.job,**kwargs)
        with self.assertRaises(ValueError):cad.directory('../other')

    def test_geometry_pages_limit_vertices_and_resume_without_losing_entities(self):
        import sqlite3
        connection=sqlite3.connect(self.folder/'geometries.sqlite3')
        connection.execute("DELETE FROM features WHERE layer='LOTES'")
        geometry=json.dumps({'type':'LineString','coordinates':[[230000+i,8185000] for i in range(15001)]})
        connection.executemany('INSERT INTO features(layer,geometry,properties) VALUES (?,?,?)',
                               [('LOTES',geometry,'{}') for _ in range(5)])
        connection.commit();connection.close()
        first=cad.features(self.job,'LOTES')
        self.assertEqual(len(first['features']),3)
        self.assertEqual(first['next_offset'],3)
        second=cad.features(self.job,'LOTES',offset=first['next_offset'])
        self.assertEqual(len(second['features']),2)
        self.assertIsNone(second['next_offset'])
        self.assertFalse({f['id'] for f in first['features']} & {f['id'] for f in second['features']})

    @patch('catastro.cad_reader.subprocess.Popen')
    def test_native_upload_is_queued_without_interpreting_it_as_json(self, process):
        with patch('catastro.cad_reader.converter_path',return_value=Path(__file__)):
            job = cad.start_import(SimpleUploadedFile('plano.dwg',b'AC1015'+b'\0'*100))
        self.assertEqual(cad.status(job)['status'],'queued')
        self.assertEqual((cad.directory(job)/'original.dwg').read_bytes()[:6],b'AC1015')
        process.assert_called_once()

    def test_renamed_json_is_not_accepted_as_a_dwg(self):
        with patch('catastro.cad_reader.converter_path',return_value=Path(__file__)):
            with self.assertRaisesRegex(ValueError,'cabecera DWG'):
                cad.start_import(SimpleUploadedFile('fake.dwg',b'{"type":"FeatureCollection"}'))


class CadAccessTests(TestCase):
    def setUp(self):
        template_patch = patch('django.template.base.Template._render', lambda template, context: template.nodelist.render(context))
        template_patch.start()
        self.addCleanup(template_patch.stop)

    def test_upload_and_layers_are_private_and_upload_requires_csrf(self):
        admin = get_user_model().objects.create_user(username='cad-admin',is_staff=True)
        ordinary = get_user_model().objects.create_user(username='cad-viewer')
        self.assertEqual(self.client.get('/catastro/api/planos/'+'a'*32+'/').status_code,401)
        self.client.force_login(ordinary)
        self.assertEqual(self.client.get('/catastro/api/planos/'+'a'*32+'/capa/').status_code,403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(admin)
        with patch('catastro.cad_reader.start_import') as start:
            response=client.post('/catastro/api/planos/importar/',{'file':SimpleUploadedFile('x.dwg',b'AC1015')})
        self.assertEqual(response.status_code,403)
        start.assert_not_called()

    def test_14_7_mb_native_upload_uses_multipart_file_stream(self):
        self.client.force_login(get_user_model().objects.create_user(username='large-cad',is_staff=True))
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ,{'CATASTRO_DATA_DIR':root}), \
                patch('catastro.cad_reader.converter_path',return_value=Path(__file__)), \
                patch('catastro.cad_reader.subprocess.Popen'):
            body=b'AC1015'+b'\0'*(14700000-6)
            response=self.client.post('/catastro/api/planos/importar/',{'file':SimpleUploadedFile('cayma.dwg',body)})
            self.assertEqual(response.status_code,202)
            job=response.json()['id']
            self.assertEqual(cad.status(job)['bytes'],14700000)
            self.assertEqual((cad.directory(job)/'original.dwg').stat().st_size,14700000)

    @skipUnless(READY and cad.converter_path() and Path(os.environ.get('CATASTRO_NATIVE_TEST_DWG','missing')).is_file(),
                'Set CATASTRO_NATIVE_TEST_DWG to a real DWG to test the native background pipeline')
    def test_real_dwg_upload_background_reader_and_layer_endpoint(self):
        sample = Path(os.environ['CATASTRO_NATIVE_TEST_DWG']).read_bytes()
        self.client.force_login(get_user_model().objects.create_user(username='native-cad',is_staff=True))
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ,{'CATASTRO_DATA_DIR':root}):
            response = self.client.post('/catastro/api/planos/importar/',{'file':SimpleUploadedFile('native.dwg',sample)})
            self.assertEqual(response.status_code,202)
            job=response.json()['id']
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                state=self.client.get('/catastro/api/planos/'+job+'/').json()
                if state['status'] not in ('queued','running'):break
                time.sleep(.2)
            self.assertEqual(state['status'],'completed',state.get('message'))
            self.assertEqual((cad.directory(job)/'original.dwg').read_bytes(),sample)
            layer=next(row for row in state['layers'] if row['drawable'])['name']
            response=self.client.get('/catastro/api/planos/'+job+'/capa/',{'layer':layer})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['features'][0]['geometry']['type'],'Polygon')
            self.assertEqual(response.json()['features'][0]['properties']['plano_origen'],job)
