# Clusters 3.0 pipelines

Prototypes behind the Clusters 3.0 scoping doc (https://claude.ai/artifact/GM93qeHueg28GEcraHidPz).
Every run is kept: `results.csv` is the before/after record.

## Layout

| Path | What | In git |
|---|---|---|
| `sql/` | Query templates for each input pull | yes |
| `sql/walkthrough_6ces/` | Queries from the 6-CE Google Ads walkthrough (28 Oct) | yes |
| `snapshots/<id>/` | Frozen inputs: the SQL used, `manifest.json` (window, CEs, row and click counts, limits), CSVs | manifest + SQL only |
| `runs/<run_id>/` | `config.json` (pipeline, snapshot, parameters, code commit), `metrics.json`, `outputs/` | config + metrics only |
| `results.csv` | Ledger: one row per run × CE × method × metric. Appended, never edited | yes |
| `reference/` | Hand-judged answer keys (LLM step for Vatican) | yes |
| `.env-clusters/` | Python 3.12 venv + multilingual model (`setup_env.sh` rebuilds it) | no |

CSV data and outputs stay local. **Before removing this worktree, copy `snapshots/` and `runs/` to `~/analytics/.cache/clusters_3_0/`.**

## Pipelines (run in this order)

```bash
PY=.env-clusters/venv/bin/python
MODEL=.env-clusters/models/paraphrase-multilingual-MiniLM-L12-v2
SNAP=20261028_v0_top3000

$PY polyfuzz_mapping.py   --snapshot $SNAP --model $MODEL                       # 1. search term -> cluster (methods A-D)
$PY cluster_scorecard.py  --snapshot $SNAP --mapping-run <mapping run_id> --ces 325   # 2. quality rubric vs paid intent
$PY bertopic_discovery.py --snapshot $SNAP --mapping-run <mapping run_id> --model $MODEL --ces 189  # 3. new-cluster discovery
$PY llm_assign_prompt.py  --snapshot $SNAP --discovery-run <discovery run_id> --ces 189 [--answer x.json --answer-label name]  # 4. LLM step
```

Set `MPLCONFIGDIR`, `HF_HUB_OFFLINE=1` and `NUMBA_CACHE_DIR` to writable temp folders when running sandboxed.

## Snapshots

New pulls go through the BigQuery MCP (the `bq` CLI needs `gcloud auth login`). Fill the templates in `sql/`,
save results as `search_terms.csv` / `cluster_keywords.csv` in a new `snapshots/<YYYYMMDD>_<label>/`, copy the filled
SQL alongside, then run `python make_manifest.py <id> '<json>'`.

| Snapshot | Window | Scope | Limits |
|---|---|---|---|
| `20261028_v0_top3000` | 30 Jul – 27 Oct 2026 | Vatican (189), Park Güell (325) | Top 3,000 terms by clicks: 85% of Vatican clicks, 96% of Park Güell |
