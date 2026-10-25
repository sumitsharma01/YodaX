"""Deterministic feature engineering shared by training and saved-artifact inference."""
import numpy as np
import pandas as pd
import exchange_calendars as xcals

MARKET_FEATURES = ['baseline_return', 'return_1', 'return_5', 'return_20',
                   'volatility_20', 'volume_ratio', 'market_return_5',
                   'oil_return_5', 'copper_return_5']
EVENT_FEATURES = ['event_log_count_7d', 'material_conflict_share_7d',
                  'material_cooperation_share_7d', 'event_coverage_7d']
FEATURE_VERSION = 'daily-v2-exposures'

def model_event_features(config):
    from .exposures import EXPOSURE_FEATURES
    return EVENT_FEATURES + (EXPOSURE_FEATURES if config.get('exposure_registry') else [])


def validate_prices(prices, stocks):
    required = {'date', 'symbol', 'close', 'volume', 'split'}
    if not required.issubset(prices):
        raise ValueError(f'Missing price columns: {required - set(prices)}')
    missing_symbols = set(stocks) - set(prices.symbol)
    if missing_symbols:
        raise ValueError(f'Missing configured equity histories: {sorted(missing_symbols)}')
    prices = prices.copy()
    prices['date'] = pd.to_datetime(prices.date).dt.tz_localize(None).dt.normalize()
    if prices.duplicated(['symbol', 'date']).any():
        raise ValueError('Duplicate symbol/date price rows')
    for field in ['close', 'volume', 'split']:
        prices[field] = pd.to_numeric(prices[field], errors='raise')
    stock = prices[prices.symbol.isin(stocks)]
    if not np.isfinite(stock[['close', 'volume', 'split']]).all().all() or (stock.close <= 0).any() or (stock.volume < 0).any():
        raise ValueError('Invalid equity price/volume/action data')
    return prices.sort_values(['symbol', 'date'])


def calendar_for(prices, horizon=5):
    return xcals.get_calendar('XNYS', start=prices.date.min() - pd.Timedelta(days=30),
                             end=prices.date.max() + pd.Timedelta(days=horizon * 4 + 30))


def stock_windows(prices, config):
    """Reindex first: missing sessions cannot silently shorten a forecast horizon."""
    prices = validate_prices(prices, config['stocks'])
    cal = calendar_for(prices, config['horizon'])
    for symbol in config['stocks']:
        frame = prices.loc[prices.symbol == symbol].set_index('date')
        if frame.empty:
            continue
        sessions = cal.sessions_in_range(frame.index.min(), frame.index.max()).tz_localize(None)
        yield symbol, frame.reindex(sessions), cal


