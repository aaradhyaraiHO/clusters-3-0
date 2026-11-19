"""Write a CE's page_facts.json from data, for the page-type rules in template.html.

  python3 facts_ce.py 325 [--force]

From data: CE type and category (dim_combined_entities), aliases (the head cluster's six largest keywords) and the
site's own brand. Not derivable: the CE's parts (sub-attractions A/B/C), artworks, artists, areas, origins and
operators; the live tool's mapping prompt supplies them, so here they stay empty and the page-type rules skip them.
Vatican's and Milford's facts were curated by hand and are kept unless --force.
"""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ce")
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    cfg = json.loads((HERE / "ces.json").read_text())["ces"][a.ce]
    out = HERE / cfg["out"] / "page_facts.json"
    if out.exists() and not a.force:
        raise SystemExit(f"{out} exists (curated); pass --force to replace it")
    env = {**os.environ, "CLOUDSDK_CONFIG": str(Path(os.environ.get("TMPDIR", "/tmp")) / "gcloud_pull_ce")}
    sql = ("SELECT combined_entity_category AS category, combined_entity_subcategory AS subcategory "
           "FROM `headout-analytics.analytics_reporting.dim_combined_entities` "
           f"WHERE CAST(combined_entity_id AS STRING) = '{a.ce}'")
    res = subprocess.run(["bq", "query", "--use_legacy_sql=false", "--format=json", "--quiet"], input=sql,
                         capture_output=True, text=True, env=env, check=True)
    row = json.loads(res.stdout)[0]
    kw = pd.read_csv(HERE / "pipeline_local" / "snapshots" / cfg["snapshot"] / "cluster_keywords.csv")
    head = kw[(kw["name"] == cfg.get("head")) | kw["name"].str.contains("Head Term", case=False)]
    aliases = head.sort_values("vol", ascending=False)["kw"].str.lower().drop_duplicates().head(6).tolist()
    site = re.sub(r"^www\.|\.[a-z.]+$", "", cfg["host"])
    facts = {"ce_type": "POI" if row["category"] == "POI" else "Non-POI",
             "category": "Cruise" if str(row["category"]).startswith("Cruise") else row["category"],
             "subcategory": row["subcategory"], "aliases": aliases,
             "components": [], "artworks": [], "artists": [], "areas": [], "origins": [], "operators": [],
             "own_brand": [site, site.replace("-", " ")],
             "source": "derived: CE type and category from dim_combined_entities, aliases from the head cluster's keywords; "
                       "parts, artworks, areas and operators not set"}
    out.write_text(json.dumps(facts, indent=1, ensure_ascii=False) + "\n")
    print(f"{out}: {facts['ce_type']}, {facts['category']}, {len(aliases)} aliases")


if __name__ == "__main__":
    main()
