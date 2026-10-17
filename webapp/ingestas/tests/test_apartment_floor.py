from django.test import SimpleTestCase, TestCase

from scrapi.apartment_floor import extract_floor
from scrapi.normalization import validate_row
from ingestas.models import PropiedadesCompetencia
from ingestas.scraping_export import CAMPOS_EXPORT, construir_libro


class ApartmentFloorTests(SimpleTestCase):
    def test_explicit_floor_expressions(self):
        examples = {
            'Piso 10 con acceso directo del ascensor. Depósito de 10 m².': '10',
            'Ubicado en el tercer piso, edificio de 10 pisos.': '3',
            'Departamento en 3er piso sin ascensor.': '3',
            'Se encuentra en el 7mo piso.': '7',
            'En el 8.º piso con ascensor.': '8',
            'Departamento en décimo primer piso.': '11',
            'Departamento en planta baja.': 'Planta baja',
            'Departamento ubicado en semisótano.': 'Semisótano',
            'Dúplex en pisos 4 y 5.': '4 y 5',
            'Triplex en el 3er, 4to y 5to piso.': '3 y 4 y 5',
            'Departamento en piso 3; cochera en el primer piso.': '3',
            'Departamento en piso 10, dos cocheras en sótano.': '10',
        }
        for description, expected in examples.items():
            with self.subTest(description=description):
                value, evidence = extract_floor('Departamento', description=description)
                self.assertEqual(value, expected)
                self.assertEqual(evidence['status'], 'explicit')

    def test_does_not_guess_from_building_unit_numbers_or_conflicts(self):
        for text in ('Edificio de 10 pisos, departamento 503.', 'Área de 220 m², depósito de 10 m².',
                     'Entre el piso 2 y 4.', 'Piso 2 al 4.', '2do al 4to piso.',
                     'Departamento en piso 3. Departamento ubicado en piso 5.',
                     'Se venden departamentos en pisos 3 y 5.', 'Departamento en piso 3.5.',
                     'Departamento en piso -1.',
                     'Dúplex. Primer piso: sala y comedor. Segundo piso: dormitorios.'):
            with self.subTest(text=text):
                self.assertIsNone(extract_floor('Departamento', description=text)[0])
        self.assertIsNone(extract_floor('Casa', description='Casa en tercer piso')[0])

    def test_structured_floor_and_building_count_stay_separate(self):
        self.assertEqual(extract_floor('Departamento', {'Piso': 6, 'numero_pisos': 15})[0], '6')
        self.assertEqual(extract_floor('Departamento', {'floor': 6.0})[0], '6')
        self.assertIsNone(extract_floor('Departamento', {'numero_pisos': 15})[0])
        self.assertIsNone(extract_floor('Departamento', {'Piso': 3}, 'Ubicado en piso 5')[0])

    def test_all_portals_share_structured_persistence_and_idempotence(self):
        for portal in ('remax', 'properati', 'adondevivir', 'urbania', 'facebook_marketplace'):
            row = validate_row({'fuente': portal, 'id_origen': 'floor-test',
                'tipo_inmueble': 'Departamento', 'descripcion': 'En el tercer piso.',
                'datos_crudos': {'Descripcion': 'En el tercer piso.'}})
            self.assertEqual(row['piso_departamento'], '3')
            self.assertEqual(row['datos_crudos']['piso_departamento'], '3')
            self.assertEqual(validate_row(row)['datos_crudos']['_floor_evidence'],
                             row['datos_crudos']['_floor_evidence'])

    def test_older_records_are_read_without_rewriting_source_data(self):
        raw = {'Descripcion': 'Piso 10 con acceso directo del ascensor.'}
        p = PropiedadesCompetencia(tipo_inmueble='Departamento', datos_crudos=raw)
        self.assertEqual(p.piso_departamento, '10')
        self.assertNotIn('piso_departamento', raw)

    def test_excel_exposes_the_floor(self):
        p = PropiedadesCompetencia(id=1, fuente='remax', id_origen='floor-test',
            tipo_inmueble='Departamento', descripcion='En el tercer piso.')
        workbook, total = construir_libro([p])
        self.assertEqual(total, 1)
        position = CAMPOS_EXPORT.index('piso_departamento') + 1
        self.assertEqual(workbook['Propiedades'].cell(1, position).value, 'Piso del departamento')
        self.assertEqual(workbook['Propiedades'].cell(2, position).value, '3')


class ApartmentFloorPersistenceTests(TestCase):
    def test_new_scraped_apartment_keeps_its_floor_across_reload(self):
        from intelligence.skills.scrapi.db_utils import guardar_propiedades
        guardar_propiedades([{'id_origen': 'floor-db', 'tipo_inmueble': 'Departamento',
            'descripcion': 'Departamento en piso 8', 'datos_crudos': {'Piso': 8}}], 'properati')
        p = PropiedadesCompetencia.objects.get(fuente='properati', id_origen='floor-db')
        self.assertEqual(p.piso_departamento, '8')
        self.assertEqual(p.datos_crudos['piso_departamento'], '8')
        self.assertEqual(p.datos_crudos['_floor_evidence']['status'], 'explicit')
