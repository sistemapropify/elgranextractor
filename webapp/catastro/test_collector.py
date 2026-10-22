import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fitz

from catastro.pdf_fields import extract_page
from catastro.registry import normalize
from catastro.report_fields import extract_report
from catastro.state import State
from scrapi.geollaqta_scraper import collect, CollectionError, GalleryLinks, validate, Stopped

LOT = '04011713059004'
BASE = 'https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistapdf/'
HTML = ('<table><tr><td>1</td><td>0001499 - 1/3</td><td><a href="' + BASE +
        'fichabc.php?id=0401172013040001499">FICHA BIENES COMUNES</a></td></tr>'
        '<tr><td>2</td><td>0006147 - 2/3</td><td><a href="' + BASE +
        'fichain.php?id=0401172013010006147">FICHA INDIVIDUAL</a></td><td><a href="' + BASE +
        'reporte.php?id=0401172013010006147"><img src="icon.gif"></a></td></tr></table>'
        '<img src="https://catastro.cofopri.gob.pe/img_catastro/040117/photo.jpg">').encode()


def pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((20, 30), 'Documento original de prueba')
    return doc.tobytes()


class FakeSource:
    def __init__(self):
        self.gets = []
        self.missing = True

    def query(self, **kwargs):
        if kwargs.get('returnIdsOnly'):
            return {'objectIds': [1]}
        return {'features': [{'attributes': {'OBJECTID': 1, 'ID_DIST': '040117', 'ID_LOTE': LOT}, 'geometry': {'rings': []}}]}

    def get(self, url, **kwargs):
        self.gets.append(url)
        if 'vistadetalle' in url:
            return HTML
        if 'fichain.php' in url and self.missing:
            raise CollectionError('COFOPRI respondió HTTP 500.')
        if url.endswith('.jpg'):
            return b'\xff\xd8\xffphoto'
        return pdf()


class FakeR2:
    def __init__(self):
        self.objects = {}

    def put_verified(self, key, body, mime):
        self.objects[key] = (body, mime)

    def get(self, key):
        return self.objects[key][0], {}


