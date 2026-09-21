from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .mobile_api import mobile_capture_detail
from .forms import ProspectEditForm, district_from_address
from .models import PropertyProspect
from .views import ProcessImageView, ProspectDetailView, _datos_completos, propify_login


class ProspectLoginNavigationTests(SimpleTestCase):
    @patch('prospects.views.get_web_propify_principal', return_value=None)
    def test_login_form_keeps_requested_capture(self, get_principal):
        request = RequestFactory().get('/prospects/login/', {'next': '/prospects/73/detail/'})
        request.session = SessionStore()

        response = propify_login(request)

        self.assertContains(response, 'name="next" value="/prospects/73/detail/"')

    @patch('prospects.views.authenticate_propify_credentials')
    def test_successful_login_returns_to_requested_capture(self, authenticate):
        authenticate.return_value = ({}, SimpleNamespace(token='test-token', profile={'username': 'viewer'}))
        request = RequestFactory().post('/prospects/login/', {
            'username': 'viewer', 'password': 'test-password', 'next': '/prospects/73/detail/',
        })
        request.session = SessionStore()

        response = propify_login(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/prospects/73/detail/')
        self.assertEqual(request.session['prospects_propify_access_token'], 'test-token')

    @patch('prospects.views.get_web_propify_principal', return_value=SimpleNamespace(username='viewer'))
    def test_existing_session_keeps_requested_capture(self, get_principal):
        request = RequestFactory().get('/prospects/login/', {'next': '/prospects/91/detail/'})

        self.assertEqual(propify_login(request).url, '/prospects/91/detail/')

    @patch('prospects.views.get_web_propify_principal', return_value=SimpleNamespace(username='viewer'))
    def test_default_and_login_destinations_open_dashboard(self, get_principal):
        for destination in ('', '/prospects/', '/prospects/login/'):
            with self.subTest(destination=destination):
                request = RequestFactory().get('/prospects/login/', {'next': destination})
                self.assertEqual(propify_login(request).url, '/marketing/prospeccion/')

    @patch('prospects.views.get_web_propify_principal', return_value=SimpleNamespace(username='viewer'))
    def test_external_redirect_is_rejected(self, get_principal):
        for destination in ('https://outside.example/capture', '//outside.example/capture'):
            with self.subTest(destination=destination):
                request = RequestFactory().get('/prospects/login/', {'next': destination})
                self.assertEqual(propify_login(request).url, '/marketing/prospeccion/')


class SharedProspectAccessTests(SimpleTestCase):
    """Las captaciones son un espacio colaborativo entre usuarios Propify."""

    @patch('prospects.views.get_object_or_404')
    def test_detail_looks_up_capture_globally(self, get_object):
        expected = SimpleNamespace(pk=73)
        get_object.return_value = expected

        result = ProspectDetailView().get_prospect(
            SimpleNamespace(propify_user=SimpleNamespace(username='viewer')),
            expected.pk,
        )

        self.assertIs(result, expected)
        get_object.assert_called_once_with(PropertyProspect, pk=expected.pk)

    @patch('prospects.views.get_object_or_404')
    def test_mobile_processing_looks_up_capture_globally(self, get_object):
        prospect = SimpleNamespace(pk=91, photo=None)
        get_object.return_value = prospect
        request = RequestFactory().post(
            f'/prospects/{prospect.pk}/process/',
            HTTP_USER_AGENT='Mozilla/5.0 (Linux; Android 14) Mobile',
        )

        response = ProcessImageView().post(request, prospect.pk)

        get_object.assert_called_once_with(PropertyProspect, pk=prospect.pk)
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content,
            {'ok': False, 'error': 'No hay foto asociada.'},
        )

    @patch('prospects.mobile_api._apply_mobile_fields')
    @patch('prospects.mobile_api.get_object_or_404')
    def test_android_api_can_update_another_users_capture(
        self,
        get_object,
        apply_fields,
    ):
        prospect = MagicMock(pk=115, status='pendiente')
        get_object.return_value = prospect
        request = APIRequestFactory().put(
            f'/prospects/api/mobile/captures/{prospect.pk}/',
            {},
            format='multipart',
        )
        force_authenticate(
            request,
            user=SimpleNamespace(
                is_authenticated=True,
                username='viewer@propify.pe',
                mobile_user=SimpleNamespace(pk=8),
            ),
            token='test-token',
        )

        response = mobile_capture_detail(request, prospect.pk)

        get_object.assert_called_once_with(PropertyProspect, pk=prospect.pk)
        apply_fields.assert_called_once()
        prospect.full_clean.assert_called_once_with()
        prospect.save.assert_called_once_with()
        self.assertEqual(response.status_code, 200)


class ProspectCompletionTests(SimpleTestCase):
    def complete(self, **overrides):
        values = {
            'district': 'Cayma', 'owner_name': 'Propietario', 'phone': '904030700',
            'operation_type': 'venta', 'contract_type': 'trato_directo',
            'property_type': 'terreno', 'price': 140000, 'currency': 'USD',
            'bedrooms': None, 'area_m2': 180,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_land_is_complete_without_bedrooms(self):
        self.assertTrue(_datos_completos(self.complete()))

    def test_house_still_requires_bedrooms(self):
        self.assertFalse(_datos_completos(self.complete(property_type='casa')))

    def test_missing_district_or_owner_prevents_green_border(self):
        self.assertFalse(_datos_completos(self.complete(district='')))
        self.assertFalse(_datos_completos(self.complete(owner_name='')))

    def test_land_clears_stale_bedrooms_during_validation(self):
        prospect = PropertyProspect(property_type='terreno', bedrooms=4)
        prospect.clean()
        self.assertIsNone(prospect.bedrooms)

    def test_editing_land_clears_bedrooms_and_infers_cayma(self):
        form = ProspectEditForm(data={
            'origin': 'calle', 'owner_name': 'Propietario', 'phone': '904030700',
            'operation_type': 'venta', 'contract_type': 'trato_directo',
            'property_type': 'terreno', 'price': '140000', 'currency': 'USD',
            'bedrooms': '4', 'area_m2': '180',
            'address': 'MFG5+CHR Cayma, Perú', 'district': '',
            'latitude': '', 'longitude': '', 'status': 'pendiente', 'captado': '0',
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        saved = form.save(commit=False)
        self.assertEqual(saved.district, 'Cayma')
        self.assertIsNone(saved.bedrooms)

    def test_district_inference_does_not_guess_generic_arequipa(self):
        self.assertEqual(district_from_address('Arequipa, Perú'), '')

    def test_capture_template_with_not_applicable_state_compiles(self):
        self.assertIsNotNone(get_template('prospects/capture.html'))
