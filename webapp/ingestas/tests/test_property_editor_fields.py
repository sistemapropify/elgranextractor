from types import SimpleNamespace

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from ingestas.models import PropiedadesCompetencia, RevisionPropiedadScraping, CambioPropiedadScraping
from ingestas.property_quality_views import PropertyEditor, EDIT_FIELDS
from intelligence.skills.scrapi.db_utils import guardar_propiedades
from scrapi.building_features import PARKING_TYPES


class CompletePropertyEditorTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(pk=1, username='reviewer', is_authenticated=True,
            is_active=True, is_staff=True, has_perm=lambda permission: True)
        self.property = PropiedadesCompetencia.objects.create(fuente='remax', id_origen='all-fields',
            tipo_inmueble='Departamento', tipo_operacion='Venta', titulo='Departamento en venta',
            precio_usd=100000, area_construida=100, distrito='Cayma',
            datos_crudos={'original_extra': 'Dato adicional del portal', '_photos': ['evidencia']})

    def call(self, method, data=None):
        request = getattr(self.factory, method)('/edit/', data=data or {}, format='json')
        force_authenticate(request, user=self.user)
        return PropertyEditor.as_view()(request, pk=self.property.pk)

    def payload(self):
        response = self.call('get')
        self.assertEqual(response.status_code, 200, response.data)
        return {**{key: response.data['record'][key] for key in EDIT_FIELDS},
                'version': response.data['version']}

    def save(self, **fields):
        response = self.call('post', {**self.payload(), **fields})
        self.assertEqual(response.status_code, 200, response.data)
        self.property.refresh_from_db()

    def test_every_model_field_and_original_source_field_is_visible(self):
        data = self.call('get').data
        visible = set(EDIT_FIELDS) | {row['name'] for row in data['readonly_fields'] if row['name'] != 'computed'} | {'datos_crudos'}
        self.assertEqual(visible, {field.name for field in self.property._meta.concrete_fields})
        self.assertIn('original_extra', {row['label'] for row in data['original_fields']})
        for key in ('tiene_cochera', 'tipos_cochera', 'tiene_ascensor', 'piso_departamento'):
            self.assertIn(f'name="{key}"', data['html'])
        for value in PARKING_TYPES:
            self.assertIn(f'value="{value}"', data['html'])

    def test_mixed_parking_elevator_and_floor_save_audit_and_survive_scraping(self):
        self.save(tiene_cochera='si', tipos_cochera=['lineal_techada', 'paralela_no_techada'],
                  estacionamientos=2, tiene_ascensor='no', piso_departamento='3 y 4')
        self.assertEqual(self.property.tipos_cochera, ['lineal_techada', 'paralela_no_techada'])
        self.assertEqual(self.property.estacionamientos, 2)
        self.assertIs(self.property.tiene_ascensor, False)
        self.assertEqual(self.property.piso_departamento, '3 y 4')
        self.assertEqual(self.property.datos_crudos['original_extra'], 'Dato adicional del portal')
        self.assertTrue({'tiene_cochera', 'tipos_cochera', 'estacionamientos', 'tiene_ascensor',
                         'piso_departamento'} <= set(self.property.revision_calidad.campos_protegidos))
        self.assertIn('tipos_cochera', CambioPropiedadScraping.objects.get().cambios)
        guardar_propiedades([{'id_origen':'all-fields', 'tipo_inmueble':'Departamento',
            'descripcion':'Sin cochera. Con ascensor. Departamento en piso 8.',
            'datos_crudos':{'new_source_value':'conservar'}}], 'remax')
        self.property.refresh_from_db()
        self.assertEqual(self.property.tipos_cochera, ['lineal_techada', 'paralela_no_techada'])
        self.assertEqual(self.property.estacionamientos, 2)
        self.assertIs(self.property.tiene_ascensor, False)
        self.assertEqual(self.property.piso_departamento, '3 y 4')
        self.assertEqual(self.property.datos_crudos['new_source_value'], 'conservar')

    def test_explicit_no_parking_is_zero_not_missing(self):
        self.save(tiene_cochera='no', tipos_cochera=[], estacionamientos=None)
        self.assertIs(self.property.tiene_cochera, False)
        self.assertEqual(self.property.estacionamientos, 0)
        self.assertEqual(self.property.tipo_cochera_display, 'Sin cochera')

    def test_unknown_parking_and_elevator_can_clear_previous_confirmed_values(self):
        self.save(tiene_cochera='si', tipos_cochera=['lineal_techada'], estacionamientos=1,
                  tiene_ascensor='si', piso_departamento='5')
        self.save(tiene_cochera='', tipos_cochera=[], estacionamientos=None,
                  tiene_ascensor='', piso_departamento='')
        self.assertIsNone(self.property.tiene_cochera)
        self.assertIsNone(self.property.tiene_ascensor)
        self.assertIsNone(self.property.estacionamientos)
        self.assertIsNone(self.property.piso_departamento)
        guardar_propiedades([{'id_origen':'all-fields', 'tipo_inmueble':'Departamento',
            'descripcion':'Una cochera lineal techada. Con ascensor. Piso 9.', 'datos_crudos':{}}], 'remax')
        self.property.refresh_from_db()
        self.assertIsNone(self.property.tiene_cochera)
        self.assertIsNone(self.property.tiene_ascensor)
        self.assertIsNone(self.property.piso_departamento)

    def test_older_client_edit_preserves_features_without_protecting_them(self):
        self.property.descripcion='Dos cocheras paralelas techadas. Con ascensor. Piso 6.'
        self.property.save()
        self.save(titulo='Título corregido')
        self.assertEqual(self.property.tipos_cochera, ['paralela_techada'])
        self.assertIs(self.property.tiene_ascensor, True)
        self.assertFalse(set(('tipos_cochera', 'tiene_ascensor')) &
                         set(self.property.revision_calidad.campos_protegidos))

    def test_incompatible_parking_and_invalid_floor_are_rejected_without_writes(self):
        invalid = [dict(tiene_cochera='no', tipos_cochera=['lineal_techada']),
                   dict(tiene_cochera='no', estacionamientos=2),
                   dict(tiene_cochera='si', estacionamientos=0),
                   dict(tiene_cochera='', estacionamientos=2),
                   dict(tipos_cochera=['inventado']), dict(piso_departamento='201'),
                   dict(piso_departamento='<script>')]
        for fields in invalid:
            with self.subTest(fields=fields):
                response = self.call('post', {**self.payload(), **fields})
                self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(CambioPropiedadScraping.objects.exists())

    def test_readonly_identifiers_and_tracking_cannot_be_changed_by_payload(self):
        old_source, old_id = self.property.fuente, self.property.id_origen
        self.save(fuente='otro', id_origen='otro', estado_publicacion='activa',
                  datos_crudos={'replace':'evidence'})
        self.assertEqual((self.property.fuente, self.property.id_origen),(old_source,old_id))
        self.assertEqual(self.property.estado_publicacion, 'sin_verificar')
        self.assertEqual(self.property.datos_crudos['original_extra'], 'Dato adicional del portal')

    def test_simultaneous_feature_edit_invalidates_previous_version(self):
        previous = self.payload()
        self.save(tiene_cochera='si', tipos_cochera=['paralela_techada'])
        self.assertEqual(self.call('post', previous).status_code, 409)

    def test_manual_review_persists_and_filters_independently_of_acm_eligibility(self):
        from unittest.mock import patch
        from django.http import HttpResponse
        from django.test import RequestFactory
        from ingestas.property_quality_views import dashboard
        self.property.latitud=-16.4
        self.property.longitud=-71.5
        self.property.precision_ubicacion='exacta'
        self.property.estado_publicacion='activa'
        self.property.save()
        self.save(correcta='true', motivo='Cotejada con la publicación')
        review=RevisionPropiedadScraping.objects.get(propiedad=self.property)
        self.assertTrue(review.correcta)
        self.assertIsNotNone(review.corregida_en)

        def count(state):
            request=RequestFactory().get('/quality/', {'estado':'acm','portal':'remax',
                'tipo':'Departamento','distrito':'Cayma','operacion':'Venta','revision':state})
            request.current_user=self.user
            with patch('ingestas.property_quality_views.render',return_value=HttpResponse()) as render:
                dashboard(request)
            return render.call_args.args[2]['page']

        self.assertEqual(count('pendientes').paginator.count,0)
        reviewed=count('revisadas')
        self.assertEqual(reviewed.paginator.count,1)
        self.assertEqual(reviewed[0]['revision_fecha'],review.corregida_en)
        self.assertTrue(self.call('get').data['record']['correcta'])
        guardar_propiedades([{'id_origen':'all-fields','tipo_inmueble':'Departamento',
            'precio_usd':100000,'area_construida':100,'datos_crudos':{}}], 'remax')
        review.refresh_from_db()
        self.assertTrue(review.correcta)
        self.assertEqual(count('pendientes').paginator.count,0)
        self.save(correcta='false')
        self.assertEqual(count('pendientes').paginator.count,1)
