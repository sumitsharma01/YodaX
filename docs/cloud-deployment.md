# Cloud deployment and operations

The current public site is [yodax-99lp.onrender.com](https://yodax-99lp.onrender.com). Render serves the website and API, Supabase stores results, and GitHub Actions runs numerical jobs. Free hosting can sleep or pause; it is not an always-on service guarantee.

## Web service and database

`render.yaml` describes the web service. It installs `requirements-web.txt` and runs one Uvicorn worker. TimesFM and PyTorch run in separate jobs, keeping numerical inference out of web requests.

Set `YODAX_STORAGE=postgres`, a valid `DATABASE_URL`, `PUBLIC_ORIGIN`, `SESSION_SECRET` and `GEMINI_API_KEY` in Render. Use the Supabase session-pooler connection string on port 5432 with TLS. The database URL must contain the remote host, user, database and password. Do not paste an incomplete placeholder or quote it as part of the value. Secrets belong in service settings, never Git.

The application uses a private `yodax` schema. GitHub Actions needs its own `DATABASE_URL` repository secret; changing Render settings does not update Actions. A local SQLite run also does not update the live website.

`backend.migrate_cloud` is a one-time migration for an empty destination. It verifies copied rows in a transaction and rejects an existing destination. Do not use it as a daily synchronization command. Back up data before any storage migration.

## Daily schedule

The `Daily forecasts` workflow runs at 21:15, 22:15 and 23:15 UTC on weekdays, with a 06:15 UTC catch-up Tuesday through Saturday. These are UTC times; local time changes with daylight saving. Calendar and cutoff checks decide whether a session needs processing. GitHub scheduling can be delayed.

| Job | Purpose | Disable variable |
| --- | --- | --- |
| `forecast` | Public dashboard, outcomes and chat-requested baseline predictions | `YODAX_CLOUD_ENABLED=false` |
| `shadow` | Original country-linked frozen comparison | `YODAX_SHADOW_ENABLED=false` |
| `global_events` | Broader 23-asset event candidate and request attachment | `YODAX_GLOBAL_EVENTS_ENABLED=false` |

The candidate jobs follow the forecast job and use separate environments. They can report failure while the last successful public dashboard remains available. Selected normalized global-event inputs are uploaded with 30-day retention. This is not permanent raw-source storage.

Stopping a worker does not disable its chat route. To stop accepting new requests for that candidate, also change `chat_enabled` in its configuration through a reviewed commit. Existing requests keep their pinned candidate identity.

## Deployment and verification

Render follows the configured `main` branch. A successful Git push is not proof of a successful deployment. Check the Render deploy result, `/api/health`, the dashboard cutoff and the relevant worker status after a release. The frontend periodically checks saved results while visible and on focus; Refresh does not trigger inference or retraining.

For private model evaluation, configure `SHADOW_ADMIN_TOKEN` and open `/model-evaluation.html`. Keep the token separate from chat sessions and out of source code.

## When data or chat stops updating

1. Check whether the expected market session has completed and its provider bars are available.
2. Inspect the Actions run for that session, including all candidate jobs.
3. Check database availability and the separate Render/Actions credentials.
4. Inspect recorded input gaps, model checksums or dependency mismatches before retrying a candidate.
5. For chat failures, distinguish Gemini quota/timeouts from unavailable numerical outputs. Retry research only after the underlying problem clears.

Never fix a stale date by changing timestamps or overwriting a forecast. Preserve the last valid result, record the failure and rerun the appropriate worker. See [system design](system-design.md) for request boundaries and [release guidance](../CONTRIBUTING.md) for version control.
