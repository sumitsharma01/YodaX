"""Measured dataset checks, not an invented aggregate quality score."""
import numpy as np
import pandas as pd
from .features import calendar_for, MARKET_FEATURES, model_event_features


def dataset_audit(prices, events, features, config):
    cal = calendar_for(prices, config['horizon'])
    equities = []
    for symbol in config['stocks']:
        frame = prices[prices.symbol.eq(symbol)]
        expected = cal.sessions_in_range(frame.date.min(),frame.date.max()).tz_localize(None)
        equities.append(dict(symbol=symbol,rows=len(frame),
            missing_sessions=[str(d.date()) for d in expected.difference(pd.DatetimeIndex(frame.date))],
            duplicate_dates=int(frame.date.duplicated().sum()),
            invalid_close_rows=int(((frame.close<=0) | ~np.isfinite(frame.close)).sum())))
    result = dict(equities=equities, feature_rows=len(features), settled_rows=int(features.target_return.notna().sum()),
        feature_missing_fraction=features[MARKET_FEATURES+model_event_features(config)].isna().mean().to_dict(),
        qualification='Checks measure coverage/validity, not independent price verification or causality.')
    if events is not None and not events.empty:
        days=pd.DatetimeIndex(pd.to_datetime(events.archive_day))
        result['event_archive_days']=len(days)
        result['missing_archive_days']=[str(d.date()) for d in pd.date_range(days.min(),days.max()).difference(days)]
        result['full_event_window_rows']=int(features.event_coverage_7d.eq(1).sum())
    if config.get('exposure_registry'):
        result['known_exposure_rows']=int(features.exposure_known.eq(1).sum())
        result['full_exposure_window_rows']=int(features.exposure_coverage_7d.eq(1).sum())
        result['exposure_sources']=config['exposure_registry']
    return result
