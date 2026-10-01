"""Context endpoints: permission/CSRF, bounded map scope and version freshness."""
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.template import Context, engines
from django.test import RequestFactory, SimpleTestCase, TestCase

from ingestas import ml_candidates, ml_context, ml_context_views as views
from ingestas.models import (MLCandidate, MLIdentityDecision, MLIdentityPair, MLObservation,
                            MLSpatialAssessment, MLZoneVersion, PropiedadesCompetencia)


BOUNDS = {'south': '-16.5', 'west': '-71.6', 'north': '-16.3', 'east': '-71.4'}
CATALOG = 'a' * 64


def user(staff=True):
    return SimpleNamespace(pk=7, username='reviewer', is_authenticated=True, is_active=True,
                           is_staff=staff, has_perm=lambda permission: staff)


class ContextViewValidationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, method='get', data=None, csrf_bypass=True, staff=True):
        request = getattr(self.factory, method)('/context/', data=data or {})
        request.current_user = user(staff)
        request._dont_enforce_csrf_checks = csrf_bypass
        return request

    def test_anonymous_reads_and_inactive_users_rejected_without_querying(self):
        request = self.factory.get('/map/', BOUNDS)
        self.assertEqual(views.map_data(request).status_code, 401)
        self.assertEqual(views.dashboard(request).status_code, 401)
        request.current_user = user()
        request.current_user.is_active = False
        self.assertEqual(views.map_data(request).status_code, 401)

    def test_map_requires_finite_ordered_bbox_and_valid_record_and_layers(self):
        cases = [{}, {**BOUNDS, 'south': 'NaN'}, {**BOUNDS, 'west': '-Infinity'},
                 {**BOUNDS, 'north': '-17'}, {**BOUNDS, 'east': '181'},
                 {**BOUNDS, 'record': '1 OR 1=1'}, {**BOUNDS, 'record': '0'},
                 {**BOUNDS, 'record': '9223372036854775808'},
                 {**BOUNDS, 'layers': 'all'}, {**BOUNDS, 'west': '-71', 'east': '-72'}]
        with patch.object(ml_context, 'schema_ready') as ready:
            for params in cases:
                with self.subTest(params=params):
                    self.assertEqual(views.map_data(self.request(data=params)).status_code, 400)
        ready.assert_not_called()

    def test_no_selected_layers_is_an_empty_bounded_response(self):
        with patch.object(ml_context, 'schema_ready', return_value=True), patch.object(views, '_candidates') as query:
            response = views.map_data(self.request(data=BOUNDS))
        data = json.loads(response.content)
        self.assertEqual((data['features'], data['shown'], data['total']), ([], 0, 0))
        query.assert_not_called()
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_schema_pending_gives_explicit_unavailable_response(self):
        with patch.object(ml_context, 'schema_ready', return_value=False):
            response = views.map_data(self.request(data={**BOUNDS, 'layers': 'eligible'}))
        self.assertEqual(response.status_code, 503)
        self.assertFalse(json.loads(response.content)['ready'])

    def test_publication_links_are_http_only_without_credentials(self):
        for value in ('javascript:alert(1)', 'data:text/html,hi', '//evil.test/path',
                      'https://user:secret@urbania.pe/item/1', 'https://x.test:bad/a',
                      'https://x.test/\nthing', 'https://x.test\\@evil.test/a', None):
            self.assertEqual(views.safe_publication(value), '')
        self.assertEqual(views.safe_publication('https://urbania.pe/inmueble/123?a=1&b=2'),
                         'https://urbania.pe/inmueble/123?a=1&b=2')

    def test_write_permission_and_post_only(self):
        request = self.request('post', {'revision': 1, 'decision': 'same', 'reason': 'Verificado'}, staff=False)
        self.assertEqual(views.decide(request, 1).status_code, 403)
        self.assertEqual(views.decide(self.request(), 1).status_code, 405)

    def test_missing_csrf_token_rejected(self):
        request = self.request('post', {'revision': 1, 'decision': 'same', 'reason': 'Verificado'}, csrf_bypass=False)
        with patch.object(ml_context, 'decide_pair') as decide:
            self.assertEqual(views.decide(request, 1).status_code, 403)
        decide.assert_not_called()

    def test_valid_multipart_csrf_and_actor_from_session(self):
        request = self.request('post', {'revision': 3, 'decision': 'different', 'reason': 'Pisos y unidades distintos',
                                        'actor': 'spoofed'}, csrf_bypass=False)
        token = get_token(request)
        request.COOKIES[settings.CSRF_COOKIE_NAME] = request.META['CSRF_COOKIE']
        request.META['HTTP_X_CSRFTOKEN'] = token
        with patch.object(ml_context, 'schema_ready', return_value=True), patch.object(ml_context, 'decide_pair') as decide:
            response = views.decide(request, 9)
        self.assertEqual(response.status_code, 200)
        decide.assert_called_once_with(9, 3, 'different', 'Pisos y unidades distintos', 'reviewer')

    def test_malformed_decisions_and_revision_rejected_without_service(self):
        for payload in ([], {'revision': 1, 'decision': {}, 'reason': 'a'},
                        {'revision': True, 'decision': 'same', 'reason': 'a'},
                        {'revision': 1, 'decision': 'same', 'reason': ' '},
                        {'revision': 1, 'decision': 'same', 'reason': 'a' * 2001}):
            request = self.factory.post('/decide/', data=json.dumps(payload), content_type='application/json')
            request.current_user = user()
            request._dont_enforce_csrf_checks = True
            with patch.object(ml_context, 'schema_ready', return_value=True), patch.object(ml_context, 'decide_pair') as decide:
                self.assertEqual(views.decide(request, 1).status_code, 400)
                decide.assert_not_called()

    def test_changed_evidence_returns_conflict(self):
        request = self.request('post', {'revision': 1, 'decision': 'same', 'reason': 'Verificado'})
        with patch.object(ml_context, 'schema_ready', return_value=True), \
                patch.object(ml_context, 'decide_pair', side_effect=RuntimeError('stale')):
            self.assertEqual(views.decide(request, 1).status_code, 409)


class ContextMapIntegrationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        ml_candidates._schema_cache = (0, False)
        ml_context._schema_cache = (0, False)
        self.catalog_patch = patch.object(ml_context, 'current_catalog_hash', return_value=CATALOG)
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)

    def make_candidate(self, key, status='eligible', **changes):
        data = dict(fuente='remax', id_origen=key, titulo='Casa de prueba', tipo_inmueble='Casa',
                    tipo_operacion='Venta', precio_usd=Decimal('300000'), area_terreno=200,
                    area_construida=180, latitud=Decimal('-16.4'), longitud=Decimal('-71.5'),
                    precision_ubicacion='exacta', direccion_texto='Los Cedros 327',
                    url='https://www.remax.pe/web/search/property/1198201/')
        data.update(changes)
        source = PropiedadesCompetencia.objects.create(**data)
        ml_candidates.capture(source.pk, origin='test')
        candidate = MLCandidate.objects.get(propiedad=source)
        candidate.status = status
        candidate.save(update_fields=['status'])
        return candidate

    def request(self, params=None):
        request = self.factory.get('/map/', {**BOUNDS, 'layers': 'eligible', **(params or {})})
        request.current_user = user()
        return request

    def map(self, params=None):
        response = views.map_data(self.request(params))
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def pair(self, left, right, **changes):
        return MLIdentityPair.objects.create(left_id=left.propiedad_id, right_id=right.propiedad_id,
            left_observation=left.latest, right_observation=right.latest,
            left_signature='l', right_signature='r', rule_version=ml_context.IDENTITY_RULE_VERSION,
            score=95, evidence=[{'code': 'identity.test', 'message': 'Evidencia para revisar'}], **changes)

    def context(self, candidate, **changes):
        zone, _ = MLZoneVersion.objects.get_or_create(zone_key=99, sequence=1,
            defaults={'content_hash': 'z' * 64,
                      'snapshot': {'nombre_zona': 'Microzona de prueba', 'codigo': 'Z1', 'id': 99}})
        data = dict(observation=candidate.latest, catalog_hash=CATALOG,
                    rule_version=ml_context.LOCATION_RULE_VERSION, state='exact_zone', zone_version=zone,
                    evidence=[{'message': 'Polígono de prueba.'}])
        data.update(changes)
        assessment = MLSpatialAssessment.objects.create(**data)
        candidate.context = assessment
        candidate.save(update_fields=['context'])
        return assessment

    def test_bbox_status_record_and_missing_context(self):
        candidate = self.make_candidate('inside')
        self.make_candidate('outside', latitud=-12)
        self.make_candidate('reference', status='reference', precision_ubicacion='aproximada')
        data = self.map()
        self.assertEqual(data['total'], 1)
        feature = data['features'][0]
        self.assertEqual((feature['id'], feature['geo_status'], feature['zone_name']),
                         (candidate.propiedad_id, 'pending', ''))
        self.assertEqual(feature['price_usd'], 300000)
        self.assertEqual(len(self.map({'layers': 'eligible,reference'})['features']), 2)
        self.assertEqual(self.map({'record': candidate.propiedad_id})['shown'], 1)
        self.assertEqual(self.map({'record': 9223372036854775807})['shown'], 0)

    def test_feature_exposes_type_and_district_for_the_map_filters(self):
        self.make_candidate('type-casa', distrito='Cayma')
        self.make_candidate('type-departamento', tipo_inmueble='Departamento', distrito='Cerro Colorado')
        data = self.map()
        self.assertEqual(sorted((item['property_type'], item['district']) for item in data['features']),
                         [('Casa', 'Cayma'), ('Departamento', 'Cerro Colorado')])

    def test_record_lookup_ignores_the_visible_area(self):
        candidate = self.make_candidate('moved-away', latitud=-13.5, longitud=-71.9)
        data = self.map({'record': candidate.propiedad_id})
        self.assertEqual((data['shown'], data['features'][0]['id']),
                         (1, candidate.propiedad_id))

    def test_current_context_shows_zone_version(self):
        candidate = self.make_candidate('zoned')
        self.context(candidate)
        feature = self.map()['features'][0]
        self.assertEqual((feature['geo_status'], feature['zone_name'], feature['zone_version']),
                         ('exact_zone', 'Microzona de prueba', 1))

    def test_changed_catalog_never_shows_old_zone_as_valid(self):
        candidate = self.make_candidate('old-zone')
        self.context(candidate, catalog_hash='old')
        feature = self.map()['features'][0]
        self.assertEqual((feature['geo_status'], feature['zone_name'], feature['zone_version']), ('stale', '', None))

    def test_changed_observation_never_shows_old_context_as_valid(self):
        candidate = self.make_candidate('old-observation')
        self.context(candidate)
        source = candidate.propiedad
        source.precio_usd = 310000
        source.save(update_fields=['precio_usd'])
        ml_candidates.capture(source.pk, origin='test')
        MLCandidate.objects.filter(pk=candidate.pk).update(status='eligible')
        feature = self.map()['features'][0]
        self.assertEqual(feature['geo_status'], 'pending')
        self.assertEqual(feature['zone_name'], '')

    def test_live_coordinates_do_not_move_snapshot_pin_and_pending_source_is_visible(self):
        candidate = self.make_candidate('bulk-edit')
        self.context(candidate)
        PropiedadesCompetencia.objects.filter(pk=candidate.propiedad_id).update(latitud=-16.41)
        feature = self.map()['features'][0]
        self.assertEqual(feature['lat'], -16.4)
        self.assertEqual(feature['geo_status'], 'stale')

    def test_snapshot_outside_viewport_is_omitted_explicitly(self):
        candidate = self.make_candidate('old-coordinate', latitud=-12)
        PropiedadesCompetencia.objects.filter(pk=candidate.propiedad_id).update(latitud=-16.4)
        data = self.map()
        self.assertEqual((data['shown'], data['omitted_stale_coordinates']), (0, 1))

    def test_duplicate_layer_does_not_require_candidate_layer(self):
        left = self.make_candidate('left', status='reference')
        right = self.make_candidate('right', status='review')
        self.make_candidate('other')
        pair = self.pair(left, right)
        data = self.map({'layers': 'duplicates'})
        self.assertEqual(data['total'], 2)
        self.assertTrue(all(item['duplicate_count'] == 1 for item in data['features']))
        pair.status = 'different'
        pair.save(update_fields=['status'])
        self.assertEqual(self.map({'layers': 'duplicates'})['total'], 0)
        pair.decision_stale = True
        pair.save(update_fields=['decision_stale'])
        self.assertEqual(self.map({'layers': 'duplicates'})['total'], 2)

    def test_stale_pair_observations_do_not_count_as_current_evidence(self):
        left = self.make_candidate('left-stale')
        right = self.make_candidate('right-stale')
        self.pair(left, right)
        right.propiedad.precio_usd = 310000
        right.propiedad.save(update_fields=['precio_usd'])
        ml_candidates.capture(right.propiedad_id, origin='test')
        self.assertEqual(self.map({'layers': 'duplicates'})['total'], 0)

    def test_map_returns_every_matching_candidate_in_deterministic_order(self):
        sources = [PropiedadesCompetencia(fuente='remax', id_origen=f'cap-{i}', latitud=-16.4,
                                         longitud=-71.5, precision_ubicacion='exacta') for i in range(4)]
        PropiedadesCompetencia.objects.bulk_create(sources)
        observations = [MLObservation(propiedad=source, sequence=1, content_hash=str(source.pk),
            rule_version='test', snapshot={'fuente': source.fuente, 'id_origen': source.id_origen,
            'latitud': '-16.4', 'longitud': '-71.5', 'precision_ubicacion': 'exacta'}) for source in sources]
        MLObservation.objects.bulk_create(observations)
        MLCandidate.objects.bulk_create([MLCandidate(propiedad=source, latest=observation, status='eligible')
                                        for source, observation in zip(sources, observations)])
        data = self.map()
        self.assertEqual((data['total'], data['shown']), (4, 4))
        self.assertEqual([item['id'] for item in data['features']], sorted(source.pk for source in sources))

    def test_dashboard_filters_record_and_renders_review_editor_once(self):
        left, right = self.make_candidate('panel-left'), self.make_candidate('panel-right')
        self.pair(left, right)
        request = self.request({'record': left.propiedad_id})
        with patch.object(views, 'render', return_value=HttpResponse('ok')) as render:
            self.assertEqual(views.dashboard(request).status_code, 200)
        context = render.call_args.args[2]
        self.assertEqual(context['context_page'].paginator.count, 1)
        self.assertEqual(context['pair_page'].paginator.count, 1)
        template = engines['django'].engine.get_template('ingestas/ml_context_panel.html')
        html = template.render(Context(context))
        self.assertEqual(html.count('id="scraped-editor"'), 1)
        self.assertIn('aún no entrenado', html)
        self.assertIn('ml_lat=-16.4', html)
        self.assertIn('ml-identity-form', html)

    def test_human_decision_is_audited_without_merging_properties(self):
        left, right = self.make_candidate('audit-left'), self.make_candidate('audit-right')
        pair = self.pair(left, right)
        request = self.factory.post('/decide/', {'revision': pair.revision, 'decision': 'same',
                                                'reason': 'Comprobadas la unidad y las fotos'})
        request.current_user = user()
        request._dont_enforce_csrf_checks = True
        self.assertEqual(views.decide(request, pair.pk).status_code, 200)
        pair.refresh_from_db()
        self.assertEqual(pair.status, 'same')
        self.assertEqual(MLIdentityDecision.objects.get(pair=pair).actor, 'reviewer')
        self.assertEqual(PropiedadesCompetencia.objects.count(), 2)
        self.assertEqual(views.decide(request, pair.pk).status_code, 409)

    def test_coverage_counts_announcements_by_current_zone_and_keeps_unassigned_pending(self):
        eligible = self.make_candidate('coverage-eligible')
        review = self.make_candidate('coverage-review', status='review')
        approximate = self.make_candidate('coverage-reference', status='reference', precision_ubicacion='aproximada')
        pending = self.make_candidate('coverage-pending', status='pending')
        stale = self.make_candidate('coverage-stale', status='excluded')
        self.context(eligible)
        self.context(review)
        self.context(approximate, state='approximate_reference', zone_version=None)
        self.context(stale, catalog_hash='old-catalog')
        coverage = views._coverage(CATALOG)
        self.assertEqual(coverage['total'], 5)
        self.assertEqual(coverage['zones'].paginator.count, 1)
        zone = list(coverage['zones'])[0]
        self.assertEqual((zone['total'], zone['eligible'], zone['review']), (2, 1, 1))
        self.assertEqual((coverage['unassigned']['total'], coverage['unassigned']['reference']), (1, 1))
        self.assertEqual((coverage['pending']['total'], coverage['pending']['pending'], coverage['pending']['excluded']), (2, 1, 1))

    def test_coverage_changed_catalog_marks_all_old_assignments_pending(self):
        candidate = self.make_candidate('coverage-new-catalog')
        self.context(candidate)
        coverage = views._coverage('new-catalog')
        self.assertEqual((coverage['total'], coverage['pending']['total']), (1, 1))
        self.assertEqual(coverage['zones'].paginator.count, 0)

    def test_archived_rejected_pairs_remain_readable_in_history(self):
        left, right = self.make_candidate('history-left'), self.make_candidate('history-right')
        self.pair(left, right, status='different', active=False)
        for state, expected in (('active', 0), ('all', 1), ('different', 1)):
            with patch.object(views, 'render', return_value=HttpResponse('ok')) as render:
                response = views.dashboard(self.request({'pair_state': state}))
            self.assertEqual(response.status_code, 200)
            context = render.call_args.args[2]
            self.assertEqual(context['pair_page'].paginator.count, expected)
            if expected:
                self.assertFalse(list(context['pair_page'])[0].evidence_current)
