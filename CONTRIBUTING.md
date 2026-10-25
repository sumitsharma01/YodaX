# Contributing to YodaX

Start with the [system design](docs/system-design.md) and [data pipeline](docs/data-pipeline.md). Small, well-explained changes are welcome, especially around data quality, evaluation and reliability.

## Working on a change

Create a branch from current `main`, for example `codex/fix-forecast-status`. Keep credentials, databases, downloaded datasets and environments out of Git. Use `YODAX_STORAGE=sqlite` for local checks so a configured cloud URL cannot redirect them to production.

Describe the problem, the behavior you changed and the checks you ran. Include limitations where they affect users. Preserve original issued forecasts and dated study evidence. When a guide becomes historical, label it and move it to the archive rather than leaving it as current instructions.

Run relevant tests with the appropriate installed environment:

```sh
YODAX_STORAGE=sqlite .venv/bin/python -m unittest discover -s tests
YODAX_STORAGE=sqlite .venv-research/bin/python -m unittest discover -s research_pipeline/tests
```

Research dependencies are separate; see [setup](docs/research-pipeline.md). Tests using mocks check software behavior, not real-world forecast quality. Never present synthetic fixtures as model results.

## Versioning

`VERSION` identifies the application release. An annotated Git tag such as `v0.3.0-beta.1` points to its exact commit. Update the changelog with user-visible changes and limitations. Beta tags identify experimental releases; they do not mean a model passed production acceptance.

Before release, review the diff, run relevant checks, update documentation and merge the reviewed branch into `main`. Tag that commit and push both `main` and the tag. Render follows the configured deployment branch; a tag alone does not deploy. Check the deployment result separately.

Model versions are independent of app versions. Use a new candidate ID and artifact directory for changed fitted models. Commit the pipeline, manifest and evaluation evidence together. Never overwrite an old candidate or rewrite its predictions to improve its score. Explicit activation is separate from training.

## Research changes

Document the target, availability assumptions, coverage gaps, split dates and baseline. Fit preprocessing only on training data. Compare models on matching rows and account for dependent observations. Explain what an event feature measures before claiming it improves forecasts. Correlation is not causation.

Do not load untrusted joblib artifacts. Do not commit or redistribute provider datasets without checking their terms. YodaX has no brokerage integration and does not place trades.
