import unittest
from unittest.mock import Mock
import numpy as np
import pandas as pd
from backend.price_feed import daily_history, require_ready_close, PendingDailyClose


def bars():
    return pd.DataFrame({'Open':[100.,101.], 'High':[102.,103.], 'Low':[99.,100.],
        'Close':[101.,np.nan], 'Volume':[1000,2000], 'Stock Splits':[0.,0.]},
        index=pd.date_range('2026-10-27', periods=2, tz='America/New_York'))


class PriceFeedTests(unittest.TestCase):
    def test_recovers_only_missing_last_bar_from_daily_source(self):
        raw=bars(); fresh=raw.copy();fresh.iloc[-1,fresh.columns.get_loc('Close')]=102.
        ticker=Mock();ticker.history.side_effect=[raw,fresh]
        out=daily_history(ticker,start='2024-08-20',end='2026-10-29',auto_adjust=False)
        self.assertEqual(out.Close.iloc[-1],102.)
        pd.testing.assert_series_equal(out.iloc[0],raw.iloc[0])
        self.assertTrue(pd.isna(raw.Close.iloc[-1]))
        self.assertEqual(ticker.history.call_args.kwargs['start'],'2026-10-21')
        self.assertFalse(ticker.history.call_args.kwargs['auto_adjust'])

    def test_older_corruption_is_not_repaired_or_deferred(self):
        raw=bars();raw.iloc[0,3]=np.nan
        ticker=Mock();ticker.history.return_value=raw
        out=daily_history(ticker,start='2024-08-20',end='2026-10-29')
        ticker.history.assert_called_once()
        require_ready_close(out,'2026-10-29',now='2026-10-29T00:55Z')
        self.assertTrue(out.Close.isna().all())

    def test_provisional_close_deferred_but_overdue_still_invalid(self):
        with self.assertRaises(PendingDailyClose):
            require_ready_close(bars(),'2026-10-29',now='2026-10-29T00:55Z')
        require_ready_close(bars(),'2026-10-29',now='2026-10-29T12:31Z')
        self.assertTrue(pd.isna(bars().Close.iloc[-1]))

    def test_bad_replacement_and_wrong_date_rejected(self):
        for field,value in [('Close',np.nan),('Volume',-1),('High',1)]:
            raw=bars();fresh=bars();fresh['Close']=102.;fresh.loc[fresh.index[-1],field]=value
            ticker=Mock();ticker.history.side_effect=[raw,fresh]
            self.assertTrue(pd.isna(daily_history(ticker,start='2024-08-20',end='2026-10-29').Close.iloc[-1]))

    def test_invalid_volume_is_not_deferred(self):
        raw=bars();raw.iloc[-1,4]=-1
        require_ready_close(raw,'2026-10-29',now='2026-10-29T00:55Z')
