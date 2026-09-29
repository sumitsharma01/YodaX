"""Postgres storage for cloud deployments; SQLite remains the local default."""
import os
import re
from urllib.parse import urlsplit, unquote
from pathlib import Path

def setting(name):
    if name in os.environ:
        return os.environ[name]
    path = Path(__file__).resolve().parents[1] / '.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                if key.strip() == name:
                    return value.strip().strip('"\'')
    return ''

class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)

def row_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names, values))

def translate(sql):
    sql = sql.strip().rstrip(';')
    if sql == 'BEGIN IMMEDIATE':
        return "SELECT pg_advisory_xact_lock(782941)"
    sql = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', sql)
    if 'INSERT OR IGNORE' in sql:
        sql = sql.replace('INSERT OR IGNORE', 'INSERT') + ' ON CONFLICT DO NOTHING'
    elif 'INSERT OR REPLACE INTO dashboard' in sql:
        sql = sql.replace('INSERT OR REPLACE', 'INSERT') + ' ON CONFLICT(id) DO UPDATE SET payload=EXCLUDED.payload'
    elif 'INSERT OR REPLACE INTO learning_state' in sql:
        sql = sql.replace('INSERT OR REPLACE', 'INSERT') + ' ON CONFLICT(symbol,revision,version) DO UPDATE SET payload=EXCLUDED.payload'
    if 'OR REPLACE' in sql:
        raise ValueError('Unsupported upsert')
    return sql.replace('?', '%s')

class Postgres:
    def __init__(self):
        import psycopg
        url = urlsplit(setting('DATABASE_URL'))
        self.db = psycopg.connect(host=url.hostname, port=url.port or 5432,
            dbname=url.path.lstrip('/'), user=unquote(url.username or ''),
            password=unquote(url.password or ''), sslmode='require',
            connect_timeout=15, row_factory=row_factory, prepare_threshold=None)
        self.db.execute('SET search_path TO yodax')
        self.db.execute('SET extra_float_digits TO 3')
    def execute(self, sql, params=()):
        return self.db.execute(translate(sql), params)
    def executescript(self, sql):
        for statement in sql.split(';'):
            if statement.strip():
                self.execute(statement)
    def __enter__(self):
        return self
    def __exit__(self, kind, value, traceback):
        try:
            self.db.rollback() if kind else self.db.commit()
        finally:
            self.db.close()
    def close(self):
        self.db.close()
