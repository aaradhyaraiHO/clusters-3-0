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
ROOT = Path.home() / "analytics" / ".claude" / "worktrees" / "clusters-3-0" / "scripts" / "clusters_3_0"
VENV = ROOT / ".env-clusters" / "venv" / "bin" / "python"
SOURCE = ROOT / "snapshots" / "20261030_validation_v1"
# pages runs the prompts doc's page prompts on the exported clusters; relink exports again with their answers.
STEPS = ["pull", "map", "prepare", "group", "facts", "export", "pages", "relink", "build"]
NO_SITE = "www.no-microbrand.invalid"


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


def key_of(ce, reg):
    """The id the tool keys a CE by. A real CE id is a number; a placeholder ("18 - Key West", a category in a city
    before the CE is created) gets a stand-in number from 900001, kept in ces.json as eos_id -> key."""
    if ce.isdigit():
        return ce
    for k, v in reg["ces"].items():
        if v.get("eos_id") == ce:
            return k
    return str(max([900000, *[int(k) for k in reg["ces"] if int(k) >= 900000]]) + 1)


def register(ce, host, final=False):
    reg = json.loads((HERE / "ces.json").read_text())
    key = key_of(ce, reg)
    if key in reg["ces"]:
        return key, reg["ces"][key]
    if final:
        # A CE outside the 30 Oct snapshot: its name and clusters come from the pipeline's own output.
        src = pd.read_csv(ROOT / "ce_sources.csv", dtype=str).set_index("ce")
        if ce not in src.index or not (ROOT / "snapshots" / f"ce_{ce}" / "final" / "clusters.csv").exists():
            raise SystemExit(f"CE {ce}: add it to ce_sources.csv and run run_ce_pipeline.py on it first")
        name = src.at[ce, "name"]
        clusters = pd.read_csv(ROOT / "snapshots" / f"ce_{ce}" / "final" / "clusters.csv")
        kw = pd.DataFrame({"ce": ce, "name": clusters["cluster"], "vol": clusters["volume"]})
    else:
        names = pd.read_csv(SOURCE / "ce_names.csv", dtype={"ce": str}).set_index("ce")
        if ce not in names.index:
            raise SystemExit(f"CE {ce} has no clusters in the 11-CE hybrid run ({SOURCE.name}); run it with --final")
        name = names.at[ce, "name"]
        kw = pd.read_csv(SOURCE / "cluster_keywords.csv", dtype={"ce": str}, usecols=["ce", "name", "vol"])
    host = host or (site_of(ce) if ce.isdigit() else None)
    if not host:
        if not final:
            raise SystemExit(f"No Payload home page lists collection {ce}; pass --host www.<site>")
        # No microbrand yet: page pulls match nothing, and the CE shows as one with no pages.
        host = NO_SITE
    host = host if host.startswith("www.") else "www." + host
    # The CE's own words: its name without the product words ("Great Barrier Reef Cruises" -> great barrier reef).
    generic = {"tickets", "ticket", "tours", "tour", "cruises", "cruise", "the", "and", "of"}
    core = [w for w in re.split(r"[^a-z0-9]+", fold(name)) if w and w not in generic]
    slug = "".join(core)[:24] or f"ce{ce}"
    # Only the name's own words: a city can be a cluster of its own ("From Cairns").
    words = sorted({w for w in core if len(w) > 2})
    by_vol = kw[kw["ce"] == ce].groupby("name")["vol"].max().sort_values(ascending=False)
    # Head cluster: "... Head Term" where the clustering named one, else the cluster named after the CE itself,
    # else the largest cluster whose name is only CE words.
    head = (next((c for c in by_vol.index if "head term" in c.lower()), None)
            or next((c for c in by_vol.index if [w for w in re.split(r"[^a-z0-9]+", fold(c)) if w] == core), None)
            or next((c for c in by_vol.index if set(re.split(r"[^a-z0-9]+", fold(c))) - {""} <= set(core)), None))
    cfg = {"slug": slug, "name": name, "host": host, "out": f"hybrid_{slug}", "data": f"{slug}.json",
           "page": f"{slug}-clusters.html", "title": f"{name} Clusters", "name_words": words}
    if key != ce:
        cfg["eos_id"] = ce
    if head and "head term" not in head.lower():
        cfg["head"] = head
    reg["ces"][key] = cfg
    (HERE / "ces.json").write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    print(f"registered CE {ce}{f' as {key}' if key != ce else ''}: {name} · {host} · head cluster {head or 'not found: set it in ces.json'}")
    return key, cfg


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ce")
    p.add_argument("--from", dest="start", choices=STEPS, default="pull")
    p.add_argument("--host")
    p.add_argument("--final", nargs="?", const="original", choices=["original", "patched"],
                   help="build from the pipeline's final/ output instead of the 11-CE mapping run")
    a = p.parse_args()
    key, cfg = register(a.ce, a.host, final=bool(a.final))
    (HERE / cfg["out"]).mkdir(exist_ok=True)
    py, venv, root = sys.executable, str(VENV), str(ROOT)
    commands = {
        "pull": [py, "pull_ce.py", key],
        "map": [py, "final_ce.py", root, key, "--prompt", a.final] if a.final else [venv, "map_ce.py", root, key],
        "prepare": [venv, "prepare_ce.py", root, key],
        "group": [venv, "group_unclustered.py", root, key],
        "facts": [py, "facts_ce.py", key],
        "export": [venv, "export_hybrid.py", root, key],
        "pages": [venv, "page_decisions.py", root, key],
        "relink": [venv, "export_hybrid.py", root, key],
        "build": [py, "build.py", cfg["slug"]],
    }
    for step in STEPS[STEPS.index(a.start):]:
        if step == "facts" and (HERE / cfg["out"] / "page_facts.json").exists():
            print("facts: kept the existing page_facts.json")
            continue
        print(f"== {step}: {' '.join(Path(x).name if i == 0 else x for i, x in enumerate(commands[step]))}", flush=True)
        if subprocess.run(commands[step], cwd=HERE).returncode:
            if step == "pages":
                # The page still builds without the prompts' answers; the tool then falls back to its own rules.
                print("pages: the page prompts failed; building on the tool's own rules. Rerun with --from pages.")
                continue
            raise SystemExit(f"stopped at {step}; fix it and rerun with --from {step}")
    print(f"done: {cfg['page']}")


if __name__ == "__main__":
    main()
