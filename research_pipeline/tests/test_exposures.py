import unittest
import pandas as pd
from research_pipeline.exposures import snapshot_for, snapshot_key, summarize_exposed, add_exposure_features


class ExposureTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = dict(symbol='AAPL', countries=['CHN','TWN'], available_at='2025-01-10T00:00:00Z', max_age_days=365)
        self.registry = {'snapshots': [self.snapshot]}

    def test_disclosure_unavailable_before_release(self):
        self.assertIsNone(snapshot_for('AAPL',pd.Timestamp('2025-01-09',tz='UTC'),self.registry))
        self.assertIsNotNone(snapshot_for('AAPL',pd.Timestamp('2025-01-10',tz='UTC'),self.registry))
        self.assertIsNone(snapshot_for('AAPL',pd.Timestamp('2026-01-11',tz='UTC'),self.registry))

    def test_later_snapshot_does_not_rewrite_earlier_exposure(self):
        later = {**self.snapshot,'countries':['IND'],'available_at':'2025-06-01T00:00:00Z'}
        registry = {'snapshots':[self.snapshot,later]}
        self.assertEqual(snapshot_for('AAPL',pd.Timestamp('2025-05-01',tz='UTC'),registry)['countries'],['CHN','TWN'])
        self.assertNotEqual(snapshot_key(self.snapshot),snapshot_key(later))

    def test_sanctions_direction_and_double_counting(self):
        frame = pd.DataFrame([
            ['1','USA','CHN','163','4'],['1','USA','CHN','163','4'],
            ['2','CHN','TWN','163','4'],['3','CHN','USA','163','4'],
            ['4','PER','USA','163','4'],['5','CHN','USA','164','3']],
            columns=['event_id','actor1_country','actor2_country','event_code','quad_class'])
        counts=summarize_exposed(frame,['CHN','TWN'])
        self.assertEqual(counts['total'],4)
        self.assertEqual(counts['sanctions'],3)
        self.assertEqual(counts['incoming_sanctions'],2)
        self.assertEqual(counts['negotiation_halt'],1)

    def test_missing_archive_is_not_zero_activity(self):
        features=pd.DataFrame([dict(symbol='AAPL',date=pd.Timestamp('2025-02-01'),cutoff_at=pd.Timestamp('2025-02-01 21:00Z'))])
        result=add_exposure_features(features,None,self.registry)
        self.assertEqual(result.iloc[0].exposure_known,1)
        self.assertEqual(result.iloc[0].exposure_coverage_7d,0)
        self.assertTrue(pd.isna(result.iloc[0].exposed_sanctions_share_7d))

    def test_unavailable_country_data_cannot_leak(self):
        features=pd.DataFrame([dict(symbol='AAPL',date=pd.Timestamp('2025-01-09'),cutoff_at=pd.Timestamp('2025-01-09 21:00Z'))])
        result=add_exposure_features(features,None,self.registry)
        self.assertEqual(result.iloc[0].exposure_known,0)
        self.assertTrue(pd.isna(result.iloc[0].exposure_age_days))

    def test_future_archive_cannot_change_past_feature(self):
        cutoff=pd.Timestamp('2025-02-01 21:00Z')
        features=pd.DataFrame([dict(symbol='AAPL',date=cutoff.tz_localize(None).normalize(),cutoff_at=cutoff)])
        key=snapshot_key(self.snapshot)
        days=pd.date_range('2025-01-26','2025-02-02',tz='UTC')
        events=pd.DataFrame({'available_at':days})
        for field in ['total','conflict','sanctions','incoming_sanctions','cooperation','negotiation_halt']:
            events[f'{key}_{field}']=10 if field=='total' else 1
        first=add_exposure_features(features,events,self.registry)
        events.loc[events.available_at > cutoff,f'{key}_sanctions']=10000
        pd.testing.assert_frame_equal(first,add_exposure_features(features,events,self.registry))
