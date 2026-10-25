> Historical document archived October 25, 2026. Use the [current guides](../README.md) for current behavior and commands.

# Event-aware forecasting research

YodaX now has a separate, reproducible research pipeline and an executable notebook. It collects source snapshots, constructs historical features, generates pinned TimesFM baselines, trains nonlinear residual models, evaluates them chronologically, and saves preprocessing and the adjustment model together.

This is a research candidate workflow. It does not change the live app, production database, daily job or TimesFM weights. The first bounded real-data check did not improve on TimesFM; no model has been promoted.

## Start here

Open `notebooks/yodax_research_pipeline.ipynb`. It contains the research question, collection controls, data inspection, feature engineering, leakage checks, model comparisons, statistical evaluation, charts and artifact reload checks. The notebook imports the same Python modules as the CLI rather than duplicating the implementation.

The default `exposure_study` mode uses the expanded, source-linked two-stock dataset described at the end of this guide. `real_check` retains the earlier verification dataset. Data is ignored by Git; a fresh clone can run `synthetic_verification` to verify the entire software path, or prepare real inputs as below. Synthetic mode is explicitly labeled and is not a market-performance demonstration.

Use an isolated environment:

```sh
python3.13 -m venv .venv-research
.venv-research/bin/pip install -r requirements-research.lock.txt
.venv-research/bin/python -m ipykernel install --user --name yodax-research --display-name 'YodaX research'
```

Open the notebook in a Jupyter-compatible editor and select that kernel. You can also execute and save its outputs without an editor:

```sh
.venv-research/bin/python -m research_pipeline.notebook --mode real_check
# For a fresh clone without local market datasets:
.venv-research/bin/python -m research_pipeline.notebook --mode synthetic_verification \
  --output data/research-runs/synthetic-notebook.ipynb
``` The research lock is the exact environment used for the saved adjustment artifacts. `requirements-research.txt` lists direct dependencies. The live application's dependency files are unchanged.

For real TimesFM baseline generation, install the existing forecasting dependencies **in a separate research environment**, before training/saving new artifacts:

```sh
python3.13 -m venv .venv-research-full
.venv-research-full/bin/pip install -r requirements.lock.txt -r requirements-research.txt
```

Do not load an artifact under a different scikit-learn/numpy/pandas/joblib version: the loader refuses it. Each run writes its exact executed dependency list. The forecasting model is the existing pinned `google/timesfm-2.5-200m-pytorch` revision from `backend/core.py`.

## Scope and current coverage

`config/research.json` defines the January 2015 start, five-session horizon, 256-session context, 20-stock watchlist, validation windows, seed and bootstrap settings.

The selected stocks span technology, finance, healthcare, consumer, industrials, energy and materials. This is a present-day selected universe, with survivorship and selection bias. Do not generalize its results to the entire stock market.

Available context series are SPY, WTI futures, Brent futures and copper futures. The first model uses SPY, WTI and copper features; Brent is collected for inspection. Futures are Yahoo front-month proxies, not spot prices or roll-adjusted investable returns. Silicon metal vs polysilicon, lithium grade/region, and the regional steel benchmark remain unresolved source/coverage gaps. Equity prices are not substitutes for those commodities. No physical-demand model is implemented.

Current collectors:

- **Prices:** yfinance, with raw CSV snapshots, content hashes and a per-symbol coverage report. The provider's access and redistribution terms still apply.
- **Global events:** official GDELT v1 daily ZIP downloads and normalized daily Parquet records, with source URLs, event codes, actor countries, hashes and collection times. v1 is used consistently from January 2015, avoiding a silent format/coverage change around the start of v2.

The first event features are global CAMEO cooperation/conflict counts and shares. They are not verified wars, tariff amounts, FTA stages, company supply-chain exposure, or causal impacts. Detailed semantic extraction, official corroboration, historical company exposure, SEC filings and vintage macro releases remain future extensions. The pipeline is deliberately explicit about this boundary.

## Collection and historical replay

```sh
.venv-research/bin/python -m research_pipeline --data data/research collect-prices --end 2026-10-22
.venv-research/bin/python -m research_pipeline --data data/research collect-events --start 2015-01-01 --end 2015-02-01
```

