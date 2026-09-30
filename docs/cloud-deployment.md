# Cloud deployment

YodaX targets a free Render web service named `yodax`, Supabase Postgres and a
daily GitHub Actions job. The public address is subject to Render availability.

## Storage and migration

Local mode remains the default. Set `YODAX_STORAGE=postgres` and `DATABASE_URL`
to use cloud storage. Use Supabase's Session pooler (port 5432) for IPv4.
Connections require TLS. Credentials are read from the environment or local
ignored `.env`; they never belong in Git or frontend files.

Run `python -m backend.migrate_cloud` once against an empty destination. It copies
both local SQLite databases into a private `yodax` schema and verifies every row
before committing. Existing destination rows cause the entire migration to abort.
Local data stays unchanged. The schema is not exposed through Supabase's public
Data API. Forecast values use double precision and full-precision serialization.

The initial migration was verified on September 29, 2026: 78 forecasts, 12 adaptive
forecasts, six learning states, one dashboard and the existing research records.

## Web service

Use `render.yaml` to create the Free Python service in Frankfurt. Its web-only
dependency file excludes TimesFM and PyTorch. Configure `DATABASE_URL`,
`GEMINI_API_KEY`, `SESSION_SECRET` (at least 32 random characters) and
`PUBLIC_ORIGIN` (the actual HTTPS Render URL). The current deployment is [`https://yodax-99lp.onrender.com`](https://yodax-99lp.onrender.com). Run one worker.

Research conversations belong to signed, secure, HttpOnly browser sessions.
A visitor cannot retrieve or append to another session's conversation. Clearing
cookies loses access; this beta does not have account recovery. Migrated local
conversations have no cloud owner and are not available to public visitors.
Research has a global 40 model-call daily cap and a 10-message browser-session
cap. Anonymous session limits are not a substitute for authenticated quotas.

## Daily forecasts

Set the GitHub repository Actions secret `DATABASE_URL`. The workflow is enabled
by default; set repository variable `YODAX_CLOUD_ENABLED=false` to pause it.
It runs at 21:15, 22:15 and 23:15 UTC on weekdays, with a 06:15 UTC fallback
Tuesday through Saturday. The exchange calendar's one-hour settlement buffer
determines which close is eligible, including across daylight-saving changes.
The extra runs provide another opportunity after a delayed or failed run; completed sessions are
skipped. GitHub scheduling may be delayed. Missing credentials produce an explicit
failed check rather than silently skipping the job.

The workspace checks for newly published data every five minutes while visible
and on returning to the tab. Refresh forecasts checks immediately, preserving the
selected stock and chart range. It does not run inference or fetch intraday prices;
the daily job publishes closing prices, forecasts and evaluations together.

The installed exchange calendar checks the latest completed session and skips
already processed sessions. A database lock prevents concurrent cloud jobs.
Predictions, scores and learner state are committed together. The pinned model
revision and all six next-session forecasts are verified after each run.

Keep the cloud workflow disabled until the local automation has been retired or
explicitly separated from cloud operation. The existing local automation still
uses SQLite; it has not been changed by this deployment preparation.

Free Render services sleep after inactivity; Supabase free projects can pause
after low activity. These plans do not provide an always-on guarantee.
