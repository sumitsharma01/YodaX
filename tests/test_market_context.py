import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import pandas as pd
import exchange_calendars as xc
from backend.market_context import coverage, symbols_in, context
from backend.core import connect
from backend.prediction_requests import validate, enqueue, listing
from backend.requested_forecasts import issuance_deadline

class MarketContextTests(unittest.TestCase):
    def test_coverage_does_not_confuse_proxy_with_physical_commodity(self):
        self.assertEqual(symbols_in('Forecast copper and Tesla'),['HG=F','TSLA'])
        self.assertEqual(symbols_in('lithium and steel demand'),[])
        self.assertIn('MSFT',coverage()['stocks'])
        self.assertEqual(validate({'symbol':'CL=F','horizon_sessions':5})['symbol'],'CL=F')
        with self.assertRaises(ValueError):validate({'symbol':'UNKNOWN=F','horizon_sessions':5})

    def test_private_requests_do_not_leak_into_chat_context(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'db.sqlite3'
            with patch('backend.prediction_requests.connect',side_effect=lambda:connect(path)),patch('backend.market_context.connect',side_effect=lambda:connect(path)):
                enqueue('t','alice','Apple next week',{'symbol':'AAPL','horizon_sessions':5},research={'sources':[]})
                self.assertEqual(listing('alice')[0]['payload']['research'],{'sources':[]})
                self.assertEqual(context('Apple forecast',[],'bob')['saved_forecasts'],[])
                self.assertEqual(context('what about it?',[{'user':'Apple forecast'}],'bob')['matched_symbols'],['AAPL'])
                self.assertEqual(context('Explain inflation',[{'user':'Apple forecast'}],'bob')['matched_symbols'],[])

    def test_futures_can_issue_during_unfinished_session(self):
        c=xc.get_calendar('COMEX');cutoff=pd.Timestamp('2026-10-26')
        deadline=issuance_deadline(c,cutoff,True)
        self.assertGreater(deadline,c.session_close(cutoff)+pd.Timedelta(hours=1))
        self.assertLess(deadline,c.session_close(c.next_session(cutoff)))
        self.assertEqual(issuance_deadline(xc.get_calendar('XNYS'),cutoff),xc.get_calendar('XNYS').session_open('2026-10-27'))

    def test_event_request_attaches_real_shadow_value_without_inventing_interval(self):
        import json
        from unittest.mock import Mock
        from backend import requested_forecasts as worker
        from backend.shadow_store import schema
        from backend.core import MODEL_REVISION
        cal=xc.get_calendar('XNYS')
        dates=cal.sessions_in_range('2025-07-01','2026-10-12')
        frame=pd.DataFrame({'Close':[100.]*len(dates),'Stock Splits':0.},index=dates.tz_localize('America/New_York'))
        ticker=Mock();ticker.history.return_value=frame
        ticker.get_history_metadata.return_value={'instrumentType':'EQUITY','exchangeTimezoneName':'America/New_York'}
        fake_pd=Mock(wraps=pd);fake_pd.Timestamp=Mock(wraps=pd.Timestamp);fake_pd.Timestamp.now.return_value=pd.Timestamp('2026-10-12T21:30:00Z')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'db.sqlite3'
            with patch('backend.prediction_requests.connect',side_effect=lambda:connect(path)),patch.object(worker,'pd',fake_pd),patch.object(worker.yf,'Ticker',return_value=ticker):
                enqueue('t','alice','AAPL next week',{'symbol':'AAPL','horizon_sessions':5},research={'sources':['news evidence']})
                with connect(path) as db:
                    schema(db)
                    p={'predicted':105.,'previous':100.,'model_revision':MODEL_REVISION}
                    db.execute('INSERT INTO shadow_predictions VALUES (?,?,?,?,?,?,?,NULL,NULL,NULL,NULL)',(listing('alice')[0]['payload'].get('requested_candidate') or 'frozen','AAPL','2026-10-12','2026-10-19','event_adjusted','2026-10-12T21:15:00Z',json.dumps(p)))
                worker.run()
                row=listing('alice')[0]
                self.assertEqual(row['state'],'predicted')
                self.assertEqual(row['payload']['predicted'],105.)
                self.assertIsNone(row['payload']['low'])
                self.assertEqual(row['payload']['research']['sources'],['news evidence'])
                self.assertFalse(row['payload']['research_used_as_model_features'])
                self.assertEqual(row['payload']['model_route'],row['payload']['requested_model_route'])

    def test_broad_event_requests_pin_candidate_and_horizon(self):
        from backend.market_context import event_route
        route=event_route('HG=F',5)
        self.assertEqual(route['route'],'global_event_adjusted')
        self.assertIsNone(event_route('HG=F',21))
        self.assertIsNone(event_route('IBM',5))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'db.sqlite3'
            with patch('backend.prediction_requests.connect',side_effect=lambda:connect(path)):
                enqueue('copper','alice','Copper price next week',{'symbol':'HG=F','horizon_sessions':5})
                payload=listing('alice')[0]['payload']
                self.assertEqual(payload['requested_candidate'],route['candidate'])
                self.assertEqual(payload['requested_model_route'],'global_event_adjusted')
