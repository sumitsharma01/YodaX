"""python -m research_pipeline --help"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import subprocess
import pandas as pd
from .collect import collect_prices, collect_events, write_json
from .features import build_features
from .evaluate import evaluate_window
from .model import save_bundle

ROOT = Path(__file__).resolve().parents[1]


def run_experiment(root, config, output, include_events=True, holdout=False, data_kind='real'):
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError('Choose a new run folder to preserve previous evaluations')
    prices = pd.read_parquet(root/'prices.parquet')
    event_path = root/('events-enriched.parquet' if config.get('exposure_registry') else 'events.parquet')
    if config.get('exposure_registry') and not event_path.exists():
        raise ValueError('Run enrich-events before the exposure study')
    events = pd.read_parquet(event_path) if event_path.exists() else None
    baselines = pd.read_parquet(root/'baselines.parquet')
    revisions = sorted(baselines.model_revision.unique().tolist())
    if data_kind == 'real':
        from backend.core import MODEL_REVISION
        if revisions != [MODEL_REVISION]:
            raise ValueError('Real experiments require pinned TimesFM forecasts, not fixture baselines')
    features = build_features(prices, events, baselines, config)
    output.mkdir(parents=True)
    features.to_parquet(output/'features.parquet', index=False)
    from .quality import dataset_audit
    write_json(output/'quality.json', dataset_audit(prices, events, features, config))
    windows = config['validation_windows']
    if holdout:
        windows = [[config['holdout_start'], str((features.date.max()+pd.Timedelta(days=1)).date())]]
    elif any(pd.Timestamp(end) > pd.Timestamp(config['holdout_start']) for _, end in windows):
        raise ValueError('Validation must not consume the reserved holdout')
    reports, predictions, final = [], [], None
    try:
        for number, (start, end) in enumerate(windows):
            final = evaluate_window(features, config, start, end, revisions, data_kind, include_events)
            final['predictions']['fold'] = number
            predictions.append(final['predictions'])
            reports.append(dict(start=start, end=end, split=final['split'],
                metrics=final['metrics'].to_dict('records'), uncertainty=final['uncertainty'], comparisons=final['comparisons']))
        combined = pd.concat(predictions, ignore_index=True)
        combined.to_parquet(output/'predictions.parquet', index=False)
        for name, model in final['models'].items():
            save_bundle(model, output/name)
        manifest = dict(status='completed_research_only', data_kind=data_kind, holdout=holdout,
            config=config, folds=reports, baseline_revisions=revisions,
            created_at=datetime.now(timezone.utc).isoformat(),
            event_coverage_fraction=float(features.event_coverage_7d.eq(1).mean()),
            source_hashes={name: sha256((root/name).read_bytes()).hexdigest() for name in
                ['prices.parquet','baselines.parquet','events.parquet','events-enriched.parquet'] if (root/name).exists()},
            code_hashes={p.name: sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
            limitations=['Retrospective price snapshots may contain vendor restatements.',
                'Foundation-model pretraining overlap with historical test periods is unknown.',
                'GDELT archive availability is a lag assumption, not verified publication time.',
                'Country presence links, when enabled, come from dated disclosures; they are not quantitative economic weights or causal evidence.',
                'Current stock universe has survivorship/selection bias.',
                'No prospective evidence, automatic promotion, calibrated intervals, or trading-cost evaluation.'])
        write_json(output/'report.json', manifest)
        packages = subprocess.run([__import__('sys').executable, '-m', 'pip', 'freeze'], capture_output=True, text=True, check=True)
        (output/'requirements-executed.txt').write_text(packages.stdout)
        print(json.dumps({'output': str(output), 'folds': reports}, indent=2))
        return manifest
    except Exception as exc:
        write_json(output/'failure.json', dict(status='failed_no_promotion', error=type(exc).__name__, message=str(exc)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'config/research.json')
    parser.add_argument('--data', type=Path, default=ROOT/'data/research')
    sub = parser.add_subparsers(dest='command', required=True)
    prices = sub.add_parser('collect-prices')
    prices.add_argument('--end', default=str(pd.Timestamp.now(tz='UTC').date()), help='Exclusive date; default excludes today')
    events = sub.add_parser('collect-events')
    events.add_argument('--start', required=True)
    events.add_argument('--end', required=True, help='Exclusive; use bounded resumable chunks')
    sub.add_parser('baseline')
    sub.add_parser('enrich-events', help='Attach dated country-presence features from cached archives')
    train = sub.add_parser('train')
    train.add_argument('--output', type=Path, required=True)
    train.add_argument('--market-only', action='store_true')
    train.add_argument('--holdout', action='store_true', help='Explicitly consume reserved holdout; do not tune afterward')
    run = sub.add_parser('run', help='Collect → baseline → features → evaluate → save')
    run.add_argument('--end', required=True)
    run.add_argument('--events-start', required=True)
    run.add_argument('--events-end', required=True)
    run.add_argument('--output', type=Path, required=True)
    predict = sub.add_parser('predict')
    predict.add_argument('--artifact', type=Path, required=True)
    predict.add_argument('--output', type=Path, required=True)
    demo = sub.add_parser('smoke')
    demo.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.command == 'run':
        if args.output.exists():
            raise FileExistsError('Choose a new output folder')
        collect_prices(config['stocks']+config['market_context'], config['start'], args.end, args.data)
        collect_events(args.events_start, args.events_end, args.data, config['event_lag_days'])
        from .baseline import timesfm_baselines
        timesfm_baselines(pd.read_parquet(args.data/'prices.parquet'), config, args.data)
        if config.get('exposure_registry'):
            from .exposures import enrich_events, export_review_examples
            enrich_events(args.data, config['exposure_registry'])
            export_review_examples(args.data, config['exposure_registry'])
        run_experiment(args.data, config, args.output)
    elif args.command == 'predict':
        from .model import load_bundle
        if args.output.exists():
            raise FileExistsError('Refusing to overwrite a prediction file')
        bundle = load_bundle(args.artifact)
        event_path = args.data/('events-enriched.parquet' if bundle.config.get('exposure_registry') else 'events.parquet')
        events = pd.read_parquet(event_path) if event_path.exists() else None
        result = bundle.predict(pd.read_parquet(args.data/'prices.parquet'), events, pd.read_parquet(args.data/'baselines.parquet'))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.to_parquet(args.output, index=False)
        print(result.to_string(index=False))
    elif args.command == 'collect-prices':
        collect_prices(config['stocks']+config['market_context'], config['start'], args.end, args.data)
    elif args.command == 'collect-events':
        # Merge completed chunks rather than replace previously collected history.
        previous = pd.read_parquet(args.data/'events.parquet') if (args.data/'events.parquet').exists() else None
        daily, _ = collect_events(args.start, args.end, args.data, config['event_lag_days'])
        if previous is not None:
            pd.concat([previous,daily]).drop_duplicates('archive_day', keep='last').sort_values('available_at').to_parquet(args.data/'events.parquet', index=False)
    elif args.command == 'enrich-events':
        from .exposures import enrich_events, export_review_examples
        if not config.get('exposure_registry'):
            raise ValueError('Config needs a sourced exposure_registry')
        enrich_events(args.data, config['exposure_registry'])
        export_review_examples(args.data, config['exposure_registry'])
    elif args.command == 'baseline':
        from .baseline import timesfm_baselines
        timesfm_baselines(pd.read_parquet(args.data/'prices.parquet'), config, args.data)
    elif args.command == 'train':
        run_experiment(args.data, config, args.output, not args.market_only, args.holdout)
    else:
        from .fixtures import synthetic_inputs
        if args.data.exists() and any(args.data.iterdir()):
            raise ValueError('Smoke fixtures require a new empty data folder')
        args.data.mkdir(parents=True, exist_ok=True)
        inputs = synthetic_inputs()
        for frame, name in zip(inputs, ['prices','events','baselines']):
            frame.to_parquet(args.data/f'{name}.parquet', index=False)
        config.update(stocks=['AAPL','FCX'], validation_windows=[['2021-01-01','2022-01-01'],['2022-01-01','2023-01-01']], holdout_start='2023-01-01')
        run_experiment(args.data, config, args.output, data_kind='synthetic_verification_only')


if __name__ == '__main__':
    main()
