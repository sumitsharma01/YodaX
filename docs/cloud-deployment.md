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
`PUBLIC_ORIGIN` (the actual HTTPS Render URL). Run one worker.

Research conversations belong to signed, secure, HttpOnly browser sessions.
A visitor cannot retrieve or append to another session's conversation. Clearing
cookies loses access; this beta does not have account recovery. Migrated local
conversations have no cloud owner and are not available to public visitors.
Research has a global 40 model-call daily cap and a 10-message browser-session
cap. Anonymous session limits are not a substitute for authenticated quotas.

## Daily forecasts

Set the GitHub repository secret `DATABASE_URL`. After validating deployment,
set repository variable `YODAX_CLOUD_ENABLED=true` to enable the workflow.
It runs at 22:15 UTC on weekdays, after the US close in both daylight-saving and
standard time. GitHub scheduling may be delayed.

The installed exchange calendar checks the latest completed session and skips
already processed sessions. A database lock prevents concurrent cloud jobs.
Predictions, scores and learner state are committed together. The pinned model
revision and all six next-session forecasts are verified after each run.

Keep the cloud workflow disabled until the local automation has been retired or
explicitly separated from cloud operation. The existing local automation still
uses SQLite; it has not been changed by this deployment preparation.

Free Render services sleep after inactivity; Supabase free projects can pause
after low activity. These plans do not provide an always-on guarantee.
