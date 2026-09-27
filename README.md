# YodaX

YodaX forecasts the next trading day's closing price for six US stocks, then compares each saved prediction with the actual close. The dashboard keeps the everyday view simple: predicted price, expected change, and results once the market closes.

It runs locally using Google's TimesFM 2.5 model. An experimental learning layer adjusts future estimates using completed predictions; it does not retrain TimesFM.

## Run locally

Tested on macOS with Apple Silicon and Python 3.13.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
.venv/bin/python -m backend.run
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 5173
```

Open [localhost:5173](http://127.0.0.1:5173). The first run downloads about 882 MB of model weights. No API key is needed.

## What it does

- Forecasts AAPL, MSFT, GOOGL, TSLA, NVDA, and AMZN one trading session ahead.
- Saves predictions before the target session opens and scores them on a later run.
- Separates historical tests from predictions published in advance.
- Displays prices in USD, INR, EUR, GBP, JPY, or CAD using dated exchange rates.
- Keeps formulas and learning diagnostics in the optional Methodology view.

To refresh data and forecasts, run `.venv/bin/python -m backend.run` again. The website reads saved results; clicking a company does not run the model.

## How it works

```text
Stock prices → TimesFM + adaptive layer → SQLite → FastAPI → Dashboard
```

TimesFM uses the previous 256 closing prices. The adaptive layer blends its forecast with a no-change estimate and a bias-corrected forecast. After actual prices arrive, approaches with smaller errors gain relative weight. Original predictions are preserved so the comparison remains inspectable.

This is a local research application. It has not established a trading advantage, and the learning loop does not guarantee improvement. Yahoo data is intended for personal use; a public deployment needs an appropriately licensed market-data source.

## Documentation

- [Model and learning loop](docs/model.md): model choice, evaluation, scoring, and references.
- [Running YodaX](docs/running.md): daily runs, storage, currencies, and troubleshooting.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check demo/dist/app.js
```

The repository contains source and documentation only. Model weights, market-data snapshots, local databases, and credentials are excluded.
