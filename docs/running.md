# Run YodaX locally

Use Python 3.13 and run commands from the repository root. Explicitly select SQLite for local work, even if `.env` contains cloud credentials.

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
YODAX_STORAGE=sqlite .venv/bin/python -m backend.run
YODAX_STORAGE=sqlite .venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 5173
```

Open [localhost:5173](http://127.0.0.1:5173). The numerical job exits when finished; keep the web server running separately. The first model run downloads pinned TimesFM weights. Missing or incomplete prices can prevent a run from publishing.

If `.env` does not exist, copy `.env.example` and configure `GEMINI_API_KEY` for chat. Keep secrets out of Git. Chat is optional for viewing saved forecasts. API documentation is at `/docs`; `/api/health` checks whether the saved dashboard is available.

## Daily results and currencies

The daily job checks the exchange calendar, scores eligible outcomes and saves next-session predictions. It waits one hour after market close and will not issue a next-session prediction after that session opens. Repeated runs preserve issued values. The browser refreshes published data; it does not run the model.

USD, INR, EUR, GBP, JPY and CAD are display options. The underlying model remains in USD. Dated cached rates apply to all displayed prices and do not represent historical foreign-currency returns. Refresh rates separately with:

```sh
YODAX_STORAGE=sqlite .venv/bin/python -m backend.fx
```

A failed rate fetch retains the last valid cache. Missing, invalid or more than seven-day-old rates disable conversion.

## Local files

| Location | Contents |
| --- | --- |
| `data/yodax.sqlite3` | Dashboard, forecasts, outcomes and model state |
| `data/research.sqlite3` | Conversations and research usage |
| `data/snapshots/` | Hashed price inputs |
| `data/model/` | Downloaded TimesFM weights |
| `demo/dist/` | Served website assets |

Back up local databases and source snapshots. They are ignored by Git. Cloning this repository does not install the original developer's local automation. The deployed application instead uses [GitHub Actions](cloud-deployment.md).

For training, use the separate [research setup](research-pipeline.md). For candidate inference, use the [evaluation worker](shadow-deployment.md).

If the dashboard is unavailable, inspect the numerical job result first. If a chat prediction is queued, inspect its worker rather than repeatedly refreshing the browser. If port 5173 is busy, stop the existing server or select another port.
