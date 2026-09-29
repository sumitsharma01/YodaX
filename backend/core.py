"""Data validation and metrics shared by the local job and API."""
import math
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
MODEL_ID = 'google/timesfm-2.5-200m-pytorch'
MODEL_REVISION = '1d952420fba87f3c6dee4f240de0f1a0fbc790e3'
COMPANIES = [
    dict(symbol='AAPL', name='Apple', logo='a', color='#d8ddd8'),
    dict(symbol='MSFT', name='Microsoft', logo='⊞', color='#90baf0'),
    dict(symbol='GOOGL', name='Alphabet', logo='G', color='#b4cff9'),
    dict(symbol='TSLA', name='Tesla', logo='T', color='#edaaa2'),
    dict(symbol='NVDA', name='NVIDIA', logo='N', color='#c8f675'),
    dict(symbol='AMZN', name='Amazon', logo='a', color='#edc17b'),
]

def connect(path=None):
    from .storage import Postgres, setting
    if path is None and setting("YODAX_STORAGE") == "postgres":
        return Postgres()
    DATA.mkdir(exist_ok=True)
    db = sqlite3.connect(path or DATA / 'yodax.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript('''
    CREATE TABLE IF NOT EXISTS forecasts (
      symbol TEXT NOT NULL, target TEXT NOT NULL, cutoff TEXT NOT NULL,
      created_at TEXT NOT NULL, model_revision TEXT NOT NULL, snapshot_sha TEXT NOT NULL,
      previous REAL NOT NULL, predicted REAL NOT NULL, low REAL NOT NULL, high REAL NOT NULL,
      kind TEXT NOT NULL, actual REAL, scored_at TEXT,
      PRIMARY KEY(symbol, target, model_revision, kind)
    );
    CREATE TABLE IF NOT EXISTS dashboard (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
    ''')
    return db

def metrics(previous, predicted, actual):
    if any(not math.isfinite(v) or v <= 0 for v in (previous, predicted, actual)):
        raise ValueError('Prices must be positive finite numbers')
    sign = lambda n: (n > 0) - (n < 0)
    return dict(error=abs(predicted-actual)/previous*100,
                baseline=abs(actual-previous)/previous*100,
                correct=sign(predicted-previous)==sign(actual-previous))

def context_for(values, target_index, length=256):
    """The target value is excluded, including when target_index == len(values)."""
    if target_index < length or target_index > len(values):
        raise ValueError('Insufficient context or invalid target')
    return values[target_index-length:target_index]

def save_forecast(db, row):
    # Re-running a session must not rewrite a previously published prediction.
    fields = ['symbol','target','cutoff','created_at','model_revision','snapshot_sha',
              'previous','predicted','low','high','kind','actual','scored_at']
    db.execute(f"INSERT OR IGNORE INTO forecasts ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [row.get(k) for k in fields])
