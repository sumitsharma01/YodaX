# Model reference

YodaX uses separate models for price forecasting, event adjustment and research conversation. They have different jobs and different evaluation requirements.

| Component | Current implementation | Learns during daily operation? |
| --- | --- | --- |
| Price baseline | TimesFM 2.5, 200M parameters, PyTorch | No |
| Event adjustment | sklearn histogram gradient boosting with fitted preprocessing | No, frozen candidate |
| Daily adaptive blend | Loss-weighted TimesFM, no-change and bias-corrected experts | Yes, eligible settled outcomes update blend state |
| Research agent | Gemini 3.1 Flash-Lite | No local model training |

## TimesFM

The model is `google/timesfm-2.5-200m-pytorch`, pinned to revision `1d952420fba87f3c6dee4f240de0f1a0fbc790e3`. The package version is `timesfm==2.0.2`. YodaX uses 256 prior closing prices and runs numerical inference outside the web process. Its 10th/90th quantile range is uncalibrated; it is not a guaranteed coverage interval.

References: [Google Research repository](https://github.com/google-research/timesfm) and [model card](https://huggingface.co/google/timesfm-2.5-200m-pytorch).

## Event adjustment

`global-v1-20261025` covers 21 US stocks plus WTI and copper at five sessions. The saved pipeline combines training-fitted median imputation, missing indicators, symbol encoding and a shallow `HistGradientBoostingRegressor`. It predicts a residual added to the TimesFM return.

Its fixed settings include 100 iterations, seven leaf nodes, minimum 30 samples per leaf, learning rate 0.05, L2 regularization 10 and seed 42. It has no fabricated prediction interval. See the [data guide](data-pipeline.md) for feature definitions and [beta results](global-event-beta.md) for measured errors.

The original `country-v2-20261023` AAPL/FCX experiment remains separate. Candidate IDs, artifact hashes and manifests distinguish them. Neither changes the pretrained TimesFM weights.

## Scores and updates

Return MAE and RMSE measure numerical error. Direction measures whether the predicted move had the correct sign. The daily adaptive score rescales squared error against recent volatility; it is not a probability or a percentage of correct forecasts. Longer horizons scale volatility by the square root of the session horizon for their score.

The [improvement guide](agent-and-improvement.md) explains the exact distinction between automatic blend updates and reviewed retraining. Scoring a frozen event model does not train it.
