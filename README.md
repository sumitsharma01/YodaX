# YodaX

YodaX forecasts the next trading day's closing price for six US stocks, then compares each saved prediction with the actual close. The dashboard keeps the everyday view simple: predicted price, expected change, and results once the market closes.

It runs locally using Google's TimesFM 2.5 model. An experimental learning layer adjusts future estimates using completed predictions; it does not retrain TimesFM.

Future Market adds an experimental commodity research assistant powered by Gemini. It analyses recent news headlines, follows an unresolved question, and presents a linked evidence map alongside the conversation. This research is separate from the stock forecasts.

## Run locally

Tested on macOS with Apple Silicon and Python 3.13.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
.venv/bin/python -m backend.run
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 5173
```

Open [localhost:5173](http://127.0.0.1:5173) for the landing page, then choose **Open workspace**. The dashboard is also available directly at [workspace.html](http://127.0.0.1:5173/workspace.html). The first run downloads about 882 MB of model weights. No API key is needed for stock forecasts. The optional [Future Market research demo](docs/future-market.md) requires a Gemini key.

## What it does

- Introduces the product through a responsive landing page with an original animated signal graphic, feature overview and FAQs.

- Forecasts AAPL, MSFT, GOOGL, TSLA, NVDA, and AMZN one trading session ahead.
- Saves predictions before the target session opens and scores them on a later run.
- Separates historical tests from predictions published in advance.
- Displays prices in USD, INR, EUR, GBP, JPY, or CAD using dated exchange rates.
- Keeps formulas and learning diagnostics in the optional Methodology view.
- Chats about commodity headlines and qualitative scenarios, with contextual follow-ups and saved conversations.
- Shows a clickable evidence map for each answer, linking sources, proposed mechanisms, risks and the outlook.
- Preserves completed research through reloads and handles temporary Gemini failures with a bounded retry.

To refresh data and forecasts, run `.venv/bin/python -m backend.run` again. The website reads saved results; clicking a company does not run the model.

## How it works

```text
Stock prices → TimesFM + adaptive layer → SQLite → FastAPI → Dashboard
News feeds → Gemini research + follow-up → SQLite → Future Market
```

TimesFM uses the previous 256 closing prices. The adaptive layer blends its forecast with a no-change estimate and a bias-corrected forecast. After actual prices arrive, approaches with smaller errors gain relative weight. Original predictions are preserved so the comparison remains inspectable.

This is a local research application. It has not established a trading advantage, and the learning loop does not guarantee improvement. Yahoo data is intended for personal use; a public deployment needs an appropriately licensed market-data source.

## Optional Gemini setup

Copy `.env.example` to `.env` if you do not already have one, then set `GEMINI_API_KEY` using a key from [Google AI Studio](https://aistudio.google.com/api-keys). Keep billing disabled in that Google project. Open **Future Market** in the website to start an investigation.

The integration uses Gemini text generation and public news feeds, with no paid search-grounding tool or model fallback. It limits generation attempts to 40 per UTC day and saves conversations locally. Temporary server errors receive one bounded retry. Google may apply lower quotas or temporarily reject requests.

The current demo reads headlines, not full articles, and does not produce validated commodity price targets or feed research into TimesFM. Live commodity chat, contextual follow-ups and linked evidence graphs have been verified with Gemini 3.1 Flash-Lite. Provider availability and free-tier quotas still apply.

## Documentation

- [Features and workflows](docs/workflows.md): how to use each section, end-to-end diagrams, component responsibilities, and current boundaries.

- [Model and learning loop](docs/model.md): model choice, evaluation, scoring, and references.
- [Running YodaX](docs/running.md): daily runs, storage, currencies, and troubleshooting.
- [Future Market](docs/future-market.md): Gemini setup, research flow, cost controls, and limitations.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check demo/dist/app.js
node --check demo/dist/future.js
node --check demo/dist/landing.js
```

The repository contains source and documentation only. Model weights, market-data snapshots, local databases, and credentials are excluded.
