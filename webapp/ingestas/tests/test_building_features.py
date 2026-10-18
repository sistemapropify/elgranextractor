from copy import deepcopy
from unittest.mock import Mock, AsyncMock
from io import StringIO
from django.test import SimpleTestCase, TestCase
from scrapi.building_features import extract_features, apply_features, parking_label, preserve_features
from scrapi.normalization import validate_row


class BuildingFeatureTests(SimpleTestCase):
    def test_four_types_and_accents(self):
        for text, kind in [
            ('2 cocheras lineales techadas', 'lineal_techada'),
            ('Dos cocheras en línea sin techo', 'lineal_no_techada'),
            ('Cocheras: 1 Paralelo Techado', 'paralela_techada'),
            ('Dos cocheras paralelas no techadas', 'paralela_no_techada'),
        ]:
            with self.subTest(text=text):
                p = extract_features('Departamento', description=text)['parking']
                self.assertTrue(p['has'])
                self.assertEqual(p['types'], [kind])
                self.assertEqual(p['count'], 1 if '1 Paralelo' in text else 2)

    def test_named_boolean_fields_and_missing_information(self):
        for value, expected in [(False, False), ('No', False), (0, False), ('Sí', True), (True, True)]:
            with self.subTest(value=value):
                p = extract_features('Oficina', {'Ascensor': value, 'Cocheras': value})
                self.assertIs(p['elevator']['has'], expected)
                self.assertIs(p['parking']['has'], expected)
        p = extract_features('Casa')
        self.assertIsNone(p['parking']['has'])
        self.assertIsNone(p['parking']['count'])
        self.assertIsNone(p['elevator']['has'])
        self.assertEqual(parking_label(p['parking']), 'Sin información')

    def test_zero_and_explicit_absence_are_not_unknown(self):
        for text in ('Sin cochera. Sin ascensor.', 'No cuenta con cochera. No tiene ascensor.', '0 cocheras. Ascensores: 0'):
            result = extract_features('Departamento', description=text)
            self.assertIs(result['parking']['has'], False)
            self.assertEqual(result['parking']['count'], 0)
            self.assertEqual(parking_label(result['parking']), 'Sin cochera')
            self.assertIs(result['elevator']['has'], False)
        self.assertIsNone(extract_features('Casa', count=0)['parking']['has'])

    def test_partial_data_does_not_invent_quantity_or_type(self):
        for text in ('Con cochera', 'Cochera techada', 'Cochera lineal', 'Cochera independiente en sótano'):
            p = extract_features('Casa', description=text)['parking']
            self.assertTrue(p['has'])
            self.assertIsNone(p['count'])
            self.assertIsNone(p['types'])
        p = extract_features('Departamento', description='Dos cocheras')['parking']
        self.assertEqual(p['count'], 2)
        self.assertIsNone(p['types'])

    def test_optional_visitor_and_projected_features_do_not_confirm_included_features(self):
        for text in ('Cochera opcional por USD 12,000 adicionales', '10 estacionamientos de visitas',
                     'Posibilidad de cochera', 'No se indica cochera'):
            p = extract_features('Oficina', description=text)['parking']
            self.assertIsNone(p['has'])
            self.assertIsNone(p['count'])
            self.assertTrue(p['conditions'])
        for text in ('Preinstalación de ascensor', 'Ascensor proyectado', 'Se instalará ascensor', 'Departamento en quinto piso'):
            self.assertIsNone(extract_features('Departamento', description=text)['elevator']['has'])

    def test_mixed_types_preserve_each_group(self):
        p = extract_features('Casa', description='Una cochera lineal techada y otra paralela no techada')['parking']
        self.assertEqual(p['count'], 2)
        self.assertEqual(p['types'], ['lineal_techada', 'paralela_no_techada'])
        self.assertEqual(parking_label(p), 'Lineal techada + Paralela no techada')

    def test_conflicts_and_ranges_are_not_silently_resolved(self):
        p = extract_features('Departamento', {'Cocheras': '0'}, 'Tiene dos cocheras. Sin ascensor. Edificio con ascensor.')
        self.assertEqual(p['parking']['status'], 'conflict')
        self.assertIsNone(p['parking']['has'])
        self.assertEqual(p['elevator']['status'], 'conflict')
        self.assertIsNone(p['elevator']['has'])
        self.assertIsNone(extract_features('Oficina', description='1 a 3 cocheras')['parking']['count'])
        self.assertIsNone(extract_features('Oficina', {'Cocheras': '1 a 3'})['parking']['count'])

    def test_unknown_labels_and_non_operational_elevator_are_distinct(self):
        for value in ('—', '', 'Sin información', 'No especificado', 'No informado'):
            result = extract_features('Departamento', {'Ascensor': value, 'Cocheras': value})
            self.assertIsNone(result['elevator']['has'])
            self.assertIsNone(result['parking']['has'])
        self.assertIs(extract_features('Departamento', {'Ascensor': 'No operativo'})['elevator']['has'], True)
        self.assertIs(extract_features('Departamento', {'Ascensor': 'No tiene'})['elevator']['has'], False)

    def test_portal_normalization_entry_points(self):
        from scrapi.paged_engine import normalize
        from scrapi.facebook_marketplace_scraper import standardize
        raw = {'ID': 'building-fixture', 'Tipo': 'Departamento en venta', 'Titulo': 'Departamento',
               'Caracteristicas': '2 cocheras lineales techadas | Ascensor: No', 'Precio': 'USD 120000'}
        for portal in ('remax', 'properati', 'adondevivir', 'urbania'):
            source = Mock()
            source.mapear_a_formato_remax.side_effect = lambda value: value
            source.estandarizar.return_value = {'id_origen': 'building-fixture', 'tipo_inmueble': 'Departamento'}
            result = normalize(portal, source, raw)
            self.assertEqual(result['datos_crudos']['tipos_cochera'], ['lineal_techada'])
            self.assertIs(result['datos_crudos']['tiene_ascensor'], False)
        result = standardize({'id': 'building-fb', 'title': 'Departamento en venta',
            'description': '2 cocheras lineales techadas. Sin ascensor.', 'price_text': 'USD 120000'})
        self.assertEqual(result['estacionamientos'], 2)
        self.assertEqual(result['datos_crudos']['tipos_cochera'], ['lineal_techada'])
        self.assertIs(result['datos_crudos']['tiene_ascensor'], False)

    def test_independent_negation_and_other_rooms(self):
        r = extract_features('Casa', description='Sin cochera, con ascensor.')
        self.assertFalse(r['parking']['has'])
        self.assertTrue(r['elevator']['has'])
        p = extract_features('Departamento', description='Cochera techada, cocina lineal')['parking']
        self.assertIsNone(p['types'])

    def test_empty_labels_and_contact_questions_do_not_confirm_features(self):
        for text in ('Cochera:', 'Cochera: ¿Te gustaría recibir más detalles?', 'Ascensor:'):
            result = extract_features('Departamento', description=text)
            self.assertIsNone(result['parking']['has'])
            self.assertIsNone(result['elevator']['has'])

    def test_every_portal_and_supported_kind_share_idempotent_normalization(self):
        for portal in ('remax', 'properati', 'adondevivir', 'urbania', 'facebook_marketplace'):
            for kind in ('Casa', 'Departamento', 'Oficina'):
                with self.subTest(portal=portal, kind=kind):
                    row = validate_row(dict(fuente=portal, id_origen='features-test', tipo_inmueble=kind,
                        datos_crudos={'Cocheras': '1 Paralelo Techado', 'Ascensor': 'Sí'}))
                    self.assertEqual(row['estacionamientos'], 1)
                    self.assertEqual(row['datos_crudos']['tipos_cochera'], ['paralela_techada'])
                    self.assertIs(row['datos_crudos']['tiene_ascensor'], True)
                    self.assertEqual(validate_row(row), row)
        r = extract_features('Terreno', description='Cochera techada. Ascensor.')
        self.assertEqual(r['parking']['status'], 'not_applicable')

    async def test_optional_detail_reader_is_bounded_and_does_not_stop_property_on_failure(self):
        from scrapi.building_feature_detail import enrich_building_features
        raw = {}
        page = Mock(evaluate=AsyncMock(return_value={'features': ['Ascensor: No'], 'description': 'Dos cocheras paralelas techadas'}))
        await enrich_building_features(page, raw, 'remax')
        self.assertEqual(extract_features('Casa', raw)['parking']['count'], 2)
        page.evaluate.side_effect = TimeoutError()
        await enrich_building_features(page, raw, 'properati')
        self.assertEqual(raw['_building_detail_error'], 'TimeoutError')


