import unittest
import numpy as np
from backend.core import connect, context_for, metrics, save_forecast

class ForecastTests(unittest.TestCase):
    def test_target_never_enters_context(self):
        values=np.arange(300,dtype=float)
        before=context_for(values,280).copy()
        values[280:]=999999
        np.testing.assert_array_equal(before,context_for(values,280))
        self.assertEqual(before[-1],279)

    def test_metrics_against_hand_calculation(self):
        result=metrics(100,102,99)
        self.assertEqual(result['error'],3)
        self.assertEqual(result['baseline'],1)
        self.assertFalse(result['correct'])
        self.assertFalse(metrics(100,100,101)['correct'])
        with self.assertRaises(ValueError): metrics(0,100,100)

    def test_rerun_preserves_original_forecast(self):
        db=connect(':memory:')
        row=dict(symbol='AAPL',target='2026-09-28',cutoff='2026-09-25',created_at='first',model_revision='abc',snapshot_sha='hash',previous=100,predicted=101,low=98,high=104,kind='prospective')
        save_forecast(db,row)
        save_forecast(db,dict(row,predicted=900,created_at='later'))
        saved=db.execute('SELECT * FROM forecasts').fetchall()
        self.assertEqual(len(saved),1)
        self.assertEqual(saved[0]['predicted'],101)
        self.assertEqual(saved[0]['created_at'],'first')
        save_forecast(db,dict(row,kind='historical'))
        self.assertEqual(db.execute('SELECT count(*) FROM forecasts').fetchone()[0],2)
        db.close()

if __name__=='__main__': unittest.main()
