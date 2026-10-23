# Private shadow evaluation

The public dashboard still uses its existing next-session forecasts. This experiment runs separately and asks whether a frozen country-linked model improves **five-session** forecasts for Apple (AAPL) and Freeport-McMoRan (FCX).

For each stock and cutoff, the worker saves three predictions: TimesFM, TimesFM with a market-only residual adjustment, and TimesFM with the country-linked event adjustment. Comparing all three on the same stock, date and horizon helps distinguish improvement from market features from improvement associated with event features. It does not establish causation.

## Daily workflow

The `shadow` job in Daily forecasts runs after the public job, in a separate environment. It checks candidate checksums and dependency versions, fetches closing prices, scores eligible pending forecasts, and issues new forecasts before the next session opens. Repeating a run cannot overwrite an issued prediction. It never backfills predictions after that deadline.

Inputs include daily Yahoo Finance prices, seven complete GDELT daily archives with a two-day availability lag, and dated company exposure disclosures. Missing or expired event inputs cause a recorded candidate skip; they are not interpreted as no events. The market and TimesFM forecasts may still be saved. Such a partial run fails the worker job so the problem remains visible.

Each saved prediction records its cutoff, target, issue timestamp, model revision, artifact and input hashes, and input coverage. The target is five exchange sessions after the cutoff. Scoring waits until one hour after that target session closes. Missing sessions, splits or restated cutoff prices leave the outcome unscored for review. Original predictions remain unchanged.

## Access and operation

Install the worker separately:

```sh
python3.13 -m venv .venv-shadow
.venv-shadow/bin/pip install -r requirements-shadow.txt
.venv-shadow/bin/python -m backend.shadow_run --check
.venv-shadow/bin/python -m backend.shadow_run
```

Use `--score-only` to process outcomes without issuing forecasts. Storage follows `YODAX_STORAGE`: SQLite locally; Postgres with `DATABASE_URL` in the cloud. Never run experimental checks against the production database unintentionally.

On Render, set `SHADOW_ADMIN_TOKEN` to a random secret of at least 32 characters. Open `/model-evaluation.html` and sign in with that token. Access expires after eight hours; rotating the token revokes existing access. This token is separate from research-chat sessions and must never appear in frontend code or Git. The page shows saved forecasts, pending outcomes, error metrics, matched comparisons and run failures. An empty page means no prospective results have been collected yet, not that the model has succeeded.

GitHub Actions uses the existing `DATABASE_URL` secret. Set repository variable `YODAX_SHADOW_ENABLED=false` to stop shadow runs without stopping public forecasts. The worker requires no Gemini key. Keeping it in a separate job prevents shadow failures from interrupting public forecast generation, although a shadow failure makes the overall workflow red.

## Frozen candidate and limitations

`config/shadow.json` selects `country-v2-20261023`. Its artifacts contain fitted preprocessing and residual models. They are trusted local artifacts; never load joblib files from untrusted sources. The worker verifies checksums and the TimesFM revision before inference. No automatic retraining or promotion occurs.

This is a two-stock pilot, not a validated model for all equities, commodities or forex. Historical validation was mixed and inconclusive. Five-session targets overlap, so a count of predictions is not a count of independent observations. The page reports descriptive metrics; it does not claim statistical significance or display an invented accuracy score.

The frozen Apple exposure disclosure becomes too old under its 730-day age limit in early November 2026. Refresh the sourced exposure data, evaluate the change, and issue a new version before expecting ongoing event-candidate coverage. Do not silently extend the limit. Future promotion requires prospective evidence, dependent-sample uncertainty estimates, data and drift review, and an explicit decision. A new candidate must use a new version and artifact directory so its results remain distinguishable.

Raw source snapshots are local to each worker run; input hashes survive in the database, but ephemeral Actions workers do not retain those source files. Durable source archiving is a further requirement for full replay audits. The current private evaluation is an early monitoring experiment, not production approval.
