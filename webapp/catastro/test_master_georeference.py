"""Synthetic controls exercise numerical failures; no real/cloud records are used."""
from copy import deepcopy
import hashlib
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from .master_georeference import calibrate, page_info
from .master_store import MasterStore, Conflict
from .source_manager_views import calibration


class CalibrationTests(SimpleTestCase):
    def setUp(self):
        import fitz
        with fitz.open() as doc:
            sheet = doc.new_page(width=100, height=200)
            sheet.set_rotation(270)
            self.pdf = doc.tobytes()
        self.controls = {'page': 1, 'target_crs': 'EPSG:32719', 'tolerance_m': .1, 'points': []}
        for i, (x, y) in enumerate([(10,10),(190,10),(190,90),(10,90),(50,30),(140,70)]):
            self.controls['points'].append({'id': str(i), 'role': 'fit' if i < 4 else 'check',
                'pdf_x': x, 'pdf_y': y, 'easting': 230000+2*x+.1*y,
                'northing': 8190000+.2*x-2*y, 'evidence': 'Coordenadas sintéticas; sólo ensayo RAM'})

    def test_rotated_page_coordinates_and_affine_recovery_use_independent_points(self):
        self.assertEqual(page_info(self.pdf,1)['width'],200)
        self.assertEqual(page_info(self.pdf,1)['height'],100)
        result = calibrate(self.pdf,self.controls)
        self.assertTrue(result['within_tolerance'])
        self.assertEqual(result['status'],'pending')
        self.assertLess(result['statistics']['check']['max_m'],1e-6)
        self.assertEqual(result['statistics']['fit']['count'],4)
        self.assertEqual(result['statistics']['check']['count'],2)
        for actual,expected in zip(result['matrix'],[[2,.1,230000],[.2,-2,8190000]]):
            for value,wanted in zip(actual,expected):self.assertAlmostEqual(value,wanted,places=6)

    def test_bad_checkpoint_cannot_be_hidden_by_refitting(self):
        self.controls['points'][-1]['easting'] += 10
        result = calibrate(self.pdf,self.controls)
        self.assertFalse(result['within_tolerance'])
        self.assertLess(result['statistics']['fit']['max_m'],1e-6)
        self.assertAlmostEqual(result['statistics']['check']['max_m'],10,places=5)

    def test_degenerate_or_collapsed_controls_are_rejected(self):
        for i,row in enumerate(self.controls['points'][:4]):row.update(pdf_x=10+i*40,pdf_y=(10+i*40)/3)
        with self.assertRaisesRegex(ValueError,'alineados'):calibrate(self.pdf,self.controls)
        self.setUp()
        for row in self.controls['points']:row['northing']=8190000
        with self.assertRaisesRegex(ValueError,'inestable'):calibrate(self.pdf,self.controls)

    def test_no_duplicate_or_unreferenced_or_outside_points(self):
        for change in ({'pdf_x':201},{'evidence':''},{'easting':float('nan')},{'role':'verified'}):
            controls=deepcopy(self.controls);controls['points'][-1].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):calibrate(self.pdf,controls)
        self.controls['points'][-1].update(pdf_x=10,pdf_y=10)
        with self.assertRaisesRegex(ValueError,'reutilices'):calibrate(self.pdf,self.controls)

    def test_crs_tolerance_and_held_out_counts_are_required(self):
        for changes in ({'target_crs':'EPSG:4326'},{'target_crs':'EPSG:3857','tolerance_m':0},
                        {'target_crs':'EPSG:999999'},{'page':2},{'tolerance_m':float('inf')}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):calibrate(self.pdf,{**self.controls,**changes})
        self.controls['points'][-1]['role']='fit'
        with self.assertRaisesRegex(ValueError,'comprobación'):calibrate(self.pdf,self.controls)

    def test_wrong_hemisphere_and_extrapolation_are_visible(self):
        controls=deepcopy(self.controls);controls['target_crs']='EPSG:32619'
        with self.assertRaisesRegex(ValueError,'área de uso'):calibrate(self.pdf,controls)
        self.controls['points'][-1].update(pdf_x=199,pdf_y=95,easting=230000+2*199+.1*95,northing=8190000+.2*199-2*95)
        self.assertTrue(calibrate(self.pdf,self.controls)['residuals'][-1]['outside_fit_hull'])

    def test_proposal_is_immutable_and_never_activates_geometries(self):
        store=MasterStore();self.addCleanup(store.db.close)
        original={'source':{'id':'pdf','name':'PDF de prueba','ubigeo':'040103'},
            'version':{'id':'original','label':'Original','crs':None,'georeferencing':{'status':'pending'},
                'original':{'sha256':hashlib.sha256(self.pdf).hexdigest(),'name':'fixture.pdf'}},'features':[]}
        store.stage(original,0,'test')
        request={'action':'calibrate','version_id':'original','controls':self.controls}
        with patch('catastro.source_manager.store',return_value=store),patch('catastro.source_manager.version_payload',return_value=original),patch('catastro.source_manager.pdf',return_value=self.pdf),patch('catastro.source_manager.durable',return_value=False),patch('catastro.source_manager.retain_pdf'):
            proposal=calibration(request,'test')
            self.assertEqual(store.revision,1)
            saved=calibration({**request,'action':'stage_calibration','revision':1,'token':proposal['token']},'test')
            self.assertEqual(store.revision,2)
            row=store.db.execute('SELECT payload FROM versions WHERE id=?',(saved['version_id'],)).fetchone()
            stored=json.loads(row[0]);self.assertEqual(stored['version']['georeferencing']['status'],'pending')
            self.assertFalse(store.records());self.assertFalse(stored['features'])
            self.assertEqual(store.db.execute('SELECT count(*) FROM versions').fetchone()[0],2)
            bad=deepcopy(request);bad['controls']['tolerance_m']=.2
            with self.assertRaises(Conflict):calibration({**bad,'action':'stage_calibration','revision':2,'token':proposal['token']},'test')
            with self.assertRaises(Conflict):calibration({**request,'action':'stage_calibration','revision':0,'token':proposal['token']},'test')
