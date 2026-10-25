# Reproduce the research

Start with [the data contract](data-pipeline.md), then open [the current multi-asset notebook](../notebooks/yodax_multi_asset_events.ipynb). The notebook uses shared pipeline code for preparation, historical baseline replay, training, evaluation and artifact checks.

The older country-link notebooks and [archived study guide](archive/research-studies-2026-10-25.md) preserve earlier experiments. They are not the default recipe for the current candidate.

## Environments

```sh
python3.13 -m venv .venv-research
.venv-research/bin/pip install -r requirements-research.lock.txt
python3.13 -m venv .venv-shadow
.venv-shadow/bin/pip install -r requirements-shadow.txt
```

The research environment supports notebooks and analysis. The shadow environment includes pinned TimesFM and the artifact-compatible sklearn stack for replay and inference. Select the research interpreter in a Jupyter-compatible editor. Artifact loading checks exact dependency versions; do not bypass a mismatch.

## Preparation, replay and training

The current recipe is `research_pipeline.broad`, configured by `config/research-broad.json`. Preparation requires a new destination directory and expects the previously collected source archive under `data/research` and reports missing inputs. A fresh clone does not include those ignored datasets. Collection code is in `research_pipeline/collect.py`; the notebook explains collection controls. Do not describe a missing local archive as a successful reproduction.

Use the following commands to inspect the interface and prepare/replay inputs:

```sh
.venv-research/bin/python -m research_pipeline.broad --help
.venv-research/bin/python -m research_pipeline.broad prepare
.venv-shadow/bin/python -m research_pipeline.broad replay
```

Replay can take substantial time because it runs pinned TimesFM on historical contexts. Training performs chronological comparisons and refits the candidate on eligible settled rows. Use a new candidate ID and output directory for a new experiment, for example:

```sh
.venv-research/bin/python -m research_pipeline.broad train   --candidate global-study-001 --output data/research-runs/global-study-001
```

Choose an unused name. Do not overwrite the released candidate. The optional `--activate-beta` flag explicitly selects a trained candidate for experimental chat; omit it during ordinary research. It does not promote the public dashboard.

Review quality, per-asset results, uncertainty and saved manifests before activation. The fitted pipeline contains preprocessing and the residual estimator. Upstream feature construction, the TimesFM revision and dependency versions remain part of the inference contract.

Published evidence lives in [the current audit](audits/2026-10-25-broad/report.json) and [beta report](global-event-beta.md). Raw downloads and regenerated datasets stay out of Git. Synthetic verification checks software only and cannot substitute for those results.