class BuildingFeaturePersistenceTests(TestCase):
    def test_table_renders_zero_and_independent_feature_cells(self):
        from bs4 import BeautifulSoup
        from django.template.loader import render_to_string
        from django.test import override_settings
        from django.urls import include, path
        from ingestas.models import PropiedadesCompetencia
        p = PropiedadesCompetencia(id=1, tipo_inmueble='Departamento', fuente='remax',
            descripcion='Sin cochera. Con ascensor.', datos_crudos={})
        # Keep the production template's URL namespace without loading workers.
        urls = type('FeatureURLs', (), {'urlpatterns': [path('', include(([
            path('galeria/<int:pk>/', lambda request, pk: None, name='scraping_galeria'),
        ], 'ingestas'), namespace='ingestas'))]})
        with override_settings(ROOT_URLCONF=urls):
            html = render_to_string('ingestas/scraping_tabla.html', {'propiedades': [p]})
        cells = BeautifulSoup(html, 'html.parser').select('tr td')
        self.assertEqual(len(cells), 39)
        self.assertEqual([cell.get_text(strip=True) for cell in cells[15:18]], ['0', 'Sin cochera', 'Sí'])

    def test_real_save_reload_zero_unknown_and_excel(self):
        from ingestas.models import PropiedadesCompetencia
        from intelligence.skills.scrapi.db_utils import guardar_propiedades
        from ingestas.scraping_export import construir_libro, CAMPOS_EXPORT
        for portal in ('remax', 'properati', 'adondevivir', 'urbania', 'facebook_marketplace'):
            guardar_propiedades([dict(id_origen='features', tipo_inmueble='Departamento',
                descripcion='Sin cochera. Edificio con ascensor.', datos_crudos={})], portal)
            p = PropiedadesCompetencia.objects.get(fuente=portal)
            self.assertEqual(p.estacionamientos, 0)
            self.assertEqual(p.cocheras_cantidad, 0)
            self.assertEqual(p.tipo_cochera_display, 'Sin cochera')
            self.assertIs(p.tiene_ascensor, True)
            book, _ = construir_libro([p])
            self.assertEqual(book['Propiedades'].cell(2, CAMPOS_EXPORT.index('estacionamientos')+1).value, 0)
            self.assertEqual(book['Propiedades'].cell(2, CAMPOS_EXPORT.index('ascensor_display')+1).value, 'Sí')

    def test_incomplete_refresh_retains_confirmed_features_and_protected_values(self):
        from ingestas.models import PropiedadesCompetencia, RevisionPropiedadScraping
        from intelligence.skills.scrapi.db_utils import guardar_propiedades
        first = dict(id_origen='keep', tipo_inmueble='Casa', descripcion='Dos cocheras lineales techadas. Con ascensor.', datos_crudos={})
        guardar_propiedades([first], 'remax')
        p = PropiedadesCompetencia.objects.get(id_origen='keep')
        guardar_propiedades([{**first, 'descripcion': 'Casa amplia', 'datos_crudos': {}}], 'remax')
        p.refresh_from_db()
        self.assertEqual(p.tipo_cochera_display, 'Lineal techada')
        self.assertIs(p.tiene_ascensor, True)
        self.assertTrue(p.caracteristicas_por_reconfirmar)
        RevisionPropiedadScraping.objects.create(propiedad=p, campos_protegidos=['estacionamientos', 'tiene_ascensor'])
        guardar_propiedades([{**first, 'descripcion': 'Sin cochera. Sin ascensor.', 'datos_crudos': {}}], 'remax')
        p.refresh_from_db()
        self.assertEqual(p.cocheras_cantidad, 2)
        self.assertIs(p.tiene_ascensor, True)

    def test_historical_read_does_not_rewrite_raw(self):
        from ingestas.models import PropiedadesCompetencia
        raw = {'Cocheras': '1 Paralelo Techado'}
        p = PropiedadesCompetencia(tipo_inmueble='Departamento', datos_crudos=deepcopy(raw))
        self.assertEqual(p.tipo_cochera_display, 'Paralela techada')
        self.assertEqual(p.datos_crudos, raw)
        p = PropiedadesCompetencia(tipo_inmueble='Oficina', estacionamientos=2, amenities='Cochera: Paralelo Techado')
        self.assertEqual(p.cocheras_cantidad, 2)
        self.assertEqual(p.tipo_cochera_display, 'Paralela techada')

    def test_backfill_is_simulation_by_default_and_resumable_and_idempotent(self):
        from django.core.management import call_command
        from ingestas.models import PropiedadesCompetencia
        p = PropiedadesCompetencia.objects.create(fuente='remax', id_origen='old-one', tipo_inmueble='Casa',
            descripcion='Sin cochera. Con ascensor.', datos_crudos={'keep_original': True})
        output = StringIO()
        call_command('reprocesar_cocheras_ascensor', stdout=output)
        p.refresh_from_db()
        self.assertEqual(p.datos_crudos, {'keep_original': True})
        call_command('reprocesar_cocheras_ascensor', apply=True, batch_size=1, stdout=StringIO())
        p.refresh_from_db()
        self.assertEqual(p.estacionamientos, 0)
        self.assertIs(p.datos_crudos['tiene_ascensor'], True)
        output = StringIO()
        call_command('reprocesar_cocheras_ascensor', apply=True, stdout=output)
        self.assertIn('0 con cambios', output.getvalue())
        output = StringIO()
        call_command('reprocesar_cocheras_ascensor', after_id=p.pk, stdout=output)
        self.assertIn('0 revisadas', output.getvalue())
