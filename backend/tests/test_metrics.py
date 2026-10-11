from datetime import datetime, timedelta, timezone
import unittest
from app.services.metrics import percentile, summarize_events


class MetricsTests(unittest.TestCase):
    def test_nearest_rank_handles_unsorted_values(self):
        self.assertEqual(percentile([40, 10, 30, 20], .5), 20)
        self.assertEqual(percentile([40, 10, 30, 20], .95), 40)
        self.assertIsNone(percentile([], .5))

    def test_invalid_quantile(self):
        for quantile in [0, -1, 1.1]:
            with self.assertRaises(ValueError):
                percentile([1], quantile)

    def test_manual_success_does_not_count_as_automated_success(self):
        start = datetime(2026, 10, 11, tzinfo=timezone.utc)
        events = [
            {'status': status, 'handling': handling, 'attempts': attempts, 'event_type': 'pull_request',
             'created_at': start, 'completed_at': start + timedelta(seconds=index + 1)}
            for index, (status, handling, attempts) in enumerate([
                ('succeeded', 'automated', 1), ('succeeded', 'manual', 1), ('failed', 'automated', 3)])
        ]
        metrics = summarize_events(events)
        self.assertEqual(metrics['successful'], 2)
        self.assertEqual(metrics['failed'], 1)
        self.assertEqual(metrics['successful_automation_fraction'], 1 / 3)
        self.assertEqual(metrics['execution_attempts'], 5)
        self.assertEqual(metrics['p50_end_to_end_ms'], 2000)
        self.assertEqual(metrics['p95_end_to_end_ms'], 3000)

    def test_empty_run_has_no_automation_percentage(self):
        self.assertIsNone(summarize_events([])['successful_automation_fraction'])

    def test_unfinished_events_have_no_latency_sample(self):
        event = {'status': 'pending', 'handling': 'automated', 'attempts': 0, 'event_type': 'blockers',
                 'created_at': datetime(2026, 10, 11), 'completed_at': None}
        metrics = summarize_events([event])
        self.assertEqual(metrics['unfinished'], 1)
        self.assertEqual(metrics['latency_samples'], 0)
        self.assertIsNone(metrics['p50_end_to_end_ms'])

    def test_negative_latency_is_rejected(self):
        start = datetime(2026, 10, 11)
        event = {'status': 'succeeded', 'handling': 'automated', 'attempts': 1, 'event_type': 'priorities',
                 'created_at': start, 'completed_at': start - timedelta(seconds=1)}
        with self.assertRaises(ValueError):
            summarize_events([event])
