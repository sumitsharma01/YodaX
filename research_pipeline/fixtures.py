"""Deterministic synthetic integration fixture. NEVER evidence of market performance."""
import numpy as np
import pandas as pd
import exchange_calendars as xcals


def synthetic_inputs(seed=42):
    rng = np.random.default_rng(seed)
    cal = xcals.get_calendar('XNYS', start='2018-01-01', end='2024-01-01')
    dates = cal.sessions_in_range('2018-01-02', '2023-12-29').tz_localize(None)
    frames = []
    for symbol in ['AAPL', 'FCX', 'SPY', 'CL=F', 'HG=F']:
        returns = rng.normal(.0002, .012, len(dates))
        frames.append(pd.DataFrame(dict(date=dates, symbol=symbol,
            close=100*np.exp(np.cumsum(returns)), volume=rng.integers(10000, 100000, len(dates)), split=0.)))
    prices = pd.concat(frames, ignore_index=True)
    days = pd.date_range('2018-01-01', '2023-12-31')
    events = pd.DataFrame(dict(archive_day=days, available_at=days.tz_localize('UTC')+pd.Timedelta(days=2),
        event_total=1000, material_conflict=rng.integers(100, 500, len(days)),
        material_cooperation=rng.integers(100, 300, len(days))))
    stocks = prices[prices.symbol.isin(['AAPL', 'FCX'])].copy()
    stocks['baseline_return'] = stocks.groupby('symbol').close.pct_change(5, fill_method=None).fillna(0)*.1
    stocks['model_revision'] = 'synthetic-fixture-not-timesfm'
    stocks['horizon_sessions'] = 5
    stocks['context_sessions'] = 256
    return prices, events, stocks[['date','symbol','baseline_return','model_revision','horizon_sessions','context_sessions']]
