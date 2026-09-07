import json
from datetime import timedelta
from unittest.mock import MagicMock, patch
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from prospects.models import MobileProspectUser, MobileNotificationDevice, MobileAppVersion
from prospects.propify_auth import PropifyPrincipal
from prospects import control_api, app_updates
from .models import LeadControlPolicy, LeadControlMember
from .control_engine import observe
from .test_lead_control import NOW, snapshot


class MobileControlTests(TestCase):
    def setUp(self):
        self.policy = LeadControlPolicy.objects.create(pk=1, active_statuses=['Nuevo'], closed_statuses=['Ganado'], weekdays=[0,1,2,3,4], stale_minutes=60)
        self.member = LeadControlMember.objects.create(name='Agente', identity_type='propify', identity_id='70', source_user_id=7, role='agent')
        self.user = MobileProspectUser.objects.create(username='mobile', propify_user_id='70')
        self.principal = PropifyPrincipal(self.user, {'id':'70'}, 'fixture')
        self.state = observe(snapshot(), self.policy, NOW)
        self.item = self.state.obligations.get(kind='first_response')

    def request(self, method, data=None):
        request = getattr(APIRequestFactory(), method)('/', data or {}, format='json')
        force_authenticate(request, user=self.principal)
        return request

    def test_filters_pagination_and_stale_do_not_accuse_agent(self):
        with patch('prospects.control_api.timezone.now', return_value=NOW+timedelta(hours=2)):
            result = control_api.alerts(self.request('get')).data
            self.assertEqual(result['total'], 1)
            self.assertFalse(result['results'][0]['fresh'])
            self.assertFalse(result['results'][0]['overdue'])
            self.assertEqual(control_api.alerts(self.request('get', {'urgent':'1'})).data['total'], 0)
        self.assertEqual(control_api.alerts(self.request('get', {'offset':'-1'})).status_code, 400)
        self.assertEqual(control_api.alerts(self.request('get', {'status':'invented'})).status_code, 400)
        self.assertEqual(control_api.alerts(self.request('get', {'offset':'1', 'limit':'1'})).data['results'], [])

    def test_complete_parses_lima_date_and_creates_next_obligation(self):
        data = {'operation':'complete', 'notes':'Llamada realizada', 'evidence_type':'call', 'evidence_reference':'Registro 17', 'next_contact_at':'2026-09-08T11:30:00-05:00'}
        with patch('django.utils.timezone.now', return_value=NOW):
            response = control_api.alert_detail(self.request('post', data), self.item.pk)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['alert']['status'], 'closed')
        self.assertEqual(self.state.obligations.filter(kind='commitment').count(), 1)

    def test_invalid_date_and_exception_permissions(self):
        response = control_api.alert_detail(self.request('post', {'operation':'complete','next_contact_at':'bad'}), self.item.pk)
        self.assertEqual(response.status_code, 400)
        response = control_api.alert_detail(self.request('post', {'operation':'dismiss','notes':'No aplica'}), self.item.pk)
        self.assertEqual(response.status_code, 400)

    def test_device_logout_scoped_to_current_account(self):
        device = MobileNotificationDevice.objects.create(user=self.user, registration_id='fid-example-12345')
        request = self.request('delete', {'registration_id':device.registration_id})
        self.assertEqual(control_api.register_device(request).status_code, 200)
        device.refresh_from_db(); self.assertFalse(device.active)
        other = MobileProspectUser.objects.create(username='other')
        device.user, device.active = other, True; device.save()
        control_api.register_device(self.request('delete', {'registration_id':device.registration_id}))
        device.refresh_from_db(); self.assertTrue(device.active)


class MobileReleaseTests(TestCase):
    def post(self, data, auth='Bearer '+('x'*40)):
        return app_updates.publish_api(RequestFactory().post('/', json.dumps(data), content_type='application/json', HTTP_AUTHORIZATION=auth))

    @patch('prospects.app_updates.requests.get')
    def test_publishing_authenticated_idempotent_and_immutable(self, github_get):
        github_get.return_value = MagicMock(status_code=200)
        data = {'version_code':100, 'version_name':'1.1', 'min_supported_version_code':1, 'download_url':'https://example.com/app.apk','sha256':'a'*64}
        self.assertEqual(self.post(data, 'Bearer wrong').status_code, 403)
        self.assertEqual(self.post(data).status_code, 201)
        self.assertEqual(self.post(data).status_code, 200)
        self.assertEqual(MobileAppVersion.objects.count(), 1)
        data['sha256'] = 'b'*64
        self.assertEqual(self.post(data).status_code, 409)

    def test_bad_release_cannot_be_published(self):
        self.assertFalse(app_updates.ReleaseForm({'version_code':10, 'min_supported_version_code':20, 'download_url':'http://example.com/app.apk', 'sha256':''}).is_valid())
