"""Issue and score chat-requested US stock forecasts after completed closes.

Run separately from the web process: python -m backend.requested_forecasts.
"""
import json
import math
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import exchange_calendars as xcals
import yfinance as yf
from .core import connect, DATA, MODEL_ID, MODEL_REVISION, metrics
from .prediction_requests import schema, database
from .learning import scale_from_history, score


def target_session(calendar, cutoff, horizon):
    target = cutoff
    for _ in range(horizon):
        target = calendar.next_session(target)
    return target


def evaluate(payload, actual):
    return {**metrics(payload['previous'], payload['predicted'], actual),
            **score(payload['previous'], payload['predicted'], actual, payload['scale'])}


def run():
    now = pd.Timestamp.now(tz='UTC')
    cal = xcals.get_calendar('XNYS')
    sessions = cal.sessions_in_range((now-pd.Timedelta(days=20)).date(), now.date())
    cutoff = [s for s in sessions if cal.session_close(s)+pd.Timedelta(hours=1) <= now][-1]
    with database() as db:
        schema(db)
        rows = [dict(r) for r in db.execute("SELECT * FROM prediction_requests WHERE state IN ('queued','predicted') ORDER BY requested_at").fetchall()]
    model = None
    issued = 0
    for row in rows:
        payload = json.loads(row['payload'])
        if row['state'] == 'predicted' and payload['target'] > str(cutoff.date()):
            continue
        if row['state'] == 'queued' and (issued >= 10 or now >= cal.session_open(cal.next_session(cutoff))):
            continue
        try:
            ticker = yf.Ticker(row['symbol'])
            frame = ticker.history(start=str((cutoff-pd.Timedelta(days=1000)).date()),
                end=str((cutoff+pd.Timedelta(days=1)).date()), auto_adjust=False, actions=True, timeout=30)
            # v1 supports exchange-calendar-compatible US-listed equities only.
            metadata = ticker.get_history_metadata()
            if metadata.get('instrumentType') != 'EQUITY' or metadata.get('exchangeTimezoneName') != 'America/New_York':
                raise ValueError('Only US-listed stocks are supported by this forecast worker.')
            frame.index = frame.index.tz_localize(None).normalize()
            frame = frame.loc[frame.index <= cutoff.tz_localize(None)]
            if frame.empty or str(frame.index[-1].date()) != str(cutoff.date()):
                raise ValueError('Latest completed closing price is unavailable; try again after the next close.')
            if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
                raise ValueError('Price history dates are invalid.')
            if row['state'] == 'predicted':
                target = pd.Timestamp(payload['target'])
                if target not in frame.index: continue
                observed = frame.loc[frame.index > pd.Timestamp(payload['cutoff'])]
                observed = observed.loc[observed.index <= target]
                if (observed['Stock Splits'] != 0).any():
                    raise ValueError('A stock split requires review before scoring.')
                if abs(float(frame.loc[pd.Timestamp(payload['cutoff']), 'Close'])/payload['previous']-1)>0.001:
                    raise ValueError('Historical price restatement requires review before scoring.')
                actual = float(frame.loc[target, 'Close'])
                payload.update(actual=actual, scored_at=datetime.now(timezone.utc).isoformat(), evaluation=evaluate(payload, actual))
                state = 'scored'
            else:
                closes = frame['Close'].to_numpy(dtype=float)
                if len(closes)<256 or not np.isfinite(closes).all() or (closes<=0).any():
                    raise ValueError('At least 256 valid closing prices are required.')
                expected = cal.sessions_in_range(frame.index[-256], cutoff)
                if list(expected.date) != list(frame.index[-256:].date):
                    raise ValueError('Price history has missing trading sessions.')
                if (frame['Stock Splits'].iloc[-256:] != 0).any():
                    raise ValueError('Recent stock split requires a price-history review.')
                if model is None:
                    import timesfm, torch
                    from huggingface_hub import snapshot_download
                    torch.set_num_threads(4)
                    folder = snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=DATA/'model', allow_patterns=['*.json','*.safetensors'])
                    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(folder, torch_compile=False, local_files_only=True)
                    model.compile(timesfm.ForecastConfig(max_context=256,max_horizon=64,per_core_batch_size=1,
                        normalize_inputs=True,use_continuous_quantile_head=True,force_flip_invariance=True,
                        infer_is_positive=True,fix_quantile_crossing=True))
                horizon = row['horizon']
                prediction, quantiles = model.forecast(horizon=horizon, inputs=[closes[-256:]])
                predicted = float(prediction[0,horizon-1]); low = float(quantiles[0,horizon-1,1]); high = float(quantiles[0,horizon-1,9])
                if not all(math.isfinite(v) and v>0 for v in (predicted,low,high)) or low>high:
                    raise ValueError('Invalid model output; no prediction saved.')
                if pd.Timestamp.now(tz='UTC') >= cal.session_open(cal.next_session(cutoff)):
                    continue
                payload = dict(predicted=predicted,low=low,high=high,previous=float(closes[-1]),
                    cutoff=str(cutoff.date()),target=str(target_session(cal,cutoff,horizon).date()),
                    issued_at=datetime.now(timezone.utc).isoformat(), model=MODEL_ID,model_revision=MODEL_REVISION,
                    currency='USD',scale=scale_from_history(closes.tolist())*math.sqrt(horizon))
                state = 'predicted'; issued += 1
            with database() as db:
                db.execute('UPDATE prediction_requests SET state=?,payload=? WHERE id=? AND state=?',
                           (state,json.dumps(payload,allow_nan=False),row['id'],row['state']))
            print(row['symbol'], state, flush=True)
        except ValueError as exc:
            # Preserve issued values even if corporate actions prevent evaluation.
            payload['error'] = str(exc)
            with database() as db:
                db.execute('UPDATE prediction_requests SET state=?,payload=? WHERE id=? AND state=?',
                    ('review' if row['state']=='predicted' else 'error',json.dumps(payload),row['id'],row['state']))
        except Exception as exc:
            # Transient provider/model failure leaves the request eligible next run.
            print(row['symbol'], 'deferred:', type(exc).__name__, flush=True)

if __name__ == '__main__':
    run()
