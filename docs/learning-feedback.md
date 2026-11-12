# Learning from forecasting errors

The daily worker now maintains two independent adaptive versions for each stock.
The current version supplies the existing dashboard forecast. The new
`online-v2-shadow` challenger runs beside it and saves its own predictions and
outcomes in `adaptive_forecasts` and its state in `learning_state`.

Each completed prospective forecast updates the learner once. The stored prediction,
input volatility and weights provide an audit trail. Historical backtest rows cannot
update the live learner. The new version starts collecting evidence on its first run.

The challenger applies a faster, bounded correction to systematic price errors.
It reduces the weight of experts with large normalized errors and adds a penalty
for an opposite-direction forecast on a material price move. It retains a small
weight for every expert so an expert can recover as conditions change.

Before making a directional call, the challenger needs 20 settled observations.
Its shadow ensemble must beat the no-change baseline's mean absolute return error
by at least 5% over the latest 20 observations. Otherwise it records a neutral
no-change forecast and a reason. The shadow ensemble continues learning while
neutral. A neutral forecast is counted separately from correct directional calls.

This gate is an operational rule, not a statistical significance test. The new
version does not automatically replace the current dashboard model. Promotion
requires reviewing prospective performance across all six stocks and both price
error and directional coverage. TimesFM's neural weights are frozen. These updates
train the correction layer.

## Reproduce the development replay

Run `.venv/bin/python -m backend.replay_learning` from the repository root.
It opens the local database read-only and uses the original saved volatility and
raw forecast. A historical outcome becomes available to the replay only at its
recorded scoring time. The output separates neutral forecasts from directional calls.

The November 12 development replay contained 27 settled forecasts for each of six
stocks. The challenger stayed neutral throughout. NVIDIA mean absolute return
error fell from 2.520 to 2.424 percentage points compared with online-v1, but errors
increased for AAPL, AMZN, MSFT and TSLA. This does not justify promotion or establish
better direction prediction. These are retrospective development results. New
prospective records are the next source of evidence.

The dashboard API exposes `adaptive_candidate` and `candidate_results` for audit.
The existing website charts continue to show the current version. No training
or evaluation record is relabelled as a newly issued forecast.