End dates are exclusive. Run event backfills in monthly chunks through the desired cutoff. Archives are cached and successful chunks are merged; a failed day remains a coverage gap, not zero activity. The full 2015-onward archive is a substantial download and has **not** been completed as part of the initial check. Do not run the full backfill inside the web process.

The local initial collection contains 71,231 price observations across 20 stocks and four context series, January 2015 through October 21, 2026. A bounded event backfill contains 190 archive days, April 15–October 21, 2026 (about 1.1 GB of compressed source archives). These counts describe this snapshot, not a permanent guarantee of provider coverage.

```sh
.venv-research-full/bin/python -m research_pipeline --data data/research baseline
```

Historical baselines are cached by price-context hash, pinned model revision, horizon and context length. Each forecast uses preceding closes only. The full 20-stock replay is a substantial CPU job; the initial real check generated 250 forecasts for AAPL and FCX instead. No placeholder forecasts are used for real-mode experiments.

Once sufficient data exists, one command can orchestrate collection through artifact saving:

```sh
.venv-research-full/bin/python -m research_pipeline --data data/research run \
  --end 2026-10-22 --events-start 2015-01-01 --events-end 2026-10-22 \
  --output data/research-runs/full-validation-001
```

This explicit full-range command can download many gigabytes and run many thousands of forecasts. Prefer completing/checking bounded collection chunks first. It does not deploy a model.

## Point-in-time rules

- Reindex equities to XNYS sessions before calculating targets. Missing sessions cannot silently shorten the five-session horizon.
- Reject duplicate/invalid equity values and contexts crossing stock splits. Labels with missing future closes or splits are ineligible.
- Rolling features use current and previous observations only; target returns are separate columns.
- Join market context on exact dates. Missing/nonpositive futures values remain missing; no arbitrary interpolation.
- GDELT daily archive availability is modeled as archive date plus two days. This is a conservative historical assumption, **not proof of the original publication time**. Occurrence dates are not used as availability dates.
- Event features require seven complete archive days. Missing coverage is never converted to evidence of no events. Event-aware training and inference fail closed on incomplete coverage.
- The imputer is fitted on each training fold, inside the saved sklearn pipeline. Evaluation rows never set imputation values.
- Historical Yahoo snapshots may reflect restatements. TimesFM pretraining overlap with historical evaluation periods is unknown. These limitations prevent claiming a fully uncontaminated historical foundation-model test. Prospective forecasts are the stronger evidence.

## Training and evaluation

```sh
.venv-research-full/bin/python -m research_pipeline --data data/research train \
  --output data/research-runs/validation-001
```

The main configuration evaluates 2022 and 2023 in separate expanding chronological folds. All assets share date boundaries. Training labels reaching the next evaluation period are purged. Evaluation labels must settle within that period. The 2024-onward holdout requires a separate explicit `--holdout` run and must not be used for tuning.

Four forecasts use the same eligible asset/date rows:

1. No change.
2. Raw TimesFM.
3. TimesFM plus a market-feature residual model.
4. The same model plus event features.

The residual learner is scikit-learn `HistGradientBoostingRegressor`: shallow trees, regularization, fixed seed and fixed hyperparameters. Random internal early stopping is disabled. There is no hyperparameter search in v1.

The primary metric is mean absolute return error in percentage points. RMSE and three-way directional agreement (down/unchanged/up) are secondary; a no-change forecast can have zero directional agreement when actual returns are nonzero. Compare error first.

The primary hypothesis concerns **event-adjusted versus market-adjusted** loss, not merely improvement over TimesFM. A paired moving-block bootstrap averages the per-asset loss difference within each date, resamples contiguous observed-date blocks, and retains all stocks together. Positive improvement favors the event model. Default blocks are 20 sessions, with 1,000 replicates; at least 60 evaluation dates are required. Review missing-date gaps and test block-length sensitivity before drawing conclusions. If confidence intervals span zero, improvement is not established. This is not causal inference or a trading-profitability test.

`--market-only` is an explicitly different experiment when event data is unavailable. It cannot establish event value. No ANOVA, chi-square or product A/B test is added without an appropriate research question.

## Reproduce the bounded real check

After collecting prices/events, create a small dataset and config:

