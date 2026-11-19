"""Run one bake-off option end to end on one or more CEs and print its scores.

  cluster (graph_cluster.py, or an existing snapshot's own clusters) -> polyfuzz_mapping.py -> cluster_scorecard.py
  -> unseen-search score: the same right-intent measure on paid searches that are in no option's keyword list

Usage:
  python run_arm.py --snapshot 20261028_v4_connected --ces 189 --graph "--universe 20261028_v2_full_plus --mode new --resolution 2.5" --label new_ids
  python run_arm.py --snapshot 20261028_v1_full --ces 189 --label eos            # score a snapshot's clusters as they are
"""
import argparse
import os
import re
import shlex
import subprocess
import sys

import pandas as pd

import cluster_scorecard as sc
import runlib

MODEL = ".env-clusters/models/paraphrase-multilingual-MiniLM-L12-v2"
ENV = {**os.environ, "MPLCONFIGDIR": "/tmp/claude-501/mpl", "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
       "NUMBA_CACHE_DIR": "/tmp/claude-501/numba"}


def step(args):
    out = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=ENV, cwd=runlib.HERE)
    if out.returncode:
        raise SystemExit(f"{args[0]} failed:\n{out.stderr[-3000:]}")
    run_line = [l for l in out.stdout.splitlines() if l.startswith("run ")]
    return out.stdout, (re.match(r"run (\S+):", run_line[-1]).group(1) if run_line else None)


def score(mapping_run, ce, col, exclude=()):
    """Right-intent, landing and unmapped shares of paid clicks for one mapper column, optionally on unseen terms only.
    The bake-off scores every option with D0.85 (identifiers -> fuzzy -> meaning): E0.85 adds the hand-written
    Vatican / Park Guell head-term rule, which looks clusters up by their EOS names and so favours EOS's clusters."""
    a = pd.read_csv(runlib.RUNS / mapping_run / "outputs" / f"assignments_{ce}.csv", low_memory=False)
    a = a[~a["term"].isin(exclude)].copy()
    a["intent"] = a["term"].map(sc.tag)
    right, landing = sc.intent_correct(a, col)
    unmapped = 100 * a.loc[a[col].isna(), "clicks"].sum() / a["clicks"].sum()
    return right, landing, unmapped, a["clicks"].sum()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", required=True)
    p.add_argument("--ces", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--graph", default=None, help="graph_cluster.py arguments; omit to score the snapshot's own clusters")
    p.add_argument("--model", default=MODEL)
    p.add_argument("--exclude-from", default="20261028_v2_full_plus",
                   help="snapshot whose keyword list defines 'seen'; terms added by an option are excluded as well")
    p.add_argument("--exclude-top", type=int, default=400, help="top paid terms by clicks left out of the unseen score")
    p.add_argument("--mapper", default="D0.85", help="assignment column to score; D0.85 has no CE-specific rules")
    a = p.parse_args()
    snap = a.snapshot
    if a.graph:
        snap = f"20261029_arm_{a.label}"
        out, _ = step(["graph_cluster.py", "--snapshot", a.snapshot, "--out-snapshot", snap, "--ces", a.ces,
                       "--model", a.model, *shlex.split(a.graph)])
        print("\n".join(l for l in out.splitlines() if l.startswith("=== CE")))
    _, mapping = step(["polyfuzz_mapping.py", "--snapshot", snap, "--ces", a.ces, "--model", MODEL])
    _, scorecard_run = step(["cluster_scorecard.py", "--snapshot", snap, "--mapping-run", mapping, "--ces", a.ces])
    seen = pd.read_csv(runlib.SNAPSHOTS / a.exclude_from / "cluster_keywords.csv", dtype={"ce": str})
    mine = pd.read_csv(runlib.SNAPSHOTS / snap / "cluster_keywords.csv", dtype={"ce": str})
    terms = pd.read_csv(runlib.SNAPSHOTS / snap / "search_terms.csv", dtype={"ce": str})
    ledger = pd.read_csv(runlib.LEDGER)
    for ce in a.ces.split(","):
        # The same unseen set for every option: research keywords plus the top terms any option may add
        top = terms[terms["ce"] == ce].nlargest(a.exclude_top, "clicks")["term"]
        exclude = set(seen.loc[seen["ce"] == ce, "kw"]) | set(top)
        all_r, all_l, all_u, _ = score(mapping, ce, a.mapper)
        right, landing, unmapped, clicks = score(mapping, ce, a.mapper, exclude)
        n_clusters = mine.loc[mine["ce"] == ce, "cid"].nunique()
        print(f"{a.label:28s} CE {ce:>5}  clusters {n_clusters:>3}  | all paid: right {all_r:5.1f}  landing {all_l:5.1f}  unmapped {all_u:5.1f}"
              f"  | unseen ({clicks:,.0f} clicks): right {right:5.1f}  landing {landing:5.1f}  unmapped {unmapped:5.1f}"
              f"  | {a.mapper} · mapping {mapping}")


if __name__ == "__main__":
    main()
