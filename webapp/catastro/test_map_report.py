import unittest
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
