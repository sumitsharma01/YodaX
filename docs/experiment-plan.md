# From shadow experiment to a public model

**Plan recorded October 25, 2026.** YodaX is already public. This plan concerns replacing its forecast model, not launching the website. The current country-linked candidate remains private and frozen.

## What we are trying to establish

Does adding global-event information improve five-session closing-return predictions for AAPL and FCX beyond TimesFM and a market-only adjustment?

The experiment unit is a stock and forecast cutoff. Each comparison must use the same stock, cutoff, target and information availability. A prediction is issued before the next session opens, then scored against the close five exchange sessions after its cutoff. We will not count a daily price movement as the outcome of a five-session forecast.

The initial scope is two stocks. This experiment cannot approve a model for 20 stocks, physical commodity demand, commodity spot prices or forex.

## Fixed comparison rules

Primary metric: mean absolute error of the predicted five-session return, expressed in percentage points. Report each stock and the equal-weight average across matched dates. Lower is better.

Compare no-change, TimesFM, market-only residual adjustment and country-linked event adjustment. Historical analysis also includes the global-event-only adjustment to isolate the contribution of country links. No-change is derived from saved prices; it does not require a fitted model. The private page currently displays three saved model variants; the four-way promotion report must include the no-change baseline too.

Secondary metrics: RMSE and direction accuracy. Report coverage, skips and failures alongside performance so a model cannot appear better merely by skipping difficult dates. Use a common eligible subset for matched comparisons, and show excluded observations separately. Do not tune against a single aggregate accuracy percentage.

Chronological evaluation must purge training labels whose target reaches the test period. Fit imputation and preprocessing on the training fold only. Use event archives and exposure disclosures only after their recorded availability dates. No random train/test split.

The historical periods already examined are development evidence. July 2026 onward is not a pristine holdout. These rules are recorded before the new prospective outcomes settle, but are not a claim that the earlier historical experiments were preregistered.

## Delivery schedule

| Date | Work | Evidence required to finish |
|---|---|---|
| Sun Oct 25 | Record this protocol; audit existing coverage, split boundaries and artifact integrity | Reproducible audit, measured findings, and explicit unresolved issues |
| Mon Oct 26 | Review 50 sampled event/company links across both stocks, dates and event categories; verify source context and update ageing disclosures | Review labels (relevant / indirect / unrelated / unverifiable), reasons, sources and dated exposure changes |
| Tue Oct 27 | Re-run matched walk-forward comparisons if the audit warrants changes; retain the previous candidate as control | Saved predictions, input/config hashes, per-stock metrics and versioned artifacts |
| Wed Oct 28 | Inspect uncertainty, outliers and performance by volatility/event category | Comparison report separating exploratory slices from primary tests; no causal claims from predictive lift |
| Thu Oct 29 | Exercise stale/missing inputs, repeated jobs, failures and rollback | Operational checklist with observed results; alert and recovery ownership |
| Fri Oct 30 | Verify the first live outcomes against their original saved predictions | Reconciled prospective report; no promotion based on the first two stock outcomes |
| Weekly afterwards | Review data quality, job reliability, coverage and accumulating outcomes | Dated review notes and an explicit continue / investigate / stop decision |
| Early December | Review progress and decide whether more evidence or a new candidate is needed | A checkpoint, not a guaranteed launch or sufficient-sample claim |

Only the existing daily worker is scheduled. The research milestones above are planned work, not background automations. We should update their status from completed artifacts, not mark them done because the date has passed.

## Promotion gates

These are conservative decision rules for this pilot, not a guarantee of profitability or proof of causation.

1. **Data and chronology:** no unresolved duplicate keys, invalid target prices or detected look-ahead. Missing source dates must be documented and excluded or cause an explicit skip. Required exposure snapshots must be current.
2. **Enough prospective evidence:** at least 60 matched cutoff dates for each stock. With 20-session moving blocks, this is the existing bootstrap implementation's minimum, not 60 independent observations. Six weeks is insufficient for this gate; early December is a progress review. Reaching the minimum does not force promotion.
3. **Incremental value:** the candidate's MAE must be lower than TimesFM, market-only and no-change on the matched prospective sample. Require positive lower bounds for the 95% paired date-block bootstrap intervals versus TimesFM and market-only, with both stocks kept together within date blocks. Treat these as two required comparisons and make no broad statistical claim across exploratory slices.
4. **Consistency and tails:** each stock must improve versus TimesFM and market-only individually; aggregate RMSE must not worsen against either. Inspect extreme errors and whether a few dates explain the result. Report 10-, 20- and 30-session block sensitivity when sample length permits; disagreement means more investigation, not selecting the most flattering interval.
5. **Operational reliability:** at least 95% of eligible scheduled issuance sessions in the assessment window must have the complete three-model set before the deadline, with no unresolved freshness, scoring or access-control incidents. Count issuance sessions, not recovery-job attempts.
6. **Reproducibility and rollback:** record exact code, data provenance, artifact versions and dependencies. Durable input snapshot retention remains a prerequisite for a fully replayable production release; hashes alone cannot recreate ephemeral worker files. Test a return to the previous public model before promotion.
7. **Explicit review:** a human approves the evidence and scope. No automatic retraining, promotion or replacement of the public model.

The numerical gates are fixed for this assessment. Any change requires a dated protocol amendment and a clear account of which results had already been seen. A changed model or exposure registry gets a separate candidate version; do not merge its performance with the current candidate.

## What happens each day

The worker fetches prices and event inputs, checks eligibility, saves immutable forecasts and scores matured outcomes. It records failures and skips. We investigate exceptions; we do not manually repeat the entire research workflow or retrain after each error.

## Status

- Completed Oct 25: protocol and snapshot/split audit. See [readiness findings](audits/2026-10-25/readiness.md) and [machine-readable evidence](audits/2026-10-25/readiness.json).
- Pending: manual relevance review, updated disclosures, additional comparison analysis, operational release review and sufficient prospective evidence.
- Decision: continue private shadow collection. Public promotion is not approved.
