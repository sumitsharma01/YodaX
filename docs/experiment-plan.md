# What happens next

The current event model is available as an experimental chat route. The public daily dashboard has not been replaced. A release date alone is not a reason to promote a model.

## While the candidate runs

After each completed eligible session, scheduled workers collect inputs, issue new forecasts and score targets that have matured. Review failed runs, stale cutoffs, missing archives and unscored outcomes. Do not retrain every day just because another row arrived.

## Next research work

1. Accumulate prospective results without changing the frozen candidate midway.
2. Review matched errors by asset, horizon and period, including no change. Use dependent-sample uncertainty rather than counting overlapping forecasts as independent.
3. Investigate weak coverage and feature shifts. Complete the historical event backfill and improve long-term input retention before expanding claims.
4. Test a specific feature or model change as a new candidate, with training-only preprocessing and chronological evaluation.
5. Keep the existing candidate unless the new one earns selection through evidence and operational checks.

Company-specific events, sourced macro vintages and better commodity benchmarks are possible extensions. Each needs a reproducible historical availability rule and a measurable target. Free-form news summaries alone are not a training dataset.

## Before broader production use

Agree on acceptance thresholds before reviewing the next comparison: error against simple baselines, per-asset regressions, uncertainty, input freshness and recovery behavior. Add load tests, durable replay storage and monitored failure alerts. Review data licensing and explain uncertainty clearly in the product.

No automatic promotion threshold is implemented today. The current historical comparison is exploratory and no change remains the strongest pooled baseline. Five or thirty sessions may reveal operational problems, but no fixed session count proves a trading advantage.

The [earlier dated plan](archive/country-model-plan-2026-10-25.md) is retained as history. It is not a promise of an automatic launch on its old dates.
