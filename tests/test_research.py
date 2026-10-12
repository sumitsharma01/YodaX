import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from fastapi import HTTPException
from starlette.requests import Request
from backend import research

SOURCES = [{'title':'Oil supply tightens', 'url':'https://example.com/report', 'published':'today', 'publisher':'Example'}]
REPORT = {'answer':'Supply could tighten [1].', 'outlook':'Conditional upside', 'follow_up_query':'',
          'nodes':[{'id':'e','label':'Supply headline','kind':'evidence','detail':'Headline observation','source_ids':[1]},
                   {'id':'m','label':'Supply pressure','kind':'mechanism','detail':'A hypothesis','source_ids':[]},
                   {'id':'o','label':'Conditional outlook','kind':'outlook','detail':'If confirmed','source_ids':[1]}],
          'edges':[{'from':'e','to':'m','label':'suggests'},{'from':'m','to':'o','label':'may support'}]}


def response(code=200):
    import json
    result=Mock(status_code=code)
    result.json.return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(REPORT)}]}}]}
    return result


class ResearchTests(unittest.TestCase):
    def test_topic_switch_uses_current_question(self):
        history = [{'user': 'What drives copper?', 'assistant': 'Copper analysis'}]
        for question in ('predict price of INR against euro', 'What drives Tesla stock?',
                         'Explain bond yields', 'What affects crude oil?'):
            query = research.research_query(question, 'Copper', history)
            self.assertNotIn('copper', query.lower())
        self.assertIn('INR', research.research_query('predict price of INR against euro', 'Copper', history))
        self.assertIn('copper', research.research_query('What about its supply?', 'Copper', history).lower())

    def test_educational_answer_does_not_require_invented_sources(self):
        report = copy.deepcopy(REPORT)
        report['answer'] = 'Bond prices generally move inversely to yields.'
        for node in report['nodes']:
            node['source_ids'] = []
            if node['kind'] == 'evidence': node['kind'] = 'mechanism'
        research.validate_result(report, [])
        report['answer'] += ' [1]'
        with self.assertRaises(ValueError): research.validate_result(report, [])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patcher=patch.object(research,'DATA',Path(self.tmp.name));self.patcher.start()

    def tearDown(self):
        self.patcher.stop();self.tmp.cleanup()

    def test_daily_limit_persists(self):
        for _ in range(research.LIMIT): research.reserve()
        with self.assertRaises(HTTPException) as caught: research.reserve()
        self.assertEqual(caught.exception.status_code,429)

    def test_graph_rejects_invalid_source_and_edge(self):
        report=copy.deepcopy(REPORT);report['nodes'][0]['source_ids']=[99]
        with self.assertRaises(ValueError): research.validate_result(report,SOURCES)
        report=copy.deepcopy(REPORT);report['edges'][0]['to']='invented'
        with self.assertRaises(ValueError): research.validate_result(report,SOURCES)

    def test_grouped_citations_are_validated(self):
        report=copy.deepcopy(REPORT);report['answer']='Claim [1, 99].'
        with self.assertRaises(ValueError): research.validate_result(report,SOURCES)

    def test_graph_rejects_disconnected_context(self):
        report=copy.deepcopy(REPORT)
        report['nodes'].append({'id':'orphan','label':'Other','kind':'risk','detail':'Unconnected','source_ids':[]})
        with self.assertRaises(ValueError): research.validate_result(report,SOURCES)

    @patch.object(research,'key',return_value='test-secret')
    @patch.object(research.requests,'post')
    def test_no_paid_tools_or_source_urls_sent(self,post,key):
        post.return_value=response()
        report=research.generate('Question',SOURCES)
        self.assertEqual(report['answer'],REPORT['answer'])
        body=post.call_args.kwargs['json']
        self.assertNotIn('tools',body)
        self.assertNotIn(SOURCES[0]['url'],str(body))

    @patch.object(research,'key',return_value='test-secret')
    @patch.object(research.requests,'post')
    def test_quota_does_not_retry_or_leak_secret(self,post,key):
        post.return_value=response(429)
        with self.assertRaises(HTTPException) as caught: research.generate('Question',SOURCES)
        self.assertEqual(post.call_count,1)
        self.assertNotIn('test-secret',caught.exception.detail)

    @patch.object(research.time,'sleep')
    @patch.object(research,'key',return_value='test-secret')
    @patch.object(research.requests,'post')
    def test_busy_retries_once_then_succeeds(self,post,key,sleep):
        post.side_effect=[response(503),response()]
        stages=[]
        research.generate('Question',SOURCES,stages.append)
        self.assertEqual(post.call_count,2)
        self.assertEqual(len(stages),1)

    @patch.object(research.time,'sleep')
    @patch.object(research,'key',return_value='test-secret')
    @patch.object(research.requests,'post')
    def test_busy_stops_after_two_attempts(self,post,key,sleep):
        post.return_value=response(503)
        with self.assertRaises(HTTPException): research.generate('Question',SOURCES)
        self.assertEqual(post.call_count,2)

    @patch.object(research.time,'sleep')
    @patch.object(research,'key',return_value='test-secret')
    @patch.object(research.requests,'post')
    def test_transport_failure_retries_once_then_succeeds(self,post,key,sleep):
        for failure in (research.requests.Timeout, research.requests.ConnectionError):
            with self.subTest(failure=failure):
                post.reset_mock()
                post.side_effect = [failure('test-secret'), response()]
                stages = []
                result = research.generate('Question', SOURCES, stages.append)
                self.assertEqual(result['answer'], REPORT['answer'])
                self.assertEqual(post.call_count, 2)
                self.assertIn('Reconnecting once', stages[0])

    @patch.object(research.time,'sleep')
    @patch.object(research,'key',return_value='test-secret')
    @patch.object(research.requests,'post')
    def test_timeout_stops_after_two_attempts_and_counts_quota(self,post,key,sleep):
        post.side_effect = research.requests.Timeout('test-secret')
        with self.assertRaises(HTTPException) as caught:
            research.generate('Question', SOURCES)
        self.assertEqual(post.call_count, 2)
        self.assertNotIn('test-secret', caught.exception.detail)
        self.assertIn('two attempts', caught.exception.detail)
        with research.database() as db:
            self.assertEqual(db.execute('SELECT calls FROM usage WHERE day=?', (research.today(),)).fetchone()[0], 2)

    @patch.object(research,'key',return_value='test-secret')
    @patch.object(research.requests,'post')
    def test_invalid_report_is_repaired_once(self,post,key):
        invalid = response()
        invalid.json.return_value = {'candidates': [{'finishReason': 'MAX_TOKENS'}]}
        post.side_effect = [invalid, response()]
        stages = []
        self.assertEqual(research.generate('Question', SOURCES, stages.append)['answer'], REPORT['answer'])
        self.assertEqual(post.call_count, 2)
        self.assertIn('Checking evidence', stages[0])
        post.reset_mock()
        post.side_effect = [invalid, invalid]
        with self.assertRaises(HTTPException): research.generate('Question', SOURCES)
        self.assertEqual(post.call_count, 2)

    def test_restart_recovers_unfinished_turn(self):
        with research.database() as db:
            db.execute('INSERT INTO turns VALUES (?,?,?,?,?,?,?,?)',('t','c','Question','running','Loading',None,None,'2026'))
        research.recover_interrupted()
        with research.database() as db: row=db.execute('SELECT state FROM turns').fetchone()
        self.assertEqual(row['state'],'error')

    @patch.object(research,'generate')
    @patch.object(research,'news',return_value=SOURCES)
    def test_worker_remembers_prior_conversation(self,news,generate):
        import json
        generate.return_value=copy.deepcopy(REPORT)
        with research.database() as db:
            db.execute('INSERT INTO turns VALUES (?,?,?,?,?,?,?,?)',('old','c','Explain oil','done','Complete',json.dumps(REPORT),None,'2026-01'))
            db.execute('INSERT INTO turns VALUES (?,?,?,?,?,?,?,?)',('new','c','What about demand?','running','Loading',None,None,'2026-02'))
        research.lock.acquire()
        research.run_turn('new','c','Oil','What about demand?')
        self.assertIn('Explain oil',generate.call_args.args[0])
        self.assertIn('What about demand?',generate.call_args.args[0])
        with research.database() as db: row=db.execute("SELECT * FROM turns WHERE id='new'").fetchone()
        self.assertEqual(row['state'],'done')
        self.assertFalse(research.lock.locked())

    def test_cross_origin_rejected(self):
        request=Request({'type':'http','scheme':'http','server':('127.0.0.1',5173),'path':'/','headers':[(b'host',b'127.0.0.1:5173'),(b'origin',b'https://evil.example')]})
        with self.assertRaises(HTTPException):research.local_only(request)

    @patch('backend.storage.setting')
    def test_render_origin_works_behind_http_proxy(self, setting):
        values = {'YODAX_STORAGE': 'postgres', 'PUBLIC_ORIGIN': 'https://old.example',
                  'RENDER_EXTERNAL_URL': 'https://yodax.onrender.com'}
        setting.side_effect = lambda name: values.get(name, '')
        request = Request({'type': 'http', 'scheme': 'http', 'server': ('internal', 10000),
                           'path': '/', 'headers': [(b'host', b'yodax.onrender.com'),
                           (b'origin', b'https://yodax.onrender.com')]})
        request.state.owner = 'test-owner'
        research.local_only(request)

    @patch('backend.storage.setting')
    def test_cloud_origin_rejects_foreign_hosts_origins_and_missing_session(self, setting):
        setting.side_effect = lambda name: {'YODAX_STORAGE': 'postgres',
            'PUBLIC_ORIGIN': 'https://yodax.onrender.com'}.get(name, '')
        for host, origin, owner in [
            ('evil.example', 'https://yodax.onrender.com', 'owner'),
            ('yodax.onrender.com', 'https://evil.example', 'owner'),
            ('yodax.onrender.com', 'null', 'owner'),
            ('yodax.onrender.com', 'https://yodax.onrender.com', None),
        ]:
            with self.subTest(host=host, origin=origin, owner=owner):
                request = Request({'type': 'http', 'scheme': 'http', 'path': '/',
                    'headers': [(b'host', host.encode()), (b'origin', origin.encode())]})
                request.state.owner = owner
                with self.assertRaises(HTTPException): research.local_only(request)

if __name__=='__main__':unittest.main()
