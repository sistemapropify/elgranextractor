from datetime import timedelta

from django.test import SimpleTestCase
from django.template.loader import get_template
from django.utils import timezone

from intelligence.learning_views import _latency_series


class LearningLatencySeriesTests(SimpleTestCase):
    def test_dashboard_template_compiles(self):
        self.assertIsNotNone(
            get_template('intelligence/learning/dashboard.html')
        )

    def test_seven_day_window_uses_six_hour_buckets(self):
        now = timezone.now().replace(
            hour=17, minute=30, second=0, microsecond=0
        )
        rows = [
            (now - timedelta(hours=1), 1000),
            (now - timedelta(hours=2), 3000),
        ]

        series = _latency_series(rows, 168, now=now)

        self.assertEqual(series['bucket_hours'], 6)
        self.assertEqual(sum(series['counts']), 2)
        populated = [
            index for index, count in enumerate(series['counts']) if count
        ]
        self.assertEqual(len(populated), 1)
        index = populated[0]
        self.assertEqual(series['average'][index], 2000)
        self.assertEqual(series['p95'][index], 3000)
        self.assertEqual(
            [point['latency'] for point in series['queries']],
            [3000, 1000],
        )
        self.assertLess(
            series['queries'][0]['timestamp'],
            series['queries'][1]['timestamp'],
        )

    def test_window_changes_chart_resolution(self):
        now = timezone.now()

        self.assertEqual(
            _latency_series([], 24, now=now)['bucket_hours'],
            1,
        )
        self.assertEqual(
            _latency_series([], 720, now=now)['bucket_hours'],
            24,
        )

    def test_empty_buckets_are_serialized_as_null(self):
        series = _latency_series([], 24, now=timezone.now())

        self.assertTrue(series['labels'])
        self.assertTrue(all(value is None for value in series['average']))
        self.assertTrue(all(value is None for value in series['p95']))
        self.assertEqual(series['queries'], [])
