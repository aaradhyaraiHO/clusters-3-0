# Keyword Clusters 3.0

Turns a Headout CE into a list of search intents (clusters), places every keyword, paid search and organic search into one of them, and shows growth, content and Perf what is set up, what is missing and what to launch.

The process from A to Z (goal, workflow, UI, backend, quality, blockers) is in the stakeholder doc: https://claude.ai/artifact/RqZ7j2hChgb3pfM1dcpUtn

## Layout

- `pipeline/`: the backend. One command per CE: `python run_ce_pipeline.py <CE>` runs pull → cluster → convert → place → judge → score → export and writes `snapshots/ce_<CE>/final/` (clusters, keywords, paid, organic, scorecard). Sample output: `pipeline/examples/ce_1695/final/`.
- `ui/`: the tool. `python3 run_ce.py <CE> --final [--host <site>]` builds the CE's page from the pipeline's `final/` files plus Google Ads, Payload, product and revenue pulls. `ui/site/` is the Vercel deploy (Google sign-in, headout.com only).

## Setup

```bash
cd pipeline && ./setup_env.sh          # venv in pipeline/.env-clusters/
gcloud auth login                      # BigQuery
```

Keys stay out of git, in `pipeline/.env-clusters/`: `typesafe.key` (Jev placement), `serpapi.key`. The clustering step uses `ANTHROPIC_API_KEY` if set, otherwise a signed-in `claude` CLI. The UI finds the pipeline at `../pipeline`; set `CLUSTERS_PIPELINE_DIR` to point elsewhere.

Every rule, prompt, threshold and hit rate is in the logic sheet: https://docs.google.com/spreadsheets/d/1qrOFysRv_qclHIroOEW8XFU3nHYLJTIYhEfRt5YFTto
