"""Pull every BigQuery input the cluster page needs for one CE, from sql/templates/, into the CE's folder.

  python3 pull_ce.py 325 [--only pages,page_products]

The CE's name, site and folder come from ces.json. Queries run in dependency order: the published pages give the
collections, the collections' rankings give the products, and the products give the variant, availability and order
queries their experience ids. Every file lands as <folder>/<query>_<ce>.csv, the names export_hybrid.py reads.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from window import FIXED, tokens as window_tokens, window

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "sql" / "templates"
# Collections come from the pages, products from the collections, so these run first and in this order.
STAGED = ["pages", "page_products"]
NEEDS_PRODUCTS = {"experience_variants", "variant_availability", "variant_orders"}


def gcloud_config():
    # Copied fresh every run: a copy kept from before a `gcloud auth login` holds the expired token.
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"gcloud_pull_ce_{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    # gcloud's own virtenv holds dangling symlinks; the credentials do not need it.
    shutil.copytree(Path.home() / ".config" / "gcloud", tmp, ignore=shutil.ignore_patterns("virtenv", "logs"), dirs_exist_ok=True)
    return str(tmp)


def render(name, ce, cfg, collections="", experiences=""):
    host = cfg["host"]
    site = re.sub(r"^www\.", "", host)
    sql = (TEMPLATES / f"{name}.sql").read_text()
    for token, value in {"__NAME__": cfg["name"], "__HOST__": host, "__SITE_RE__": site.replace(".", r"\."), "__SITE__": site,
                         "__COLLECTIONS__": collections, "__EXPERIENCES__": experiences, "__CE__": ce, **window_tokens()}.items():
        sql = sql.replace(token, value)
    # A CE whose pages also sit on another site (Park Güell under barcelona-tickets.com/park-guell) lists those uid
    # prefixes in ces.json page_prefixes; Payload pages are read from its own host and from each of them.
    prefixes = cfg.get("page_prefixes") or []
    if prefixes:
        sql = sql.replace(f"STARTS_WITH(uid, '{host}')",
                          "(" + " OR ".join(f"STARTS_WITH(uid, '{h}')" for h in [host, *prefixes]) + ")")
    left = re.findall(r"__[A-Z_]+__", sql)
    if left:
        raise SystemExit(f"{name}: unfilled {sorted(set(left))}")
    return sql


def run(name, sql, out, env):
    res = subprocess.run(["bq", "query", "--use_legacy_sql=false", "--format=csv", "--max_rows=10000000", "--quiet"],
                         input=sql, capture_output=True, text=True, env=env)
    if res.returncode:
        raise SystemExit(f"{name}: bq failed\n{res.stderr[-2000:] or res.stdout[-2000:]}")
    text = res.stdout
    if not text.strip():
        # bq prints nothing for 0 rows; a dry run of the same query gives the columns, so the file keeps its header.
        dry = subprocess.run(["bq", "query", "--use_legacy_sql=false", "--dry_run", "--format=json"], input=sql,
                             capture_output=True, text=True, env=env)
        text = ",".join(f["name"] for f in json.loads(dry.stdout)["statistics"]["query"]["schema"]["fields"]) + "\n"
    out.write_text(text)
    print(f"{out.name}: {max(text.count(chr(10)) - 1, 0)} rows")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ce")
    p.add_argument("--only", default="")
    a = p.parse_args()
    cfg = json.loads((HERE / "ces.json").read_text())["ces"][a.ce]
    folder = HERE / cfg["out"]
    folder.mkdir(exist_ok=True)
    # The export labels the CE's numbers with the window they were pulled on, not whatever window.py says later.
    start, end = window()
    # Search terms and keyword totals are not pulled here: they come from the 30 Oct validation snapshot (map_ce.py,
    # final_ce.py), fixed at 30 Jul - 27 Oct. Another window would mix those with the new one under the new label.
    if (start, end) != FIXED:
        raise SystemExit(f"window {start} to {end}: search terms and keyword totals still come from the fixed 30 Oct "
                         f"snapshot, so the numbers would mix windows. Re-pull them for every CE before moving the window.")
    (folder / "window.json").write_text(json.dumps({"start": start, "end": end}))
    env = {**os.environ, "CLOUDSDK_CONFIG": gcloud_config()}
    names = [t.stem for t in sorted(TEMPLATES.glob("*.sql"))]
    order = STAGED + [n for n in names if n not in STAGED]
    only = set(filter(None, a.only.split(",")))
    out = lambda n: folder / f"{n}_{a.ce}.csv"
    collections = experiences = ""
    for name in order:
        if name == "page_products" or name in NEEDS_PRODUCTS:
            if name == "page_products":
                pages = pd.read_csv(out("pages"), dtype={"collection_id": str})
                ids = {a.ce} | set(pages.loc[pages["status_en"] == "published", "collection_id"].dropna().str.split(".").str[0])
                collections = ", ".join(f"'{i}'" for i in sorted(ids))
            else:
                prods = pd.read_csv(out("page_products"), dtype={"experience_id": str})
                experiences = ",".join(sorted(prods["experience_id"].dropna().unique()))
        if only and name not in only:
            continue
        run(name, render(name, a.ce, cfg, collections, experiences), out(name), env)


if __name__ == "__main__":
    main()
