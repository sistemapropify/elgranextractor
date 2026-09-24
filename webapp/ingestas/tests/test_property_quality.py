from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase, SimpleTestCase, RequestFactory
from django.template.loader import get_template
from rest_framework.test import APIRequestFactory, force_authenticate
from ingestas.models import PropiedadesCompetencia, RevisionPropiedadScraping, CambioPropiedadScraping
from ingestas.property_quality import analyze, inspect_row
from ingestas.property_quality_views import PropertyEditor, EDIT_FIELDS, dashboard
from intelligence.skills.scrapi.db_utils import guardar_propiedades

class QualityRulesTests(SimpleTestCase):
    def test_house_example(self):
        row = inspect_row({'tipo_inmueble': 'Casa', 'tipo_operacion': 'Venta',
                           'precio_usd': 200000, 'area_terreno': 20})
        self.assertEqual(row['ratios']['area_terreno'], Decimal('10000'))
        self.assertTrue(any('menor de 30' in a for a in row['alertas']))

    def test_rental_not_divided(self):
        self.assertEqual(inspect_row({'tipo_operacion': 'Alquiler', 'precio_usd': 200000, 'area_m2': 20})['ratios'], {})

    def test_currency_conversion(self):
        row = inspect_row({'tipo_operacion': 'Venta', 'precio_soles': 688000, 'area_terreno': 20})
        self.assertEqual(row['ratios']['area_terreno'], 10000)

    def test_iqr_comparable_group(self):
        rows = [dict(id=i, tipo_operacion='Venta', tipo_inmueble='Departamento', distrito='Cayma',
                     latitud=-16.4, longitud=-71.5, precision_ubicacion='exacta',
                     estado_publicacion='activa', precio_usd=price, area_construida=100)
                for i, price in enumerate([100000, 105000, 110000, 115000, 120000, 125000, 130000, 1000000])]
        result = analyze(rows)
        self.assertTrue(any('IQR' in a for a in result[-1]['alertas']))

class QualityEditorTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(pk=1, username='reviewer', is_authenticated=True, is_active=True,
                                    is_staff=True, has_perm=lambda p: True)
        self.prop = PropiedadesCompetencia.objects.create(fuente='remax', id_origen='quality-1',
            tipo_inmueble='Casa', tipo_operacion='Venta', area_m2=20, area_terreno=20,
            precio_usd=200000, estado_publicacion='activa', latitud=-16.4, longitud=-71.5)

    def call(self, method, data=None, user=None):
        req = getattr(self.factory, method)('/edit/', data=data or {}, format='json')
        force_authenticate(req, user=user or self.user)
        return PropertyEditor.as_view()(req, pk=self.prop.pk)

    def payload(self):
        response = self.call('get')
        self.assertEqual(response.status_code, 200)
        return {**{k: response.data['record'][k] for k in EDIT_FIELDS}, 'version': response.data['version']}

    def test_save_protects_and_audits_then_scrape_preserves(self):
        payload = self.payload()
        payload.update(area_terreno='200', excluida='true', motivo='Verificar datos')
        response = self.call('post', payload)
        self.assertEqual(response.status_code, 200, response.data)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.area_m2, 200)
        self.assertEqual(CambioPropiedadScraping.objects.count(), 1)
        result = guardar_propiedades([{'id_origen':'quality-1', 'area_terreno':20, 'area_m2':20, 'precio_usd':210000}], 'remax')
        self.assertEqual(result['errores'], 0)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.area_terreno, 200)
        self.assertEqual(self.prop.precio_usd, 210000)
        self.assertTrue(self.prop.revision_calidad.excluida)
        from cuadrantizacion.views import _available_scraped_properties
        self.assertTrue(_available_scraped_properties()[0]['quality_excluded'])

    def test_stale_save_rejected(self):
        payload = self.payload()
        PropiedadesCompetencia.objects.filter(pk=self.prop.pk).update(precio_usd=100)
        self.assertEqual(self.call('post', payload).status_code, 409)

    def test_invalid_values_rejected(self):
        payload = self.payload()
        payload['area_terreno'] = '-1'
        self.assertEqual(self.call('post', payload).status_code, 400)
        self.assertFalse(CambioPropiedadScraping.objects.exists())

    def test_permission_denied(self):
        user = SimpleNamespace(is_authenticated=True, is_active=True, is_staff=False, has_perm=lambda p: False)
        self.assertEqual(self.call('post', self.payload(), user=user).status_code, 403)

    def test_anonymous_denied(self):
        req = self.factory.get('/edit/')
        self.assertIn(PropertyEditor.as_view()(req, pk=self.prop.pk).status_code, (401,403))

    def test_missing_csrf_rejected_with_prometeo_session(self):
        req = APIRequestFactory(enforce_csrf_checks=True).post('/edit/', {})
        req.current_user = self.user
        self.assertEqual(PropertyEditor.as_view()(req, pk=self.prop.pk).status_code, 403)

    def test_exclusion_needs_reason_and_can_restore(self):
        payload = self.payload(); payload['excluida']='true'
        self.assertEqual(self.call('post', payload).status_code, 400)
        payload['motivo']='Revisar'; self.assertEqual(self.call('post', payload).status_code, 200)
        payload=self.payload(); payload['excluida']='false'
        self.assertEqual(self.call('post', payload).status_code, 200)
        self.assertFalse(RevisionPropiedadScraping.objects.get(propiedad=self.prop).excluida)

    def test_export_real_rows(self):
        request=RequestFactory().get('/quality/', {'exportar':'csv'})
        request.current_user=self.user
        response=dashboard(request)
        self.assertEqual(response.status_code,200)
        self.assertIn(b'quality-1', response.content)

    def test_templates_compile(self):
        for name in ('ingestas/property_editor.html','ingestas/property_quality.html','cuadrantizacion/mapa_zonas.html'):
            get_template(name)