def build_features(prices, events, baselines, config):
    """Returns features for both labeled historical rows and unlabeled latest rows."""
    prices = validate_prices(prices, config['stocks'])
    horizon, context = config['horizon'], config['context']
    if horizon < 1 or context < 21:
        raise ValueError('Invalid horizon/context')
    for column, expected in [('horizon_sessions', horizon), ('context_sessions', context)]:
        if column not in baselines or not baselines[column].eq(expected).all():
            raise ValueError(f'Baseline {column} does not match feature configuration')
    if baselines.duplicated(['symbol', 'date']).any():
        raise ValueError('Duplicate baseline forecasts')
    baseline = baselines.copy()
    baseline['date'] = pd.to_datetime(baseline.date)
    if not np.isfinite(baseline.baseline_return).all():
        raise ValueError('Nonfinite baseline forecast')
    frames = []
    for symbol, frame, cal in stock_windows(prices, config):
        close = frame.close
        ret = close.pct_change(fill_method=None)
        dates = frame.index
        all_sessions = cal.sessions_in_range(dates.min(), dates.max() + pd.Timedelta(days=horizon * 4 + 10)).tz_localize(None)
        targets = all_sessions[all_sessions.get_indexer(dates) + horizon]
        f = pd.DataFrame({'symbol': symbol, 'date': dates, 'target_date': targets,
            'close': close.to_numpy(), 'return_1': ret.to_numpy(),
            'return_5': close.pct_change(5, fill_method=None).to_numpy(),
            'return_20': close.pct_change(20, fill_method=None).to_numpy(),
            'volatility_20': ret.rolling(20).std().to_numpy(),
            'volume_ratio': (frame.volume / frame.volume.rolling(20).mean().replace(0, np.nan)).to_numpy(),
            'target_return': (close.shift(-horizon) / close - 1).to_numpy()})
        # Exclude contexts crossing splits, missing sessions, and incomplete future labels.
        valid = close.notna().rolling(context).sum().eq(context)
        valid &= frame.split.fillna(0).ne(0).rolling(context).sum().eq(0)
        future_splits = pd.concat([frame.split.shift(-i).ne(0) for i in range(1, horizon + 1)], axis=1).any(axis=1)
        future_missing = pd.concat([close.shift(-i).isna() for i in range(1, horizon + 1)], axis=1).any(axis=1)
        f.loc[(future_splits | future_missing).to_numpy(), 'target_return'] = np.nan
        clocks=[cal]
        if config.get('completed_futures_context'):
            # WTI/copper daily candles may finish after equities. Historical replay
            # and live issuance must both wait for the latest input market close.
            clocks += [xcals.get_calendar(name, start=dates.min()-pd.Timedelta(days=30),
                         end=dates.max()+pd.Timedelta(days=30)) for name in ['NYMEX','COMEX']]
        f['cutoff_at'] = [max(clock.session_close(d) for clock in clocks) + pd.Timedelta(hours=1) for d in dates]
        frames.append(f.loc[valid.to_numpy()])
    if not frames:
        raise ValueError('No equity windows available')
    features = pd.concat(frames, ignore_index=True)
    # Exact-date joins: stale market context stays missing instead of silently forward filling.
    for symbol, name in [('SPY', 'market_return_5'), ('CL=F', 'oil_return_5'), ('HG=F', 'copper_return_5')]:
        series = prices[prices.symbol == symbol].set_index('date').close
        sessions = calendar_for(prices, horizon).sessions_in_range(prices.date.min(), prices.date.max()).tz_localize(None)
        series = series.reindex(sessions)
        # Nonpositive futures observations are not treated as ordinary percentage returns.
        series = series.where(series > 0)
        feature = (series / series.shift(5) - 1).where(series.notna().rolling(6).sum() == 6)
        features[name] = features.date.map(feature)
    features = features.merge(baseline[['symbol', 'date', 'baseline_return']], on=['symbol', 'date'], how='inner', validate='one_to_one')
    if features.empty:
        raise ValueError('No matching price/baseline windows')
    event_rows = []
    if events is not None and not events.empty:
        events = events.copy()
        events['available_at'] = pd.to_datetime(events.available_at, utc=True)
        events['archive_day'] = pd.to_datetime(events.archive_day)
        if events.archive_day.duplicated().any():
            raise ValueError('Duplicate event archive days')
        count_fields = ['event_total', 'material_conflict', 'material_cooperation']
        if not np.isfinite(events[count_fields]).all().all() or (events[count_fields] < 0).any().any():
            raise ValueError('Invalid event counts')
        if (events.available_at < pd.to_datetime(events.archive_day, utc=True) + pd.Timedelta(days=config.get('event_lag_days', 2))).any():
            raise ValueError('Event availability violates configured archive lag')
    for cutoff in features.cutoff_at.drop_duplicates().sort_values():
        if events is None or events.empty:
            subset = pd.DataFrame()
        else:
            subset = events[(events.available_at <= cutoff) & (events.available_at > cutoff - pd.Timedelta(days=7))]
        covered = len(subset)
        # An incomplete collection is not evidence of no events.
        count = subset.event_total.sum() if covered == 7 else np.nan
        event_rows.append(dict(cutoff_at=cutoff,
            event_log_count_7d=np.log1p(count),
            material_conflict_share_7d=subset.material_conflict.sum()/count if covered == 7 and count else np.nan,
            material_cooperation_share_7d=subset.material_cooperation.sum()/count if covered == 7 and count else np.nan,
            event_coverage_7d=covered/7))
    features = features.merge(pd.DataFrame(event_rows), on='cutoff_at', validate='many_to_one')
    if config.get('exposure_registry'):
        from .exposures import add_exposure_features
        features = add_exposure_features(features, events, config['exposure_registry'])
    return features.replace([np.inf, -np.inf], np.nan).sort_values(['date', 'symbol']).reset_index(drop=True)
