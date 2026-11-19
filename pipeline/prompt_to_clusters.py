"""Turn prompt v2 outputs (snapshots/<snap>/outputs/<ce>.json) into the pipeline's cluster files.

Writes into the target snapshot:
  cluster_keywords.csv   one row per cluster x example keyword (ce, cid, rank, t, name, parent, ids, kw, vol); rows for
                         CEs not in the prompt run are copied from --base so the snapshot stays complete
  cluster_descriptions.csv   ce, name, description: the definitions jev_classify.py --descriptions reads
Example volumes come from the input pack's keyword families (0 for paid or organic examples).

Usage: python prompt_to_clusters.py --prompt-snapshot 20261030_prompt_v2 --base 20261030_validation_v1
       --out-snapshot 20261030_validation_v2 --ces 3945,1695,...
"""
import argparse
import json
import shutil
import uuid

import pandas as pd

import runlib


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompt-snapshot", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--out-snapshot", required=True)
    p.add_argument("--ces", required=True)
    a = p.parse_args()
    src, base, dst = runlib.SNAPSHOTS / a.prompt_snapshot, runlib.SNAPSHOTS / a.base, runlib.SNAPSHOTS / a.out_snapshot
    dst.mkdir(exist_ok=True)
    for f in base.iterdir():
        if f.is_file() and f.name not in ("cluster_keywords.csv", "cluster_descriptions.csv", "manifest.json"):
            shutil.copy(f, dst / f.name)
    ces = a.ces.split(",")
    kept = pd.read_csv(base / "cluster_keywords.csv", dtype={"ce": str})
    rows, desc = [kept[~kept["ce"].isin(ces)]], []
    for ce in ces:
        out = json.loads((src / "outputs" / f"{ce}.json").read_text())
        pack = json.loads((src / "inputs" / f"{ce}.json").read_text())
        vol = {m: f["volume"] for f in pack["keyword_families"] for m in [f["representative"], *f["members"]]}
        recs = []
        for rank, c in enumerate(out["clusters"], start=1):
            cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ce}|v2|{c['name']}"))
            for ex in c["examples"]:
                recs.append({"ce": ce, "cid": cid, "rank": None, "t": c["intent_type"], "name": c["name"], "parent": c.get("parent"),
                             "ids": "[]", "kw": ex, "vol": vol.get(ex, 0)})
            desc.append({"ce": ce, "name": c["name"], "description": c["definition"]})
        rows.append(pd.DataFrame(recs))
        print(f"CE {ce}: {len(out['clusters'])} clusters, {len(recs)} example keywords")
    pd.concat(rows, ignore_index=True).to_csv(dst / "cluster_keywords.csv", index=False)
    pd.DataFrame(desc).to_csv(dst / "cluster_descriptions.csv", index=False)
    (dst / "manifest.json").write_text(json.dumps({"snapshot": a.out_snapshot, "derived_from": a.base,
                                                   "how": f"prompt v2 cluster lists for {a.ces} from {a.prompt_snapshot}"}, indent=2))


if __name__ == "__main__":
    main()
