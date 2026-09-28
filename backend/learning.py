"""Versioned online correction layer. TimesFM weights remain frozen.

Only settled prospective predictions update the learner. Each prediction stores
its experts and scale before the outcome, so reruns cannot rewrite its evaluation.
"""
import json
import math
import statistics

VERSION = 'online-v1'
EXPERTS = ('timesfm', 'no_change', 'bias_corrected')

def scale_from_history(values):
    returns = [b/a-1 for a,b in zip(values[-21:-1],values[-20:])]
    if len(returns) < 20:
        raise ValueError('Need 21 prior closes for volatility')
    return max(0.005, statistics.stdev(returns))

def score(previous, predicted, actual, scale):
    if not all(math.isfinite(x) and x > 0 for x in (previous,predicted,actual,scale)):
        raise ValueError('Invalid scoring input')
    signed = predicted-actual
    loss = (signed/previous/scale)**2
    baseline_loss = ((previous-actual)/previous/scale)**2
    return dict(signed_error=signed, absolute_error=abs(signed), normalized_loss=loss,
                score=100/(1+loss), reward=baseline_loss-loss)

def initial_state():
    return dict(weights=[0.6,0.2,0.2], bias=0.0, count=0)

def issue(previous, raw, scale, state):
    correction=max(-scale,min(scale,state['bias']))
    experts=[raw,previous,max(0.01,raw+previous*correction)]
    return dict(experts=experts, weights=list(state['weights']),
                predicted=sum(w*p for w,p in zip(state['weights'],experts)),
                scale=scale, prior_count=state['count'], version=VERSION)

def update(state, prediction, actual, previous):
    losses=[score(previous,p,actual,prediction['scale'])['normalized_loss'] for p in prediction['experts']]
    weights=[w*math.exp(-0.1*min(loss,25)) for w,loss in zip(state['weights'],losses)]
    total=sum(weights)
    # 3% uniform mixing prevents an expert from being permanently eliminated.
    weights=[.97*w/total+.01 for w in weights]
    residual=(actual-prediction['experts'][0])/previous
    bound=prediction['scale']
    bias=.9*state['bias']+.1*max(-bound,min(bound,residual))
    return dict(weights=weights,bias=bias,count=state['count']+1)

def schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS adaptive_forecasts (
      symbol TEXT, target TEXT, revision TEXT, version TEXT,
      created_at TEXT NOT NULL, previous REAL NOT NULL, payload TEXT NOT NULL,
      evaluated_at TEXT, actual REAL, result TEXT,
      PRIMARY KEY(symbol,target,revision,version));
    CREATE TABLE IF NOT EXISTS learning_state (
      symbol TEXT, revision TEXT, version TEXT, payload TEXT NOT NULL,
      PRIMARY KEY(symbol,revision,version));
    ''')

def advance(db, snapshot, revision, now):
    symbol=snapshot['symbol']
    stored=db.execute('SELECT payload FROM learning_state WHERE symbol=? AND revision=? AND version=?', (symbol,revision,VERSION)).fetchone()
    state=json.loads(stored['payload']) if stored else initial_state()
    # Joining only prospective rows makes historical test data ineligible for learning.
    rows=db.execute('''SELECT a.*, f.actual AS outcome FROM adaptive_forecasts a
      JOIN forecasts f ON f.symbol=a.symbol AND f.target=a.target AND f.model_revision=a.revision
      AND f.kind='prospective' WHERE a.symbol=? AND a.revision=? AND a.version=?
      AND a.evaluated_at IS NULL AND f.actual IS NOT NULL AND f.target<=?
      ORDER BY a.target''',(symbol,revision,VERSION,snapshot['forecast']['cutoff'])).fetchall()
    for row in rows:
        prediction=json.loads(row['payload'])
        result=score(row['previous'],prediction['predicted'],row['outcome'],prediction['scale'])
        result['raw']=score(row['previous'],prediction['experts'][0],row['outcome'],prediction['scale'])
        result['state_before']=json.loads(json.dumps(state))
        state=update(state,prediction,row['outcome'],row['previous'])
        result['state_after']=json.loads(json.dumps(state))
        db.execute('UPDATE adaptive_forecasts SET evaluated_at=?,actual=?,result=? WHERE symbol=? AND target=? AND revision=? AND version=?',
                   (now,row['outcome'],json.dumps(result),symbol,row['target'],revision,VERSION))
    db.execute('INSERT OR REPLACE INTO learning_state VALUES (?,?,?,?)',(symbol,revision,VERSION,json.dumps(state)))
    forecast=snapshot['forecast']
    prediction=issue(forecast['previous'],forecast['predicted'],scale_from_history(snapshot['history']),state)
    db.execute('INSERT OR IGNORE INTO adaptive_forecasts VALUES (?,?,?,?,?,?,?,NULL,NULL,NULL)',
               (symbol,forecast['target'],revision,VERSION,now,forecast['previous'],json.dumps(prediction)))
    frozen=db.execute('SELECT * FROM adaptive_forecasts WHERE symbol=? AND target=? AND revision=? AND version=?',
                      (symbol,forecast['target'],revision,VERSION)).fetchone()
    snapshot['adaptive']=dict(json.loads(frozen['payload']),created_at=frozen['created_at'],state=state)
    outcomes=db.execute('SELECT * FROM adaptive_forecasts WHERE symbol=? AND revision=? AND version=? AND evaluated_at IS NOT NULL ORDER BY target DESC',
                        (symbol,revision,VERSION)).fetchall()
    snapshot['learning_results']=[dict(target=r['target'],actual=r['actual'],previous=r['previous'],
        predicted=json.loads(r['payload'])['predicted'],**json.loads(r['result'])) for r in outcomes]
    for r in snapshot['records']:
        if r['kind']=='prospective':
            saved=db.execute('SELECT payload FROM adaptive_forecasts WHERE symbol=? AND target=? AND revision=? AND version=?',
                             (symbol,r['target'],revision,VERSION)).fetchone()
            scale=json.loads(saved['payload'])['scale'] if saved else None
        else:
            index=snapshot['dates'].index(r['target']) if r['target'] in snapshot['dates'] else 0
            scale=scale_from_history(snapshot['history'][:index]) if index>=21 else None
        r['scoring']=score(r['previous'],r['predicted'],r['actual'],scale) if scale else None
