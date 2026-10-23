"""Serializable fitted preprocessing + nonlinear residual model + feature contract."""
from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256
import importlib.metadata
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import HistGradientBoostingRegressor
from .features import MARKET_FEATURES, EVENT_FEATURES, FEATURE_VERSION, build_features, model_event_features
from .collect import write_json


def make_pipeline(include_events=True, seed=42, event_columns=None):
    columns = MARKET_FEATURES + ((event_columns if event_columns is not None else EVENT_FEATURES) if include_events else [])
    return Pipeline([
        ('select', ColumnTransformer([('numeric', SimpleImputer(strategy='median', add_indicator=True,
            keep_empty_features=True), columns)], remainder='drop')),
        ('model', HistGradientBoostingRegressor(max_iter=100, max_leaf_nodes=7,
            min_samples_leaf=30, learning_rate=0.05, l2_regularization=10,
            early_stopping=False, random_state=seed))])


@dataclass
class ForecastBundle:
    pipeline: Pipeline
    config: dict
    metadata: dict

    def predict_features(self, features):
        required = MARKET_FEATURES + (self.metadata.get('event_columns', EVENT_FEATURES) if self.metadata['include_events'] else [])
        missing = set(required) - set(features)
        if missing:
            raise ValueError(f'Missing features: {sorted(missing)}')
        if not np.isfinite(features.baseline_return).all():
            raise ValueError('A finite TimesFM baseline is required')
        if self.metadata['include_events'] and not features.event_coverage_7d.eq(1).all():
            raise ValueError('Event-aware inference requires seven complete event archive days')
        if self.metadata['include_events'] and self.config.get('exposure_registry'):
            if not features.exposure_known.eq(1).all() or not features.exposure_coverage_7d.eq(1).all():
                raise ValueError('Missing or stale as-of exposure evidence')
        predicted = features.baseline_return.to_numpy() + self.pipeline.predict(features)
        if not np.isfinite(predicted).all() or (predicted <= -1).any():
            raise ValueError('Invalid adjusted return; do not publish')
        return predicted

    def predict(self, prices, events, baselines):
        revisions = set(baselines.model_revision) if 'model_revision' in baselines else set()
        if revisions != set(self.metadata['baseline_revisions']):
            raise ValueError('Baseline model revision does not match artifact')
        features = build_features(prices, events, baselines, self.config)
        # Require callers to supply latest as-of snapshots; return one forecast per asset.
        latest = features.groupby('symbol', sort=False).tail(1).copy()
        expected = prices[prices.symbol.isin(self.config['stocks'])].groupby('symbol').date.max()
        observed = latest.set_index('symbol').date
        if set(expected.index) != set(observed.index) or not pd.to_datetime(expected).eq(observed.reindex(expected.index)).all():
            raise ValueError('Latest input session has no valid features/baseline; refusing stale inference')
        latest['predicted_return'] = self.predict_features(latest)
        latest['predicted_price'] = latest.close * (1 + latest.predicted_return)
        return latest[['symbol', 'date', 'target_date', 'predicted_return', 'predicted_price']]


def fit_bundle(features, config, include_events, baseline_revisions, data_kind='real'):
    if features.target_return.isna().any() or features.empty:
        raise ValueError('Training requires settled targets')
    if include_events and not features.event_coverage_7d.eq(1).all():
        raise ValueError('Event-aware training requires complete coverage')
    event_columns = model_event_features(config)
    if include_events and config.get('exposure_registry'):
        if not features.exposure_known.eq(1).all() or not features.exposure_coverage_7d.eq(1).all():
            raise ValueError('Training requires available exposure snapshots and complete archives')
    pipe = make_pipeline(include_events, config.get('seed', 42), event_columns)
    pipe.fit(features, features.target_return - features.baseline_return)
    metadata = dict(feature_version=FEATURE_VERSION, include_events=include_events, event_columns=event_columns,
        baseline_revisions=list(baseline_revisions), data_kind=data_kind,
        training_start=str(features.date.min().date()), training_end=str(features.date.max().date()),
        last_training_target=str(features.target_date.max().date()), rows=len(features),
        status='research_candidate_not_approved_for_production',
        versions={name: importlib.metadata.version(name) for name in ['scikit-learn','numpy','pandas','joblib']})
    return ForecastBundle(pipe, dict(config), metadata)


def save_bundle(bundle, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'pipeline.joblib'
    if target.exists():
        raise FileExistsError('Use a new artifact folder; existing candidates are immutable')
    temporary = folder / 'pipeline.joblib.tmp'
    joblib.dump(bundle, temporary)
    temporary.replace(target)
    metadata = {**bundle.metadata, 'config': bundle.config, 'sha256': sha256(target.read_bytes()).hexdigest()}
    write_json(folder / 'manifest.json', metadata)
    return target


def load_bundle(folder):
    """Only load artifacts you produced/trust: joblib loading executes Python code."""
    folder = Path(folder)
    metadata = json.loads((folder/'manifest.json').read_text())
    file = folder/'pipeline.joblib'
    if sha256(file.read_bytes()).hexdigest() != metadata['sha256']:
        raise ValueError('Artifact checksum mismatch')
    if metadata['feature_version'] != FEATURE_VERSION:
        raise ValueError('Incompatible feature implementation')
    for name, version in metadata['versions'].items():
        if importlib.metadata.version(name) != version:
            raise ValueError(f'Environment mismatch for {name}; use saved requirements')
    return joblib.load(file)
