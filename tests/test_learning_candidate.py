import copy
import unittest
from backend import learning_candidate as candidate
from backend.learning import advance, schema
from backend.core import connect, save_forecast


class CandidateTests(unittest.TestCase):
    def test_large_errors_reduce_raw_weight_and_correct_bias(self):
        state = candidate.initial_state()
        prediction = candidate.issue(100, 102, .02, state)
        frozen = copy.deepcopy(prediction)
        changed = candidate.update(state, prediction, 95, 100)
        self.assertLess(changed['weights'][0], state['weights'][0])
        self.assertLess(changed['bias'], -.01)
        self.assertAlmostEqual(sum(changed['weights']), 1)
        self.assertEqual(prediction, frozen)
        self.assertEqual(state['count'], 0)

    def test_gate_requires_prior_evidence_and_reverts_after_losses(self):
        state = candidate.initial_state()
        self.assertEqual(candidate.issue(100, 102, .02, state)['decision'], 'no_change')
        state['recent'] = [dict(ensemble_error=.01, baseline_error=.02)] * 20
        self.assertEqual(candidate.issue(100, 102, .02, state)['decision'], 'adaptive')
        state['recent'] = [dict(ensemble_error=.03, baseline_error=.02)] * 20
        self.assertEqual(candidate.issue(100, 102, .02, state)['decision'], 'no_change')

    def test_parallel_versions_settle_once_without_rewriting_v1(self):
        db = connect(':memory:')
        schema(db)
        def forecast(target, cutoff):
            return dict(symbol='NVDA', target=target, cutoff=cutoff, kind='prospective',
                actual=None, predicted=102, previous=100, low=90, high=110,
                created_at='2026-11-10T22:00:00+00:00', model_revision='r', snapshot_sha='s')
        first = forecast('2026-11-11', '2026-11-10')
        save_forecast(db, first)
        snapshot = dict(symbol='NVDA', history=[100]*30, dates=[], records=[], forecast=first)
        advance(db, snapshot, 'r', first['created_at'])
        frozen = db.execute('SELECT version,payload FROM adaptive_forecasts ORDER BY version').fetchall()
        db.execute("UPDATE forecasts SET actual=95 WHERE target='2026-11-11'")
        second = forecast('2026-11-12','2026-11-11')
        save_forecast(db, second)
        snapshot['forecast'] = second
        advance(db, snapshot, 'r','2026-11-11T22:00:00+00:00')
        advance(db, snapshot, 'r','2026-11-11T23:00:00+00:00')
        self.assertEqual(snapshot['adaptive_candidate']['state']['count'],1)
        self.assertEqual(snapshot['adaptive']['state']['count'],1)
        for row in frozen:
            saved=db.execute("SELECT payload FROM adaptive_forecasts WHERE version=? AND target='2026-11-11'",(row['version'],)).fetchone()
            self.assertEqual(row['payload'],saved['payload'])
        self.assertEqual(db.execute('SELECT COUNT(*) FROM adaptive_forecasts').fetchone()[0],4)
        db.close()
