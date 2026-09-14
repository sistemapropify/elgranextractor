from datetime import timedelta
from unittest.mock import patch
from django.http import QueryDict
from django.test import TestCase, SimpleTestCase
from django.utils import timezone
from .test_lead_control import ControlTests, NOW, snapshot
from .control_engine import observe, create_obligation
from .control_presentation import page_context, describe, entry_label, notice_description
from .models import LeadControlNotice, LeadObligation
from . import control_views


class BoardTests(TestCase):
    setUp = ControlTests.setUp
    request = ControlTests.request

    def page(self, query='', now=NOW):
        return page_context(QueryDict(query), LeadObligation.objects.select_related('lead', 'action', 'action__diagnosis'), now, now-timedelta(hours=1))

    def test_default_sorts_by_entry_not_deadline(self):
        old = observe(dict(snapshot(2), entered_at=(NOW-timedelta(days=1)).isoformat()), self.settings, NOW)
        old.obligations.get().action.__class__.objects.filter(pk=old.obligations.get().action_id).update(due_at=NOW-timedelta(hours=2))
        page = self.page()
        self.assertEqual([i.lead.source_lead_id for i in page['page']], [1, 2])
        self.assertEqual([i.lead.source_lead_id for i in self.page('order=priority')['page']], [2, 1])

    def test_day_filters_use_lima_entry_not_observation(self):
        midnight = NOW.replace(hour=5, minute=0)
        self.state.entered_at = midnight-timedelta(seconds=1)
        self.state.save(update_fields=['entered_at'])
        observe(dict(snapshot(2), entered_at=midnight.isoformat()), self.settings, NOW)
        self.assertEqual([i.lead.source_lead_id for i in self.page('entry=today')['page']], [2])
        self.assertEqual([i.lead.source_lead_id for i in self.page('entry=yesterday')['page']], [1])
        self.assertTrue(entry_label(self.state.entered_at, NOW).startswith('Ayer'))

    def test_unknown_entry_is_last_in_both_orders(self):
        unknown = observe(snapshot(2), self.settings, NOW)
        unknown.entered_at = None
        unknown.save(update_fields=['entered_at'])
        for order in ('recent', 'oldest'):
            self.assertEqual([i.lead.source_lead_id for i in self.page('order='+order)['page']], [1, 2])
        self.assertEqual(self.page('entry=unknown')['summary']['leads'], 1)

    def test_stale_never_counted_as_verified_overdue(self):
        self.state.quality = 'unknown'
        self.state.save(update_fields=['quality'])
        summary = self.page(now=NOW+timedelta(minutes=10))['summary']
        self.assertEqual(summary['overdue'], 0)
        self.assertEqual(summary['unverified'], 1)
        self.assertEqual(self.page('overdue=1', NOW+timedelta(minutes=10))['summary']['actions'], 0)

    def test_pagination_preserves_all_filters(self):
        context = self.page('entry=today&order=priority&overdue=1&escalated=1&category=reply&page=2')
        query = QueryDict(context['page_query'])
        self.assertNotIn('page', query)
        self.assertEqual(query['entry'], 'today')
        self.assertEqual(query['overdue'], '1')
        self.assertEqual(query['escalated'], '1')
        self.assertEqual(query['category'], 'reply')

    def test_explanation_has_evidence_and_does_not_confuse_followup(self):
        describe(self.item, NOW, NOW-timedelta(hours=1))
        self.assertEqual(self.item.evidence_text, 'Información')
        self.item.kind = 'followup'
        describe(self.item, NOW, NOW-timedelta(hours=1))
        self.assertIn('No significa que el cliente esté esperando', self.item.reason_text)
        self.item.action.diagnosis.evidence = {'type': 'crm_entry'}
        describe(self.item, NOW, NOW-timedelta(hours=1))
        self.assertIn('No se ha identificado un mensaje', self.item.reason_text)

    def test_board_is_scoped_and_get_does_not_create_notices(self):
        observe(snapshot(2, owner=88), self.settings, NOW)
        with patch('lead_intelligence.control_views.timezone.now', return_value=NOW), patch('lead_intelligence.control_views.render') as render:
            control_views.board(self.request())
        context = render.call_args.args[2]
        self.assertEqual(context['summary']['leads'], 1)
        self.assertEqual(context['summary']['actions'], 1)
        self.assertFalse(LeadControlNotice.objects.exists())

    def test_template_renders_dates_explanation_and_escapes_evidence(self):
        self.item.action.diagnosis.evidence = {'message': '<script>alert(1)</script>'}
        self.item.action.diagnosis.save(update_fields=['evidence'])
        with patch('lead_intelligence.control_views.timezone.now', return_value=NOW):
            response = control_views.board(self.request())
        html = response.content.decode()
        self.assertIn('Hoy · 07/09/2026', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('Sin aviso registrado', html)


class NoticePresentationTests(SimpleTestCase):
    def test_internal_and_provider_acceptance_are_not_delivery_claims(self):
        notice = LeadControlNotice(channel='internal', status='available', level='agent')
        self.assertIn('solo en el tablero', notice_description(notice, {}).status_label)
        notice.channel, notice.status = 'push', 'accepted'
        self.assertIn('no confirma lectura', notice_description(notice, {'push': True}).status_label)
        notice.status = 'pending'
        self.assertIn('deshabilitado', notice_description(notice, {'push': False}).status_label)
