"""Reproduce the broader global-event beta without changing the original candidate.

prepare -> replay -> train. Training writes an evaluation and frozen candidate,
not a claim of production approval. Public dashboard forecasts are untouched.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from .collect import collect_prices, write_json
from .evaluate import chronological_split, summarize, block_bootstrap
from .features import MARKET_FEATURES, EVENT_FEATURES
from .model import fit_bundle, save_bundle, load_bundle

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_DATA=ROOT/'data/research-broad-20261025'
DEFAULT_RUN=ROOT/'data/research-runs/broad-global-20261025'
CONFIG=ROOT/'config/research-broad.json'
CANDIDATE='global-v1-20261025'


def prepare(destination, source, config):
    destination,source=Path(destination),Path(source)
    if destination.exists():
        raise FileExistsError('Use a new dataset directory; source snapshots are immutable')
    destination.mkdir(parents=True)
    prices=pd.read_parquet(source/'prices.parquet')
    required=list(dict.fromkeys(config['stocks']+config['market_context']))
    missing=sorted(set(required)-set(prices.symbol))
    if missing:
        extra,_=collect_prices(missing,config['start'],config['baseline_end'],destination/'additional-prices')
        prices=pd.concat([prices,extra],ignore_index=True)
    prices=prices[prices.symbol.isin(required) & prices.date.ge(config['start']) & prices.date.lt(config['baseline_end'])]
    if set(required)-set(prices.symbol):
        raise ValueError('Missing required asset histories')
    prices.to_parquet(destination/'prices.parquet',index=False)
    shutil.copyfile(source/'events.parquet',destination/'events.parquet')
    write_json(destination/'source-manifest.json',{
        'source':str(source),'config':config,
        'source_hashes':{name:sha256((source/name).read_bytes()).hexdigest() for name in ['prices.parquet','events.parquet']},
        'note':'Cached historical source snapshots. Collection timestamps and raw archives remain in the source directory; no claim of original point-in-time prices.'})


def train(root, output, config, artifact_root=None, candidate=CANDIDATE, activate_beta=False):
    from .__main__ import run_experiment
    root,output=Path(root),Path(output)
    report=run_experiment(root,config,output)
    features=pd.read_parquet(output/'features.parquet')
    predictions=pd.read_parquet(output/'predictions.parquet')
    eligible=features[features.event_coverage_7d.eq(1)].dropna(subset=['target_return'])
    per_asset=[]
    for fold,(start,end) in enumerate(config['validation_windows']):
        training,test=chronological_split(eligible,start,end)
        for symbol in config['stocks']:
            train_rows=training[training.symbol.eq(symbol)]
            test_rows=test[test.symbol.eq(symbol)]
            if len(train_rows)<30 or len(test_rows)<20:
                raise ValueError(f'Insufficient per-asset evidence: {symbol}, fold {fold}')
            observed=predictions[predictions.fold.eq(fold)&predictions.symbol.eq(symbol)]
            per_asset.append({'fold':fold,'symbol':symbol,'training_rows':len(train_rows),'evaluation_rows':len(test_rows),
                'metrics':summarize(observed).to_dict('records'),
                'event_vs_market':block_bootstrap(observed,'market_adjusted','event_adjusted',config['horizon'],seed=config['seed']),
                'event_vs_timesfm':block_bootstrap(observed,'timesfm','event_adjusted',config['horizon'],seed=config['seed']),
                'feature_shift':{name:{'training_mean':float(train_rows[name].mean()),'evaluation_mean':float(test_rows[name].mean()),
                    'standardized_mean_difference':float((test_rows[name].mean()-train_rows[name].mean())/train_rows[name].std()) if train_rows[name].std()>0 else None}
                    for name in MARKET_FEATURES+EVENT_FEATURES if train_rows[name].notna().any() and test_rows[name].notna().any()}})
    write_json(output/'per-asset-evaluation.json',per_asset)
    artifact_root=Path(artifact_root or ROOT/'models/shadow'/candidate)
    if artifact_root.exists():
        raise FileExistsError('Frozen deployment artifact already exists; choose a new candidate/version')
    # Refit once after frozen historical comparisons. This final artifact is assessed prospectively.
    cfg=dict(config)
    for key in ['baseline_start','baseline_end']:
        cfg.pop(key,None)
    artifacts={}
    revisions=report['baseline_revisions']
    for name,include_events in [('market_adjusted',False),('event_adjusted',True)]:
        bundle=fit_bundle(eligible,cfg,include_events,revisions)
        bundle.metadata['evaluation_report_sha256']=sha256((output/'report.json').read_bytes()).hexdigest()
        bundle.metadata['deployment_role']='experimental_chat_beta_not_production_approved'
        path=save_bundle(bundle,artifact_root/name)
        reloaded=load_bundle(path.parent)
        np.testing.assert_allclose(bundle.predict_features(eligible.tail(23)),reloaded.predict_features(eligible.tail(23)))
        artifacts[name]={'path':str(path.parent.relative_to(ROOT)),'sha256':sha256(path.read_bytes()).hexdigest()}
    deployment={'candidate':candidate,'mode':'shadow','chat_enabled':True,'include_no_change':True,'symbols':cfg['stocks'],
        'horizon_sessions':cfg['horizon'],'artifacts':artifacts,
        'note':'Global event statistics, not company-specific causation. Experimental chat beta. Historical evaluation is exploratory; no automatic promotion.',
        'issuance_deadline':'After all input markets close plus one hour; before the next XNYS session opens.'}
    if activate_beta:
        write_json(ROOT/'config/shadow-broad.json',deployment)
    write_json(output/'deployment.json',deployment)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('step',choices=['prepare','replay','train'])
    p.add_argument('--data',type=Path,default=DEFAULT_DATA)
    p.add_argument('--source',type=Path,default=ROOT/'data/research')
    p.add_argument('--output',type=Path,default=DEFAULT_RUN)
    p.add_argument('--candidate',default=CANDIDATE)
    p.add_argument('--activate-beta',action='store_true',help='Explicitly select this frozen candidate for experimental chat; never promotes the public dashboard')
    args=p.parse_args();cfg=json.loads(CONFIG.read_text())
    if args.step=='prepare':prepare(args.data,args.source,cfg)
    elif args.step=='replay':
        from .baseline import timesfm_baselines
        timesfm_baselines(pd.read_parquet(args.data/'prices.parquet'),cfg,args.data)
    else:train(args.data,args.output,cfg,candidate=args.candidate,activate_beta=args.activate_beta)

if __name__=='__main__':main()
