import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core import mail
from django.test import TestCase, SimpleTestCase, RequestFactory, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import LeadControlPolicy, LeadControlState, LeadControlMember, LeadObligation, LeadControlNotice, LeadControlEvent, ActionOutcome
from .control_calendar import add_minutes, calendar_for, business_seconds
from .control_engine import observe, intervene, change_owner, create_obligation
from .control_notifications import tick, send_pending, queue_notice
from .control_metrics import metrics
from .control_access import ControlAccess, access_for
from . import control_views
from prospects.models import MobileProspectUser, MobileNotificationDevice
from prospects.propify_auth import PropifyPrincipal
from prospects import control_api

NOW = datetime(2026, 9, 7, 15, tzinfo=dt_timezone.utc)  # Monday 10:00 Lima


def snapshot(lead_id=1, owner=7, now=NOW):
    return {'lead_id': lead_id, 'agent_id': owner, 'nombre': 'Ana', 'propiedad': 'Casa', 'status_name': 'Nuevo', 'entered_at': (NOW-timedelta(minutes=1)).isoformat(), 'observed_at': now.isoformat(), 'messages': [{'id': 'in-1', 'sender': 'lead', 'text': 'Información', 'timestamp': NOW.isoformat()}]}


def message(sender, minute, message_id=None):
    return {'id': message_id or f'{sender}-{minute}', 'sender': sender, 'text': 'Mensaje', 'timestamp': (NOW+timedelta(minutes=minute)).isoformat()}


