"""Private chat requests; numerical forecasts are issued by the separate worker."""
import json
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from .core import connect


@contextmanager
def database():
    db = connect()
    try:
        with db:
            yield db
    finally:
        db.close()


def schema(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS prediction_requests (
        id TEXT PRIMARY KEY, turn_id TEXT UNIQUE NOT NULL, owner TEXT NOT NULL,
        symbol TEXT NOT NULL, horizon INTEGER NOT NULL, question TEXT NOT NULL,
        requested_at TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL);''')


def validate(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('Invalid prediction request')
    symbol, horizon = value.get('symbol'), value.get('horizon_sessions')
    from .market_context import FUTURES
    if not isinstance(symbol, str) or (symbol not in FUTURES and not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,14}', symbol)):
        raise ValueError('Invalid stock ticker')
    if type(horizon) is not int or not 1 <= horizon <= 60:
        raise ValueError('Horizon must be 1–60 trading sessions')
    return {'symbol': symbol, 'horizon_sessions': horizon}


def enqueue(turn_id, owner, question, request, research=None):
    request = validate(request)
    with database() as db:
        schema(db)
        old = db.execute('SELECT * FROM prediction_requests WHERE turn_id=?', (turn_id,)).fetchone()
        if old:
            return dict(old)
        ident = uuid.uuid4().hex
        payload={'research':research} if research else {}
        from .market_context import event_route
        route=event_route(request['symbol'],request['horizon_sessions'])
        payload['requested_model_route']=route['route'] if route else 'timesfm_price_only'
        if route:
            payload['requested_candidate']=route['candidate']
            payload['requested_model_name']=route['name']
        db.execute('INSERT INTO prediction_requests VALUES (?,?,?,?,?,?,?,?,?)',
                   (ident, turn_id, owner, request['symbol'], request['horizon_sessions'], question,
                    datetime.now(timezone.utc).isoformat(), 'queued', json.dumps(payload,allow_nan=False)))
    return {'id': ident, 'state': 'queued', **request}


def listing(owner):
    with database() as db:
        schema(db)
        rows = db.execute('SELECT * FROM prediction_requests WHERE owner=? ORDER BY requested_at DESC LIMIT 100', (owner,)).fetchall()
    return [{**dict(r), 'payload': json.loads(r['payload'])} for r in rows]
