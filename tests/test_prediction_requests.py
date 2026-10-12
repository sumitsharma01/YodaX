import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import exchange_calendars as xcals
from backend.core import connect
from backend import prediction_requests as pr
from backend.requested_forecasts import target_session, evaluate


class PredictionTests(unittest.TestCase):
    def test_rejects_invalid_ticker_or_horizon(self):
        for value in ({'symbol':'AAPL','horizon_sessions':True},
                      {'symbol':'EUR/INR','horizon_sessions':5},
                      {'symbol':'AAPL','horizon_sessions':61},
                      {'symbol':'AAPL','horizon_sessions':0}):
            with self.assertRaises(ValueError): pr.validate(value)
        self.assertEqual(pr.validate({'symbol':'IBM','horizon_sessions':21})['symbol'], 'IBM')

    def test_queue_is_idempotent_and_private(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'db.sqlite3'
            with patch.object(pr,'connect',side_effect=lambda:connect(path)):
                first = pr.enqueue('turn','alice','Predict IBM in a week',{'symbol':'IBM','horizon_sessions':5})
                second = pr.enqueue('turn','alice','Predict IBM in a week',{'symbol':'IBM','horizon_sessions':5})
                self.assertEqual(first['id'],second['id'])
                self.assertEqual(len(pr.listing('alice')),1)
                self.assertEqual(pr.listing('bob'),[])
                self.assertEqual(pr.listing('alice')[0]['state'],'queued')

    def test_horizon_skips_weekends(self):
        cal=xcals.get_calendar('XNYS')
        self.assertEqual(str(target_session(cal,pd.Timestamp('2026-10-09'),1).date()),'2026-10-12')
        self.assertEqual(str(target_session(cal,pd.Timestamp('2026-10-09'),5).date()),'2026-10-16')

    def test_scoring_does_not_rewrite_prediction(self):
        payload={'previous':100.,'predicted':105.,'scale':.02}
        before=dict(payload)
        exact=evaluate(payload,105.)
        missed=evaluate(payload,95.)
        self.assertEqual(exact['score'],100.)
        self.assertLess(missed['score'],exact['score'])
        self.assertFalse(missed['correct'])
        self.assertEqual(payload,before)

    def test_worker_issues_then_scores_without_changing_forecast(self):
        import sys
        import numpy as np
        from types import SimpleNamespace
        from unittest.mock import Mock
        from backend import requested_forecasts as worker
        cal=xcals.get_calendar('XNYS')
        dates=cal.sessions_in_range('2025-07-01','2026-10-13')
        frame=pd.DataFrame({'Close':np.arange(len(dates),dtype=float)+100,'Stock Splits':0.},index=dates.tz_localize('America/New_York'))
        model=Mock()
        model.forecast.return_value=(np.array([[450.]]),np.array([[[450.,440.,441.,442.,443.,444.,445.,446.,447.,460.]]]))
        fake_timesfm=SimpleNamespace(TimesFM_2p5_200M_torch=Mock(),ForecastConfig=lambda **kw:kw)
        fake_timesfm.TimesFM_2p5_200M_torch.from_pretrained.return_value=model
        ticker=Mock();ticker.history.return_value=frame
        ticker.get_history_metadata.return_value={'instrumentType':'EQUITY','exchangeTimezoneName':'America/New_York'}
        fake_pd=Mock(wraps=pd);fake_pd.Timestamp=Mock(wraps=pd.Timestamp)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'db.sqlite3'
            with patch.object(pr,'connect',side_effect=lambda:connect(path)), patch.object(worker,'pd',fake_pd), patch.object(worker.yf,'Ticker',return_value=ticker), patch.dict(sys.modules,{'timesfm':fake_timesfm,'torch':Mock(),'huggingface_hub':SimpleNamespace(snapshot_download=lambda *a,**kw:folder)}):
                pr.enqueue('t','alice','IBM tomorrow',{'symbol':'IBM','horizon_sessions':1})
                fake_pd.Timestamp.now.return_value=pd.Timestamp('2026-10-12T21:30:00Z')
                worker.run()
                first=pr.listing('alice')[0]
                self.assertEqual(first['state'],'predicted')
                self.assertEqual(first['payload']['target'],'2026-10-13')
                fake_pd.Timestamp.now.return_value=pd.Timestamp('2026-10-13T21:30:00Z')
                worker.run()
                settled=pr.listing('alice')[0]
                self.assertEqual(settled['state'],'scored')
                for key,value in first['payload'].items(): self.assertEqual(settled['payload'][key],value)
                worker.run()
                self.assertEqual(pr.listing('alice')[0],settled)
                self.assertEqual(model.forecast.call_count,1)
