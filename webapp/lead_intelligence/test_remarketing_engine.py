import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase, SimpleTestCase, RequestFactory, override_settings
from django.template.loader import get_template

from .models import RemarketingCampaign, RemarketingDelivery, RemarketingEnrollment, RemarketingStep
from .remarketing_engine import eligibility, policy_for, enroll, claim, reconcile, record_result, dispatch
from .remarketing_forms import CampaignForm, render_message
from .remarketing_views import report_rows, campaign_edit, campaign_action, delivery_receipt, campaigns, deliveries_report


ANCHOR = datetime(2026, 9, 7, 15, tzinfo=dt_timezone.utc)  # Monday 10:00 Lima


def snapshot(lead_id=1):
    return {'lead_id': lead_id, 'closed': False, 'visit_intent': False, 'visit_scheduled': False, 'version': 'v1', 'contact_key': f'phone:{lead_id}', 'status_name': 'Contactado', 'channel_name': 'WhatsApp', 'agent_id': 7, 'nombre': 'Ana', 'propiedad': 'Casa', 'agente': 'Luis', 'contact_allowed': True, 'messages': [
        {'id': 'in', 'sender': 'lead', 'text': 'Información', 'timestamp': (ANCHOR-timedelta(minutes=10)).isoformat()},
        {'id': 'out', 'sender': 'agent', 'text': 'Aquí tienes los detalles', 'timestamp': ANCHOR.isoformat()},
    ]}


def make_campaign(**kwargs):
    data = dict(name='Prueba', status='active', allowed_statuses=['Contactado'], allowed_channels=['WhatsApp'], weekdays=[0, 1, 2, 3, 4], start_hour=0, end_hour=24)
    data.update(kwargs)
    campaign = RemarketingCampaign.objects.create(**data)
    for index, minutes in enumerate((120, 240, 360), 1):
        RemarketingStep.objects.create(campaign=campaign, title=f'Paso {index}', delay_minutes=minutes, body='Hola {{nombre}}, ¿revisaste {{propiedad}}?')
    return campaign


class EngineTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.snapshot = snapshot()
        self.enrollment, _ = enroll(self.campaign, self.snapshot, ANCHOR)
        self.first = self.enrollment.deliveries.first()

    def test_steps_are_absolute_and_content_is_snapshotted(self):
        self.assertEqual(list(self.enrollment.deliveries.values_list('due_at', flat=True)), [ANCHOR+timedelta(hours=n) for n in (2, 4, 6)])
        self.assertIn('Ana', self.first.body)
        self.campaign.steps.update(body='Changed')
        self.first.refresh_from_db()
        self.assertIn('Ana', self.first.body)

    def test_reenrollment_and_other_campaign_do_not_duplicate(self):
        enroll(self.campaign, self.snapshot, ANCHOR)
        other = make_campaign()
        duplicate = dict(self.snapshot, lead_id=999)
        enroll(other, duplicate, ANCHOR)
        self.assertEqual(RemarketingEnrollment.objects.count(), 1)
        self.assertEqual(RemarketingDelivery.objects.count(), 3)

    def test_last_customer_message_controls_24_hour_window(self):
        old = snapshot(2)
        old['messages'][0]['timestamp'] = (ANCHOR-timedelta(hours=23)).isoformat()
        enrollment, _ = enroll(self.campaign, old, ANCHOR)
        self.assertEqual(set(enrollment.deliveries.values_list('status', flat=True)), {'skipped'})

    def test_unknown_channel_never_enrolls(self):
        data = dict(snapshot(2), channel_name='Unknown')
        self.assertIsNone(enroll(self.campaign, data, ANCHOR)[0])

    def test_outbound_only_does_not_open_window(self):
        data = snapshot(2)
        data['messages'] = data['messages'][1:]
        self.assertIsNone(enroll(self.campaign, data, ANCHOR)[0])

    def test_rejection_and_visit_are_excluded(self):
        data = snapshot(2)
        data['messages'][0]['text'] = 'No me interesa'
        self.assertIsNone(enroll(self.campaign, data, ANCHOR)[0])
        self.assertIsNone(enroll(self.campaign, dict(snapshot(2), visit_intent=True), ANCHOR)[0])

    def test_late_receipt_can_credit_already_observed_response(self):
        now = ANCHOR+timedelta(hours=2)
        claim(self.first.pk, self.snapshot, now)
        record_result(self.first.pk, dict(status='accepted', message_id='1'), now)
        response_at = now+timedelta(minutes=30)
        self.snapshot['messages'].append(dict(sender='lead', text='Sí', timestamp=response_at.isoformat()))
        reconcile(self.enrollment, self.snapshot, response_at)
        record_result(self.first.pk, dict(status='sent', message_id='1', sent_at=now.isoformat()), response_at)
        reconcile(self.enrollment, self.snapshot, response_at)
        self.first.refresh_from_db()
        self.assertEqual(self.first.response_at, response_at)

    def test_gateway_confirmed_failure_is_distinct_from_timeout(self):
        now = ANCHOR+timedelta(hours=2)
        claim(self.first.pk, self.snapshot, now)
        record_result(self.first.pk, dict(status='failed', definitely_not_sent=True), now)
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, 'failed')

    def test_bot_does_not_count_as_human_contact(self):
        data = snapshot(2)
        data['messages'][1]['sender'] = 'bot'
        self.assertIsNone(enroll(self.campaign, data, ANCHOR)[0])

    def test_missing_variable_prevents_enrollment(self):
        with self.assertRaises(ValueError):
            enroll(self.campaign, dict(snapshot(2), propiedad=''), ANCHOR)

    def test_response_before_send_cancels_all(self):
        now = ANCHOR+timedelta(hours=2)
        self.snapshot['messages'].append({'sender': 'lead', 'text': 'Sí', 'timestamp': now.isoformat()})
        self.assertIsNone(claim(self.first.pk, self.snapshot, now))
        self.assertEqual(set(self.enrollment.deliveries.values_list('status', flat=True)), {'cancelled'})

    def test_claim_once_and_campaign_quota(self):
        now = ANCHOR+timedelta(hours=2)
        self.campaign.daily_limit = 1
        self.campaign.save()
        self.assertIsNotNone(claim(self.first.pk, self.snapshot, now))
        self.assertIsNone(claim(self.first.pk, self.snapshot, now))
        second, _ = enroll(self.campaign, snapshot(2), ANCHOR)
        self.assertIsNone(claim(second.deliveries.first().pk, snapshot(2), now))

    def test_recovery_skips_older_due_steps(self):
        now = ANCHOR+timedelta(hours=5)
        self.assertIsNone(claim(self.first.pk, self.snapshot, now))
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, 'skipped')
        self.assertIsNotNone(claim(self.enrollment.deliveries.get(position=2).pk, self.snapshot, now))

    def test_paused_campaign_never_claims(self):
        self.campaign.status = 'paused'
        self.campaign.save()
        self.assertIsNone(claim(self.first.pk, self.snapshot, ANCHOR+timedelta(hours=2)))

    def test_agent_intervention_cancels(self):
        now = ANCHOR+timedelta(hours=2)
        self.snapshot['messages'].append({'id': 'manual', 'sender': 'agent', 'text': 'Seguimos', 'timestamp': (now-timedelta(minutes=1)).isoformat()})
        self.assertIsNone(claim(self.first.pk, self.snapshot, now))
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'stopped')

    def test_weekday_and_hours_retain_step(self):
        self.enrollment.policy['weekdays'] = [1]
        self.enrollment.save()
        self.assertIsNone(claim(self.first.pk, self.snapshot, ANCHOR+timedelta(hours=2)))
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, 'pending')

    def test_only_last_template_gets_response_credit(self):
        for position, hour in ((1, 2), (2, 4)):
            now = ANCHOR+timedelta(hours=hour)
            item = self.enrollment.deliveries.get(position=position)
            claim(item.pk, self.snapshot, now)
            record_result(item.pk, {'status': 'sent', 'message_id': str(position), 'sent_at': now.isoformat()}, now)
        response_at = ANCHOR+timedelta(hours=5)
        self.snapshot['messages'].append({'sender': 'lead', 'timestamp': response_at.isoformat(), 'text': 'Sí'})
        reconcile(self.enrollment, self.snapshot, response_at)
        self.assertEqual(self.enrollment.deliveries.filter(response_at__isnull=False).count(), 1)
        self.assertIsNotNone(self.enrollment.deliveries.get(position=2).response_at)

    def test_provider_timeout_is_not_retried(self):
        now = ANCHOR+timedelta(hours=2)
        gateway = Mock()
        gateway.snapshot.return_value = dict(self.snapshot, observed_at=now.isoformat())
        gateway.send.side_effect = TimeoutError()
        dispatch(self.first.pk, gateway, now)
        dispatch(self.first.pk, gateway, now)
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, 'uncertain')
        self.assertEqual(gateway.send.call_count, 1)

    def test_stale_or_unconsented_live_snapshot_never_sends(self):
        now = ANCHOR+timedelta(hours=2)
        gateway = Mock()
        gateway.snapshot.return_value = dict(self.snapshot, observed_at=(now-timedelta(minutes=2)).isoformat())
        self.assertFalse(dispatch(self.first.pk, gateway, now))
        gateway.snapshot.return_value = dict(self.snapshot, observed_at=now.isoformat(), contact_allowed=False)
        self.assertFalse(dispatch(self.first.pk, gateway, now))
        gateway.send.assert_not_called()

    def test_receipt_monotonic_and_authenticated(self):
        now = ANCHOR+timedelta(hours=2)
        claim(self.first.pk, self.snapshot, now)
        delivered = dict(status='delivered', message_id='1', sent_at=now.isoformat(), delivered_at=now.isoformat())
        record_result(self.first.pk, delivered, now)
        record_result(self.first.pk, dict(status='accepted', message_id='1'), now)
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, 'delivered')
        request = RequestFactory().post('/', json.dumps({'idempotency_key': str(self.first.idempotency_key), **delivered}), content_type='application/json')
        with override_settings(REMARKETING_RECEIPT_TOKEN='test'):
            self.assertEqual(delivery_receipt(request).status_code, 403)

    def test_accepted_is_not_counted_as_sent(self):
        now = ANCHOR+timedelta(hours=2)
        claim(self.first.pk, self.snapshot, now)
        record_result(self.first.pk, dict(status='accepted', message_id='1'), now)
        self.first.refresh_from_db()
        rows = report_rows([self.first])
        self.assertEqual(rows[0]['sent'], 0)
        self.assertEqual(rows[0]['accepted'], 1)
        self.assertIsNone(rows[0]['rate'])


