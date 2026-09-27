"""REMAX 1198720, observado el 24-09-2026; sin navegador ni escrituras a BD."""
import unittest
from scrapi.remax_areas import calcular_areas_remax, parse_area

DESCRIPTION = ('Con un terreno imponente de 2,541 m² (1,086 m² urbanos + 1,455 m² rústicos) '
               'y 615 m² de construcción tradicional, esta casona combina el encanto colonial-rústico.')


class RemaxAreasTests(unittest.TestCase):
    def areas(self, **overrides):
        raw = {'ID': '1198720', 'Tipo': 'CASA DE CAMPO EN VENTA', 'Descripcion': DESCRIPTION,
               'Area Terreno': '', 'Area Construida': '', 'Medidas': '0 X 0', **overrides}
        return calcular_areas_remax(raw), raw['_area_evidence']

    def test_live_sabandia_fields(self):
        result, evidence = self.areas(**{'Area Terreno':'2,541.00 m2', 'Area Construida':'615.00 m²'})
        self.assertEqual(result, {'area_terreno':2541, 'area_construida':615, 'area_m2':615})
        self.assertEqual(evidence['fields']['area_terreno']['source'], 'portal_field')

    def test_live_cerro_colorado_1182974_keeps_thousand_separator(self):
        result, evidence = self.areas(ID='1182974', Descripcion='',
            **{'Area Terreno':'1,005.00 m²', 'Area Construida':'371.61 m²'})
        self.assertEqual(result['area_terreno'], 1005)
        self.assertEqual(result['area_construida'], 371.61)
        self.assertEqual(evidence['fields']['area_terreno']['raw'], '1,005.00 m²')

    def test_both_missing_use_description_without_adding_subdivisions(self):
        result, evidence = self.areas()
        self.assertEqual(result['area_terreno'], 2541)
        self.assertEqual(result['area_construida'], 615)
        self.assertEqual(evidence['fields']['area_construida']['source'], 'detail_description')

    def test_each_missing_field_independently_and_zero_counts_missing(self):
        result, _ = self.areas(**{'Area Terreno':'2600 m2', 'Area Construida':'0.00 m²'})
        self.assertEqual((result['area_terreno'],result['area_construida']), (2600,615))
        result, _ = self.areas(**{'Area Terreno':'0', 'Area Construida':'700 m²'})
        self.assertEqual((result['area_terreno'],result['area_construida']), (2541,700))

    def test_explicit_fields_are_not_overwritten(self):
        result, _ = self.areas(**{'Area Terreno':'2700', 'Area Construida':'710'})
        self.assertEqual((result['area_terreno'],result['area_construida']), (2700,710))

    def test_occupied_is_not_built(self):
        result, _ = self.areas(**{'Area Ocupada':'180 m2','Descripcion':''})
        self.assertIsNone(result['area_construida'])

    def test_number_formats_and_units(self):
        for text, expected in [('2,541.00 m2',2541),('2.541,00 m²',2541),('2,541 m²',2541),
                               ('1 200 m²',1200),('120,50 m2',120.5),('2 ha',20000)]:
            with self.subTest(text=text): self.assertEqual(parse_area(text),expected)
        for text in ('m²','0 X 0','0.00 m²','60 a 120 m2','-10 m2','1,2,3 m2', 'nan'):
            with self.subTest(text=text): self.assertIsNone(parse_area(text))

    def test_missing_land_does_not_take_construction(self):
        result, _ = self.areas(Descripcion='Área de terreno: no informada. Área construida: 200 m2')
        self.assertIsNone(result['area_terreno'])
        self.assertEqual(result['area_construida'],200)

    def test_ranges_are_not_exact_surfaces(self):
        for description in ('Área de terreno: 60 a 120 m2', 'Terreno: 60 m2 a 120 m2', 'Terreno desde 120 m2'):
            with self.subTest(description=description):
                result, _ = self.areas(Descripcion=description)
                self.assertIsNone(result['area_terreno'])

    def test_conflicting_description_stays_missing_with_evidence(self):
        result, evidence = self.areas(Descripcion='Área terreno: 120 m2. Área terreno: 200 m2.')
        self.assertIsNone(result['area_terreno'])
        self.assertEqual(evidence['issues'][0]['reason'],'description_conflict')

    def test_abbreviations_and_suffixes(self):
        result, _ = self.areas(Descripcion='A.T.: 150 m2; A.C.: 200 m2')
        self.assertEqual((result['area_terreno'],result['area_construida']), (150,200))
        result, _ = self.areas(Descripcion='150 m2 de terreno y 200 m² construidos.')
        self.assertEqual((result['area_terreno'],result['area_construida']), (150,200))

    def test_per_floor_and_unlabelled_areas_are_not_total_construction(self):
        for description in ('Construcción: 100 m2 por piso', 'Hermosa casa de 150 m2'):
            result, _ = self.areas(Descripcion=description)
            self.assertIsNone(result['area_construida'])

    def test_preserves_description_and_records_provenance(self):
        raw={'Descripcion':DESCRIPTION}
        calcular_areas_remax(raw)
        self.assertEqual(raw['Descripcion'],DESCRIPTION)
        self.assertIn('2,541',raw['_area_evidence']['fields']['area_terreno']['text'])

    def test_dimensions_fallback_and_land_priority(self):
        result, _ = self.areas(Tipo='TERRENO EN VENTA',Descripcion='',Medidas='8 X 16',**{'Area Construida':'12'})
        self.assertEqual(result,{'area_terreno':128,'area_construida':12,'area_m2':128})


if __name__ == '__main__':
    unittest.main()
