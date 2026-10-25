# Changelog

## 0.3.0-beta.1 · October 25, 2026

This is the first formal release tag. It documents the current application and the recent global-event chat integration; it does not imply that every feature was introduced in the documentation commit.

- Added five-session event-aware chat coverage for 21 US stocks, WTI and copper, using the frozen `global-v1-20261025` candidate.
- Connected saved forecasts and recorded inputs to research answers, evidence maps and source links.
- Kept new numerical requests separate from Gemini research, with scheduled inference and later outcome scoring.
- Published the multi-asset training notebook and historical model comparisons.
- Replaced outdated local-demo documentation with system design, ETL, agent, deployment and release guides. Preserved older study plans in an archive.

The no-change baseline still has lower pooled historical error than this candidate. Event features are correlational; free-form headlines do not directly enter numerical inference. The candidate remains experimental, and retraining/promotion are not automatic.
