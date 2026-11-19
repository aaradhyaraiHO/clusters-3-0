"""One command from a CE id to its built cluster page.

  python3 run_ce.py 243                    every step, registering the CE in ces.json if it is new
  python3 run_ce.py 243 --from export      resume from a step: pull, map, prepare, group, facts, export, build
  python3 run_ce.py 243 --host www.eiffeltowertickets.com   when the site cannot be read from Payload
  python3 run_ce.py 1695 --final            clusters and placements from the pipeline's run_ce_pipeline.py output
                                           (snapshots/ce_<CE>/final/; --final patched for the patched prompt)

A new CE's name comes from the clustering snapshot, its site from its Payload home page (the "Theme" page whose
collection is the CE), and its name words (left out of page matching) from its name. The head cluster is read
from the cluster names ("... Head Term", or the cluster named like the CE); check it in ces.json before sharing.
Clusters must already exist for the CE in the 11-CE hybrid run: a CE outside it is clustered by the pipeline first.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CLUSTERS_PIPELINE_DIR", Path(__file__).resolve().parent.parent / "pipeline"))
VENV = ROOT / ".env-clusters" / "venv" / "bin" / "python"
SOURCE = ROOT / "snapshots" / "20261030_validation_v1"
STEPS = ["pull", "map", "prepare", "group", "facts", "export", "build"]


def fold(t):
    return unicodedata.normalize("NFKD", str(t).lower()).encode("ascii", "ignore").decode()


def bq_json(sql):
    from pull_ce import gcloud_config
    env = {**os.environ, "CLOUDSDK_CONFIG": gcloud_config()}
    res = subprocess.run(["bq", "query", "--use_legacy_sql=false", "--format=json", "--quiet"], input=sql,
                         capture_output=True, text=True, env=env)
    if res.returncode:
        raise SystemExit(f"bq failed\n{res.stderr[-1500:] or res.stdout[-1500:]}")
    return json.loads(res.stdout or "[]")


HOST_RE = re.compile(r"^(www\.[a-z0-9-]+\.(?:co\.[a-z]{2}|com\.[a-z]{2}|[a-z]{2,3}))(?:\.(.*))?$")


def site_of(ce):
    """The CE's microbrand host: a Payload "Theme" page that lists the CE's own collection at the root of its site
    (www.x.com or www.x.com/home). A Theme page under a path of a city site (paristickets.com/eiffel-tower) is not a
    microbrand of its own, so the CE is then left for --host."""
    rows = bq_json(f"""
        SELECT uid, COUNT(*) AS n FROM `segment-data.payload_cms.payload_pages_v2`
        WHERE JSON_VALUE(categorisation, '$.pageType') = 'Theme' AND JSON_VALUE(categorisation, '$.collectionId') = '{ce}'
        GROUP BY 1 ORDER BY n DESC""")
    roots, others = [], []
    for r in rows:
        m = HOST_RE.match(r["uid"])
        if m:
            (roots if (m.group(2) or "") in ("", "home") else others).append(m.group(1))
    if roots:
        return roots[0]
    if others:
        raise SystemExit(f"CE {ce} has no microbrand of its own; its home page sits under {others[0]}. Pass --host to use that site.")
    return None


def register(ce, host):
    reg = json.loads((HERE / "ces.json").read_text())
    if ce in reg["ces"]:
        return reg["ces"][ce]
    names = pd.read_csv(SOURCE / "ce_names.csv", dtype={"ce": str}).set_index("ce")
    if ce not in names.index:
        raise SystemExit(f"CE {ce} has no clusters in the 11-CE hybrid run ({SOURCE.name}). The pipeline session clusters it first.")
    name = names.at[ce, "name"]
    host = host or site_of(ce)
    if not host:
        raise SystemExit(f"No Payload home page lists collection {ce}; pass --host www.<site>")
    host = host if host.startswith("www.") else "www." + host
    # The CE's own words: its name without the product words ("Great Barrier Reef Cruises" -> great barrier reef).
    generic = {"tickets", "ticket", "tours", "tour", "cruises", "cruise", "the", "and", "of"}
    core = [w for w in re.split(r"[^a-z0-9]+", fold(name)) if w and w not in generic]
    slug = "".join(core)[:24] or f"ce{ce}"
    # Only the name's own words: a city can be a cluster of its own ("From Cairns").
    words = sorted({w for w in core if len(w) > 2})
    kw = pd.read_csv(SOURCE / "cluster_keywords.csv", dtype={"ce": str}, usecols=["ce", "name", "vol"])
    by_vol = kw[kw["ce"] == ce].groupby("name")["vol"].max().sort_values(ascending=False)
    # Head cluster: "... Head Term" where the clustering named one, else the cluster named after the CE itself,
    # else the largest cluster whose name is only CE words.
    head = (next((c for c in by_vol.index if "head term" in c.lower()), None)
            or next((c for c in by_vol.index if [w for w in re.split(r"[^a-z0-9]+", fold(c)) if w] == core), None)
            or next((c for c in by_vol.index if set(re.split(r"[^a-z0-9]+", fold(c))) - {""} <= set(core)), None))
    cfg = {"slug": slug, "name": name, "host": host, "out": f"hybrid_{slug}", "data": f"{slug}.json",
           "page": f"{slug}-clusters.html", "title": f"{name} Clusters", "name_words": words}
    if head and "head term" not in head.lower():
        cfg["head"] = head
    reg["ces"][ce] = cfg
    (HERE / "ces.json").write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    print(f"registered CE {ce}: {name} · {host} · head cluster {head or 'not found: set it in ces.json'}")
    return cfg


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ce")
    p.add_argument("--from", dest="start", choices=STEPS, default="pull")
    p.add_argument("--host")
    p.add_argument("--final", nargs="?", const="original", choices=["original", "patched"],
                   help="build from the pipeline's final/ output instead of the 11-CE mapping run")
    a = p.parse_args()
    cfg = register(a.ce, a.host)
    (HERE / cfg["out"]).mkdir(exist_ok=True)
    py, venv, root = sys.executable, str(VENV), str(ROOT)
    commands = {
        "pull": [py, "pull_ce.py", a.ce],
        "map": [py, "final_ce.py", root, a.ce, "--prompt", a.final] if a.final else [venv, "map_ce.py", root, a.ce],
        "prepare": [venv, "prepare_ce.py", root, a.ce],
        "group": [venv, "group_unclustered.py", root, a.ce],
        "facts": [py, "facts_ce.py", a.ce],
        "export": [venv, "export_hybrid.py", root, a.ce],
        "build": [py, "build.py", cfg["slug"]],
    }
    for step in STEPS[STEPS.index(a.start):]:
        if step == "facts" and (HERE / cfg["out"] / "page_facts.json").exists():
            print("facts: kept the existing page_facts.json")
            continue
        print(f"== {step}: {' '.join(Path(x).name if i == 0 else x for i, x in enumerate(commands[step]))}", flush=True)
        if subprocess.run(commands[step], cwd=HERE).returncode:
            raise SystemExit(f"stopped at {step}; fix it and rerun with --from {step}")
    print(f"done: {cfg['page']}")


if __name__ == "__main__":
    main()
