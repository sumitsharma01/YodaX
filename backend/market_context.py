"""Typed market coverage and bounded, read-only model evidence for research chat."""
import json
import re
from pathlib import Path
from .core import connect, COMPANIES

FUTURES = {
    'CL=F': {'name':'WTI oil futures proxy','calendar':'XNYS','close_calendar':'NYMEX','unit':'USD per barrel'},
    'HG=F': {'name':'Copper futures proxy','calendar':'XNYS','close_calendar':'COMEX','unit':'USD per pound'},
}
ALIASES = {'apple':'AAPL','microsoft':'MSFT','google':'GOOGL','alphabet':'GOOGL','amazon':'AMZN',
 'nvidia':'NVDA','meta':'META','jpmorgan':'JPM','bank of america':'BAC','goldman sachs':'GS',
 'johnson & johnson':'JNJ','unitedhealth':'UNH','procter & gamble':'PG','walmart':'WMT',
 'home depot':'HD','caterpillar':'CAT','deere':'DE','exxon':'XOM','chevron':'CVX',
 'freeport':'FCX','nucor':'NUE','tesla':'TSLA','wti':'CL=F','copper':'HG=F'}


def coverage():
    config=json.loads((Path(__file__).resolve().parents[1]/'config/research.json').read_text())
    return {'stocks':sorted(set(config['stocks'])|{c['symbol'] for c in COMPANIES}),
        'additional_us_equities':'Ticker and exchange validated by the worker',
        'numerical_futures':FUTURES,
        'research_only':{'Brent oil':'Exchange session mapping not validated for numerical issuance',
                         'silicon':'No validated benchmark/history', 'lithium':'No validated benchmark/history',
                         'steel':'No validated benchmark/history','forex':'No numerical worker configured'},
        'event_adjustment':{'symbols':['AAPL','FCX'],'horizon_sessions':5,'status':'experimental'},
        'baseline_horizon_sessions':[1,60],
        'commodity_horizon_basis':'US equity-session sampling grid; provider futures close must also be completed. Not exchange settlement prices.'}


def symbols_in(text):
    supported=coverage()['stocks']+list(FUTURES)
    found={s for s in supported if re.search(r'(?<![A-Za-z0-9])'+re.escape(s)+r'(?![A-Za-z0-9])',text,re.I)}
    for alias,symbol in ALIASES.items():
        if re.search(r'\b'+re.escape(alias)+r'\b',text,re.I):found.add(symbol)
    return sorted(found)


def context(message, history, owner):
    symbols=symbols_in(message)
    if not symbols and re.search(r'\b(it|that|those|same|this forecast)\b',message,re.I) and history:
        symbols=symbols_in(history[-1]['user'])
    result={'coverage':coverage(),'matched_symbols':symbols,'saved_forecasts':[],
            'contract':'Only saved model outputs are numerical evidence. News is research evidence, not a numerical model input unless explicitly recorded as such.'}
    if not symbols:return result
    from .prediction_requests import listing
    # Private saved requests are always scoped to this browser owner.
    for row in listing(owner):
        if row['symbol'] in symbols and row['state'] in ('predicted','scored','review'):
            result['saved_forecasts'].append({'symbol':row['symbol'],'horizon_sessions':row['horizon'],
                'state':row['state'],'request_id':row['id'],'payload':row['payload']})
    with connect() as db:
        # Only immutable forecast evidence is exposed, never worker logs or credentials.
        try:
            rows=db.execute("SELECT symbol,cutoff,target,model,issued_at,payload,actual,evaluation FROM shadow_predictions ORDER BY cutoff DESC LIMIT 120").fetchall()
        except Exception:
            rows=[]
        seen=set()
        for row in rows:
            if row['symbol'] not in symbols or (row['symbol'],row['model']) in seen:continue
            seen.add((row['symbol'],row['model']))
            p=json.loads(row['payload'])
            result['saved_forecasts'].append({'symbol':row['symbol'],'horizon_sessions':5,'state':'scored' if row['actual'] is not None else 'pending',
                'experimental':True,'model_variant':row['model'],'payload':{k:p.get(k) for k in ['previous','predicted','predicted_return','model_revision','feature_version','event_coverage','exposure_coverage']},
                'cutoff':row['cutoff'],'target':row['target'],'issued_at':row['issued_at'],'actual':row['actual']})
    result['saved_forecasts']=result['saved_forecasts'][:18]
    return result
