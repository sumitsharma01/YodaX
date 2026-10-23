"""Separate append-only shadow predictions. Never updates public forecast tables."""
import json
from datetime import datetime, timezone
from .core import connect


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS shadow_runs (
      id TEXT PRIMARY KEY, candidate TEXT NOT NULL, cutoff TEXT, started_at TEXT NOT NULL,
      finished_at TEXT, status TEXT NOT NULL, detail TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS shadow_predictions (
      candidate TEXT NOT NULL, symbol TEXT NOT NULL, cutoff TEXT NOT NULL, target TEXT NOT NULL,
      model TEXT NOT NULL, issued_at TEXT NOT NULL, payload TEXT NOT NULL,
      actual REAL, scored_at TEXT, evaluation TEXT, scoring_issue TEXT,
      PRIMARY KEY(candidate,symbol,cutoff,model));
    ''')


def start_run(db, run_id, candidate):
    schema(db)
    db.execute('INSERT INTO shadow_runs VALUES (?,?,NULL,?,NULL,?,?)',
               (run_id,candidate,now_iso(),'running','{}'))


def finish_run(db, run_id, cutoff, status, detail):
    db.execute('UPDATE shadow_runs SET cutoff=?,finished_at=?,status=?,detail=? WHERE id=?',
               (cutoff,now_iso(),status,json.dumps(detail,allow_nan=False),run_id))


def save_prediction(db, candidate, symbol, cutoff, target, model, issued_at, payload, deadline):
    import pandas as pd
    if pd.Timestamp(issued_at) >= pd.Timestamp(deadline):
        raise ValueError('Issuance deadline passed; refusing retrospective shadow forecast')
    if not payload.get('prospective') or payload.get('horizon_sessions') != 5:
        raise ValueError('Shadow v1 requires prospective five-session forecasts')
    db.execute('INSERT OR IGNORE INTO shadow_predictions VALUES (?,?,?,?,?,?,?,NULL,NULL,NULL,NULL)',
        (candidate,symbol,cutoff,target,model,issued_at,json.dumps(payload,allow_nan=False)))


def score_pending(db, prices, now=None):
    """Only assign outcomes; immutable predicted values stay in the original payload."""
    import math
    import pandas as pd
    import exchange_calendars as xcals
    now = pd.Timestamp(now or now_iso())
    cal = xcals.get_calendar('XNYS')
    count = 0
    for saved in db.execute('SELECT * FROM shadow_predictions WHERE actual IS NULL').fetchall():
        target = pd.Timestamp(saved['target'])
        if cal.session_close(target) + pd.Timedelta(hours=1) > now:
            continue
        frame = prices[prices.symbol.eq(saved['symbol'])].set_index('date').sort_index()
        cutoff = pd.Timestamp(saved['cutoff'])
        if cutoff not in frame.index or target not in frame.index:
            issue = 'Awaiting verified cutoff and target closing prices'
        else:
            payload = json.loads(saved['payload'])
            window = frame.loc[(frame.index > cutoff) & (frame.index <= target)]
            actual = float(frame.loc[target,'close'])
            expected = cal.sessions_in_range(cutoff,target).tz_localize(None)[1:]
            issue = None
            if list(window.index) != list(expected):
                issue = 'Missing sessions in outcome window'
            elif window.split.ne(0).any() or abs(float(frame.loc[cutoff,'close'])/payload['previous']-1) > .001:
                issue = 'Corporate action or historical price restatement requires review'
            elif not math.isfinite(actual) or actual <= 0:
                issue = 'Invalid outcome price'
            if issue is None:
                actual_return = actual/payload['previous']-1
                predicted_return = payload['predicted_return']
                sign = lambda x: (x > 0)-(x < 0)
                result = dict(actual_return=actual_return,
                    absolute_error_pp=abs(predicted_return-actual_return)*100,
                    squared_error_pp=((predicted_return-actual_return)*100)**2,
                    direction_correct=sign(predicted_return)==sign(actual_return))
                db.execute('UPDATE shadow_predictions SET actual=?,scored_at=?,evaluation=?,scoring_issue=NULL '
                           'WHERE candidate=? AND symbol=? AND cutoff=? AND model=? AND actual IS NULL',
                    (actual,now.isoformat(),json.dumps(result),saved['candidate'],saved['symbol'],saved['cutoff'],saved['model']))
                count += 1
                continue
        db.execute('UPDATE shadow_predictions SET scoring_issue=? WHERE candidate=? AND symbol=? AND cutoff=? AND model=? AND actual IS NULL',
            (issue,saved['candidate'],saved['symbol'],saved['cutoff'],saved['model']))
    return count


def summary(db):
    import math
    from collections import defaultdict
    schema(db)
    # Bounded UI payload; summary covers the full saved history independently.
    raw = db.execute('SELECT * FROM shadow_predictions ORDER BY cutoff DESC,symbol,model LIMIT 600').fetchall()
    predictions = []
    for row in raw:
        value = dict(row)
        value['payload'] = json.loads(value['payload'])
        value['evaluation'] = json.loads(value['evaluation']) if value['evaluation'] else None
        predictions.append(value)
    metrics = []
    groups = defaultdict(list)
    all_rows = db.execute('SELECT candidate,symbol,cutoff,model,evaluation FROM shadow_predictions WHERE evaluation IS NOT NULL').fetchall()
    for row in all_rows:
        groups[(row['candidate'],row['model'])].append((row['cutoff'],json.loads(row['evaluation'])))
    for (candidate,model), values in groups.items():
        metrics.append(dict(candidate=candidate,model=model,scored=len(values),dates=len(set(d for d,_ in values)),
            mae_pp=sum(v['absolute_error_pp'] for _,v in values)/len(values),
            rmse_pp=math.sqrt(sum(v['squared_error_pp'] for _,v in values)/len(values)),
            direction_accuracy=sum(v['direction_correct'] for _,v in values)/len(values)))
    # Compare ONLY matched assets, dates and candidate versions, never unmatched averages.
    paired = defaultdict(dict)
    for row in all_rows:
        paired[(row['candidate'],row['symbol'],row['cutoff'])][row['model']] = json.loads(row['evaluation'])
    comparisons = []
    for candidate in sorted({key[0] for key in paired}):
        matches=[(key,values) for key,values in paired.items() if key[0]==candidate and all(m in values for m in ['timesfm','market_adjusted','event_adjusted'])]
        if matches:
            comparisons.append(dict(candidate=candidate,matched_forecasts=len(matches),dates=len({key[2] for key,_ in matches}),
                improvement_vs_timesfm_pp=sum(v['timesfm']['absolute_error_pp']-v['event_adjusted']['absolute_error_pp'] for _,v in matches)/len(matches),
                improvement_vs_market_pp=sum(v['market_adjusted']['absolute_error_pp']-v['event_adjusted']['absolute_error_pp'] for _,v in matches)/len(matches)))
    runs=[]
    for row in db.execute('SELECT * FROM shadow_runs ORDER BY started_at DESC LIMIT 50').fetchall():
        value=dict(row);value['detail']=json.loads(value['detail']);runs.append(value)
    return dict(mode='shadow',horizon_sessions=5,public_forecasts_changed=False,
        evidence_status='Prospective monitoring only. No automatic promotion; overlapping targets are dependent.',
        predictions=predictions,metrics=metrics,comparisons=comparisons,runs=runs,
        counts=dict(db.execute('SELECT count(*) AS issued,sum(CASE WHEN actual IS NOT NULL THEN 1 ELSE 0 END) AS scored FROM shadow_predictions').fetchone()))
