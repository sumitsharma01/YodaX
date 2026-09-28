import copy
import unittest
from backend.evidence import replay, summarize


class EvidenceTests(unittest.TestCase):
    def stocks(self):
        dates=[f'2026-01-{i:02d}' for i in range(1,31)]
        records=[dict(kind='historical',target=dates[i],cutoff=dates[i-1],previous=100,
                      predicted=102,actual=100,created_at='2026-02-01',snapshot_sha='snapshot') for i in (21,22)]
        return [dict(symbol='TEST',dates=dates,history=[100]*30,records=records)]

    def test_replay_is_read_only_and_chronological(self):
        stocks=self.stocks();unchanged=copy.deepcopy(stocks)
        rows=replay(stocks)['rows']
        self.assertEqual(stocks,unchanged)
        self.assertEqual(rows[0]['state_before']['count'],0)
        self.assertEqual(rows[1]['state_before'],rows[0]['state_after'])
        self.assertNotEqual(rows[0]['state_before']['weights'],rows[0]['state_after']['weights'])
        self.assertEqual(rows[1]['state_after']['count'],2)

    def test_current_outcome_cannot_change_its_prediction(self):
        stocks=self.stocks();before=replay(stocks)['rows']
        stocks[0]['records'][0]['actual']=105
        after=replay(stocks)['rows']
        self.assertEqual(before[0]['adaptive'],after[0]['adaptive'])
        self.assertNotEqual(before[1]['adaptive'],after[1]['adaptive'])

    def test_live_rows_never_enter_replay(self):
        stocks=self.stocks();stocks[0]['records'][0]['kind']='prospective'
        rows=replay(stocks)['rows']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['state_before']['count'],0)

    def test_summary_reports_worse_results_honestly(self):
        result=summarize([dict(target='2026-01-01',raw_error=1,adaptive_error=2,baseline_error=.5)])
        self.assertEqual(result['improvement'],-100)
        self.assertIsNone(summarize([])['improvement'])

if __name__=='__main__': unittest.main()
