import json
import sqlite3
import unittest
from unittest.mock import patch
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend import shadow_store as store
from backend.shadow_api import router, COOKIE


class ShadowStorageTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        store.schema(self.db)
        self.payload = dict(prospective=True, horizon_sessions=5, previous=100., predicted_return=.05)
        self.prices = pd.DataFrame(dict(symbol=['AAPL']*6,
            date=pd.bdate_range('2026-10-12', periods=6), close=[100,101,102,103,104,106], split=[0]*6))

    def save(self, model='timesfm', payload=None, issued='2026-10-12T22:00:00Z'):
        store.save_prediction(self.db,'candidate','AAPL','2026-10-12','2026-10-19',model,issued,
                              payload or self.payload,'2026-10-13T13:30:00Z')

    def test_predictions_are_immutable_and_deadline_enforced(self):
        self.save()
        self.save(payload={**self.payload,'predicted_return':.99})
        saved = self.db.execute('SELECT * FROM shadow_predictions').fetchall()
        self.assertEqual(len(saved),1)
        self.assertEqual(json.loads(saved[0]['payload']),self.payload)
        with self.assertRaises(ValueError): self.save(issued='2026-10-13T13:30:00Z')

    def test_scores_only_after_close_and_once(self):
        self.save()
        self.assertEqual(store.score_pending(self.db,self.prices,now='2026-10-19T19:00:00Z'),0)
        self.assertEqual(store.score_pending(self.db,self.prices,now='2026-10-19T22:00:00Z'),1)
        self.assertEqual(store.score_pending(self.db,self.prices,now='2026-10-20T22:00:00Z'),0)
        row=self.db.execute('SELECT * FROM shadow_predictions').fetchone()
        self.assertAlmostEqual(json.loads(row['evaluation'])['absolute_error_pp'],1.)
        self.assertEqual(json.loads(row['payload']),self.payload)

    def test_bad_outcomes_wait_for_review(self):
        for change in ('missing','split','restatement','invalid'):
            with self.subTest(change=change):
                self.db.execute('DELETE FROM shadow_predictions');self.save()
                prices=self.prices.copy()
                if change=='missing': prices=prices.drop(2)
                if change=='split': prices.loc[2,'split']=2
                if change=='restatement': prices.loc[0,'close']=50
                if change=='invalid': prices.loc[5,'close']=0
                self.assertEqual(store.score_pending(self.db,prices,now='2026-10-20T22:00:00Z'),0)
                self.assertTrue(self.db.execute('SELECT scoring_issue FROM shadow_predictions').fetchone()[0])

    def test_comparisons_require_all_three_matching_predictions(self):
        self.save()
        store.score_pending(self.db,self.prices,now='2026-10-20T22:00:00Z')
        self.assertEqual(store.summary(self.db)['comparisons'],[])
        self.save('market_adjusted');self.save('event_adjusted')
        store.score_pending(self.db,self.prices,now='2026-10-20T22:00:00Z')
        self.assertEqual(store.summary(self.db)['comparisons'][0]['matched_forecasts'],1)


class ShadowAuthTests(unittest.TestCase):
    def setUp(self):
        self.token='a'*64
        self.settings=patch('backend.shadow_api.setting',side_effect=lambda name: {
            'SHADOW_ADMIN_TOKEN':self.token,'PUBLIC_ORIGIN':'http://testserver'}.get(name,''))
        self.settings.start();self.addCleanup(self.settings.stop)
        app=FastAPI();app.include_router(router)
        self.client=TestClient(app)

    def test_anonymous_and_research_cookie_cannot_read_data(self):
        with patch('backend.shadow_api.connect') as connect:
            self.assertEqual(self.client.get('/api/shadow').status_code,401)
            self.client.cookies.set('yodax_session','research-user')
            self.assertEqual(self.client.get('/api/shadow').status_code,401)
            connect.assert_not_called()

    def test_login_tampering_logout_and_origin(self):
        self.assertEqual(self.client.post('/api/shadow/login',json={'token':'wrong'}).status_code,401)
        self.assertEqual(self.client.post('/api/shadow/login',json={'token':self.token},headers={'Origin':'https://other.test'}).status_code,403)
        result=self.client.post('/api/shadow/login',json={'token':self.token})
        self.assertEqual(result.status_code,200)
        self.assertIn('HttpOnly',result.headers['set-cookie'])
        self.assertEqual(self.client.get('/api/shadow/session').json(),{'authenticated':True})
        cookie=self.client.cookies.get(COOKIE)
        self.client.cookies.clear();self.client.cookies.set(COOKIE,cookie+'x')
        self.assertFalse(self.client.get('/api/shadow/session').json()['authenticated'])
        self.client.cookies.clear()
        self.client.post('/api/shadow/login',json={'token':self.token})
        self.client.post('/api/shadow/logout')
        self.assertFalse(self.client.get('/api/shadow/session').json()['authenticated'])

    def test_expired_cookie_and_database_failure(self):
        self.client.post('/api/shadow/login',json={'token':self.token})
        with patch('backend.shadow_api.time.time',return_value=9999999999):
            self.assertFalse(self.client.get('/api/shadow/session').json()['authenticated'])
        with patch('backend.shadow_api.connect',side_effect=RuntimeError('private connection details')):
            result=self.client.get('/api/shadow')
            self.assertEqual(result.status_code,503)
            self.assertNotIn('private connection details',result.text)

    def test_cloud_origin_uses_trusted_render_url_and_secure_cookie(self):
        values={'SHADOW_ADMIN_TOKEN':self.token,'YODAX_STORAGE':'postgres',
                'PUBLIC_ORIGIN':'https://old-name.example','RENDER_EXTERNAL_URL':'https://testserver'}
        with patch('backend.shadow_api.setting',side_effect=lambda name:values.get(name,'')):
            result=self.client.post('/api/shadow/login',json={'token':self.token},headers={'Origin':'https://testserver'})
            self.assertEqual(result.status_code,200)
            self.assertIn('Secure',result.headers['set-cookie'])
            result=self.client.post('/api/shadow/login',json={'token':self.token},headers={'Origin':'https://attacker.example'})
            self.assertEqual(result.status_code,403)
            result=self.client.post('/api/shadow/login',json={'token':self.token},headers={'Origin':'https://testserver','Host':'attacker.example'})
            self.assertEqual(result.status_code,403)

    def test_pasted_environment_token_trims_line_endings(self):
        with patch('backend.shadow_api.setting',side_effect=lambda name: (self.token+'\n') if name=='SHADOW_ADMIN_TOKEN' else ''):
            result=self.client.post('/api/shadow/login',json={'token':self.token})
            self.assertEqual(result.status_code,200)