class ControlTests(TestCase):
    def setUp(self):
        self.settings = LeadControlPolicy.objects.create(pk=1, active_statuses=['Nuevo', 'Contactado'], closed_statuses=['Ganado', 'Perdido'], weekdays=[0, 1, 2, 3, 4], stale_minutes=60)
        self.manager = LeadControlMember.objects.create(name='Gerencia', identity_type='django', identity_id='10', role='manager', email='manager@example.invalid')
        self.supervisor = LeadControlMember.objects.create(name='Supervisor', identity_type='django', identity_id='20', role='supervisor', supervisor=self.manager, email='supervisor@example.invalid')
        self.agent = LeadControlMember.objects.create(name='Agente', identity_type='django', identity_id='30', source_user_id=7, role='agent', supervisor=self.supervisor, email='agent@example.invalid', mobile_identity_id='70')
        self.state = observe(snapshot(), self.settings, NOW)
        self.item = self.state.obligations.get(kind='first_response')

    def test_bot_and_customer_insistence_do_not_reset_clock(self):
        data = snapshot(now=NOW+timedelta(minutes=4))
        data['messages'] += [message('bot', 1), message('lead', 3)]
        observe(data, self.settings, NOW+timedelta(minutes=4))
        self.item.refresh_from_db()
        self.assertEqual(self.item.action.status, 'pending')
        self.assertEqual(self.item.started_at, NOW)
        self.assertEqual(self.item.original_due_at, NOW+timedelta(minutes=5))
        self.assertEqual(self.state.obligations.filter(kind__in=['first_response', 'reply']).count(), 1)

    def test_human_response_closes_and_creates_next_step(self):
        data = snapshot(now=NOW+timedelta(minutes=2))
        data['messages'].append(message('agent', 2))
        observe(data, self.settings, NOW+timedelta(minutes=2))
        self.item.refresh_from_db()
        self.assertEqual(self.item.action.status, 'completed')
        self.assertEqual(self.item.action.completed_at, NOW+timedelta(minutes=2))
        self.assertEqual(self.state.obligations.filter(kind='followup', action__status='pending').count(), 1)

    def test_old_lead_reactivated_gets_reply_obligation(self):
        data = snapshot(now=NOW+timedelta(days=5))
        data['entered_at'] = (NOW-timedelta(days=300)).isoformat()
        data['messages'] += [message('agent', 2), message('lead', 5*24*60)]
        observe(data, self.settings, NOW+timedelta(days=5))
        self.assertEqual(self.state.obligations.filter(kind='reply', action__status='pending').count(), 1)

    def test_duplicate_observation_does_not_duplicate_work(self):
        observe(snapshot(), self.settings, NOW)
        self.assertEqual(LeadObligation.objects.count(), 1)

    def test_out_of_order_snapshot_does_not_rollback(self):
        observe(snapshot(owner=8, now=NOW+timedelta(minutes=1)), self.settings, NOW+timedelta(minutes=1))
        observe(snapshot(), self.settings, NOW+timedelta(minutes=2))
        self.state.refresh_from_db()
        self.assertEqual(self.state.owner_id, 8)

    def test_assignment_changes_preserve_deadline_and_history(self):
        observe(snapshot(owner=8, now=NOW+timedelta(minutes=10)), self.settings, NOW+timedelta(minutes=10))
        self.item.refresh_from_db()
        self.assertEqual(self.item.action.source_assigned_user_id, 8)
        self.assertEqual(self.item.original_due_at, NOW+timedelta(minutes=5))
        event = self.state.events.filter(kind='owner_changed').first()
        self.assertEqual(event.payload['from'], 7)

    def test_unassigned_lead_has_assignment_obligation(self):
        data = snapshot(lead_id=2, owner=None)
        state = observe(data, self.settings, NOW)
        self.assertTrue(state.obligations.filter(kind='assignment', action__status='pending').exists())
        data.update(agent_id=7, observed_at=(NOW+timedelta(minutes=1)).isoformat())
        observe(data, self.settings, NOW+timedelta(minutes=1))
        self.assertFalse(state.obligations.filter(kind='assignment', action__status='pending').exists())

    def test_unknown_data_does_not_look_healthy(self):
        observe(dict(snapshot(), messages='invalid'), self.settings, NOW)
        self.state.refresh_from_db()
        self.assertEqual(self.state.quality, 'unknown')
        self.assertEqual(self.item.action.status, 'pending')

    def test_unknown_status_not_automatically_closed(self):
        observe(dict(snapshot(), status_name='Desconocido'), self.settings, NOW)
        self.state.refresh_from_db()
        self.assertTrue(self.state.active)
        self.assertEqual(self.state.quality, 'unknown')

    def test_closed_lead_cancels_open_work(self):
        observe(dict(snapshot(), status_name='Perdido'), self.settings, NOW)
        self.item.refresh_from_db()
        self.assertEqual(self.item.action.status, 'dismissed')

    def test_acknowledgment_does_not_close_or_extend(self):
        intervene(self.item.pk, 'ack', 'django:30', 7, {}, now=NOW)
        intervene(self.item.pk, 'ack', 'django:30', 7, {}, now=NOW)
        self.item.refresh_from_db()
        self.assertEqual(self.item.action.status, 'pending')
        self.assertEqual(self.item.events.filter(kind='acknowledged').count(), 1)

    def test_response_deadline_cannot_be_postponed(self):
        with self.assertRaises(ValueError):
            intervene(self.item.pk, 'reschedule', 'agent', 7, {'notes': 'Luego', 'next_contact_at': NOW+timedelta(days=1)}, now=NOW)

    def test_completion_requires_evidence_and_next_step(self):
        with self.assertRaises(ValueError):
            intervene(self.item.pk, 'complete', 'agent', 7, {'notes': 'Hecho'}, now=NOW)
        intervene(self.item.pk, 'complete', 'django:30', 7, {'notes': 'Cliente pidió llamada mañana', 'evidence_type': 'call', 'evidence_reference': 'call-123', 'next_contact_at': NOW+timedelta(days=1)}, now=NOW)
        self.item.refresh_from_db()
        self.assertEqual(self.item.resolved_evidence['source'], 'user_recorded')
        self.assertEqual(ActionOutcome.objects.count(), 1)
        self.assertTrue(self.state.obligations.filter(kind='commitment', action__status='pending').exists())

    def test_visit_not_closed_by_generic_response(self):
        data = dict(snapshot(), visit_intent_at=NOW.isoformat())
        observe(data, self.settings, NOW)
        data['messages'].append(message('agent', 2))
        data['observed_at'] = (NOW+timedelta(minutes=2)).isoformat()
        observe(data, self.settings, NOW+timedelta(minutes=2))
        self.assertTrue(self.state.obligations.filter(kind='visit', action__status='pending').exists())
        data['visit_registered_at'] = (NOW+timedelta(minutes=2)).isoformat()
        observe(data, self.settings, NOW+timedelta(minutes=2))
        self.assertFalse(self.state.obligations.filter(kind='visit', action__status='pending').exists())

    def test_tick_escalates_once_without_ai(self):
        tick(NOW+timedelta(minutes=31))
        tick(NOW+timedelta(minutes=32))
        self.assertEqual(self.item.notices.filter(channel='internal').count(), 3)
        self.assertEqual(self.item.notices.get(level='manager', channel='internal').recipient, self.manager)

    def test_stale_source_alerts_management_not_agent(self):
        tick(NOW+timedelta(hours=2))
        self.assertTrue(self.item.notices.filter(level='data', recipient=self.manager).exists())
        self.assertFalse(self.item.notices.filter(level='agent').exists())

    def test_unroutable_is_visible(self):
        LeadControlMember.objects.update(active=False)
        tick(NOW+timedelta(minutes=31))
        self.assertTrue(self.item.notices.filter(status='unroutable').exists())

    def test_unanswered_is_in_sla_denominator(self):
        result = metrics([self.item], NOW+timedelta(minutes=10))
        self.assertEqual(result['eligible'], 1)
        self.assertEqual(result['compliance'], 0)

    @override_settings(LEAD_CONTROL_EMAIL_ENABLED=True)
    def test_email_is_accepted_not_delivered_and_not_duplicated(self):
        queue_notice(self.item, 'agent', NOW)
        send_pending(now=NOW)
        send_pending(now=NOW)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.item.notices.get(channel='email').status, 'accepted')

    @override_settings(LEAD_CONTROL_EMAIL_ENABLED=True)
    def test_resolved_alert_does_not_send(self):
        queue_notice(self.item, 'agent', NOW)
        data = snapshot(now=NOW+timedelta(minutes=2))
        data['messages'].append(message('agent', 2))
        observe(data, self.settings, NOW+timedelta(minutes=2))
        send_pending(now=NOW)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(LEAD_CONTROL_EMAIL_ENABLED=True)
    def test_transport_error_does_not_blindly_retry(self):
        queue_notice(self.item, 'agent', NOW)
        with patch('lead_intelligence.control_notifications.EmailMessage.send', side_effect=TimeoutError()):
            send_pending(now=NOW)
            send_pending(now=NOW)
        self.assertEqual(self.item.notices.get(channel='email').status, 'uncertain')

    def test_agent_scope_and_supervisor_scope(self):
        other = observe(snapshot(2, 88), self.settings, NOW)
        self.assertEqual(list(ControlAccess(member=self.agent).states().values_list('pk', flat=True)), [self.state.pk])
        self.assertEqual(ControlAccess(member=self.supervisor).states().count(), 1)
        self.assertEqual(ControlAccess(member=self.manager).states().count(), 2)

    def test_session_simulation_does_not_grant_control_access(self):
        request = RequestFactory().get('/')
        request.session = {'simulated_profile_level': 5, 'simulated_profile_domains': ['gerencia']}
        self.assertIsNone(access_for(request))

    def request(self, user_id='30', method='get', data=None):
        request = getattr(RequestFactory(), method)('/', data=data or {})
        request.user = SimpleNamespace(pk=user_id, is_authenticated=True, is_superuser=False)
        request._messages = []
        return request

    def test_pages_render_for_scoped_users(self):
        self.assertEqual(control_views.board(self.request()).status_code, 200)
        self.assertEqual(control_views.lead_detail(self.request(), 1).status_code, 200)
        self.assertEqual(control_views.rules(self.request('10')).status_code, 200)
        self.assertEqual(control_views.directory(self.request('10')).status_code, 200)
        self.assertEqual(control_views.rules(self.request()).status_code, 403)

    def test_manager_can_sync_one_lead_from_web_without_transport(self):
        from django.utils import timezone
        now = timezone.now()
        data = snapshot(3, now=now)
        data['entered_at'] = (now-timedelta(minutes=1)).isoformat()
        data['messages'][0]['timestamp'] = now.isoformat()
        with patch('lead_intelligence.control_views.source_snapshot', return_value=data):
            response = control_views.sync_lead(self.request('10', 'post', {'lead_id': '3'}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LeadControlEvent.objects.filter(lead__source_lead_id=3, kind='manual_sync').exists())
        self.assertFalse(LeadControlNotice.objects.exists())

    def test_agent_cannot_sync_arbitrary_crm_lead(self):
        with patch('lead_intelligence.control_views.source_snapshot') as source:
            response = control_views.sync_lead(self.request('30', 'post', {'lead_id': '3'}))
        self.assertEqual(response.status_code, 403)
        source.assert_not_called()

    def test_cannot_access_other_agent_object(self):
        from django.http import Http404
        observe(snapshot(2, 88), self.settings, NOW)
        with self.assertRaises(Http404):
            control_views.lead_detail(self.request(), 2)

    def test_ingest_requires_secret(self):
        request = RequestFactory().post('/', json.dumps(snapshot()), content_type='application/json')
        self.assertEqual(control_views.ingest(request).status_code, 403)

    def test_mobile_contract_and_registration(self):
        user = MobileProspectUser.objects.create(username='agent', propify_user_id='70')
        principal = PropifyPrincipal(user, {'id': '70'}, 'not-a-real-token')
        request = APIRequestFactory().post('/', {'registration_id': 'fid-example-123456', 'target_type': 'fid'}, format='json')
        force_authenticate(request, user=principal)
        self.assertEqual(control_api.register_device(request).status_code, 200)
        self.assertEqual(MobileNotificationDevice.objects.count(), 1)
        request = APIRequestFactory().get('/')
        force_authenticate(request, user=principal)
        response = control_api.alerts(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['lead_id'], 1)

    @override_settings(LEAD_CONTROL_PUSH_ENABLED=True)
    def test_push_uses_registered_device_and_preserves_status(self):
        user = MobileProspectUser.objects.create(username='agent', propify_user_id='70')
        MobileNotificationDevice.objects.create(user=user, registration_id='fid-123456789', target_type='fid')
        queue_notice(self.item, 'agent', NOW)
        sender = Mock(return_value='projects/test/messages/1')
        send_pending(push_sender=sender, now=NOW)
        sender.assert_called_once()
        self.assertEqual(self.item.notices.get(channel='push').status, 'accepted')


class CalendarTests(SimpleTestCase):
    def test_weekend_and_holiday(self):
        calendar = {'start_hour': 9, 'end_hour': 18, 'weekdays': [0, 1, 2, 3, 4], 'holidays': ['2026-09-14']}
        friday = datetime(2026, 9, 11, 22, 58, tzinfo=dt_timezone.utc)
        self.assertEqual(add_minutes(friday, 5, calendar), datetime(2026, 9, 15, 14, 3, tzinfo=dt_timezone.utc))

    def test_empty_calendar_rejected(self):
        with self.assertRaises(ValueError):
            add_minutes(NOW, 5, {'start_hour': 9, 'end_hour': 18, 'weekdays': [], 'holidays': []})


class ControlRegressionTests(TestCase):
    setUp = ControlTests.setUp

    def test_entry_and_later_chat_are_one_first_response(self):
        data = dict(snapshot(3), messages=[])
        state = observe(data, self.settings, NOW)
        original = state.obligations.get(kind='first_response')
        data.update(messages=[message('bot', 0), message('lead', 2)], observed_at=(NOW+timedelta(minutes=2)).isoformat())
        observe(data, self.settings, NOW+timedelta(minutes=2))
        self.assertEqual(state.obligations.filter(kind='first_response').count(), 1)
        self.assertEqual(state.obligations.get(kind='first_response').original_due_at, original.original_due_at)
        data.update(messages=data['messages']+[message('agent', 3), message('agent', 4)], observed_at=(NOW+timedelta(minutes=4)).isoformat())
        observe(data, self.settings, NOW+timedelta(minutes=4))
        original.refresh_from_db()
        self.assertEqual(original.action.completed_at, NOW+timedelta(minutes=3))

    def test_only_bot_still_requires_human(self):
        state = observe(dict(snapshot(3), messages=[message('bot', 0)]), self.settings, NOW)
        self.assertTrue(state.obligations.filter(kind='first_response', action__status='pending').exists())

    def test_reopened_lead_uses_new_customer_turn(self):
        closed_at = NOW+timedelta(minutes=1)
        observe(dict(snapshot(now=closed_at), status_name='Perdido'), self.settings, closed_at)
        data = snapshot(now=NOW+timedelta(minutes=30))
        data['messages'].append(message('lead', 30))
        observe(data, self.settings, NOW+timedelta(minutes=30))
        pending = self.state.obligations.get(kind='first_response', action__status='pending')
        self.assertEqual(pending.started_at, NOW+timedelta(minutes=30))
        self.item.refresh_from_db()
        self.assertEqual(self.item.action.status, 'dismissed')

    def test_real_followup_resolves_old_and_sets_next(self):
        data = snapshot(now=NOW+timedelta(minutes=2))
        data['messages'].append(message('agent', 2))
        observe(data, self.settings, NOW+timedelta(minutes=2))
        previous = self.state.obligations.get(kind='followup')
        data.update(messages=data['messages']+[message('agent', 24*60)], observed_at=(NOW+timedelta(days=1)).isoformat())
        observe(data, self.settings, NOW+timedelta(days=1))
        previous.refresh_from_db()
        self.assertEqual(previous.action.status, 'completed')
        self.assertEqual(self.state.obligations.filter(kind='followup', action__status='pending').count(), 1)

    @override_settings(LEAD_CONTROL_EMAIL_ENABLED=True)
    def test_stale_queued_alert_is_held_until_source_recovers(self):
        queue_notice(self.item, 'agent', NOW)
        send_pending(now=NOW+timedelta(hours=2))
        self.assertEqual(len(mail.outbox), 0)
        observe(snapshot(now=NOW+timedelta(hours=2)), self.settings, NOW+timedelta(hours=2))
        send_pending(now=NOW+timedelta(hours=2))
        self.assertEqual(len(mail.outbox), 1)

    def test_stale_pending_is_excluded_from_compliance(self):
        result = metrics([self.item], NOW+timedelta(hours=2), self.settings.stale_minutes)
        self.assertEqual(result['eligible'], 0)
        self.assertEqual(result['unknown'], 1)

    def test_permission_rechecked_when_intervening_after_reassignment(self):
        from django.http import Http404
        change_owner(self.state, 88, 'Rescate')
        with self.assertRaises(Http404):
            intervene(self.item.pk, 'ack', 'agent', 7, {}, now=NOW, access=ControlAccess(member=self.agent))

    def test_bad_history_opens_data_task_and_recovery_closes_it(self):
        state = observe(dict(snapshot(3), messages=None), self.settings, NOW)
        task = state.obligations.get(kind='data')
        observe(snapshot(3), self.settings, NOW)
        task.refresh_from_db()
        self.assertEqual(task.action.status, 'completed')

    def test_page_failure_still_checks_known_leads_and_releases_lease(self):
        from io import StringIO
        from django.core.management import call_command
        with patch('lead_intelligence.management.commands.process_lead_control.source_page', side_effect=RuntimeError()), patch('lead_intelligence.management.commands.process_lead_control.source_snapshot', return_value=snapshot()), patch('lead_intelligence.management.commands.process_lead_control.tick') as clock:
            call_command('process_lead_control', stdout=StringIO(), stderr=StringIO())
            clock.assert_called_once()
        self.settings.refresh_from_db()
        self.assertIsNone(self.settings.scan_lease_until)

    def test_clock_not_blocked_by_scanner_lease(self):
        from io import StringIO
        from django.core.management import call_command
        from django.utils import timezone
        self.settings.scan_lease_token = 'another-worker'
        self.settings.scan_lease_until = timezone.now()+timedelta(minutes=5)
        self.settings.save()
        with patch('lead_intelligence.management.commands.process_lead_control.tick') as clock:
            call_command('process_lead_control', tick_only=True, stdout=StringIO())
            clock.assert_called_once()

    def test_mobile_agent_cannot_read_other_agent_lead(self):
        state = observe(snapshot(3, 88), self.settings, NOW)
        item = state.obligations.get(kind='first_response')
        user = MobileProspectUser.objects.create(username='agent', propify_user_id='70')
        request = APIRequestFactory().get('/')
        force_authenticate(request, user=PropifyPrincipal(user, {'id': '70'}, 'test'))
        self.assertEqual(control_api.alert_detail(request, item.pk).status_code, 404)

    def test_current_visit_assessment_reused_without_importing_llm(self):
        from .models import LeadConversationAssessment
        from .conversation_identity import conversation_hash
        from .control_source import source_snapshot
        data = snapshot()
        data['entered_at'] = NOW-timedelta(minutes=1)
        LeadConversationAssessment.objects.create(source_lead_id=1, history_hash=conversation_hash(data['messages']), qualified_status='confirmed', qualified_confidence=1, visit_intent_status='confirmed', visit_intent_confidence=1, visit_intent_evidence=[{'text': 'Quiero visitar', 'timestamp': NOW.isoformat()}], model_version='fixture')
        with patch('lead_intelligence.control_source.crm_snapshot', return_value=data):
            result = source_snapshot(1)
        self.assertEqual(result['visit_intent_at'], NOW.isoformat())

    @override_settings(LEAD_CONTROL_EMAIL_ENABLED=True)
    def test_daily_digest_is_scoped_and_sent_once(self):
        from .control_digest import daily_digest
        from .models import LeadControlDigest
        observe(snapshot(3, 88), self.settings, NOW)
        self.settings.digest_hour = 9
        self.settings.save()
        daily_digest(NOW, send=True)
        daily_digest(NOW, send=True)
        self.assertEqual(LeadControlDigest.objects.count(), 2)
        self.assertEqual(LeadControlDigest.objects.get(recipient=self.supervisor).payload['stats']['open'], 1)
        self.assertEqual(LeadControlDigest.objects.get(recipient=self.manager).payload['stats']['open'], 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertFalse(LeadControlDigest.objects.exclude(email_status='accepted').exists())

    def test_daily_digest_waits_for_configured_hour(self):
        from .control_digest import daily_digest
        from .models import LeadControlDigest
        daily_digest(NOW)
        self.assertFalse(LeadControlDigest.objects.exists())
