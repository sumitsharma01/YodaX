"""Copy local data once into an empty private cloud schema, verifying every row."""
import json
import sqlite3
from .core import DATA
from .storage import Postgres

TABLES = {
    'yodax.sqlite3': ('forecasts', 'dashboard', 'adaptive_forecasts', 'learning_state'),
    'research.sqlite3': ('usage', 'conversations', 'turns'),
}

def migrate():
    with Postgres() as dest:
        dest.execute('CREATE SCHEMA IF NOT EXISTS yodax')
        dest.execute('REVOKE ALL ON SCHEMA yodax FROM PUBLIC, anon, authenticated')
        for filename, tables in TABLES.items():
            source = sqlite3.connect(f'file:{DATA / filename}?mode=ro', uri=True)
            source.row_factory = sqlite3.Row
            try:
                for table in tables:
                    ddl = source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
                    dest.execute(ddl.replace('CREATE TABLE ', 'CREATE TABLE IF NOT EXISTS ',1))
                    rows = source.execute(f'SELECT * FROM {table}').fetchall()
                    if dest.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:
                        raise ValueError(f'{table} is not empty; refusing to overwrite cloud data')
                    for row in rows:
                        columns = ','.join(row.keys())
                        marks = ','.join('?' for _ in row)
                        dest.execute(f'INSERT INTO {table} ({columns}) VALUES ({marks})', tuple(row))
                    copied = dest.execute(f'SELECT * FROM {table}').fetchall()
                    canonical = lambda items: sorted(json.dumps(dict(r),sort_keys=True) for r in items)
                    if canonical(rows) != canonical(copied):
                        raise ValueError(f'{table} verification failed')
                    print(f'{table}: {len(rows)} rows verified', flush=True)
            finally:
                source.close()
        dest.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        fx = DATA / 'fx.json'
        if fx.exists():
            dest.execute('INSERT INTO settings VALUES (?,?)', ('fx',fx.read_text()))
    print('Migration committed. Local data unchanged.')

if __name__ == '__main__':
    migrate()
