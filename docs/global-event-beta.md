# Global-event forecasts in chat

YodaX now has a frozen five-session event-aware candidate for the 20-stock research watchlist, Tesla, WTI oil (`CL=F`) and copper (`HG=F`). It combines a TimesFM baseline with recent price/volume features, market context and structured global event statistics. This is a **research beta**, not a production-approved replacement for the dashboard forecasts.

## What changed

Gemini resolves the asset and horizon, researches the question and queues a typed request. The numerical worker independently fetches prices and GDELT event archives. It uses the same deterministic features and fitted preprocessing as training. It saves the original prediction, model version, target, input values and archive references. Chat can explain those numbers and display an expandable input panel beside the mind map. Saved public model outputs have their own evidence links, distinct from news citations. Comparator descriptions show only the inputs each model uses; no change copies the last close.

Eligible five-session requests are pinned to `global-v1-20261025`. Other supported horizons and additional US equities use TimesFM. Requests for physical demand are research scenarios, not price forecasts. Missing current event inputs leave an event request queued; the worker does not silently substitute another model.

The previous two-company country-linked experiment remains frozen separately. Old requests retain their original candidate route. Neither experiment changes TimesFM weights or rewrites published forecasts.

## What events mean here

The numerical inputs are seven-day global event volume and material-cooperation/conflict shares from GDELT's dated archives. Asset identity is encoded within the fitted pipeline. These signals are broader than company-specific exposure and can miss local economic mechanisms.

The archive availability lag is two days, enforced in both replay and inference. Newly discovered Gemini headlines remain qualitative context; they do not become sentiment scores or causal price adjustments. A specific war, tariff or FTA mentioned by the agent is not automatically a trained feature. Expanding that representation requires historically reproducible extraction and a new evaluation.

The model also waits until the equity, WTI and copper input markets have closed, plus one hour. Futures are sampled on the XNYS reference grid. Their targets are provider daily prices, not official settlements, spot benchmarks or roll-adjusted investment returns.

## What we tested

The available price archive starts in 2015. The event archive used here starts in January 2025; **the 2015–2024 event backfill is not complete**. Price context starts in 2023, and two expanding comparisons cover September–December 2025 and January–June 2026. Split-crossing windows and incomplete seven-day event windows are excluded. All 23 assets occur in both comparisons. Training labels overlapping the evaluation boundary are purged.

Both residual models use fixed, shallow histogram-gradient-boosted trees. Median imputation and asset encoding are fitted inside the saved sklearn pipeline. Evaluation uses identical rows for events, market-only adjustment, TimesFM and no change. The primary statistical comparison uses a 20-session paired moving-block bootstrap, retaining all assets together by date.

| Period | Predictions per model | No change MAE | TimesFM MAE | Market-only MAE | Event-aware MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sep–Dec 2025 | 1,840 | 2.796 | 2.868 | 3.090 | 2.867 |
| Jan–Jun 2026 | 2,714 | 3.815 | 4.000 | 4.014 | 3.861 |

MAE is in return percentage points; lower is better. The event-versus-market improvement intervals are approximately **−0.118 to 0.675 pp** and **0.064 to 0.230 pp** respectively. The first includes zero. The second favors events in this exploratory historical comparison. No change still wins on pooled MAE in both windows. These results do not establish profitability, causation or reliable improvement for every asset.

Per-asset errors, uncertainty and feature shifts are in [the audit](audits/2026-10-25-broad/per-asset-evaluation.json). Some dates overlap earlier studies; this is not an untouched holdout. Current-universe selection, vendor restatements, news coverage bias, futures rolls and unknown TimesFM pretraining overlap remain limitations.

After evaluation, preprocessing and each adjustment model were refitted once on all eligible settled rows through June 2026. Those final artifacts are checked into `models/shadow/global-v1-20261025` with hashes and training metadata. Historical fold scores above are not prospective scores for that refit. The new candidate needs its own forward record.

## Daily operation

The existing GitHub Actions workflow now runs a separate `global_events` job. It verifies artifact hashes and environment versions, waits for all input market closes, scores eligible outcomes and issues four comparison forecasts per asset: no change, TimesFM, market-only and event-aware. It then attaches the event forecast to matching chat requests. Original values are immutable.

The job runs on the existing daily schedule, not immediately after every chat message. The UI distinguishes queued from issued forecasts. A second job retains normalized replay inputs and collection manifests as workflow artifacts for 30 days; longer-term archival is not yet configured. Set `YODAX_GLOBAL_EVENTS_ENABLED=false` to stop this job. To disable new beta routing as well, set `chat_enabled` to false in `config/shadow-broad.json`; already-pinned requests still require their original candidate.

## Reproduce and inspect

Open [the executed notebook](../notebooks/yodax_multi_asset_events.ipynb). It covers collection preparation, quality checks, preprocessing, chronological splits, evaluation, per-asset diagnostics, artifact reload and the serving contract. It uses the same modules as the worker. Data snapshots are ignored by Git; a fresh clone needs the source collection described in [the research guide](research-pipeline.md).

Use the pinned shadow environment for replay and training:

```sh
.venv-shadow/bin/python -m research_pipeline.broad prepare --data data/broad-new
.venv-shadow/bin/python -m research_pipeline.broad replay --data data/broad-new
.venv-shadow/bin/python -m research_pipeline.broad train --data data/broad-new \
  --output data/research-runs/broad-new --candidate global-new
```

Training does not select a new live candidate by default. `--activate-beta` explicitly changes the beta configuration after review; it never promotes the public dashboard. Use new dataset, run and candidate names to preserve previous evidence.

## Remaining coverage

Silicon, lithium, steel, Brent and forex remain research-only where a numerical benchmark/session contract is not validated. This candidate does not forecast physical demand and is not a full semantic model of geopolitical events. More detailed event features, the earlier archive backfill, additional horizons and a longer prospective comparison remain separate work.
