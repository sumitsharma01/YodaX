# Running YodaX

## Daily workflow

From the repository root:

```sh
.venv/bin/python -m backend.run
```

The job fetches completed daily bars, scores pending outcomes, updates the adaptive layer, and saves forecasts for the next trading session. It uses the US exchange calendar, waits one hour after the scheduled close, and refuses to issue a new forecast after its target session has opened. It exits when finished; the web server runs separately.

A local Codex automation is configured on the original development machine for weekdays at **23:15 Europe/Berlin**. It skips holidays and already processed sessions. That automation is not installed by cloning this repository. It requires the computer to be awake, online, and Codex running. On another machine, schedule the command in the repository directory after US market close.

Refresh the browser after a run. To evaluate a longer historical window, use `--backtest-days 20` (up to 60). More historical tests do not train the online learner.

## Currencies

Prices can be displayed in US dollars, Indian rupees, euros, pounds sterling, Japanese yen, and Canadian dollars. The model and database always use USD.

The daily job caches dated USD exchange rates from [Frankfurter](https://frankfurter.dev/), using its ECB-backed v1 endpoint. Conversion changes prices, ranges, chart labels, and price differences together. Percentage changes and model scores are unchanged.

All displayed dates use the same cached exchange rate. This is a convenience conversion, not a historical foreign-currency return or an FX forecast. The page shows the rate date for converted prices. Rates older than seven days, missing rates, or invalid rates disable conversion and retain USD. A failed refresh retains the last valid cache.

To refresh only exchange rates:

```sh
.venv/bin/python -m backend.fx
```

## Files and services

| Location | Purpose |
| --- | --- |
| `backend/run.py` | Daily data and prediction job |
| `backend/learning.py` | Adaptive forecasts and settled-outcome updates |
| `backend/app.py` | API and website server |
| `backend/fx.py` | Exchange-rate cache and validation |
| `backend/research.py` | Gemini chat, news feeds, evidence graphs, and usage limits |
| `demo/dist/` | Website source; directory retained from the first prototype |
| `data/yodax.sqlite3` | Saved forecasts, outcomes, learning state, and dashboard |
| `data/snapshots/` | Input CSVs identified by content hash |
| `data/model/` | Downloaded model weights |
| `data/research.sqlite3` | Conversations, research turns, and daily Gemini request counts |
| `.env` | Local Gemini credential; excluded from Git |

`GET /api/health` checks the API; `GET /api/dashboard` returns saved results. API documentation is at `/docs`.

Future Market uses `POST /api/research/chat`, `GET /api/research/turns/{id}`, `GET /api/research/conversations/{id}`, and `GET /api/research/status`. Research requests must come from the same localhost origin as the server. See [Future Market setup](future-market.md) for details. Daily stock jobs do not run commodity research.

Back up the database and input snapshots. Weights can be downloaded again. Local data and the Python environment are ignored by Git. A process lock prevents simultaneous prediction jobs, and failed runs preserve the last completed dashboard.

## Troubleshooting

- **Forecasts unavailable:** run the prediction job, then start the API with the command in the README.
- **Results pending:** the next session has not been scored yet. Run the job after that session closes.
- **Missing latest prices:** the provider has not supplied a complete session. Retry later; the job will not invent missing bars.
- **Port 5173 is busy:** stop the old local server or choose another port with `--port`.
- **Currency selector only allows USD:** run `python -m backend.fx` using the project environment and refresh the page.

The current application uses SQLite and binds to localhost. Public deployment will need managed storage, monitoring, backups, load testing, and a data provider licensed for redistribution. [yfinance's documentation](https://github.com/ranaroussi/yfinance) describes its personal-use data restrictions. No brokerage or order execution is included.
