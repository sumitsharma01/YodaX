# Model and learning loop

## TimesFM

YodaX uses Google's pretrained **TimesFM 2.5 200M** checkpoint, with `timesfm==2.0.2`. It runs on local CPU through PyTorch, without fine-tuning. Each input contains 256 completed daily closing prices; the output is the next trading session's estimated close.

The checkpoint is pinned in `backend/core.py` to revision `1d952420fba87f3c6dee4f240de0f1a0fbc790e3`. The shaded chart range uses its 10th and 90th quantiles. That range is not a calibrated coverage guarantee.

The main forecast cards show the original TimesFM estimate. Adaptive results and diagnostics are available in Methodology. The model is a general time-series forecaster, not a stock-specific model or proof of profitable trading.

References: [Google's repository](https://github.com/google-research/timesfm), [checkpoint and model card](https://huggingface.co/google/timesfm-2.5-200m-pytorch), and the original [TimesFM paper](https://arxiv.org/abs/2310.10688). The 2.5 checkpoint is distributed under Apache 2.0; its model card is the source for this particular release.

## What “self-improving” means here

The learning loop is a small, versioned layer around TimesFM. Its foundation-model weights remain frozen. For each stock, it starts with three forecasts:

| Approach | Initial weight |
| --- | ---: |
| Original TimesFM | 60% |
| No change from the last close | 20% |
| TimesFM with a learned bias correction | 20% |

Before a session opens, YodaX saves the blended prediction, the three component prices, their weights, and the volatility used for scoring. When the daily job later observes the actual close, it scores that saved prediction and updates the weights for future forecasts. Better-performing components gain relative weight; larger mistakes are penalized more heavily.

The bias correction tracks whether TimesFM tends to predict too high or too low. It uses a moving average with a 0.1 update rate and limits corrections to one volatility unit. Weights use exponential loss updates with a 0.1 learning rate, a loss cap of 25, and 3% uniform mixing to keep any component from disappearing permanently.

Only completed **prospective** forecasts train this layer. Historical test results never train it. Each outcome is processed once, and the update, outcome, and next forecast are committed together. Rerunning a job cannot rewrite an issued prediction or reward the same result twice. State is separated by stock, model revision, and strategy version (`online-v1`).

This creates a feedback loop, not a promise of improvement. We compare the adaptive and original forecasts on the same future sessions. The interface reports the sample size and observed error difference; neither is a statistical significance test.

## Scores and evaluation

The user-facing result shows predicted close, actual close, the price difference, direction, and a quality score out of 100. It is a **quality index, not a probability or percentage correct**.

For scoring, the price error is divided by the previous close and then by the sample standard deviation of the preceding 20 daily returns. Volatility has a 0.5% floor and is saved before the outcome is known. Calling the resulting normalized error `z`:

- Loss is `z²`, so large errors receive a quadratic penalty.
- The display score is `100 / (1 + z²)`: an exact prediction scores 100, and a one-volatility miss scores 50.
- Reward is the no-change baseline's loss minus the forecast's loss. Positive means it beat the baseline; negative means it did worse.

The learner caps its update loss for stability; displayed losses and rewards are not capped. Direction accuracy is reported separately: a correct direction can still have a large price error. Aggregate comparisons also use mean absolute return error and the no-change baseline.

These choices draw on [forecast-error evaluation](https://otexts.com/fpp3/accuracy.html) and [online prediction with expert advice](https://arxiv.org/abs/math/0602629). The display score and tuning constants are YodaX design choices; no theoretical guarantee from those references is claimed for this implementation.

## Limits of the evidence

Historical evaluation uses ten rolling forecast origins per stock by default. Each target is excluded from its input window, but the downloaded history may include provider corrections and split restatements. This is not a fully point-in-time backtest, and pretraining overlap has not been independently ruled out.

The job rejects missing sessions, invalid prices, and recent split targets. It leaves pending forecasts unscored if their reference price has materially changed. Full corporate-action reconciliation is still needed before a production rollout.

## Inspecting the evidence

Methodology separates two records:

- **Live record:** immutable prospective prices, save times, actual outcomes when available, and the next eligible scoring checkpoint. New settlements also store the learner's state before and after the update. Older outcomes without such an audit are labelled accordingly.
- **Historical replay:** the current saved historical predictions are passed through the same blend and update functions in chronological order. Each stock starts from the initial weights. Volatility uses prices before the target; that target's actual close updates only subsequent predictions. The replay is computed read-only and never alters the live learner.

The comparison uses mean absolute price miss divided by the previous close, in percentage points. TimesFM, the adaptive blend and the unchanged-price baseline are evaluated on identical rows. The per-outcome inspector shows the three prices and before/after weights, including outcomes where adaptation made the error worse.

`GET /api/evidence` returns both records. `GET /api/evidence/export` downloads the same evidence as JSON, including timestamps, revision, source hashes and state changes. These endpoints read saved data; they do not retrain TimesFM or fetch new closing prices. The daily job still supplies live outcomes.
