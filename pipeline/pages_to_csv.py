"""Combine paged BigQuery MCP results (JSON files) into one CSV, de-duplicated, with a row-count check.

Usage: python pages_to_csv.py <out.csv> <expected_rows|0> <page1.json> [<page2.json> ...]
Each page file is the saved output of execute_sql_readonly / get_query_results ({"rows": [...], "schema": {...}}).
"""
import csv
import json
import sys


def main(out, expected, pages):
    header, seen, rows = None, set(), []
    for p in pages:
        d = json.load(open(p))
        names = [f["name"] for f in d["schema"]["fields"]]
        if header and names != header:
            raise SystemExit(f"schema mismatch in {p}")
        header = names
        for r in d["rows"]:
            vals = tuple(c["v"] for c in r["f"])
            if vals not in seen:
                seen.add(vals)
                rows.append(vals)
    if expected and len(rows) != expected:
        raise SystemExit(f"expected {expected} rows, got {len(rows)}")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"{len(rows)} rows from {len(pages)} pages -> {out}")


def expand(args):
    """Accept explicit files or one 'glob=<pattern>' (expanded here, optionally filtered by 'job=<jobId>')."""
    import glob
    pattern = next((a[5:] for a in args if a.startswith("glob=")), None)
    job = next((a[4:] for a in args if a.startswith("job=")), None)
    files = sorted(glob.glob(pattern)) if pattern else [a for a in args if "=" not in a]
    if job:
        files = [f for f in files if json.load(open(f)).get("jobId") == job]
    return files


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), expand(sys.argv[3:]))
