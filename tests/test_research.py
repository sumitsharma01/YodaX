import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from fastapi import HTTPException
from backend import research


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patcher = patch.object(research, 'DATA', Path(self.tmp.name))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_daily_limit_is_persistent(self):
        for _ in range(research.LIMIT):
            research.reserve()
        with self.assertRaises(HTTPException) as caught:
            research.reserve()
        self.assertEqual(caught.exception.status_code, 429)

    @patch.object(research, 'key', return_value='test-secret')
    @patch.object(research.requests, 'post')
    def test_no_sources_not_published(self, post, key):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'Unsupported assertion'}]}}]}
        with self.assertRaises(HTTPException):
            research.generate('test', [{'title': 'Report', 'url': 'https://example.com'}])

    @patch.object(research, 'key', return_value='test-secret')
    @patch.object(research.requests, 'post')
    def test_quota_does_not_retry(self, post, key):
        post.return_value = Mock(status_code=429)
        with self.assertRaises(HTTPException) as caught:
            research.generate('test', [{'title': 'Report', 'url': 'https://example.com'}])
        self.assertEqual(post.call_count, 1)
        self.assertNotIn('test-secret', caught.exception.detail)

    @patch.object(research, 'key', return_value='test-secret')
    @patch.object(research.requests, 'post')
    def test_invalid_reference_rejected(self, post, key):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"text":"Claim [99]", "follow_up_query":"oil"}'}]}}]}
        with self.assertRaises(HTTPException):
            research.generate('test', [{'title': 'Report', 'url': 'https://example.com'}])

    @patch.object(research, 'key', return_value='test-secret')
    @patch.object(research.requests, 'post')
    def test_no_paid_search_tool(self, post, key):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"text":"Claim [1]", "follow_up_query":"oil"}'}]}}]}
        report = research.generate('test', [{'title': 'Report', 'url': 'https://example.com'}])
        self.assertEqual(report['text'], 'Claim [1]')
        self.assertNotIn('tools', post.call_args.kwargs['json'])

if __name__ == '__main__':
    unittest.main()
