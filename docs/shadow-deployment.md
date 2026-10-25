# Frozen candidate evaluation

Two candidates run separately from the public daily dashboard:

| Configuration | Candidate | Scope |
| --- | --- | --- |
| `config/shadow.json` | `country-v2-20261023` | AAPL and FCX, dated country exposures, five sessions |
| `config/shadow-broad.json` | `global-v1-20261025` | 21 stocks, WTI and copper, global event features, five sessions |

The broader candidate saves no-change, TimesFM, market-adjusted and event-adjusted comparisons. It is available to eligible chat requests as a beta. The original experiment remains separate, including requests already pinned to it.

## Worker contract

Each run verifies frozen artifacts and dependencies, collects eligible inputs, scores due outcomes and issues prospective predictions. Original issued values are immutable. Late inputs cannot be turned into backdated forecasts. Missing required events cause a recorded failure or skip, not an invented zero or silent model substitution.

Prediction records retain issue time, cutoff, target, revision, artifact/input hashes and features. Scoring checks target availability and corporate actions. Restatements or invalid inputs can leave an outcome unscored for review.

Install `requirements-shadow.txt` in a separate environment. Validate locally without writing to cloud storage:

```sh
YODAX_STORAGE=sqlite .venv-shadow/bin/python -m backend.shadow_run --check
YODAX_STORAGE=sqlite .venv-shadow/bin/python -m backend.shadow_run --config config/shadow-broad.json --check
```

Remove `--check` only when intending to run inference. `--score-only` processes outcomes without issuing forecasts. See [cloud operations](cloud-deployment.md) for scheduled jobs and controls.

## Review and limits

The private `/model-evaluation.html` page requires `SHADOW_ADMIN_TOKEN`. It shows saved outcomes and worker diagnostics. Public model-evidence links expose selected prediction fields, not administrative logs or private conversation history.

Neither candidate retrains or promotes itself. The older Apple disclosure reaches its configured age limit in early November 2026; updating it requires sourced data and a new evaluated candidate, not silently extending the limit.

Overlapping five-session targets are dependent observations. Historical and prospective results answer different questions. No-change still wins pooled historical MAE for the broader study. Use [the measured results](global-event-beta.md) and [acceptance plan](experiment-plan.md) when deciding what to change.

Selected normalized broad inputs are retained as Actions artifacts for 30 days. Full permanent raw-source replay storage remains unfinished.
