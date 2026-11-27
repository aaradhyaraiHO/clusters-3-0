"""Turn EOS clusters-prompt outputs (Harsha's prompt, prompts/eos/clusters.md, synced from the prompts doc by sync_prompts.py) into the pipeline's files.

The prompt returns clusters only (rank, level, name, type, identifiers, primary keyword). EOS then assigns keywords with
a regex: in rank order, a cluster claims every unclaimed keyword that contains one of its identifiers as whole words.
This script reproduces that pass ("EOS-style"), so the list EOS would ship can be scored, and writes a one-line
definition per cluster for Jev ("our way" assigns keywords and searches with Jev instead).
Writes into --out-snapshot:
  cluster_keywords.csv       ce, cid, rank, t, name, ids, kw, vol: the EOS-style assignment; unclaimed keywords are "Others"
  cluster_descriptions.csv   ce, name, description
Files other than these two are copied from --base.
Usage: python harsha_to_clusters.py --prompt-snapshot 20261119_harsha_clusters --base 20261104_validation_v23
       --out-snapshot 20261119_validation_harsha --ces 189,325,...
"""
import argparse
import json
import re
import shutil
import unicodedata
import uuid

import pandas as pd

import runlib

LEVEL = {1: "a named place, operator, route or combo", 2: "a specific product format", 3: "general booking or the bare name",
         4: "planning and logistics", 5: "background information"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    return " ".join(re.sub(r"[\W_]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).split())


def claims(identifier, keyword):
    i = norm(identifier)
    return bool(i) and f" {i} " in f" {keyword} "


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompt-snapshot", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--out-snapshot", required=True)
    p.add_argument("--ces", required=True)
    a = p.parse_args()
    src, base, dst = (runlib.SNAPSHOTS / x for x in (a.prompt_snapshot, a.base, a.out_snapshot))
    dst.mkdir(exist_ok=True)
    for f in base.iterdir() if base != dst else []:
        if f.is_file() and f.name not in ("cluster_keywords.csv", "cluster_descriptions.csv", "manifest.json"):
            shutil.copy(f, dst / f.name)
    rows, desc = [], []
    for ce in a.ces.split(","):
        out = json.loads((src / "outputs" / f"{ce}.json").read_text())["keywordsClusters"]
        pack = json.loads((src / "inputs" / f"{ce}.json").read_text())
        # "no data" clusters (an empty playbook topic, primaryKeyword null) hold no keyword and are left out
        empty = [c["name"] for c in out if not c.get("primaryKeyword")]
        out = sorted([c for c in out if c.get("primaryKeyword")], key=lambda c: c["rank"])
        # The prompt excludes any keyword containing a negative keyword (its step 4); the regex pass must too, or a
        # competitor search ("viator grand canyon") is claimed by the cluster whose identifier it contains.
        neg = [norm(n) for n in pack.get("negativeKeywords") or [] if norm(n)]
        unclaimed = {norm(k["keyword"]): (k["keyword"], k["searchVolume"]) for k in pack["keywordData"]
                     if not any(claims(n, norm(k["keyword"])) for n in neg)}
        for c in out:
            cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ce}|harsha|{c['name']}"))
            ids = c.get("identifiers") or [c.get("primaryIdentifier", "")]
            got = [k for k in unclaimed if any(claims(i, k) for i in ids)]
            fkw = norm((c.get("primaryKeyword") or {}).get("keyword", ""))
            if fkw in unclaimed and fkw not in got:
                got.append(fkw)
            for k in got:
                kw, vol = unclaimed.pop(k)
                rows.append({"ce": ce, "cid": cid, "rank": c["rank"], "t": c["clusterType"], "name": c["name"],
                             "ids": json.dumps(ids, ensure_ascii=False), "kw": kw, "vol": vol})
            if not got:
                pk = c.get("primaryKeyword") or {}
                rows.append({"ce": ce, "cid": cid, "rank": c["rank"], "t": c["clusterType"], "name": c["name"],
                             "ids": json.dumps(ids, ensure_ascii=False), "kw": pk.get("keyword", c["name"]), "vol": pk.get("searchVolume", 0)})
            what = LEVEL.get(c.get("level"), "")
            # The patched prompt writes its own definition; the original prompt has none, so one is built from its fields
            desc.append({"ce": ce, "name": c["name"], "description": c.get("definition") or
                         f"{c['clusterType'].title()} intent about {what}: searches containing {', '.join(repr(i) for i in ids)}"
                         f" in the sense of '{c['name']}', e.g. '{(c.get('primaryKeyword') or {}).get('keyword', '')}'."})
        oid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ce}|harsha|Others"))
        rows += [{"ce": ce, "cid": oid, "rank": None, "t": "OTHER", "name": "Others", "ids": "[]", "kw": kw, "vol": vol}
                 for kw, vol in unclaimed.values()]
        print(f"CE {ce}: {len(out)} clusters (+{len(empty)} empty), {len(unclaimed)} of {len(pack['keywordData'])} keywords unclaimed by the regex")
    pd.DataFrame(rows).to_csv(dst / "cluster_keywords.csv", index=False)
    pd.DataFrame(desc).to_csv(dst / "cluster_descriptions.csv", index=False)
    (dst / "manifest.json").write_text(json.dumps({"snapshot": a.out_snapshot, "derived_from": a.base,
                                                   "how": f"Harsha's EOS clusters prompt (18 Nov) on {a.ces}, EOS-style regex assignment"}, indent=2))


if __name__ == "__main__":
    main()
