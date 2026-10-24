"""Read existing snapshots and evaluate release readiness without fitting any model."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import pandas as pd
from .quality import dataset_audit
from .evaluate import chronological_split

ROOT = Path(__file__).resolve().parents[1]


def audit(root=ROOT):
    root = Path(root)
    cfg_path = root/'config/research-exposure-study.json'
    config = json.loads(cfg_path.read_text())
    source = root/'data/research-exposure-study'
    run = root/'data/research-runs/notebook-exposure_study-20261023T111657803314Z'
    paths = {'config': cfg_path, 'prices': source/'prices.parquet',
             'events': source/'events-enriched.parquet', 'features': run/'features.parquet',
             'predictions': run/'predictions.parquet'}
    frames = {name: pd.read_parquet(paths[name]) for name in ['prices','events','features','predictions']}
    features = frames['features']
    result = {'audit_date': '2026-10-25', 'scope': 'Existing two-stock research snapshots; no retraining or live writes',
              'input_sha256': {name:sha256(path.read_bytes()).hexdigest() for name,path in paths.items()},
              'quality': dataset_audit(frames['prices'],frames['events'],features,config), 'splits':[]}
    eligible = features[features.event_coverage_7d.eq(1) & features.exposure_known.eq(1) & features.exposure_coverage_7d.eq(1)]
    for start,end in config['validation_windows']:
        train,test = chronological_split(eligible,start,end)
        checks = {'training_outcomes_before_test': bool((train.target_date<pd.Timestamp(start)).all()),
                  'test_outcomes_before_end': bool((test.target_date<pd.Timestamp(end)).all()),
                  'disjoint_asset_dates': not bool(set(zip(train.symbol,train.date)) & set(zip(test.symbol,test.date))),
                  'no_unsettled_labels': bool(train.target_return.notna().all() and test.target_return.notna().all())}
        result['splits'].append({'start':start,'end_exclusive':end,'train_rows':len(train),'test_rows':len(test),
            'train_dates':train.date.nunique(),'test_dates':test.date.nunique(),
            'last_training_target':str(train.target_date.max().date()), 'checks':checks,
            'training_rows_by_stock':train.groupby('symbol').size().to_dict()})
    predictions=frames['predictions']
    model_keys={model:set(zip(group.symbol,group.date)) for model,group in predictions.groupby('model')}
    result['comparison_asset_dates_identical']=all(keys==next(iter(model_keys.values())) for keys in model_keys.values())
    result['models']=sorted(model_keys)
    result['prediction_duplicate_keys']=int(predictions.duplicated(['symbol','date','model']).sum())
    result['holdout_status']=config['holdout_note']
    result['coverage']={symbol:{'first':str(group.date.min().date()),'last':str(group.date.max().date()),'rows':len(group)}
                        for symbol,group in frames['prices'].groupby('symbol')}
    result['exposure_expiry']=[{'symbol':s['symbol'],'age_limit_date':str((pd.Timestamp(s['available_at'])+pd.Timedelta(days=s['max_age_days'])).date())} for s in config['exposure_registry']['snapshots']]
    shadow=json.loads((root/'config/shadow.json').read_text())
    result['frozen_artifacts_match']={name:sha256((root/spec['path']/'pipeline.joblib').read_bytes()).hexdigest()==spec['sha256'] for name,spec in shadow['artifacts'].items()}
    result['limitations']=[
        'The 2015 ambition is not the coverage of this event-aware pilot: event archives start in 2025.',
        'July 2026 onward was examined previously; it is not an untouched final test set.',
        'Country presence is a proxy for exposure. Event-to-company relevance and causal effects have not been validated.',
        'Chronological checks do not establish original source availability: event and disclosure delays are conservative assumptions.',
        'A fixed two-stock universe has selection bias; no conclusion about all stocks or commodities follows.',
        'No independent vendor reconciliation, drift clearance, profitability evaluation or calibrated prediction intervals are established.',
        'Historical comparison results were already inspected. New criteria are prospective, not preregistration of those results.'
    ]
    return result


def markdown(result):
    q=result['quality']
    lines=['# YodaX readiness audit — October 25, 2026','',
           'This checks the saved pilot datasets and evaluation splits. It does not train a new model or change the live candidate.','',
           '## Findings','',
           f"- Feature rows: {q['feature_rows']}; settled rows: {q['settled_rows']}; complete exposure windows: {q['full_exposure_window_rows']}.",
           f"- Event archive days: {q['event_archive_days']}; missing dates within that interval: {len(q['missing_archive_days'])}.",
           f"- All models use identical stock/date evaluation keys: {result['comparison_asset_dates_identical']}.",
           f"- Duplicate model/stock/date predictions: {result['prediction_duplicate_keys']}.",
           f"- Frozen shadow artifact checksums match: {all(result['frozen_artifacts_match'].values())}.", '',
           '| Stock | Price rows | Missing sessions | Duplicate dates | Invalid closes |','|---|---:|---:|---:|---:|']
    for x in q['equities']:lines.append(f"| {x['symbol']} | {x['rows']} | {len(x['missing_sessions'])} | {x['duplicate_dates']} | {x['invalid_close_rows']} |")
    lines+=['','## Chronological splits','', '| Test interval (end exclusive) | Train rows | Test rows / dates | Last training outcome | Checks |','|---|---:|---:|---|---|']
    for s in result['splits']:lines.append(f"| {s['start']} → {s['end_exclusive']} | {s['train_rows']} | {s['test_rows']} / {s['test_dates']} | {s['last_training_target']} | {'PASS' if all(s['checks'].values()) else 'FAIL'} |")
    lines+=['','Checks cover target-date purging, disjoint asset/date keys and settled labels. Preprocessing is fitted inside each training fold in the implementation; this report does not independently reconstruct every historical fit.','',
            '## Open issues','']+[f'- {x}' for x in result['limitations']]
    lines+=['', 'Missing event archive dates: '+', '.join(q['missing_archive_days'])+'.','',
            'Exposure age-limit dates: '+ '; '.join(f"{x['symbol']}: {x['age_limit_date']}" for x in result['exposure_expiry'])+'.', '',
            '## Decision','',
            '**Continue private shadow evaluation; do not promote.** The mechanical split checks pass, but relevance review, source freshness and prospective performance evidence remain open. There is no defensible single dataset-quality score.','',
            'The accompanying JSON contains input checksums, per-feature missingness, coverage bounds and individual checks. Reproduce with `.venv-research/bin/python -m research_pipeline.readiness_audit`.','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/audits/2026-10-25')
    args=parser.parse_args();result=audit();args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'readiness.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (args.output/'readiness.md').write_text(markdown(result))
    print(markdown(result))

if __name__=='__main__':main()
