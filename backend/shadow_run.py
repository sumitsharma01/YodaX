"""Separate prospective shadow worker. Failures never write public forecasts.

python -m backend.shadow_run [--check] [--score-only]
Default scores/collects and issues only within a valid prospective window.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import uuid
import numpy as np
import pandas as pd
import exchange_calendars as xcals
from .core import ROOT, DATA, connect, MODEL_REVISION
from .shadow_store import schema,start_run,finish_run,save_prediction,score_pending,now_iso


def load_candidate(config_path=None):
    from research_pipeline.model import load_bundle
    cfg=json.loads((Path(config_path) if config_path else ROOT/'config/shadow.json').read_text())
    if cfg['horizon_sessions']!=5 or cfg['mode']!='shadow':
        raise ValueError('Unsupported shadow contract')
    models={}
    for name,artifact in cfg['artifacts'].items():
        folder=ROOT/artifact['path']
        if sha256((folder/'pipeline.joblib').read_bytes()).hexdigest()!=artifact['sha256']:
            raise ValueError('Frozen candidate checksum mismatch')
        models[name]=load_bundle(folder)
        if models[name].config['stocks']!=cfg['symbols'] or models[name].config['horizon']!=5:
            raise ValueError('Candidate scope mismatch')
        if models[name].metadata['baseline_revisions']!=[MODEL_REVISION]:
            raise ValueError('Candidate baseline revision mismatch')
    return cfg,models


def run(check=False, issue=True, config_path=None):
    from research_pipeline.collect import collect_prices,collect_events
    from research_pipeline.baseline import timesfm_baselines
    from research_pipeline.exposures import enrich_events
    from research_pipeline.features import build_features
    cfg,models=load_candidate(config_path) if config_path else load_candidate()
    if check:
        print(json.dumps(dict(status='verified',candidate=cfg['candidate'],symbols=cfg['symbols'],horizon_sessions=5)))
        return
    run_id=uuid.uuid4().hex
    with connect() as db:
        start_run(db,run_id,cfg['candidate'])
    cutoff=None
    try:
        now=pd.Timestamp.now(tz='UTC');cal=xcals.get_calendar('XNYS')
        sessions=cal.sessions_in_range((now-pd.Timedelta(days=20)).date(),now.date())
        completed=[d for d in sessions if cal.session_close(d)+pd.Timedelta(hours=1)<=now]
        cutoff=completed[-1]
        cutoff_text=str(cutoff.date())
        from .market_context import FUTURES
        # Futures daily candles must also be final, even on the shared XNYS grid.
        for symbol in cfg['symbols']:
            if symbol in FUTURES:
                future_cal=xcals.get_calendar(FUTURES[symbol]['close_calendar'])
                if not future_cal.is_session(cutoff) or future_cal.session_close(cutoff)+pd.Timedelta(hours=1)>now:
                    with connect() as db:
                        finish_run(db,run_id,cutoff_text,'skipped',dict(reason='awaiting_completed_futures_close'))
                    return
        target=cutoff
        for _ in range(5):target=cal.next_session(target)
        target_text=str(target.date())
        deadline=cal.session_open(cal.next_session(cutoff))
        # Reject retrospectively backfilled candidate predictions, including old training runs.
        if any(pd.Timestamp(m.metadata['last_training_target'])>=cutoff.tz_localize(None) for m in models.values()):
            raise ValueError('Candidate training extends beyond the forecast cutoff')
        work=DATA/'shadow-work'/run_id
        work.mkdir(parents=True)
        model_config=models['event_adjusted'].config
        requested=list(dict.fromkeys(cfg['symbols']+['SPY','CL=F','HG=F']))
        prices,coverage=collect_prices(requested,str((cutoff-pd.Timedelta(days=800)).date()),
            str((cutoff+pd.Timedelta(days=1)).date()),work)
        # Use exactly the same daily reference grid as feature engineering/scoring.
        grid=cal.sessions_in_range(prices.date.min(),cutoff).tz_localize(None)
        prices=prices[prices.date.isin(grid)].copy()
        prices.to_parquet(work/'model-prices.parquet',index=False)
        fresh={symbol for symbol in cfg['symbols'] if prices.loc[prices.symbol.eq(symbol),'date'].max()==cutoff.tz_localize(None)}
        if fresh!=set(cfg['symbols']):
            raise ValueError('Latest completed equity prices missing')
        with connect() as db:
            schema(db);scored=score_pending(db,prices,candidate=cfg['candidate'])
            existing={(r['symbol'],r['model']) for r in db.execute('SELECT symbol,model FROM shadow_predictions WHERE candidate=? AND cutoff=?',(cfg['candidate'],cutoff_text))}
        comparison_models=['timesfm','market_adjusted','event_adjusted']+(['no_change'] if cfg.get('include_no_change') else [])
        required={(s,m) for s in cfg['symbols'] for m in comparison_models}
        if not issue or pd.Timestamp.now(tz='UTC')>=deadline or existing==required:
            reason='already_issued' if existing==required else ('score_only' if not issue else 'issuance_window_closed')
            with connect() as db:finish_run(db,run_id,cutoff_text,'skipped',dict(reason=reason,newly_scored=scored))
            return
        baselines=timesfm_baselines(prices,model_config,work,only_latest=True)
        # End-of-day archive features use the frozen two-day replay lag, also in live collection.
        lag=model_config['event_lag_days']
        last=cutoff.tz_localize(None)-pd.Timedelta(days=lag)
        events=None;event_problem=None
        try:
            events,_=collect_events(str((last-pd.Timedelta(days=6)).date()),str((last+pd.Timedelta(days=1)).date()),work,lag)
            if model_config.get('exposure_registry'):
                events=enrich_events(work,model_config['exposure_registry'])
        except Exception as exc:
            event_problem='Event collection incomplete: '+type(exc).__name__
        features=build_features(prices,events,baselines,model_config)
        latest=features[features.date.eq(cutoff.tz_localize(None))]
        if set(latest.symbol)!=set(cfg['symbols']):
            raise ValueError('Current feature context incomplete')
        baseline_hash=sha256((work/'baselines.parquet').read_bytes()).hexdigest()
        snapshot_hash=sha256((work/'model-prices.parquet').read_bytes()).hexdigest()
        event_path=work/('events-enriched.parquet' if model_config.get('exposure_registry') else 'events.parquet')
        event_hash=sha256(event_path.read_bytes()).hexdigest() if event_path.exists() else None
        outputs={'timesfm':latest.baseline_return.to_numpy(),
                 'market_adjusted':models['market_adjusted'].predict_features(latest)}
        if cfg.get('include_no_change'):
            outputs['no_change']=np.zeros(len(latest))
        try:
            if event_problem:raise ValueError(event_problem)
            outputs['event_adjusted']=models['event_adjusted'].predict_features(latest)
        except ValueError:
            event_problem=event_problem or 'Missing, incomplete or expired exposure/event inputs'
        issued=now_iso()
        # One transaction prevents partial per-model publication if the deadline passes.
        with connect() as db:
            for model,values in outputs.items():
                for row,predicted_return in zip(latest.itertuples(),values):
                    if not np.isfinite(predicted_return) or predicted_return<=-1:
                        raise ValueError('Invalid shadow output')
                    payload=dict(prospective=True,horizon_sessions=5,previous=float(row.close),
                        predicted_return=float(predicted_return),predicted=float(row.close*(1+predicted_return)),
                        model_revision=MODEL_REVISION,artifact_sha=cfg['artifacts'].get(model,{}).get('sha256'),
                        feature_version=models['event_adjusted'].metadata['feature_version'],
                        prices_sha=snapshot_hash,baseline_sha=baseline_hash,events_sha=event_hash,
                        event_coverage=float(row.event_coverage_7d),exposure_coverage=float(row.exposure_coverage_7d) if model_config.get('exposure_registry') else None,
                        source='Yahoo Finance, GDELT daily archives'+(', dated company disclosures' if model_config.get('exposure_registry') else ''),
                        exposure_sources=model_config.get('exposure_registry'),run_id=run_id,deadline=deadline.isoformat(),
                        unit=FUTURES.get(row.symbol,{}).get('unit','USD per share'),
                        asset_type='futures_proxy' if row.symbol in FUTURES else 'equity',
                        model_inputs={name:float(getattr(row,name)) if np.isfinite(getattr(row,name)) else None for name in
                            ['return_5','volatility_20','market_return_5','oil_return_5','copper_return_5','event_log_count_7d','material_conflict_share_7d','material_cooperation_share_7d','event_coverage_7d']},
                        event_sources=[f'https://data.gdeltproject.org/events/{day.strftime("%Y%m%d")}.export.CSV.zip' for day in pd.date_range(last-pd.Timedelta(days=6),last)],
                        event_lag_days=lag,
                        model_input_note='Structured global event counts and cooperation/conflict shares, lagged two days; not causal estimates or Gemini headline sentiment.' if not model_config.get('exposure_registry') else 'Structured GDELT events and dated company country exposures.')
                    save_prediction(db,cfg['candidate'],row.symbol,cutoff_text,target_text,model,issued,payload,deadline)
            finish_run(db,run_id,cutoff_text,'partial' if event_problem else 'issued',
                dict(newly_scored=scored,issued_models=list(outputs),candidate_skip_reason=event_problem,
                     target=target_text,source_cutoff=cutoff_text))
        print(json.dumps(dict(candidate=cfg['candidate'],status='partial' if event_problem else 'issued',cutoff=cutoff_text,target=target_text)))
        if event_problem:
            raise RuntimeError('Shadow candidate skipped; see private evaluation run details')
    except Exception as exc:
        with connect() as db:
            # Preserve a recorded partial run and any previously saved successful predictions.
            state=db.execute('SELECT status FROM shadow_runs WHERE id=?',(run_id,)).fetchone()
            if state and state['status']=='running':
                finish_run(db,run_id,str(cutoff.date()) if cutoff is not None else None,'failed',
                    dict(error_type=type(exc).__name__,reason='Shadow worker failed; inspect job logs. Public forecasts are unaffected.'))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true')
    p.add_argument('--score-only',action='store_true')
    p.add_argument('--config',type=Path)
    args=p.parse_args()
    run(check=args.check,issue=not args.score_only,config_path=args.config)
