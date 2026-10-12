import unittest
from unittest.mock import patch
from types import SimpleNamespace
from fastapi import HTTPException
from backend.storage import translate, Row, database_parameters, Postgres
from backend.research import authorize

class CloudTests(unittest.TestCase):
    @patch('psycopg.connect')
    @patch('backend.storage.setting')
    def test_invalid_database_url_never_attempts_local_connection(self, setting, connect):
        for value in ('', 'postgresql:///postgres', 'https://host/db',
                      'postgresql://user:secret@host:bad/db',
                      'postgresql://user:secret@host', 'postgresql://host/db'):
            with self.subTest(value=value):
                setting.return_value = value
                with self.assertRaises(RuntimeError) as caught: Postgres()
                self.assertIn('DATABASE_URL', str(caught.exception))
                self.assertNotIn('secret', str(caught.exception).replace('Actions secret', ''))
        connect.assert_not_called()

    @patch('backend.storage.setting')
    def test_database_url_preserves_encoded_credentials(self, setting):
        setting.return_value = 'postgresql://user:pass%40word@db.example:5432/postgres'
        self.assertEqual(database_parameters(), dict(host='db.example', port=5432,
            dbname='postgres', user='user', password='pass@word'))

    def test_precision_and_idempotent_sql(self):
        self.assertIn('DOUBLE PRECISION', translate('CREATE TABLE x(price REAL)'))
        self.assertEqual(translate('INSERT OR IGNORE INTO x VALUES (?)'), 'INSERT INTO x VALUES (%s) ON CONFLICT DO NOTHING')
        self.assertIn('ON CONFLICT(symbol,revision,version)', translate('INSERT OR REPLACE INTO learning_state VALUES (?,?,?,?)'))
    def test_row_supports_existing_access_patterns(self):
        r=Row(symbol='AAPL', price=12.5)
        self.assertEqual(r[0],r['symbol'])
        self.assertEqual(dict(r),{'symbol':'AAPL','price':12.5})
    @patch('backend.storage.setting',return_value='postgres')
    def test_conversations_require_matching_owner(self,setting):
        from unittest.mock import Mock
        db=Mock();db.execute.return_value.fetchone.return_value={'owner':'alice'}
        authorize(db,'chat',SimpleNamespace(state=SimpleNamespace(owner='alice')))
        with self.assertRaises(HTTPException):
            authorize(db,'chat',SimpleNamespace(state=SimpleNamespace(owner='bob')))
        db.execute.return_value.fetchone.return_value=None
        with self.assertRaises(HTTPException):
            authorize(db,'legacy-chat',SimpleNamespace(state=SimpleNamespace(owner='alice')))
