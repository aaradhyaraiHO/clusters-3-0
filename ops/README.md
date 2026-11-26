# ops

Shell steps that run the pipeline and the tool build for a list of CEs, until the Airflow DAG takes them over. Each
writes its logs and status lines to `$RUNS` (default `/tmp/claude-501/runs32`), and every step that writes the tool's
`ces.json` or pages takes the `$RUNS/full.lock` directory as a lock, so parallel jobs build one at a time.

| Script | What it does |
|---|---|
| `full_ce.sh <ce>` | Full Keyword Planner pass for one CE: merges `planner_ideas_1-8.csv` (seeds) and `9+` (vendor seeds) with `research_ce.py --stage finish`, clusters it (`run_ce_pipeline.py --keywords own --runs 3`), then builds its tool page (`run_ce.py --final`, moving to the city site when the CE has no microbrand). Status in `$RUNS/full_status.txt`. |
| `build_host.sh <ce> <host> ...` | Builds a CE's tool page on a given site (`run_ce.py --final --host`). |
| `reexport.sh <key> ...` | Re-runs the tool's export and page build for `ces.json` keys, and says which clusters changed type or focus keyword. |
| `stage.sh` | Rebuilds every registered CE's page so each CE switcher lists all of them, and copies them to the deploy folder (`/tmp/claude-501/clusters-deploy`). Deploying is `vercel deploy --prod` from there, run by a person. |
| `mvn.sh <ce> <n>`, `mvw.sh <ce> <n>` | Files the newest Keyword Planner download from `~/Downloads` as the CE's `planner_ideas_<n>.csv` (`mvw` waits for it). |
| `vendors_from_csv.py <ce>` | The vendor step with the CE's internal vendors read from the tool's experiences pull instead of BigQuery. |
| `report.py` | Per-CE summary of the full passes: seeds, ideas, kept, volumes, clusters, run agreement, against the top-10 run. |

The paths inside point at the analytics worktrees (`clusters-3-0/scripts/clusters_3_0` for the pipeline,
`clusters-3-0-ui/.../parag-v1` for the tool); `ui/` and `pipeline/` here are copies of those.
