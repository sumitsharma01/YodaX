# YodaX readiness audit — October 25, 2026

This checks the saved pilot datasets and evaluation splits. It does not train a new model or change the live candidate.

## Findings

- Feature rows: 980; settled rows: 970; complete exposure windows: 828.
- Event archive days: 641; missing dates within that interval: 18.
- All models use identical stock/date evaluation keys: True.
- Duplicate model/stock/date predictions: 0.
- Frozen shadow artifact checksums match: True.

| Stock | Price rows | Missing sessions | Duplicate dates | Invalid closes |
|---|---:|---:|---:|---:|
| AAPL | 745 | 0 | 0 | 0 |
| FCX | 745 | 0 | 0 | 0 |

## Chronological splits

| Test interval (end exclusive) | Train rows | Test rows / dates | Last training outcome | Checks |
|---|---:|---:|---|---|
| 2025-09-01 → 2026-01-01 | 244 | 160 / 80 | 2025-08-29 | PASS |
| 2026-01-01 → 2026-07-01 | 414 | 236 / 118 | 2025-12-31 | PASS |

Checks cover target-date purging, disjoint asset/date keys and settled labels. Preprocessing is fitted inside each training fold in the implementation; this report does not independently reconstruct every historical fit.

## Open issues

- The 2015 ambition is not the coverage of this event-aware pilot: event archives start in 2025.
- July 2026 onward was examined previously; it is not an untouched final test set.
- Country presence is a proxy for exposure. Event-to-company relevance and causal effects have not been validated.
- Chronological checks do not establish original source availability: event and disclosure delays are conservative assumptions.
- A fixed two-stock universe has selection bias; no conclusion about all stocks or commodities follows.
- No independent vendor reconciliation, drift clearance, profitability evaluation or calibrated prediction intervals are established.
- Historical comparison results were already inspected. New criteria are prospective, not preregistration of those results.

Missing event archive dates: 2025-06-14, 2025-06-15, 2025-06-16, 2025-06-17, 2025-06-18, 2025-06-19, 2025-06-20, 2025-06-21, 2025-06-22, 2025-06-23, 2025-06-24, 2025-06-25, 2025-06-26, 2025-06-27, 2025-06-28, 2025-06-29, 2025-06-30, 2025-07-01.

Exposure age-limit dates: AAPL: 2026-11-04; FCX: 2027-03-01.

## Decision

**Continue private shadow evaluation; do not promote.** The mechanical split checks pass, but relevance review, source freshness and prospective performance evidence remain open. There is no defensible single dataset-quality score.

The accompanying JSON contains input checksums, per-feature missingness, coverage bounds and individual checks. Reproduce with `.venv-research/bin/python -m research_pipeline.readiness_audit`.