class EditorTests(SimpleTestCase):
    def test_variable_validation(self):
        for body in ('Hola {{unknown}}', 'Hola {{nombre', 'Hola {{ nombre }}'):
            with self.assertRaises(ValueError):
                render_message(body, {})

    def test_all_templates_compile(self):
        for name in ('remarketing_campaigns', 'remarketing_campaign_edit', 'remarketing_deliveries'):
            self.assertIsNotNone(get_template(f'lead_intelligence/{name}.html'))


TEST_TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'OPTIONS': {'loaders': [('django.template.loaders.locmem.Loader', {'base.html': '{% block content %}{% endblock %}'}), 'django.template.loaders.app_directories.Loader']}}]


@override_settings(ROOT_URLCONF='lead_intelligence.remarketing_test_urls', TEMPLATES=TEST_TEMPLATES)
class EditorFlowTests(TestCase):
    def request(self, path='/', data=None, method='get'):
        request = getattr(RequestFactory(), method)(path, data=data or {})
        request.user = SimpleNamespace(is_superuser=True)
        request._messages = Mock()
        return request

    def data(self):
        data = dict(name='Sin respuesta', allowed_statuses='Contactado', allowed_channels='WhatsApp', agent_ids='', contact_sender='agent', daily_limit=100, hourly_limit=20, contact_limit=3, min_gap_minutes=60, window_margin_minutes=10, start_hour=9, end_hour=18, weekdays=['0', '1', '2', '3', '4'], **{'steps-TOTAL_FORMS': '3', 'steps-INITIAL_FORMS': '0', 'steps-MIN_NUM_FORMS': '0', 'steps-MAX_NUM_FORMS': '1000'})
        for i, delay in enumerate((120, 240, 360)):
            data.update({f'steps-{i}-title': f'Plantilla {i}', f'steps-{i}-delay_minutes': delay, f'steps-{i}-body': 'Hola {{nombre}}, ¿revisaste los datos?'})
        return data

    def test_create_three_steps_and_render_all_pages(self):
        response = campaign_edit(self.request())
        self.assertContains(response, 'steps-2-delay_minutes')
        response = campaign_edit(self.request(data=self.data(), method='post'))
        self.assertEqual(response.status_code, 302)
        campaign = RemarketingCampaign.objects.get()
        self.assertEqual(campaign.steps.count(), 3)
        self.assertEqual(campaign.status, 'draft')
        self.assertEqual(campaign_edit(self.request(), campaign.pk).status_code, 200)
        self.assertEqual(campaigns(self.request()).status_code, 200)
        self.assertEqual(deliveries_report(self.request()).status_code, 200)

    def test_invalid_step_does_not_save_campaign(self):
        data = self.data()
        data['steps-1-delay_minutes'] = 130
        response = campaign_edit(self.request(data=data, method='post'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'separación mínima')
        self.assertFalse(RemarketingCampaign.objects.exists())

    def test_unknown_variable_does_not_save(self):
        data = self.data()
        data['steps-1-body'] = '{{secret}}'
        campaign_edit(self.request(data=data, method='post'))
        self.assertFalse(RemarketingCampaign.objects.exists())

    def test_activate_pause_and_immutable_history(self):
        campaign = make_campaign(status='draft')
        response = campaign_action(self.request(data={'action': 'activate'}, method='post'), campaign.pk)
        self.assertEqual(response.status_code, 302)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'active')
        enroll(campaign, snapshot(), ANCHOR)
        campaign_action(self.request(data={'action': 'pause'}, method='post'), campaign.pk)
        self.assertEqual(campaign_edit(self.request(data=self.data(), method='post'), campaign.pk).status_code, 409)
        campaign_action(self.request(data={'action': 'duplicate'}, method='post'), campaign.pk)
        copied = RemarketingCampaign.objects.exclude(pk=campaign.pk).get()
        self.assertEqual(copied.status, 'draft')
        self.assertEqual(copied.steps.count(), 3)

    def test_receipt_rejects_malformed_uuid(self):
        request = RequestFactory().post('/', json.dumps({'idempotency_key': 'invalid'}), content_type='application/json', HTTP_AUTHORIZATION='Bearer test')
        with override_settings(REMARKETING_RECEIPT_TOKEN='test'):
            self.assertEqual(delivery_receipt(request).status_code, 400)

    def test_report_rejects_invalid_dates(self):
        self.assertEqual(deliveries_report(self.request(data={'from': 'wrong'})).status_code, 400)