```python
from pathlib import Path
import json
import pandas as pd
root = Path('data/research-real-check')
root.mkdir(exist_ok=True)
config = json.loads(Path('config/research.json').read_text())
config.update(stocks=['AAPL', 'FCX'],
              validation_windows=[['2026-08-24', '2026-10-22']],
              holdout_start='2026-10-22')
prices = pd.read_parquet('data/research/prices.parquet')
prices = prices[prices.symbol.isin(['AAPL', 'FCX', 'SPY', 'CL=F', 'HG=F'])]
prices.groupby('symbol', group_keys=False).tail(380).to_parquet(root/'prices.parquet', index=False)
pd.read_parquet('data/research/events.parquet').to_parquet(root/'events.parquet', index=False)
(root/'config.json').write_text(json.dumps(config, indent=2))
```

Run `baseline` using this data/config, then `train` with the same arguments:

```sh
.venv-research-full/bin/python -m research_pipeline --data data/research-real-check \
  --config data/research-real-check/config.json baseline
.venv-research-full/bin/python -m research_pipeline --data data/research-real-check \
  --config data/research-real-check/config.json train --output data/research-runs/real-check-new
```

The initial check evaluated 74 predictions per model across 37 dates. Approximate MAE was 2.63 percentage points for TimesFM, 3.18 for market adjustment, and 3.61 for event adjustment. **The added models performed worse.** There were too few dates for the configured bootstrap interval. These are integration-check results, not a full-study finding or a reason to tune on the same short period until it looks good.

## Artifacts and future serving

Each run writes:

- `features.parquet`: engineered rows, cutoff times and target dates.
- `predictions.parquet`: fold/model predictions and observed targets.
- `report.json`: metrics, split boundaries, statistical results, config, input/code hashes and limitations.
- `requirements-executed.txt`: exact environment.
- `market_adjusted/` and `event_adjusted/`: `pipeline.joblib` and `manifest.json`.

The bundle contains fitted column selection, imputation and the nonlinear adjustment estimator, plus feature configuration, schema version and training metadata. `ForecastBundle.predict(prices, events, baselines)` runs the same deterministic feature builder and combines its adjustment with the required pinned TimesFM baseline. It refuses stale latest-session features, missing event coverage, incompatible baseline revisions and invalid adjusted prices.

This is **not** a standalone replacement for the upstream collectors or TimesFM weights. Deploy the Python package and matching environment alongside the saved artifact. Only load trusted joblib files; they can execute Python code. Checksum validation detects corruption but does not authenticate an untrusted author.

```sh
.venv-research-full/bin/python -m research_pipeline --data data/research-real-check predict \
  --artifact data/research-runs/real-check-new/event_adjusted \
  --output data/research-runs/real-check-new/predictions-latest.parquet
```

Saved models are from the last evaluation fold, with exact training dates recorded. They are not silently refitted on the holdout. Existing run folders and prediction files cannot be overwritten. A failed run writes a failure record; there is no production promotion path in v1.

Before production: finish/audit coverage, enrich and validate features, evaluate the prespecified full study, consume the untouched holdout once, and collect sufficient prospective shadow evidence. Periodic candidate retraining is separate from daily scoring. Keep the current model if a candidate does not improve it.

## Checks

