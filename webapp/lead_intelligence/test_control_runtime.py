from unittest.mock import patch
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from .management.commands.run_lead_control import plan_refresh
from .test_lead_control import snapshot, NOW
from .control_engine import observe
from .control_notifications import tick
from .models import LeadControlPolicy, LeadControlNotice


class RefreshPlanningTests(SimpleTestCase):
    def test_unchanged_rows_are_not_replayed_and_inflight_is_not_duplicated(self):
        unchanged, pending = plan_refresh([(1, 'a', 'Nuevo'), (2, 'b', 'Nuevo'), (3, 'c', 'Nuevo')], {1: 'a'}, {2: object()}, [])
        self.assertEqual(unchanged, [1])
        self.assertEqual([row[0] for row in pending], [3])

    def test_old_lead_with_new_message_precedes_initial_backlog(self):
        _, pending = plan_refresh([(4000, 'x', 'Nuevo'), (1, 'new', 'Nuevo'), (3500, 'z', 'Cierre')], {}, {}, ['Cierre'], {1})
        self.assertEqual([row[0] for row in pending], [1, 4000, 3500])

    def test_changed_known_lead_reprocessed(self):
        _, pending = plan_refresh([(2, 'new', 'Nuevo')], {2: 'old'}, {}, [])
        self.assertEqual(pending, [(2, 'new', 'Nuevo')])


class EmptyDirectoryClockTests(TestCase):
    def test_batch_notices_without_directory_are_deduplicated(self):
        from datetime import timedelta
        rules = LeadControlPolicy.objects.create(pk=1, active_statuses=['Nuevo'], closed_statuses=['Cierre'], weekdays=[0, 1, 2, 3, 4], stale_minutes=120)
        state = observe(snapshot(), rules, NOW)
        with patch('lead_intelligence.control_notifications.queue_notice') as routed:
            tick(NOW+timedelta(minutes=40))
            count = LeadControlNotice.objects.count()
            tick(NOW+timedelta(minutes=41))
        self.assertEqual(count, 3)
        self.assertEqual(LeadControlNotice.objects.count(), count)
        self.assertTrue(all(n.status == 'unroutable' for n in LeadControlNotice.objects.all()))
        state.obligations.get().action.refresh_from_db()
        self.assertEqual(state.obligations.get().action.priority, 'critical')
        routed.assert_not_called()
