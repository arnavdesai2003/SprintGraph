from datetime import date
import unittest
from app.services.scoring import prioritize, detect_blockers

def issue(key='SG-1', **kwargs):
    return {'key': key, 'summary': 'Example', 'status': 'To Do', 'priority': 'Medium', 'severity': 0,
            'sprint': False, 'due_date': None, 'dependencies': [], 'updated': '2026-10-10', **kwargs}

class ScoringTests(unittest.TestCase):
    def test_done_excluded(self):
        self.assertEqual(prioritize([issue(status='Done')]), [])
    def test_explainable_sum(self):
        result = prioritize([issue(priority='Highest', severity=4, sprint=True, due_date='2026-10-09')], date(2026, 10, 11))[0]
        self.assertEqual(result['score'], 105)
        self.assertEqual(result['score'], sum(result['components'].values()))
    def test_blocking_dependency_boost(self):
        results = prioritize([issue('SG-1'), issue('SG-2', dependencies=['SG-1'])])
        self.assertEqual(results[0]['key'], 'SG-1')
        self.assertEqual(results[0]['components']['unblocks'], 15)
    def test_stable_ties_and_custom_weights(self):
        results = prioritize([issue('SG-2'), issue('SG-1')], weights={'Medium': 3})
        self.assertEqual([r['key'] for r in results], ['SG-1', 'SG-2'])
        self.assertEqual(results[0]['score'], 3)
    def test_completed_dependency_does_not_block(self):
        results = detect_blockers([issue('SG-1', status='Done'), issue('SG-2', dependencies=['SG-1'])], date(2026, 10, 11))
        self.assertEqual(results, [])
    def test_explicit_and_potential(self):
        results = detect_blockers([issue(status='Blocked', updated='2026-09-01')], date(2026, 10, 11))
        self.assertEqual({r['certainty'] for r in results}, {'definite', 'potential'})
    def test_unknown_dependency_is_potential(self):
        result = detect_blockers([issue(dependencies=['OUT-1'])], date(2026, 10, 11))[0]
        self.assertEqual(result['certainty'], 'potential')
    def test_overdue_evidence(self):
        result = detect_blockers([issue(due_date='2026-10-01')], date(2026, 10, 11))[0]
        self.assertEqual(result['kind'], 'overdue')
        self.assertIn('2026-10-01', result['evidence'])

if __name__ == '__main__':
    unittest.main()
