"""Build one CE's pipeline snapshot and map its searches to its clusters, the way Milford's were made.

  <clusters_3_0>/.env-clusters/venv/bin/python map_ce.py <clusters_3_0> 325 [--snapshot-only] [--name <snapshot>]

The snapshot is the 30 Oct validation snapshot (11-CE hybrid clusters, Google Ads and Search Console rows) filtered to
the CE, plus the two term lists the mapper reads. The mapper then runs three times, on search-term pairs, Search
Console queries and ad keywords, and the run ids are written to ces.json for export_hybrid.py.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
LOCAL = HERE / "pipeline_local"
SOURCE = "20261030_validation_v1"
COPIED = ["ad_groups", "campaigns", "ce_names", "cluster_keywords", "gsc_terms", "keyword_terms", "keyword_totals",
          "pair_terms", "search_term_pairs"]
RUNS = {"pairs": "pair_terms.csv", "organic": "gsc_terms.csv", "keywords": "ad_keywords.csv"}


def build_snapshot(root, ce, name, source=None, source_ce=None):
    """source: a snapshot folder holding the CE (snapshot_ce.py writes one for a CE outside the 30 Oct snapshot);
    source_ce: the CE's id in that folder when the tool keys it by a stand-in number."""
    src, dst = source or root / "snapshots" / SOURCE, LOCAL / "snapshots" / name
    dst.mkdir(parents=True, exist_ok=True)
    rows = {}
    for f in COPIED:
        d = pd.read_csv(src / f"{f}.csv", dtype={"ce": str}, low_memory=False)
        rows[f] = d[d["ce"] == (source_ce or ce)].assign(ce=ce)
        rows[f].to_csv(dst / f"{f}.csv", index=False)
    rows["pair_terms"][["ce", "term", "clicks", "spend", "conv", "impr"]].to_csv(dst / "search_terms.csv", index=False)
    # The mapper only matches ad keywords by text; spend and conversions stay 0 here, as in Milford's first snapshot.
    rows["keyword_terms"].assign(spend=0, conv=0)[["ce", "term", "clicks", "spend", "conv", "impr"]].to_csv(dst / "ad_keywords.csv", index=False)
    (dst / "manifest.json").write_text(json.dumps({"snapshot": name, "derived_from": [f"{src.name} (clusters, Google Ads, Search Console)"],
                                                    "ces": ce}, indent=1))
    print(f"snapshot {name}: " + ", ".join(f"{k} {len(v)}" for k, v in rows.items()))
    return dst


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("ce")
    p.add_argument("--snapshot-only", action="store_true")
    p.add_argument("--name")
    a = p.parse_args()
    root = Path(a.root).resolve()
    reg = json.loads((HERE / "ces.json").read_text())
    cfg = reg["ces"][a.ce]
    name = a.name or f"{SOURCE.split('_')[0]}_{cfg['slug']}_full"
    build_snapshot(root, a.ce, name)
    if a.snapshot_only:
        return
    model = root / ".env-clusters" / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
    runs = {}
    for kind, terms in RUNS.items():
        before = set((LOCAL / "runs").glob("*")) if (LOCAL / "runs").exists() else set()
        subprocess.run([sys.executable, str(HERE / "run_pipeline_local.py"), str(root), "polyfuzz_mapping.py", "--snapshot", name,
                        "--ces", a.ce, "--terms", terms, "--model", str(model)], check=True)
        new = sorted(set((LOCAL / "runs").glob("*")) - before)
        runs[kind] = new[-1].name
        print(f"{kind}: {runs[kind]}")
    # Re-read the registry before writing: the mapper runs take minutes and the file may have been edited meanwhile.
    reg = json.loads((HERE / "ces.json").read_text())
    reg["ces"][a.ce]["snapshot"], reg["ces"][a.ce]["runs"] = name, runs
    (HERE / "ces.json").write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
