import copy
import json
import unittest
from backend.core import connect, save_forecast
from backend.learning import advance, initial_state, issue, schema, score, update, scale_from_history

class LearningTests(unittest.TestCase):
    def test_score_and_quadratic_penalty(self):
        self.assertEqual(score(100,100,100,.01)['score'],100)
        self.assertEqual(score(100,101,100,.01)['score'],50)
        self.assertEqual(score(100,102,100,.01)['normalized_loss'],4)
        self.assertLess(score(100,102,100,.01)['reward'],score(100,101,100,.01)['reward'])
        self.assertGreater(score(100,102,102,.01)['reward'],0)
        with self.assertRaises(ValueError): score(100,float('nan'),100,.01)

    def test_reward_changes_future_weights_only(self):
        state=initial_state()
        prediction=issue(100,102,.01,state)
        frozen=copy.deepcopy(prediction)
        changed=update(state,prediction,100,100)
        self.assertGreater(changed['weights'][1],state['weights'][1])
        self.assertAlmostEqual(sum(changed['weights']),1)
        self.assertEqual(prediction,frozen)
        self.assertLess(changed['bias'],0)
        self.assertGreaterEqual(changed['bias'],-.01)

    def test_scale_uses_past_and_has_floor(self):
        self.assertEqual(scale_from_history([100]*21),.005)
        with self.assertRaises(ValueError): scale_from_history([100]*10)

    def test_settlement_updates_once_and_ignores_historical(self):
        db=connect(':memory:');schema(db)
        def raw(target,cutoff,kind='prospective',actual=None):
            return dict(symbol='AAPL',target=target,cutoff=cutoff,kind=kind,actual=actual,
                predicted=102,previous=100,low=98,high=104,created_at='2026-09-27T20:00:00+00:00',model_revision='r',snapshot_sha='s')
        first=raw('2026-09-28','2026-09-25');save_forecast(db,first)
        snapshot=dict(symbol='AAPL',history=[100]*30,dates=[],records=[],forecast=first)
        advance(db,snapshot,'r','2026-09-27T20:00:00+00:00')
        frozen=copy.deepcopy(snapshot['adaptive'])
        advance(db,snapshot,'r','2026-09-27T21:00:00+00:00')
        self.assertEqual(snapshot['adaptive']['created_at'],frozen['created_at'])
        self.assertEqual(snapshot['adaptive']['state']['count'],0)
        save_forecast(db,raw('2026-09-27','2026-09-26','historical',100))
        db.execute("UPDATE forecasts SET actual=100 WHERE target='2026-09-28'")
        # Even a populated outcome after the cutoff cannot influence this forecast.
        advance(db,snapshot,'r','2026-09-27T21:30:00+00:00')
        self.assertEqual(snapshot['adaptive']['state']['count'],0)
        second=raw('2026-09-29','2026-09-28');save_forecast(db,second)
        snapshot['forecast']=second
        advance(db,snapshot,'r','2026-09-28T22:00:00+00:00')
        self.assertEqual(snapshot['adaptive']['state']['count'],1)
        self.assertEqual(len(snapshot['learning_results']),1)
        weights=copy.deepcopy(snapshot['adaptive']['weights'])
        advance(db,snapshot,'r','2026-09-28T23:00:00+00:00')
        self.assertEqual(snapshot['adaptive']['state']['count'],1)
        self.assertEqual(snapshot['adaptive']['weights'],weights)
        self.assertEqual(db.execute("SELECT predicted FROM forecasts WHERE target='2026-09-28'").fetchone()[0],102)
        db.close()
