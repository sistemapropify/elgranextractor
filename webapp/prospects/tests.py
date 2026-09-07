from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .mobile_api import mobile_capture_detail
from .models import PropertyProspect
from .views import ProcessImageView, ProspectDetailView


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
