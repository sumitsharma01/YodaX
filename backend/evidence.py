"""Read-only evidence for adaptation: prospective records and a separate historical replay."""
import json
from datetime import datetime, timezone
import exchange_calendars as xcals
import pandas as pd
from .learning import VERSION, initial_state, issue, update, scale_from_history


def errors(previous, raw, adaptive, actual):
    return dict(raw_error=abs(raw-actual)/previous*100,
                adaptive_error=abs(adaptive-actual)/previous*100,
                baseline_error=abs(previous-actual)/previous*100)


def summarize(rows):
    if not rows:
        return dict(count=0, sessions=0, raw_error=None, adaptive_error=None, baseline_error=None, improvement=None)
    values={key:sum(r[key] for r in rows)/len(rows) for key in ('raw_error','adaptive_error','baseline_error')}
    return dict(count=len(rows), sessions=len({r['target'] for r in rows}), **values,
                improvement=(1-values['adaptive_error']/values['raw_error'])*100 if values['raw_error'] else None)


def replay(stocks):
    """Predict before updating at each historical target; never mutate the live learner."""
    rows=[]
    for stock in stocks:
        state=initial_state()
        dates=stock['dates']
        for record in sorted((r for r in stock['records'] if r['kind']=='historical'), key=lambda r:r['target']):
            if record['target'] not in dates:
                continue
            index=dates.index(record['target'])
            if index < 21:
                continue
            before=json.loads(json.dumps(state))
            prediction=issue(record['previous'],record['predicted'],scale_from_history(stock['history'][:index]),state)
            state=update(state,prediction,record['actual'],record['previous'])
            rows.append(dict(symbol=stock['symbol'],target=record['target'],cutoff=record['cutoff'],
                             raw=record['predicted'],adaptive=prediction['predicted'],actual=record['actual'],
                             previous=record['previous'],state_before=before,state_after=state,
                             experts=prediction['experts'],source_created_at=record['created_at'],
                             snapshot_sha=record.get('snapshot_sha'), **errors(record['previous'],record['predicted'],prediction['predicted'],record['actual'])))
    rows.sort(key=lambda r:(r['target'],r['symbol']))
    trend=[]
    for target in sorted({r['target'] for r in rows}):
        trend.append(dict(target=target,**summarize([r for r in rows if r['target']<=target])))
    return dict(kind='historical_replay',version=VERSION,rows=rows,summary=summarize(rows),trend=trend)


def build(db, payload, now=None):
    now=now or datetime.now(timezone.utc)
    pending=[]; settled=[]
    calendar=xcals.get_calendar('XNYS')
    for row in db.execute('''SELECT a.*,f.predicted AS raw,f.cutoff,f.snapshot_sha FROM adaptive_forecasts a
        JOIN forecasts f ON a.symbol=f.symbol AND a.target=f.target AND a.revision=f.model_revision
        AND f.kind='prospective' WHERE a.revision=? AND a.version=? ORDER BY a.target,a.symbol''',
        (payload['model_revision'],VERSION)):
        row=dict(row); prediction=json.loads(row['payload'])
        item=dict(symbol=row['symbol'],target=row['target'],cutoff=row['cutoff'],created_at=row['created_at'],
                  raw=row['raw'],adaptive=prediction['predicted'],previous=row['previous'],
                  weights=prediction['weights'],prior_count=prediction['prior_count'],snapshot_sha=row['snapshot_sha'])
        if row['evaluated_at']:
            result=json.loads(row['result'])
            item.update(actual=row['actual'],evaluated_at=row['evaluated_at'],
                        state_before=result.get('state_before'),state_after=result.get('state_after'),
                        **errors(row['previous'],row['raw'],prediction['predicted'],row['actual']))
            settled.append(item)
        else:
            eligible=calendar.session_close(pd.Timestamp(row['target']))+pd.Timedelta(hours=1)
            item.update(score_after=eligible.isoformat(),status='waiting_for_close' if pd.Timestamp(now)<eligible else 'awaiting_daily_run')
            pending.append(item)
    return dict(as_of=now.isoformat(),model=payload['model'],model_revision=payload['model_revision'],
                generated_at=payload['generated_at'],live=dict(rows=settled,pending=pending,summary=summarize(settled)),
                replay=replay(payload['stocks']))
