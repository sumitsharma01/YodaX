import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import numpy as np
import pandas as pd
from research_pipeline.collect import parse_gdelt
from research_pipeline.fixtures import synthetic_inputs
from research_pipeline.features import build_features, MARKET_FEATURES, EVENT_FEATURES
from research_pipeline.evaluate import chronological_split, evaluate_window, block_bootstrap
from research_pipeline.model import save_bundle, load_bundle


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path('config/research.json').read_text())
        cls.config.update(stocks=['AAPL','FCX'], bootstrap_repetitions=100)
        cls.prices, cls.events, cls.baselines = synthetic_inputs()
        cls.features = build_features(cls.prices, cls.events, cls.baselines, cls.config)
        cls.result = evaluate_window(cls.features, cls.config, '2022-01-01', '2023-01-01',
                                    ['synthetic-fixture-not-timesfm'], data_kind='synthetic_verification_only')

    def test_future_prices_cannot_change_past_features(self):
        changed = self.prices.copy()
        changed.loc[changed.date > '2022-06-01', 'close'] *= 1.5
        rebuilt = build_features(changed, self.events, self.baselines, self.config)
        cols = ['date','symbol'] + MARKET_FEATURES + EVENT_FEATURES
        pd.testing.assert_frame_equal(self.features.loc[self.features.date <= '2022-06-01', cols].reset_index(drop=True),
                                      rebuilt.loc[rebuilt.date <= '2022-06-01', cols].reset_index(drop=True))

    def test_unavailable_event_cannot_change_prediction_inputs(self):
        changed = self.events.copy()
        changed.loc[changed.available_at > pd.Timestamp('2022-06-01 21:00Z'), 'material_conflict'] = 999
        rebuilt = build_features(self.prices, changed, self.baselines, self.config)
        cols = ['date','symbol'] + EVENT_FEATURES
        pd.testing.assert_frame_equal(self.features.loc[self.features.date <= '2022-06-01', cols].reset_index(drop=True),
                                      rebuilt.loc[rebuilt.date <= '2022-06-01', cols].reset_index(drop=True))

    def test_missing_event_days_are_not_zero_events(self):
        rebuilt = build_features(self.prices, None, self.baselines, self.config)
        self.assertTrue(rebuilt.event_log_count_7d.isna().all())
        self.assertTrue(rebuilt.event_coverage_7d.eq(0).all())
        with self.assertRaisesRegex(ValueError, 'training dates'):
            evaluate_window(rebuilt, self.config, '2022-01-01','2023-01-01', ['fixture'])

    def test_baseline_horizon_mismatch_rejected(self):
        changed = self.baselines.copy()
        changed['horizon_sessions'] = 1
        with self.assertRaisesRegex(ValueError, 'horizon_sessions'):
            build_features(self.prices, self.events, changed, self.config)

    def test_stale_latest_baseline_rejected(self):
        stale = self.baselines[self.baselines.date < self.baselines.date.max()]
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.result['models']['event_adjusted'].predict(self.prices, self.events, stale)

    def test_duplicate_prices_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            build_features(pd.concat([self.prices, self.prices.iloc[:1]]), self.events, self.baselines, self.config)

    def test_missing_session_does_not_shorten_horizon(self):
        prices = self.prices[~((self.prices.symbol == 'AAPL') & (self.prices.date == '2022-06-02'))]
        rebuilt = build_features(prices, self.events, self.baselines, self.config)
        before = rebuilt[(rebuilt.symbol == 'AAPL') & (rebuilt.date == '2022-06-01')].iloc[0]
        self.assertTrue(pd.isna(before.target_return))
        self.assertFalse(((rebuilt.symbol == 'AAPL') & (rebuilt.date == '2022-06-03')).any())

    def test_overlapping_labels_purged(self):
        train, test = chronological_split(self.features, '2022-01-01','2023-01-01')
        self.assertLess(train.target_date.max(), test.date.min())
        self.assertLess(test.target_date.max(), pd.Timestamp('2023-01-01'))
        # All assets for a date belong to the same side of the split.
        self.assertFalse(set(train.date) & set(test.date))

    def test_artifact_roundtrip_and_tamper_detection(self):
        model = self.result['models']['event_adjusted']
        _, test = chronological_split(self.features, '2022-01-01','2023-01-01')
        with tempfile.TemporaryDirectory() as folder:
            save_bundle(model, folder)
            restored = load_bundle(folder)
            np.testing.assert_allclose(model.predict_features(test), restored.predict_features(test))
            original = model.predict(self.prices, self.events, self.baselines)
            pd.testing.assert_frame_equal(original, restored.predict(self.prices, self.events, self.baselines))
            with self.assertRaises(FileExistsError):
                save_bundle(model, folder)
            path = Path(folder)/'pipeline.joblib'
            path.write_bytes(path.read_bytes()+b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                load_bundle(folder)

    def test_preprocessing_fitted_on_training_only(self):
        train, _ = chronological_split(self.features, '2022-01-01','2023-01-01')
        imputer = self.result['models']['event_adjusted'].pipeline.named_steps['select'].named_transformers_['numeric']
        expected = train[MARKET_FEATURES + EVENT_FEATURES].median().fillna(0).to_numpy()
        np.testing.assert_allclose(imputer.statistics_, expected)

    def test_event_inference_requires_complete_coverage(self):
        bad = self.features.iloc[-2:].copy()
        bad['event_coverage_7d'] = 0
        with self.assertRaisesRegex(ValueError, 'complete'):
            self.result['models']['event_adjusted'].predict_features(bad)

    def test_bootstrap_direction_and_minimum_sample(self):
        rows = []
        for date in pd.bdate_range('2020-01-01', periods=100):
            for symbol in ['A','B']:
                for model, predicted in [('reference', .02), ('candidate', .01)]:
                    rows.append(dict(date=date,symbol=symbol,model=model,predicted_return=predicted,target_return=0.))
        result = block_bootstrap(pd.DataFrame(rows),'reference','candidate',5,repetitions=100)
        self.assertAlmostEqual(result['mean_improvement_pp'], 1.)
        self.assertGreater(result['ci95_pp'][0], 0)
        small = block_bootstrap(pd.DataFrame(rows).iloc[:40], 'reference','candidate',5,repetitions=100)
        self.assertEqual(small['status'], 'insufficient_dates')

    def test_gdelt_schema_and_archive_availability(self):
        row = ['']*58
        for index, value in {0:'123',1:'20140101',7:'USA',17:'CHN',26:'190',28:'19',29:'4',56:'20150101',57:'https://example.org'}.items():
            row[index] = value
        stream = io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            archive.writestr('20150101.export.CSV', '\t'.join(row)+'\n')
        events = parse_gdelt(stream.getvalue(), '2015-01-01')
        self.assertEqual(events.iloc[0].quad_class, '4')
        self.assertEqual(events.iloc[0].available_at, pd.Timestamp('2015-01-03', tz='UTC'))
        self.assertEqual(events.iloc[0].event_date, '20140101')


if __name__ == '__main__':
    unittest.main()

class BroadContractTests(unittest.TestCase):
    def test_futures_context_is_not_available_at_equity_close(self):
        import exchange_calendars as xc
        prices,events,baselines=synthetic_inputs()
        config=json.loads(Path('config/research.json').read_text())
        config.update(stocks=['AAPL','FCX'],completed_futures_context=True)
        features=build_features(prices,events,baselines,config)
        row=features.iloc[-1]
        for name in ['XNYS','NYMEX','COMEX']:
            self.assertGreaterEqual(row.cutoff_at,xc.get_calendar(name).session_close(row.date)+pd.Timedelta(hours=1))

    def test_asset_encoder_rejects_untrained_assets_and_missing_training_asset(self):
        from research_pipeline.model import fit_bundle
        prices,events,baselines=synthetic_inputs()
        config=json.loads(Path('config/research.json').read_text())
        config.update(stocks=['AAPL','FCX'],include_symbol=True)
        features=build_features(prices,events,baselines,config)
        train=features[features.event_coverage_7d.eq(1)].dropna(subset=['target_return'])
        model=fit_bundle(train,config,True,['fixture'],'synthetic_verification_only')
        changed=train.tail(1).copy();changed['symbol']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'outside'):
            model.predict_features(changed)
        with self.assertRaisesRegex(ValueError,'every configured asset'):
            fit_bundle(train[train.symbol.eq('AAPL')],config,True,['fixture'])
