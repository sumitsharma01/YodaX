"""Dated display conversions; forecasts and evaluation stay in USD."""
import json
import math
from datetime import date, datetime, timezone
import requests
from .core import DATA

CURRENCIES = ('USD', 'INR', 'EUR', 'GBP', 'JPY', 'CAD')
URL = 'https://api.frankfurter.dev/v1/latest?base=USD&symbols=INR,EUR,GBP,JPY,CAD'

def validate(payload):
    if payload.get('base') != 'USD' or payload.get('amount') != 1:
        raise ValueError('Expected rates for one USD')
    day = date.fromisoformat(payload['date'])
    if day > datetime.now(timezone.utc).date():
        raise ValueError('Exchange-rate date is in the future')
    rates = {'USD': 1.0}
    for currency in CURRENCIES[1:]:
        rate = float(payload['rates'][currency])
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError('Invalid exchange rate')
        rates[currency] = rate
    return dict(base='USD', date=day.isoformat(), rates=rates, source='Frankfurter / ECB')

def refresh():
    response = requests.get(URL, timeout=20)
    response.raise_for_status()
    payload = validate(response.json())
    from .storage import setting
    if setting('YODAX_STORAGE') == 'postgres':
        from .core import connect
        with connect() as db:
            db.execute("INSERT INTO settings(key,payload) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload", ('fx',json.dumps(payload)))
        return payload
    DATA.mkdir(exist_ok=True)
    temporary = DATA / 'fx.json.tmp'
    temporary.write_text(json.dumps(payload))
    temporary.replace(DATA / 'fx.json')
    return payload

def cached():
    try:
        from .storage import setting
        if setting('YODAX_STORAGE') == 'postgres':
            from .core import connect
            with connect() as db:
                row = db.execute("SELECT payload FROM settings WHERE key=?", ('fx',)).fetchone()
            data = json.loads(row['payload']) if row else {}
        else:
            data = json.loads((DATA / 'fx.json').read_text())
        data = validate(dict(data, amount=1))
        data['stale'] = (datetime.now(timezone.utc).date()-date.fromisoformat(data['date'])).days > 7
        if data['stale']:
            data['rates'] = {'USD': 1.0}
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return dict(base='USD', date=None, rates={'USD': 1.0}, source='Frankfurter / ECB', stale=True)

if __name__ == '__main__':
    print(json.dumps(refresh()))
