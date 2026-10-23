"""Purged chronological comparisons and paired date-block bootstrap."""
import numpy as np
import pandas as pd
from .model import fit_bundle


def chronological_split(features, start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    settled = features.dropna(subset=['target_return'])
    # Purge every training label whose outcome overlaps the test period.
    train = settled[(settled.date < start) & (settled.target_date < start)]
    test = settled[(settled.date >= start) & (settled.date < end) & (settled.target_date < end)]
    if train.date.nunique() < 60 or test.date.nunique() < 20:
        raise ValueError('Need at least 60 training dates and 20 evaluation dates')
    return train, test


def summarize(predictions):
    rows = []
    for model, group in predictions.groupby('model'):
        error = group.predicted_return - group.target_return
        rows.append(dict(model=model, observations=len(group), dates=group.date.nunique(),
            mae_return_pp=float(error.abs().mean()*100),
            rmse_return_pp=float(np.sqrt(np.mean(error**2))*100),
            direction_accuracy=float((np.sign(group.predicted_return) == np.sign(group.target_return)).mean())))
    return pd.DataFrame(rows)


def block_bootstrap(predictions, reference, candidate, horizon, block=20, repetitions=1000, seed=42):
    if block < horizon or repetitions < 100:
        raise ValueError('Block must cover the horizon; use at least 100 repetitions')
    predictions = predictions.copy()
    predictions['loss'] = abs(predictions.predicted_return - predictions.target_return)
    wide = predictions.pivot(index=['date', 'symbol'], columns='model', values='loss')
    paired = wide[[reference, candidate]].dropna()
    # All assets stay together per date. Positive improvement favors candidate.
    difference = (paired[reference] - paired[candidate]).groupby('date').mean().sort_index()
    values = difference.to_numpy()
    if len(values) < 3*block:
        return dict(status='insufficient_dates', dates=len(values), minimum=3*block)
    # Do not create blocks that jump across missing exchange sessions.
    import exchange_calendars as xcals
    cal = xcals.get_calendar('XNYS', start=difference.index.min()-pd.Timedelta(days=10), end=difference.index.max()+pd.Timedelta(days=10))
    session_dates = cal.sessions_in_range(difference.index.min(), difference.index.max()).tz_localize(None)
    positions = session_dates.get_indexer(pd.DatetimeIndex(difference.index))
    valid_starts = [i for i in range(len(values)-block+1) if (positions[i:i+block] >= 0).all() and (np.diff(positions[i:i+block]) == 1).all()]
    if not valid_starts:
        return dict(status='insufficient_contiguous_dates', dates=len(values), block_sessions=block)
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(repetitions):
        starts = rng.choice(valid_starts, size=int(np.ceil(len(values)/block)), replace=True)
        sample = np.concatenate([values[start:start+block] for start in starts])[:len(values)]
        means.append(sample.mean())
    low, high = np.quantile(means, [.025, .975])
    return dict(status='computed', dates=len(values), block_sessions=block,
        valid_blocks=len(valid_starts), mean_improvement_pp=float(values.mean()*100), ci95_pp=[float(low*100), float(high*100)],
        interpretation='Positive favors candidate; dependence-aware interval, not proof of causation or profitability.')


def evaluate_window(features, config, start, end, revisions, data_kind='real', include_events=True):
    eligible = features[features.event_coverage_7d.eq(1)] if include_events else features
    if include_events and config.get('exposure_registry'):
        eligible = eligible[eligible.exposure_known.eq(1) & eligible.exposure_coverage_7d.eq(1)]
    train, test = chronological_split(eligible, start, end)
    models = {'market_adjusted': fit_bundle(train, config, False, revisions, data_kind)}
    if include_events:
        models['event_adjusted'] = fit_bundle(train, config, True, revisions, data_kind)
        if config.get('exposure_registry'):
            global_config = {k: v for k, v in config.items() if k != 'exposure_registry'}
            models['global_event_adjusted'] = fit_bundle(train, global_config, True, revisions, data_kind)
    rows = []
    variants = {'no_change': np.zeros(len(test)), 'timesfm': test.baseline_return.to_numpy()}
    variants.update({name: bundle.predict_features(test) for name, bundle in models.items()})
    for name, predicted in variants.items():
        part = test[['symbol','date','target_date','target_return']].copy()
        part['model'] = name
        part['predicted_return'] = predicted
        rows.append(part)
    predictions = pd.concat(rows, ignore_index=True)
    uncertainty = block_bootstrap(predictions, 'market_adjusted' if include_events else 'timesfm',
        'event_adjusted' if include_events else 'market_adjusted', config['horizon'],
        config.get('bootstrap_block_sessions', 20), config.get('bootstrap_repetitions', 1000), config.get('seed', 42))
    comparisons = {'event_vs_market': uncertainty}
    if 'global_event_adjusted' in models:
        comparisons['exposure_vs_global'] = block_bootstrap(predictions, 'global_event_adjusted', 'event_adjusted', config['horizon'], config.get('bootstrap_block_sessions',20), config.get('bootstrap_repetitions',1000), config.get('seed',42))
    return dict(models=models, predictions=predictions, metrics=summarize(predictions), uncertainty=uncertainty, comparisons=comparisons,
        split=dict(train_start=str(train.date.min().date()), train_end=str(train.date.max().date()),
            last_training_target=str(train.target_date.max().date()), test_start=str(test.date.min().date()),
            test_end=str(test.date.max().date()), training_rows=len(train), test_rows=len(test)))
