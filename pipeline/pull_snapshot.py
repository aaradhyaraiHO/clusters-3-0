"""Run a snapshot's pulls.sql with the bq CLI: each statement preceded by "-- out: <file>.csv" is written to that file.

The sandbox cannot write to ~/.config/gcloud, so bq runs against a copy of the credentials in $TMPDIR (CLOUDSDK_CONFIG).

Usage: python pull_snapshot.py --snapshot 20261030_validation_v1 [--only keyword_totals.csv]
"""
import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

import runlib


def gcloud_config():
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "gcloud"
    if not tmp.exists():
        shutil.copytree(Path.home() / ".config" / "gcloud", tmp)
    return str(tmp)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", required=True)
    p.add_argument("--only", nargs="*")
    a = p.parse_args()
    snap = runlib.SNAPSHOTS / a.snapshot
    sql = (snap / "pulls.sql").read_text()
    env = {**os.environ, "CLOUDSDK_CONFIG": gcloud_config()}
    for out, statement in re.findall(r"-- out: (\S+)[^\n]*\n(.*?;)", sql, flags=re.S):
        if a.only and out not in a.only:
            continue
        res = subprocess.run(["bq", "query", "--use_legacy_sql=false", "--format=csv", "--max_rows=10000000", "--quiet"],
                             input=statement, capture_output=True, text=True, env=env)
        if res.returncode:
            raise SystemExit(f"{out}: bq failed\n{res.stderr[-2000:] or res.stdout[-2000:]}")
        (snap / out).write_text(res.stdout)
        print(f"{out}: {res.stdout.count(chr(10)) - 1} rows")


if __name__ == "__main__":
    main()