```sh
.venv-research/bin/python -m unittest discover -s research_pipeline/tests -v
.venv-research/bin/python -m research_pipeline --data data/fresh-fixture smoke \
  --output data/research-runs/fresh-smoke
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover future-data leakage, purging, missing sessions/events, training-only imputation, source parsing, artifact round trips and tampering, and bootstrap behavior. Synthetic fixtures never enter the production database.

## References

- [GDELT datasets](https://gdeltproject.org/data.html)
- [GDELT v1 format](https://data.gdeltproject.org/documentation/GDELT-Data_Format_Codebook.pdf)
- [TimesFM repository](https://github.com/google-research/timesfm)
- [scikit-learn histogram gradient boosting](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)
- [scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html)

## Country-linked event study

The notebook now defaults to `exposure_study`. This is a broader follow-up to the short two-stock check, with sourced country presence and longer chronological validation. It is still a two-company experiment, not a completed 20-stock backtest from 2015.

`config/research-exposures.json` records Apple's outsourced-manufacturing countries and Freeport-McMoRan's mining-operation countries from their 2024 annual filings. Each entry has a source URL/section, filing date, conservative availability date and maximum age. These are manually reviewed binary country links, not estimated revenue or production weights. We do not backdate the disclosures or infer continuous verification of the company's exposure afterward.

The new features count relevant-country events once per company and distinguish reported sanctions directed at a relevant country from sanctions issued by it. CAMEO 163 covers embargoes, boycotts and sanctions; CAMEO 164 covers halted negotiations. Neither establishes tariff amounts, FTA stages or a company-specific impact. Source-age and coverage checks prevent missing/stale exposure information from silently becoming zero.

The local event archive now covers 641 days between January 1, 2025 and October 21, 2026. Eighteen daily files between June 14 and July 1, 2025 were unavailable from the provider and are retained as gaps. Affected seven-day windows are excluded. The expanded two-stock TimesFM replay contains 980 forecasts. Earlier 2015–2024 event history is still outstanding.

To reproduce the study, collect the relevant event chunks into `data/research`, then prepare its input directory:

```python
from pathlib import Path
import json
import pandas as pd
root = Path('data/research-exposure-study')
root.mkdir(exist_ok=True)
config = json.loads(Path('config/research-exposure-study.json').read_text())
prices = pd.read_parquet('data/research/prices.parquet')
prices = prices[prices.symbol.isin(['AAPL','FCX','SPY','CL=F','HG=F']) & (prices.date >= config['start'])]
prices.to_parquet(root/'prices.parquet', index=False)
pd.read_parquet('data/research/events.parquet').to_parquet(root/'events.parquet', index=False)
if not (root/'events_daily').exists():
    (root/'events_daily').symlink_to('../research/events_daily', target_is_directory=True)
```

Generate baselines in the TimesFM environment, then enrich/evaluate in the matching research environment:

```sh
.venv-research-full/bin/python -m research_pipeline --data data/research-exposure-study \
  --config config/research-exposure-study.json baseline
.venv-research/bin/python -m research_pipeline --data data/research-exposure-study \
  --config config/research-exposure-study.json enrich-events
.venv-research/bin/python -m research_pipeline --data data/research-exposure-study \
  --config config/research-exposure-study.json train --output data/research-runs/exposure-study-new
.venv-research/bin/python -m research_pipeline.notebook --mode exposure_study
```

The comparison now includes a global-only event model and a country-linked event model on the same rows. Tree settings remain fixed. The bootstrap excludes blocks crossing gaps in exchange sessions. These are exploratory comparisons; no multiple-comparison-adjusted confirmatory claim is made.

| Validation window | Dates | TimesFM MAE | Market adjustment | Global events | Country-linked events |
|---|---:|---:|---:|---:|---:|
| Sep–Dec 2025 | 80 | 3.655 | 3.941 | 3.777 | 3.779 |
| Jan–Jun 2026 | 118 | 4.956 | 4.893 | 4.869 | 4.561 |

Values are return percentage points; lower is better. Country links did not help over the global model in the first window and had lower observed error in the second. The paired-bootstrap intervals for country-linked improvement over global events span zero in both windows (approximately −0.158 to 0.140 pp, and −0.471 to 0.977 pp). Reliable added value has not been established, and the models remain unapproved research candidates.

The excluded July 2026-onward period overlaps the earlier exploratory check, so it is **not** an untouched holdout. Prospective evidence is still required.

Additional outputs:

- `quality.json`: source coverage, missing dates, feature missingness and source registry.
- `exposure-audit.json`: counts of missing actor countries/URLs, normalized-file hashes and limitations.
- `event-relevance-review.csv`: 50 recent source-linked examples for a human relevance review. These are unreviewed convenience samples, not proof of corroboration or a representative accuracy estimate.

Feature version `daily-v2-exposures` deliberately rejects older serialized artifacts; rerun the notebook to create compatible models. No production code or database is migrated.

Primary evidence: [Apple filing](https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm), [Apple filing date](https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123-index.html), [Freeport filing](https://www.sec.gov/Archives/edgar/data/831259/000083125925000006/fcx-20241231.htm), [Freeport filing date](https://www.sec.gov/Archives/edgar/data/831259/000083125925000006/0000831259-25-000006-index.htm), [CAMEO code definitions](https://parusanalytics.com/eventdata/cameo.dir/CAMEO.CDB.09b5.pdf).
