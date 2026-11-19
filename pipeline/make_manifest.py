"""Write snapshots/<id>/manifest.json: what was pulled, how, and row/click counts per CE.

Usage: python make_manifest.py <snapshot_id> '<json with window, ces, limits, full_population>'
"""
import collections
import csv
import json
import sys

from runlib import SNAPSHOTS


def main(snapshot, meta):
    s = SNAPSHOTS / snapshot
    files = {}
    st = list(csv.DictReader((s / "search_terms.csv").open()))
    by = collections.defaultdict(lambda: {"terms": 0, "clicks": 0, "spend": 0.0})
    for r in st:
        b = by[r["ce"]]
        b["terms"] += 1
        b["clicks"] += int(float(r["clicks"]))
        b["spend"] = round(b["spend"] + float(r["spend"]), 2)
    files["search_terms.csv"] = {"rows": len(st), "by_ce": by}
    ck = list(csv.DictReader((s / "cluster_keywords.csv").open()))
    files["cluster_keywords.csv"] = {"rows": len(ck), "by_ce": collections.Counter(r["ce"] for r in ck),
                                     "clusters_by_ce": {ce: len({r["cid"] for r in ck if r["ce"] == ce}) for ce in {r["ce"] for r in ck}}}
    manifest = {"snapshot": snapshot, **meta, "files": files}
    (s / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(json.dumps(files, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], json.loads(sys.argv[2]))
