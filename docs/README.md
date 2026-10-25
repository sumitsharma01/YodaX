# YodaX documentation

These guides describe release **0.3.0-beta.1**, dated October 25, 2026. Start with the system design, then follow the data and agent guides.

| Guide | What it answers |
| --- | --- |
| [System design](system-design.md) | What runs where, how requests move, and why the services are separate |
| [Data pipeline](data-pipeline.md) | Where data comes from, how it is cleaned, and how it becomes model input |
| [Agent and improvement loop](agent-and-improvement.md) | How research, forecasting, scoring and retraining fit together |
| [Model reference](model.md) | Which model handles each task and how scores are calculated |
| [User workflows](workflows.md) | What each website section does |
| [Research chat](future-market.md) | Forecast requests, sources, reports and failure handling |
| [Local setup](running.md) | Environments, commands and safe local storage |
| [Cloud operations](cloud-deployment.md) | Deployments, schedules, secrets and recovery |
| [Evaluation workers](shadow-deployment.md) | Frozen candidates, prospective scoring and the private evaluation page |
| [Research reproduction](research-pipeline.md) | How to rerun collection preparation, replay and training |
| [Current beta results](global-event-beta.md) | Measured historical performance and remaining limitations |
| [Next steps](experiment-plan.md) | Evidence required before expanding or promoting the model |
| [Release process](../CONTRIBUTING.md) | Git branches, checks, tags and model version control |

## Notebooks

[Multi-asset events](../notebooks/yodax_multi_asset_events.ipynb) is the current training and evaluation notebook. [The earlier country-link study](../notebooks/yodax_research_pipeline.ipynb) and [readiness audit](../notebooks/yodax_readiness_audit.ipynb) remain historical evidence, not the default guide to the current release.

## Historical evidence

The [archive](archive/README.md) preserves the original two-company study and its dated plan. Their instructions and schedules are not current operational guidance. Machine-readable findings remain under `docs/audits/`; retain them when comparing candidate versions.
