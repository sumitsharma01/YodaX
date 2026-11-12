"""Read-only chronological replay of the challenger over saved prospective inputs.

This is retrospective development evidence, not prospective challenger performance.
Run with python -m backend.replay_learning --database data/yodax.sqlite3
"""
import argparse
import json
import sqlite3
from datetime import datetime
from . import learning_candidate as candidate


def replay(database):
    db = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    rows = db.execute('''SELECT a.*, f.predicted AS raw, f.scored_at
        FROM adaptive_forecasts a JOIN forecasts f
        ON a.symbol=f.symbol AND a.target=f.target AND a.revision=f.model_revision
        AND f.kind='prospective' WHERE a.version='online-v1'
        ORDER BY a.created_at, a.symbol, a.target''').fetchall()
    states, pending, results = {}, {}, []
    for row in rows:
        key = (row['symbol'], row['revision'])
        state = states.setdefault(key, candidate.initial_state())
        waiting = pending.setdefault(key, [])
        available = [entry for entry in waiting if entry['settled'] <= datetime.fromisoformat(row['created_at'])]
        for entry in sorted(available, key=lambda entry: (entry['settled'], entry['target'])):
            state = candidate.update(state, entry['prediction'], entry['actual'], entry['previous'])
            waiting.remove(entry)
        states[key] = state
        saved = json.loads(row['payload'])
        prediction = candidate.issue(row['previous'], row['raw'], saved['scale'], state)
        if row['actual'] is None or row['scored_at'] is None:
            continue
        waiting.append(dict(settled=datetime.fromisoformat(row['scored_at']), target=row['target'],
            prediction=prediction, actual=row['actual'], previous=row['previous']))
        results.append(dict(symbol=row['symbol'], target=row['target'], previous=row['previous'],
            actual=row['actual'], v1=saved['predicted'], v2=prediction['predicted'],
            ensemble=prediction['ensemble'], raw=row['raw'], decision=prediction['decision']))
    db.close()
    report = {}
    for symbol in sorted({r['symbol'] for r in results}):
        selected = [r for r in results if r['symbol']==symbol]
        report[symbol] = {'observations':len(selected), 'models':{}}
        for model in ['raw','v1','v2','previous']:
            errors = [abs(r[model]-r['actual']) / r['previous'] * 100 for r in selected]
            calls = [r for r in selected if abs(r[model]/r['previous']-1)>1e-10]
            correct = sum((r[model]-r['previous'])*(r['actual']-r['previous'])>0 for r in calls)
            report[symbol]['models'][model] = dict(return_mae_pp=sum(errors)/len(errors),
                directional_calls=len(calls), correct_direction=correct,
                neutral=len(selected)-len(calls))
    return dict(evidence='retrospective development replay, not an untouched test', by_symbol=report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='data/yodax.sqlite3')
    args = parser.parse_args()
    print(json.dumps(replay(args.database), indent=2))
