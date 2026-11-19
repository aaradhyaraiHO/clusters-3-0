"""Run bookkeeping for the Clusters 3.0 pipelines: snapshots in, one folder per run out, one results ledger.

Layout (all under scripts/clusters_3_0/):
  snapshots/<snapshot_id>/   frozen inputs: the SQL that made them, manifest.json (window, row counts), CSVs
  runs/<run_id>/             config.json (pipeline, snapshot, params, git commit), outputs/, metrics.json
  results.csv                ledger: one row per run x CE x method x metric. Never edited, only appended.

Nothing is overwritten: every run gets a new run_id, so "before" and "after" are two rows in results.csv.
CSV data (snapshots/*/*.csv, runs/*/outputs/) stays out of git; SQL, manifests, configs, metrics and the ledger go in.
"""
import argparse
import csv
import datetime as dt
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
SNAPSHOTS, RUNS, LEDGER = HERE / "snapshots", HERE / "runs", HERE / "results.csv"
LEDGER_COLS = ["run_id", "run_at", "pipeline", "snapshot", "ce", "method", "metric", "value", "notes"]


def git_commit():
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=HERE, capture_output=True, text=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except OSError:
        return "unknown"


class Run:
    def __init__(self, pipeline, snapshot, params, run_id=None):
        self.pipeline, self.snapshot, self.params = pipeline, snapshot, params
        self.snap = SNAPSHOTS / snapshot
        if not self.snap.exists():
            raise SystemExit(f"snapshot not found: {self.snap}")
        self.run_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.id = run_id or f"{dt.datetime.now():%Y%m%d-%H%M%S}_{pipeline}_{snapshot}"
        # Two runs started in the same second (cached Jev runs finish that fast) must not share a folder
        n = 2
        while not run_id and (RUNS / self.id).exists():
            self.id = f"{dt.datetime.now():%Y%m%d-%H%M%S}-{n}_{pipeline}_{snapshot}"
            n += 1
        self.dir = RUNS / self.id
        self.out = self.dir / "outputs"
        self.out.mkdir(parents=True, exist_ok=True)
        (self.dir / "config.json").write_text(json.dumps({
            "run_id": self.id, "run_at": self.run_at, "pipeline": pipeline, "snapshot": snapshot,
            "params": params, "code_commit": git_commit()}, indent=2))
        self.metrics = []

    def input(self, name):
        return self.snap / name

    def upstream(self, run_id, name):
        """An output of an earlier run (e.g. the mapping run a scorecard is built on)."""
        p = RUNS / run_id / "outputs" / name
        if not p.exists():
            raise SystemExit(f"upstream output not found: {p}")
        return p

    def record(self, ce, method, metric, value, notes=""):
        self.metrics.append({"run_id": self.id, "run_at": self.run_at, "pipeline": self.pipeline, "snapshot": self.snapshot,
                             "ce": ce, "method": method, "metric": metric,
                             "value": None if value is None else round(float(value), 4), "notes": notes})

    def close(self):
        (self.dir / "metrics.json").write_text(json.dumps(self.metrics, indent=2))
        new = not LEDGER.exists()
        with LEDGER.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_COLS)
            if new:
                w.writeheader()
            w.writerows(self.metrics)
        print(f"\nrun {self.id}: {len(self.metrics)} metrics -> {LEDGER.name}; outputs in runs/{self.id}/outputs/")


def args(pipeline, extra=None):
    p = argparse.ArgumentParser(description=f"Clusters 3.0 {pipeline}")
    p.add_argument("--snapshot", required=True, help="folder name under snapshots/")
    p.add_argument("--ces", default="189,325", help="comma-separated CE ids")
    for name, kw in (extra or {}).items():
        p.add_argument(name, **kw)
    return p.parse_args()
