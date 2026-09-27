"""Fetch completed daily bars, run real TimesFM inference, and atomically publish.

Usage: .venv/bin/python -m backend.run [--backtest-days 10]
"""
import argparse
import fcntl
import hashlib
import json
import os
import time
from datetime import datetime, timezone

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import yfinance as yf
from .learning import schema as learning_schema, advance
from .core import COMPANIES, DATA, MODEL_ID, MODEL_REVISION, connect, context_for, metrics, save_forecast


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def run(backtest_days=10):
    from .fx import refresh
    try:
        refresh()
    except Exception as error:
        print(f'Currency refresh failed; retaining cached rates: {type(error).__name__}', flush=True)
    import timesfm
    import torch
    from huggingface_hub import snapshot_download

    started = time.monotonic()
    now = pd.Timestamp.now(tz='UTC')
    calendar = xcals.get_calendar('XNYS')
    sessions = calendar.sessions_in_range((now-pd.Timedelta(days=20)).date(), now.date())
    completed = [d for d in sessions if calendar.session_close(d)+pd.Timedelta(hours=1) <= now]
    cutoff = completed[-1]
    target = calendar.next_session(cutoff)
    DATA.mkdir(exist_ok=True)
    yf.set_tz_cache_location(str(DATA / 'yf-cache'))
    snapshots, jobs, inputs = [], [], []
    for company in COMPANIES:
        symbol = company['symbol']
        print(f'Fetching {symbol} through {cutoff.date()}', flush=True)
        frame = yf.Ticker(symbol).history(
            start=str((cutoff-pd.Timedelta(days=800)).date()),
            end=str((cutoff+pd.Timedelta(days=1)).date()),
            auto_adjust=False, actions=True, raise_errors=True, timeout=30)
        frame.index = frame.index.tz_localize(None).normalize()
        frame = frame.loc[frame.index <= cutoff.tz_localize(None)]
        if frame.empty or frame.index[-1].date() != cutoff.date():
            raise ValueError(f'{symbol}: missing latest completed session; refusing stale forecast')
        if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
            raise ValueError(f'{symbol}: invalid date order')
        closes = frame['Close'].to_numpy(dtype=np.float64)
        if len(closes) < 256+backtest_days or not np.isfinite(closes).all() or (closes<=0).any():
            raise ValueError(f'{symbol}: insufficient or invalid price history')
        expected = calendar.sessions_in_range(frame.index[-256-backtest_days], cutoff)
        if list(expected.date) != list(frame.index[-len(expected):].date):
            raise ValueError(f'{symbol}: missing trading sessions in input window')
        # Reject recent split targets rather than silently compare incompatible price scales.
        if (frame['Stock Splits'].iloc[-backtest_days-1:] != 0).any():
            raise ValueError(f'{symbol}: recent split requires corporate-action review')
        csv = frame.to_csv().encode()
        digest = hashlib.sha256(csv).hexdigest()
        (DATA / 'snapshots').mkdir(exist_ok=True)
        (DATA / 'snapshots' / f'{symbol}-{digest[:16]}.csv').write_bytes(csv)
        dates = [str(d.date()) for d in frame.index]
        snapshot = dict(**company, history=closes.tolist(), dates=dates, price=float(closes[-1]),
                        change=float(closes[-1]/closes[-2]-1), snapshot_sha=digest)
        snapshots.append(snapshot)
        for idx in range(len(closes)-backtest_days, len(closes)+1):
            inputs.append(context_for(closes, idx))
            jobs.append(dict(symbol=symbol, target=dates[idx] if idx<len(closes) else str(target.date()),
                             cutoff=dates[idx-1], previous=float(closes[idx-1]),
                             actual=float(closes[idx]) if idx<len(closes) else None,
                             kind='historical' if idx<len(closes) else 'prospective', snapshot_sha=digest))
    revision_file = DATA / 'model-revision.txt'
    revision = MODEL_REVISION
    revision_file.write_text(revision+'\n')
    print(f'Loading TimesFM 2.5 revision {revision} on CPU', flush=True)
    model_dir = snapshot_download(MODEL_ID, revision=revision, local_dir=DATA/'model', allow_patterns=['*.json','*.safetensors'])
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(model_dir, torch_compile=False, local_files_only=True)
    model.compile(timesfm.ForecastConfig(max_context=256, max_horizon=1,
                  per_core_batch_size=4, normalize_inputs=True, use_continuous_quantile_head=True,
                  force_flip_invariance=True, infer_is_positive=True, fix_quantile_crossing=True))
    predictions, quantiles = [], []
    for offset in range(0, len(inputs), 4):
        p, q = model.forecast(horizon=1, inputs=inputs[offset:offset+4])
        predictions.extend(p[:,0].tolist())
        quantiles.extend(q[:,0,:].tolist())
        print(f'Inferred {min(offset+4,len(inputs))}/{len(inputs)} forecasts', flush=True)
    if len(predictions) != len(jobs):
        raise ValueError('Incomplete model output')
    created_at = now_iso()
    if pd.Timestamp(created_at) >= calendar.session_open(target):
        raise ValueError('Target session has started; rerun after the next completed close')
    with connect() as db:
        learning_schema(db)
        for job, predicted, quantile in zip(jobs, predictions, quantiles):
            if not np.isfinite([predicted,*quantile]).all() or min(predicted,quantile[1],quantile[9]) <= 0:
                raise ValueError('Invalid model output; no results published')
            save_forecast(db, dict(**job, created_at=created_at, model_revision=revision,
                                  predicted=predicted, low=quantile[1], high=quantile[9],
                                  scored_at=created_at if job['actual'] is not None else None))
        for snapshot in snapshots:
            # Previously made forecasts gain an outcome only after the session completes.
            for pending in db.execute("SELECT * FROM forecasts WHERE symbol=? AND kind='prospective' AND actual IS NULL", (snapshot['symbol'],)).fetchall():
                if pending['target'] in snapshot['dates']:
                    index = snapshot['dates'].index(pending['target'])
                    # Detect price restatements instead of silently changing the scale.
                    if index == 0 or abs(snapshot['history'][index-1]/pending['previous']-1) > 0.001:
                        continue
                    db.execute('UPDATE forecasts SET actual=?, scored_at=? WHERE symbol=? AND target=? AND model_revision=? AND kind=?',
                               (snapshot['history'][index],created_at,pending['symbol'],pending['target'],pending['model_revision'],pending['kind']))
            rows = [dict(r) for r in db.execute('SELECT * FROM forecasts WHERE symbol=? AND model_revision=? ORDER BY target', (snapshot['symbol'],revision))]
            snapshot['records'] = [dict(r, date=r['target'], **metrics(r['previous'],r['predicted'],r['actual'])) for r in rows if r['actual'] is not None]
            snapshot['forecast'] = next(r for r in rows if r['target']==str(target.date()) and r['kind']=='prospective')
            snapshot['drift'] = snapshot['forecast']['predicted']/snapshot['price']-1
            advance(db, snapshot, revision, created_at)
        payload = dict(stocks=snapshots, generated_at=created_at, cutoff=str(cutoff.date()),target=str(target.date()),
                       source='Yahoo Finance via yfinance', model=MODEL_ID, model_revision=revision,
                       runtime='Local CPU · PyTorch', context_sessions=256, duration_seconds=round(time.monotonic()-started,2),
                       price_basis='Yahoo Close (split-adjusted, not dividend-adjusted)',backtest_days=backtest_days)
        db.execute('INSERT OR REPLACE INTO dashboard VALUES (1,?)', (json.dumps(payload, allow_nan=False),))
    print(f"Published {len(snapshots)} forecasts; {len(jobs)-len(snapshots)} historical evaluations in {payload['duration_seconds']}s", flush=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--backtest-days',type=int,default=10,choices=range(1,61))
    args=parser.parse_args()
    DATA.mkdir(exist_ok=True)
    with (DATA/'run.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args.backtest_days)
