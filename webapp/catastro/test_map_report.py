import unittest
from django.core.cache import cache
from unittest.mock import patch

from catastro.map_report import measurements, report_measurements, ReportUnavailable

LOT = '04010206058015'
RECORD = '0401022012010025582'


def pages(built='20.5', land='200'):
    fields = [{'original_label': label, 'section': 'Ubicación geográfica', 'value': value}
              for label, value in [('SECT','06'),('MZA','058'),('LOTE','015')]]
    fields += [{'original_label':'AREA LOTE (M2)','value':land},
               {'original_label':'AREA CONSTRUIDA (M2)','value':built}]
    fields += [{'original_label':side,'label':'Medida perimétrica · '+side,'value':value}
               for side,value in [('FRENTE','10'),('DERECHA','20'),('IZQUIERDA','20'),('FONDO','10')]]
    fields += [{'original_label':'NRO DOCUMENTO','value':'87654321'}]
    return [{'named_fields':fields}]


class MapReportTests(unittest.TestCase):
    def setUp(self):
        cache.clear()

    def test_areas_and_four_measures_are_independent_of_vector_values(self):
        result=measurements(pages(),LOT)
        self.assertEqual(result['land_area'],'200')
        self.assertEqual(result['built_area'],'20.5')
        self.assertEqual(result['boundaries'],{'frente':'10','derecha':'20','izquierda':'20','fondo':'10'})
        self.assertNotIn('87654321',str(result))

    def test_blank_area_is_kept_blank_instead_of_using_a_vector_fallback(self):
        self.assertIsNone(measurements(pages(land=None),LOT)['land_area'])

    def test_another_lot_or_unrecognized_document_is_rejected(self):
        with self.assertRaises(ReportUnavailable): measurements(pages(),'04010206058016')
        with self.assertRaises(ReportUnavailable): measurements([{'named_fields':[]}],LOT)

    def test_each_unit_report_is_selected_separately_without_summing_areas(self):
        reports=[{'type':'cadastral_report_pdf','record_id':RECORD,'form_number':'1/2','pages':pages()},
                 {'type':'cadastral_report_pdf','record_id':'0401022012010025583','form_number':'2/2','pages':pages(built='42.35')}]
        with patch('catastro.map_report._archived_reports',return_value=reports):
            first=report_measurements(LOT)
            second=report_measurements(LOT,reports[1]['record_id'])
            with self.assertRaises(ReportUnavailable): report_measurements(LOT,'0401022012019999999')
        self.assertEqual(first['metrics']['built_area'],'20.5')
        self.assertEqual(second['metrics']['built_area'],'42.35')
        self.assertEqual(len(first['reports']),2)
        self.assertNotIn('87654321',str(first))


    @patch('catastro.map_report.Source')
    def test_both_maps_use_the_same_bounded_source_request(self, source):
        from catastro import master
        source.return_value.get.return_value = b'gallery'
        url = 'https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistadetalle.php?id_lote=' + LOT
        self.assertEqual(master._download(url), b'gallery')
        source.return_value.get.assert_called_once_with(url, retry=False)

    @patch('catastro.map_report.download', side_effect=ReportUnavailable('offline'))
    def test_failures_do_not_poison_the_shared_cache(self, download):
        from catastro.map_report import cached_report
        reports = [{'type':'cadastral_report_pdf','record_id':RECORD,
                    'source_url':'https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistapdf/reporte.php?id=' + RECORD}]
        with self.assertRaises(ReportUnavailable):
            report_measurements(LOT, reports=reports)
        self.assertIsNone(cached_report(LOT))
        reports[0]['pages'] = pages()
        self.assertEqual(report_measurements(LOT, reports=reports)['metrics']['built_area'], '20.5')

    @patch('catastro.map_report.download')
    def test_untrusted_archived_document_url_is_rejected_before_download(self, download):
        reports = [{'type':'cadastral_report_pdf','record_id':RECORD,
                    'source_url':'https://evil.test/report.pdf'}]
        with self.assertRaises(ReportUnavailable): report_measurements(LOT, reports=reports)
        download.assert_not_called()

    @patch('catastro.map_report.State')
    def test_old_archive_extraction_is_read_again_instead_of_trusting_wrong_columns(self, state):
        import tempfile, json
        from pathlib import Path
        from catastro.map_report import _archived_reports
        with tempfile.TemporaryDirectory() as directory:
            state.return_value.root = Path(directory)
            folder = Path(directory) / LOT[:6] / LOT
            folder.mkdir(parents=True)
            (folder / 'datos.json').write_text(json.dumps({'lot_id': LOT, 'district_ubigeo': LOT[:6],
                'extraction_revision': 1, 'reports': [{'type': 'cadastral_report_pdf',
                'record_id': RECORD, 'pages': pages(built='2012')}]}), encoding='utf8')
            self.assertNotIn('pages', _archived_reports(LOT)[0])
        state.return_value.close.assert_called_once()


    def test_shared_reader_keeps_individual_form_priority_and_report_fallback(self):
        documents = [{'type':'individual_record_pdf','record_id':RECORD,'pages':pages(land='199',built=None)},
                     {'type':'cadastral_report_pdf','record_id':RECORD,'pages':pages()}]
        value = report_measurements(LOT, reports=documents)
        self.assertEqual(value['metrics']['land_area'], '199')
        self.assertEqual(value['metrics']['built_area'], '20.5')
        self.assertEqual(len(value['reports']), 1)

    def test_individual_form_without_report_still_works(self):
        documents = [{'type':'individual_record_pdf','record_id':RECORD,'pages':pages()}]
        self.assertEqual(report_measurements(LOT, reports=documents)['metrics']['land_area'], '200')
