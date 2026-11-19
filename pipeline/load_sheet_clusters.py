"""Turn Krupa's KWR Testing sheet exports (EOS and the prototype Cluster Tool, side by side) into bake-off snapshots.

  <out>                     = <base> snapshot + EOS clusters from the sheets for CEs the EOS database has no research for
  <out>_clustertool         = <base> snapshot with the Cluster Tool's clusters for every CE in the sheets

The exports are local copies of the sheet tabs (.env-clusters/krupa_docs/kwr__*_clusters.tsv); each tab holds the two
tools in either column order, with a tool-name row and a header row on top. EOS rows carry the cluster heading
("Name (Intent)") only on a cluster's first row.

Usage: python load_sheet_clusters.py --base 20261029_bakeoff_v0 --out 20261029_bakeoff_v1
"""
import argparse
import csv
import json
import shutil
import uuid
from pathlib import Path

import pandas as pd

import runlib

SHEETS = Path(__file__).parent / ".env-clusters" / "krupa_docs"
CE_OF_TAB = {"eiffel_tower": "243", "moulin_rouge": "257", "seine_river_cruises": "261", "harry_potter_walking_tour": "2010",
             "montserrat_monastery": "3176", "sydney_whale_watching": "1695", "cappadocia_hot_air_balloon": "2640"}
INTENTS = {"transactional": "TRANSACTIONAL", "planning": "PLANNING", "informational": "INFORMATIONAL"}


def num(s):
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def parse(path, ce):
    rows = list(csv.reader(path.open(encoding="utf-8"), delimiter="\t"))
    tools, header = rows[0], rows[1]
    start = {name: i for i, name in enumerate(tools) if name in ("EOS", "Cluster Tool")}
    eos, tool = [], []
    e0, t0 = start["EOS"], start["Cluster Tool"]
    heading, ids = None, {}
    for r in rows[2:]:
        r = r + [""] * (len(header) - len(r))
        if r[e0].strip():
            heading = r[e0].strip()
        if heading and (r[e0 + 1].strip() or r[e0 + 2].strip()):
            ids.setdefault(heading, [])
            if r[e0 + 1].strip():
                ids[heading].append(r[e0 + 1].strip().lower())
            if r[e0 + 2].strip():
                eos.append((heading, r[e0 + 2].strip().lower(), num(r[e0 + 3])))
        if r[t0].strip() and r[t0 + 2].strip():
            tool.append((r[t0 + 2].strip(), r[t0].strip().lower(), num(r[t0 + 1])))
    out_e = []
    for rank_heading in dict.fromkeys(h for h, _, _ in eos):
        name, _, intent = rank_heading.rpartition("(")
        t = INTENTS.get(intent.rstrip(")").strip().lower(), "INFORMATIONAL")
        name = name.strip() or rank_heading
        cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"sheet-eos|{ce}|{rank_heading}"))
        for h, kw, vol in eos:
            if h == rank_heading:
                out_e.append({"ce": ce, "cid": cid, "rank": None, "t": t, "name": name,
                              "ids": json.dumps(ids.get(h, []), ensure_ascii=False), "kw": kw, "vol": vol})
    out_t = [{"ce": ce, "cid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"sheet-tool|{ce}|{c}")), "rank": None, "t": "INFORMATIONAL",
              "name": c, "ids": "[]", "kw": kw, "vol": vol} for c, kw, vol in tool]
    return pd.DataFrame(out_e), pd.DataFrame(out_t)


def copy_base(base, dst):
    dst.mkdir(exist_ok=True)
    for f in base.iterdir():
        if f.is_file() and f.name not in ("cluster_keywords.csv", "manifest.json"):
            shutil.copy(f, dst / f.name)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    base = runlib.SNAPSHOTS / a.base
    have = pd.read_csv(base / "cluster_keywords.csv", dtype={"ce": str})
    eos_parts, tool_parts, log = [have], [], []
    for tab, ce in CE_OF_TAB.items():
        e, t = parse(SHEETS / f"kwr__{tab}_clusters.tsv", ce)
        tool_parts.append(t)
        use_sheet = ce not in set(have["ce"])
        if use_sheet:
            eos_parts.append(e)
        log.append({"ce": ce, "tab": tab, "eos_from": "sheet" if use_sheet else "database",
                    "sheet_eos_keywords": int(e["kw"].nunique()) if len(e) else 0, "sheet_eos_clusters": int(e["cid"].nunique()) if len(e) else 0,
                    "tool_keywords": int(t["kw"].nunique()) if len(t) else 0, "tool_clusters": int(t["cid"].nunique()) if len(t) else 0})
    for name, parts in ((a.out, eos_parts), (f"{a.out}_clustertool", tool_parts)):
        dst = runlib.SNAPSHOTS / name
        copy_base(base, dst)
        pd.concat(parts).to_csv(dst / "cluster_keywords.csv", index=False)
        (dst / "manifest.json").write_text(json.dumps({"snapshot": name, "derived_from": a.base, "how": "load_sheet_clusters.py",
                                                       "source": "Krupa's KWR Testing sheet exports (local copies)", "tabs": log}, indent=2))
    print(pd.DataFrame(log).to_string(index=False))


if __name__ == "__main__":
    main()
