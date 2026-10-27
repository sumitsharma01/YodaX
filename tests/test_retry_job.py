import unittest
from subprocess import CompletedProcess
from unittest.mock import patch
from backend.retry_job import run


class RetryJobTests(unittest.TestCase):
    @patch('backend.retry_job.time.sleep')
    @patch('backend.retry_job.subprocess.run')
    def test_recovers_without_extra_execution(self, execute, sleep):
        execute.side_effect = [CompletedProcess([], 1), CompletedProcess([], 0)]
        self.assertEqual(run(['worker']), 0)
        self.assertEqual(execute.call_count, 2)
        sleep.assert_called_once_with(30)

    @patch('backend.retry_job.time.sleep')
    @patch('backend.retry_job.subprocess.run')
    def test_persistent_failure_remains_failure(self, execute, sleep):
        execute.return_value = CompletedProcess([], 2)
        self.assertEqual(run(['worker']), 2)
        self.assertEqual(execute.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch('backend.retry_job.time.sleep')
    @patch('backend.retry_job.subprocess.run')
    def test_success_or_calendar_skip_does_not_retry(self, execute, sleep):
        execute.return_value = CompletedProcess([], 0)
        self.assertEqual(run(['worker']), 0)
        execute.assert_called_once_with(['worker'], check=False)
        sleep.assert_not_called()
