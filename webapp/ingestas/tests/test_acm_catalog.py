from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import SimpleTestCase, TestCase, RequestFactory, override_settings
from django.template.loader import render_to_string

from acm.catalog import annotate_catalog
from acm.components_engine import candidates, calculate, parameters
from ingestas.models import PropiedadesCompetencia, RevisionPropiedadScraping
from ingestas.property_quality_views import dashboard


def listing(**changes):
    data = dict(id=1, fuente='remax', id_origen='catalogue-1', titulo='Casa en venta',
        tipo_inmueble='Casa', tipo_operacion='Venta', precio_usd=200000,
        area_terreno=200, area_construida=120, latitud=-16.4, longitud=-71.5,
        precision_ubicacion='exacta', estado_publicacion='activa', distrito='Cayma',
        url='https://www.remax.pe/property/venta/1', excluida=False, correcta=False)
    return {**data, **changes}


class CatalogPolicyTests(SimpleTestCase):
    def test_manual_review_is_not_required_and_missing_age_is_optional(self):
        row = annotate_catalog(listing())
        self.assertTrue(row['acm_primary'])
        self.assertFalse(row['correcta'])

    def test_reference_route_matches_actual_fallback_including_retired_limitation(self):
        row = annotate_catalog(listing(estado_publicacion='retirada'))
        self.assertEqual(row['acm_status'], 'referencia')
        p = parameters(dict(property_type='Casa',lat=-16.4,lng=-71.5,radius=300,
            max_radius=300,land=200,built=120,sources=['remax']))
        records = candidates([dict(id='remax-1',source='remax',kind='Casa',title=row['titulo'],
            operation='Venta',price=200000,land=200,built=120,lat=-16.4,lng=-71.5,
            state='retirada',precision='exacta',url=row['url'])], p)
        result = calculate(records,p)
        self.assertEqual(result['reference_ids'], ['remax-1'])
        self.assertTrue(result['reference_mode'])

    def test_exclusions_rentals_bad_coordinates_and_disabled_sources_never_enter(self):
        for fields in ({'excluida':True}, {'tipo_operacion':'Alquiler','titulo':'Casa alquiler',
                      'url':'https://www.remax.pe/property/alquiler/1'},
                      {'latitud':None}, {'latitud':'nan'}, {'fuente':'urbania'},
                      {'tipo_inmueble':'Local'}, {'precio_usd':0}, {'area_construida':None}):
            with self.subTest(fields=fields):
                self.assertFalse(annotate_catalog(listing(**fields))['acm_available'])

    def test_original_rental_title_overrides_synthetic_sale_title(self):
        row = annotate_catalog(listing(original_listing_title='Casa en alquiler'))
        self.assertFalse(row['acm_available'])

    def test_land_requires_land_area_but_not_built_area(self):
        row = annotate_catalog(listing(tipo_inmueble='Terreno',area_construida=None,
                                      titulo='Terreno en venta'))
        self.assertTrue(row['acm_primary'])

    def test_unsafe_link_is_never_rendered_as_an_announcement(self):
        row = annotate_catalog(listing(url='javascript:alert(1)'))
        self.assertEqual(row['acm_listing_url'], '')


class CatalogDashboardTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True,is_active=True,is_staff=True,
                                    has_perm=lambda permission:True)
        values = listing()
        for key in ('id','excluida','correcta'):
            values.pop(key)
        self.property = PropiedadesCompetencia.objects.create(**values)

    def request(self, params):
        request = self.factory.get('/ingestas/scraping/calidad/',params)
        request.current_user = self.user
        return request

    def context(self, params=None, propify=None):
        with patch('ingestas.property_quality_views.propify_catalog_rows',return_value=propify or []), \
             patch('ingestas.property_quality_views.render',return_value=HttpResponse('ok')) as render:
            dashboard(self.request(params or {'estado':'acm'}))
        return render.call_args.args[2]

    def test_complete_catalog_is_paginated_and_csv_exports_every_page(self):
        for index in range(57):
            PropiedadesCompetencia.objects.create(**{
                **{field:getattr(self.property,field) for field in
                   ('fuente','titulo','tipo_inmueble','tipo_operacion','precio_usd','area_terreno',
                    'area_construida','latitud','longitud','precision_ubicacion','estado_publicacion','distrito','url')},
                'id_origen':f'extra-{index}'})
        context = self.context({'estado':'acm','portal':'remax','page':'2'})
        self.assertEqual(context['page'].paginator.count,58)
        self.assertEqual(len(context['page']),8)
        response = dashboard(self.request({'estado':'acm','portal':'remax','exportar':'csv'}))
        self.assertEqual(len(response.content.decode('utf-8-sig').splitlines()),59)

    def test_default_lists_all_even_excluded_retired_and_manually_reviewed(self):
        RevisionPropiedadScraping.objects.create(propiedad=self.property,correcta=True,excluida=True,motivo='Revisar')
        self.property.estado_publicacion='retirada';self.property.save()
        context=self.context({'portal':'remax'})
        self.assertEqual(context['filters']['estado'],'todas')
        self.assertEqual(context['page'].paginator.count,1)
        self.assertFalse(context['page'][0]['acm_available'])

    def test_automatic_alerts_are_independent_of_manual_approval(self):
        self.assertEqual(self.context({'estado':'sin_alertas'})['page'].paginator.count,1)
        self.assertEqual(self.context({'estado':'correctas'})['page'].paginator.count,0)
        self.property.area_terreno=20;self.property.save()
        RevisionPropiedadScraping.objects.create(propiedad=self.property,correcta=True)
        self.assertEqual(self.context({'estado':'con_alertas'})['page'].paginator.count,1)
        self.assertEqual(self.context({'estado':'sin_alertas'})['page'].paginator.count,0)
        self.assertEqual(self.context({'estado':'correctas'})['page'].paginator.count,1)

    def test_all_filters_restrict_same_reviewable_list(self):
        for fields, expected in [({'portal':'remax','tipo':'Casa','distrito':'Cayma','operacion':'Venta'},1),
                                 ({'distrito':'Yanahuara'},0),({'tipo':'Departamento'},0),
                                 ({'operacion':'Alquiler'},0),({'portal':'properati'},0),
                                 ({'pub_estado':'retirada'},0)]:
            with self.subTest(fields=fields):
                self.assertEqual(self.context({'estado':'todas',**fields})['page'].paginator.count,expected)

    def test_correctas_stays_manual_and_catalog_includes_unreviewed(self):
        self.assertEqual(self.context()['page'].paginator.count,1)
        self.assertEqual(self.context({'estado':'correctas'})['page'].paginator.count,0)
        RevisionPropiedadScraping.objects.create(propiedad=self.property,correcta=True)
        self.assertEqual(self.context({'estado':'correctas'})['page'].paginator.count,1)

    def test_reference_route_is_separate_and_exclusion_removes_record(self):
        self.property.estado_publicacion='retirada';self.property.save()
        context = self.context({'estado':'acm','acm_ruta':'referencia','portal':'remax'})
        self.assertEqual(context['page'].paginator.count,1)
        self.assertEqual(context['summary']['acm_principal'],0)
        self.assertEqual(self.context({'estado':'acm','acm_ruta':'principal'})['page'].paginator.count,0)
        RevisionPropiedadScraping.objects.create(propiedad=self.property,excluida=True,motivo='Revisar')
        self.assertEqual(self.context()['page'].paginator.count,0)

    def test_propify_joins_catalog_and_filters_preserve_source(self):
        propify = listing(id='propify-8',fuente='propify',id_origen='P008',correcta=False,
                          ia_veredicto=None,motivo='')
        self.assertEqual(self.context(propify=[propify])['page'].paginator.count,2)
        context=self.context({'estado':'acm','portal':'propify'},propify=[propify])
        self.assertEqual(context['page'].paginator.count,1)
        self.assertEqual(context['page'][0]['fuente'],'propify')

    def test_propify_failure_is_visible_and_does_not_claim_complete_catalog(self):
        with patch('ingestas.property_quality_views.propify_catalog_rows',side_effect=TimeoutError), \
             patch('ingestas.property_quality_views.render',return_value=HttpResponse()) as render:
            dashboard(self.request({'estado':'acm'}))
        self.assertIn('incompleto',render.call_args.args[2]['catalog_warnings'][0])

    def test_inactive_user_cannot_read_catalog(self):
        request = self.request({'estado':'acm'});request.current_user.is_active=False
        with patch('ingestas.property_quality_views.propify_catalog_rows') as source:
            self.assertEqual(dashboard(request).status_code,401)
        source.assert_not_called()

    def test_body_links_each_listing_gallery_and_individual_editor(self):
        context=self.context()
        from django.conf import settings
        configured=deepcopy(settings.TEMPLATES)
        configured[0]['APP_DIRS']=False
        configured[0]['OPTIONS']={'loaders':[
            ('django.template.loaders.locmem.Loader',{'propifai_base.html':
                '{% block extra_head %}{% endblock %}{% block content %}{% endblock %}'}),
            'django.template.loaders.filesystem.Loader']}
        with override_settings(TEMPLATES=configured):
            html=render_to_string('ingestas/property_quality.html',context)
        self.assertIn('Base de propiedades del ACM',html)
        self.assertIn('Fotos y captura',html)
        self.assertIn(f'openScrapedEditor({self.property.pk})',html)
        self.assertIn('Ver publicación',html)
        self.assertIn('catalogue-1',html)


class EmbeddedEvidenceTests(TestCase):
    def setUp(self):
        self.property=PropiedadesCompetencia.objects.create(fuente='remax',id_origen='capture-test',
            titulo='Publicación de prueba')
        self.factory=RequestFactory()
        self.user=SimpleNamespace(is_active=True,is_authenticated=True)

    def response(self, authenticated=True):
        from ingestas.views import ScrapingCaptureView
        request=self.factory.get('/ingestas/scraping/propiedades/1/captura/?embedded=1')
        request.current_user=self.user if authenticated else None
        request.user=SimpleNamespace(is_authenticated=False)
        return ScrapingCaptureView.as_view()(request,pk=self.property.pk)

    def test_missing_capture_explained_in_private_same_origin_frame(self):
        response=self.response();response.render()
        self.assertEqual(response['X-Frame-Options'],'SAMEORIGIN')
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertContains(response,'No hay una captura disponible')
        self.assertNotContains(response,'Volver al scraper')
        self.assertNotContains(response,'propifai-sidebar')

    def test_anonymous_cannot_read_capture(self):
        with override_settings(LOGIN_URL='/login/'):
            self.assertEqual(self.response(False).status_code,302)