class CollectorTests(unittest.TestCase):
    def test_geometry_identity_tolerates_source_whitespace_but_rejects_mismatch(self):
        manifest = {'lot_id': LOT, 'district_ubigeo': '040117',
                    'feature': {'attributes': {'ID_LOTE': ' '+LOT+' ', 'ID_DIST': ' 040117 '},
                                'geometry': {'rings': []}},
                    'artifacts': [], 'reports': [], 'missing': []}
        self.assertEqual(normalize(manifest)[0]['lot_id'], LOT)
        manifest['feature']['attributes']['ID_LOTE'] = '04011713059005'
        with self.assertRaisesRegex(ValueError, 'geometría no corresponde'):
            normalize(manifest)

    def test_parser_keeps_names_multiple_forms_and_reports(self):
        parser = GalleryLinks('040117')
        parser.feed(HTML.decode())
        self.assertEqual([d['document_name'] for d in parser.documents],
                         ['FICHA BIENES COMUNES', 'FICHA INDIVIDUAL', 'REPORTE CATASTRAL'])
        self.assertEqual(parser.documents[0]['form_number'], '0001499 - 1/3')
        self.assertEqual(len(parser.images), 1)
        parser.feed('<tr><td>1</td><td>x</td><td><a href="https://other.example/fichain.php?id=0401172013010006147">FICHA</a></td></tr>')
        self.assertEqual(len(parser.documents), 3)

    def test_resume_and_retry_preserve_originals_and_document_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, cloud = FakeSource(), FakeR2()
            first = collect('040117', lot_id=LOT, root=tmp, source=source, r2=cloud)
            self.assertEqual((first['processed'], first['uploaded'], first['partial']), (1, 1, 1))
            manifest = json.loads((Path(tmp) / '040117' / LOT / 'datos.json').read_text())
            self.assertEqual(manifest['missing'][0]['document_name'], 'FICHA INDIVIDUAL')
            self.assertEqual(manifest['reports'][0]['document_name'], 'FICHA BIENES COMUNES')
            self.assertFalse(first['complete'])
            get_count = len(source.gets)
            second = collect('040117', lot_id=LOT, root=tmp, source=source, r2=cloud)
            self.assertEqual(second['processed'], 0)
            self.assertEqual(len(source.gets), get_count)
            source.missing = False
            third = collect('040117', lot_id=LOT, retry_missing=True, root=tmp, source=source, r2=cloud)
            self.assertEqual(third['processed'], 1)
            self.assertTrue(third['complete'])
            self.assertEqual(len(source.gets), get_count + 1)
            self.assertTrue(any('0401172013040001499' in key for key in cloud.objects))
            self.assertTrue(any('/datos-' in key for key in cloud.objects))
            for artifact in manifest['artifacts']:
                stored = cloud.objects['geollaqta/040117/' + LOT + '/' + artifact['filename']][0]
                self.assertEqual(hashlib.sha256(stored).hexdigest(), artifact['sha256'])

    def test_incomplete_inventory_is_not_success(self):
        source = FakeSource()
        original_query = source.query
        source.query = lambda **kw: {'objectIds': [1, 2]} if kw.get('returnIdsOnly') else original_query(**kw)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CollectionError):
                collect('040117', root=tmp, source=source, r2=FakeR2())

    def test_individual_scope_does_not_include_other_lots_pending_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = State(tmp)
            state.save_lot('04011713059005', '040117', status='partial', missing=1, uploaded=1)
            state.close()
            source = FakeSource()
            source.missing = False
            result = collect('040117', lot_id=LOT, root=tmp, source=source, r2=FakeR2())
            self.assertTrue(result['complete'])
            self.assertEqual(result['selected_objects'], 1)
            self.assertEqual(result['remaining_objects'], 0)

    def test_storage_error_keeps_retryable_local_copy(self):
        class BrokenR2:
            def put_verified(self, *args):
                from catastro.storage import StorageError
                raise StorageError('R2 no disponible.')
        with tempfile.TemporaryDirectory() as tmp:
            result = collect('040117', lot_id=LOT, root=tmp, source=FakeSource(), r2=BrokenR2())
            self.assertEqual(result['failed'], 1)
            self.assertEqual(result['remaining_objects'], 1)
            state = State(tmp)
            self.assertFalse(state.lot(LOT)['uploaded'])
            state.close()
            self.assertTrue((Path(tmp) / '040117' / LOT / 'datos.json').is_file())

    def test_r2_retries_transient_failure_but_not_access_denied(self):
        from catastro.storage import R2, StorageError
        cloud = R2({'R2_BUCKET': 'test', 'R2_ACCOUNT_ID': 'a'*32})
        with patch.object(cloud, '_put_verified', side_effect=[StorageError('No se pudo conectar con R2.'), None]) as put, patch('catastro.storage.time.sleep'):
            cloud.put_verified('geollaqta/test.pdf', b'pdf', 'application/pdf')
            self.assertEqual(put.call_count, 2)
        with patch.object(cloud, '_put_verified', side_effect=StorageError('R2 respondió HTTP 403.')) as put:
            with self.assertRaises(StorageError):
                cloud.put_verified('geollaqta/test.pdf', b'pdf', 'application/pdf')
            self.assertEqual(put.call_count, 1)

    def test_one_active_job_across_districts_and_stale_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = State(tmp)
            first = state.create_job('040117', 10)
            with self.assertRaises(ValueError):
                state.create_job('040126', 10)
            state.db.execute('UPDATE jobs SET heartbeat=0 WHERE id=?', (first,))
            state.db.commit()
            state.create_job('040126', 10)
            self.assertEqual(state.job(first)['status'], 'interrupted')
            state.close()

    def test_finished_batch_keeps_remaining_inventory_explicit(self):
        from catastro.jobs import run_job
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CATASTRO_DATA_DIR': tmp}):
            state = State()
            job_id = state.create_job('040126', 10)
            state.close()
            result = {'processed': 10, 'uploaded': 10, 'partial': 2, 'failed': 0,
                      'remaining_objects': 5229, 'complete': False}
            with patch('catastro.jobs.collect', return_value=result):
                run_job(job_id)
            state = State()
            job = state.job(job_id)
            state.close()
            self.assertEqual(job['status'], 'completed')
            self.assertIn('5229 registros', job['message'])
            self.assertIn('reanudar', job['message'])
            self.assertNotIn('automáticamente', job['message'])

    def test_complete_district_streams_more_than_500_without_manual_batches(self):
        class DistrictSource:
            def __init__(self):
                self.events=[]
            def query(self, **params):
                if params.get('returnIdsOnly'):
                    return {'objectIds':list(range(1,504))}
                ids=list(map(int,params['objectIds'].split(',')))
                self.events.append(('query',ids[0],len(ids)))
                return {'features':[{'attributes':{'OBJECTID':i,'ID_DIST':'040117','ID_LOTE':'040117'+str(i).zfill(8)},'geometry':{'rings':[]}} for i in ids]}
            def get(self, url, **kwargs):
                self.events.append(('gallery',url))
                return b'<html><table></table></html>'
        with tempfile.TemporaryDirectory() as tmp:
            source=DistrictSource();progress=[]
            result=collect('040117',root=tmp,source=source,r2=FakeR2(),progress=progress.append,keep_local=False)
            self.assertEqual(result['processed'],503)
            self.assertEqual(result['uploaded'],503)
            self.assertEqual(result['remaining_objects'],0)
            self.assertEqual([e[2] for e in source.events if e[0]=='query'],[100,100,100,100,100,3])
            self.assertEqual(source.events[1][0],'gallery')
            self.assertEqual(progress[0]['remaining_objects'],503)
            self.assertEqual(progress[-1]['remaining_objects'],0)

    def test_r2_only_archive_retries_missing_without_redownloading_saved_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,cloud=FakeSource(),FakeR2()
            collect('040117',lot_id=LOT,root=tmp,source=source,r2=cloud,keep_local=False)
            self.assertFalse((Path(tmp)/'040117'/LOT/'datos.json').exists())
            get_count=len(source.gets);source.missing=False
            result=collect('040117',lot_id=LOT,retry_missing=True,root=tmp,source=source,r2=cloud,keep_local=False)
            self.assertEqual(result['uploaded'],1)
            self.assertTrue(result['complete'])
            self.assertEqual(len(source.gets),get_count+1)
            self.assertFalse((Path(tmp)/'040117'/LOT).exists())

    def test_r2_working_copy_cleanup_preserves_existing_review_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'040117'/LOT;folder.mkdir(parents=True)
            (folder/'review.txt').write_text('Keep this review')
            collect('040117',lot_id=LOT,root=tmp,source=FakeSource(),r2=FakeR2(),keep_local=False)
            self.assertEqual([p.name for p in folder.iterdir()],['review.txt'])

    def test_missing_gallery_is_pending_without_failing_district_collection(self):
        source=FakeSource()
        source.get=lambda *args,**kwargs: (_ for _ in ()).throw(CollectionError('COFOPRI respondió HTTP 404.',404))
        with tempfile.TemporaryDirectory() as tmp:
            result=collect('040117',root=tmp,source=source,r2=FakeR2())
            self.assertEqual((result['failed'],result['partial'],result['uploaded'],result['remaining_objects']),(0,1,1,0))

    def test_district_job_has_no_record_limit_and_persists_inventory_progress(self):
        from catastro.jobs import start_job, run_job
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CATASTRO_DATA_DIR':tmp}),patch('catastro.jobs.credentials'),patch('catastro.master_pipeline.require_collection_ready'):
            job_id=start_job('040117',launch=False)
            def collector(ubigeo,limit,**kwargs):
                self.assertIsNone(limit)
                kwargs['progress']({'processed':4,'skipped':96,'source_objects':15000,'selected_objects':14904,'remaining_objects':14900,'message':'avance'})
                raise Stopped('Detenida')
            with patch('catastro.jobs.collect',side_effect=collector):
                run_job(job_id)
            state=State();job=state.job(job_id);state.close()
            self.assertEqual(job['limit_lots'],0)
            self.assertEqual(job['source_objects'],15000)
            self.assertEqual(job['remaining_objects'],14900)
            self.assertEqual(job['status'],'stopped')

    def test_rejects_unbounded_or_cross_district_requests(self):
        for params in [('040117', 0, None), ('040117', 501, None), ('040117', 10, '04012607041014'), ('999999', 10, None)]:
            with self.assertRaises(ValueError):
                validate(*params)

    def test_numbered_fields_keep_blanks_and_repeated_table_rows(self):
        doc = fitz.open()
        page = doc.new_page()
        def cell(rect, fill, text, color=(.18,.18,.18), size=6):
            page.draw_rect(rect, fill=fill)
            if text:
                page.insert_text((rect[0]+2,rect[1]+9),text,fontsize=size,color=color)
        cell((10,20,23,32),(.824,.824,.824),'07')
        cell((23,20,120,32),(.53,.77,1),'CODIGO VIA')
        cell((10,32,120,44),None,'000387',(0,.29,1),7)
        cell((130,20,145,32),(.824,.824,.824),'105')
        cell((145,20,230,32),(.53,.77,1),'NUMERO PARTIDA')
        cell((130,32,230,44),None,'')
        cell((10,60,55,72),(.824,.824,.824),'87')
        cell((10,72,55,84),(.53,.77,1),'VERIFICADA')
        cell((10,84,55,96),None,'59.78',(0,.29,1),7)
        cell((10,96,55,108),None,'26.7',(0,.29,1),7)
        fields = {f['number']: f for f in extract_page(page)['numbered_fields']}
        self.assertEqual(fields['07']['value'], '000387')
        self.assertIsNone(fields['105']['value'])
        self.assertEqual([v['text'] for v in fields['87']['values']], ['59.78','26.7'])
        self.assertNotEqual(fields['87']['values'][0]['row'],fields['87']['values'][1]['row'])

    def test_report_names_all_columns_and_keeps_second_owner(self):
        cells=[]
        def c(text,box):
            cells.append({'id':len(cells),'text':text,'bbox':box,'fill':None,'values':[]})
        for i,(label,value) in enumerate([('DEPARTAMENTO','AREQUIPA'),('PROVINCIA','AREQUIPA'),('DISTRITO','YANAHUARA')]):
            c(label,[i*100,20,(i+1)*100,32]);c(value,[i*100,32,(i+1)*100,44])
        c('CUC-LOTE',[0,0,150,10]);c('',[0,10,150,20])
        c('NOMBRES Y APELLIDOS O RAZON SOCIAL',[0,60,150,72]);c('TIPO DOCUMENTO',[150,60,200,72]);c('NRO DOCUMENTO',[200,60,300,72])
        for y,name,num in [(72,'TITULAR UNO','00123456'),(84,'TITULAR DOS','00056789')]:
            c(name,[0,y,150,y+12]);c('DNI',[150,y,200,y+12]);c(num,[200,y,300,y+12])
        c('AREA LOTE (M2)',[0,150,150,162]);c('128',[0,162,150,174])
        c('FRENTE',[0,200,60,212]);c('CALLE 7',[60,200,180,212]);c('8.00',[180,200,300,212])
        result=extract_report(cells)
        fields={f['label']:f for f in result['named_fields']}
        self.assertEqual(fields['Distrito']['value'],'YANAHUARA')
        self.assertEqual(fields['Nombres y apellidos o razón social']['value'],'TITULAR UNO | TITULAR DOS')
        self.assertEqual(fields['Número de documento']['value'],'00123456 | 00056789')
        self.assertIsNone(fields['CUC del lote']['value'])
        self.assertEqual(fields['Área del lote (m²)']['value'],'128')
        self.assertEqual(fields['Colindancia · Frente']['value'],'CALLE 7')
        self.assertEqual(fields['Medida perimétrica · Frente (m)']['value'],'8.00')
        self.assertFalse(result['unmapped_cells'])

    def test_unmapped_values_are_not_presented_as_named_fields(self):
        doc=fitz.open();page=doc.new_page()
        page.insert_text((40,80),'VALOR SIN CABECERA',color=(0,.29,1),fontsize=7)
        data=extract_page(page)
        self.assertTrue(data['unassigned_values'])
        self.assertFalse(data['additional_fields'])


if __name__ == '__main__':
    unittest.main()
