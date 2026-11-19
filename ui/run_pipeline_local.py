"""Run a clusters_3_0 pipeline script with its snapshots, runs and ledger in pipeline_local/ next to this file.

The pipeline lives in the clusters-3-0 worktree; this keeps the mockup's own runs (e.g. Milford's mapping) out of it.
  <clusters_3_0>/.env-clusters/venv/bin/python run_pipeline_local.py <clusters_3_0> polyfuzz_mapping.py --snapshot ... --ces ...
"""
import runpy
import sys
from pathlib import Path

ROOT, SCRIPT, rest = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3:]
LOCAL = Path(__file__).resolve().parent / "pipeline_local"
sys.path.insert(0, str(ROOT))
import runlib  # noqa: E402

runlib.SNAPSHOTS, runlib.RUNS, runlib.LEDGER = LOCAL / "snapshots", LOCAL / "runs", LOCAL / "results.csv"
sys.argv = [str(ROOT / SCRIPT), *rest]
# polyfuzz_mapping.py embeds the terms the rules left unmapped; when every term is already mapped (a CE with a dozen
# Search Console queries, like Great Barrier Reef) it multiplies an empty matrix and stops. Until the pipeline guards
# it, run its source with that one call skipped when there is nothing left to embed.
EMPTY_CALL = 'em = embed_match(rest, kw[kw["ce"] == ce], cc, EMBED_MODEL).rename(columns={"tn": "term"})'
src = (ROOT / SCRIPT).read_text()
if SCRIPT == "polyfuzz_mapping.py" and EMPTY_CALL in src:
    src = src.replace(EMPTY_CALL, EMPTY_CALL.replace("em = ", "em = (") +
                      ' if len(rest) else pd.DataFrame(columns=["term", "e_match", "e_score", "E_raw"]))')
    exec(compile(src, str(ROOT / SCRIPT), "exec"), {"__name__": "__main__", "__file__": str(ROOT / SCRIPT)})
else:
    runpy.run_path(str(ROOT / SCRIPT), run_name="__main__")
