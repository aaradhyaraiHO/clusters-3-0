"""Fetch Google's top-10 organic URLs for a CE's highest-volume keyword families (SerpApi), for the SERP-overlap signal.

Two keywords that share several top-10 URLs are one page in Google's eyes; graph_cluster.py --serp uses that as a link.
Results are cached per query in .env-clusters/serp_cache/ (local, never committed), so a query is paid for once. The
API key is read from .env-clusters/serpapi.key and never printed or written anywhere else.

Usage: python serp_fetch.py --snapshot 20261029_bakeoff_v1 --ce 257 --top 120 [--gl us --hl en] [--dry-run]
Writes snapshots/<snapshot>/serp_<ce>.json: {keyword: [url, ...]} for the families fetched.
"""
import argparse
import hashlib
import http.client
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

import graph_cluster as gc
import runlib

ENV = Path(__file__).parent / ".env-clusters"
CACHE = ENV / "serp_cache"


def fetch(query, gl, hl, key):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / (hashlib.sha1(f"{query}|{gl}|{hl}".encode()).hexdigest() + ".json")
    if path.exists():
        return json.loads(path.read_text()), False
    # Only the organic links: full responses are 100-200 KB and get truncated by the sandbox proxy
    params = urllib.parse.urlencode({"engine": "google", "q": query, "gl": gl, "hl": hl, "num": 10, "api_key": key,
                                     "json_restrictor": "organic_results[].{link}"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(f"https://serpapi.com/search.json?{params}", timeout=60) as r:
                data = json.loads(r.read())
            break
        except (http.client.IncompleteRead, TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    urls = [o.get("link") for o in data.get("organic_results", [])[:10] if o.get("link")]
    path.write_text(json.dumps({"query": query, "gl": gl, "hl": hl, "urls": urls}))
    return {"urls": urls}, True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", required=True)
    p.add_argument("--ce", required=True)
    p.add_argument("--top", type=int, default=100)
    p.add_argument("--gl", default="us")
    p.add_argument("--hl", default="en")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    kw = gc.load_universe(a.snapshot, a.snapshot, a.ce, 0)
    fam = gc.build_families(kw).sort_values("vol", ascending=False)
    fam = fam[~fam["members"].map(lambda ms: any(pd.Series(ms).str.contains(gc.cluster_fix.COMPETITORS, case=False)))]
    picks = fam.head(a.top)["rep"].tolist()
    cached = sum((CACHE / (hashlib.sha1(f"{q}|{a.gl}|{a.hl}".encode()).hexdigest() + ".json")).exists() for q in picks)
    print(f"CE {a.ce}: {len(picks)} families, {cached} cached, {len(picks) - cached} to fetch")
    if a.dry_run:
        return
    key = (ENV / "serpapi.key").read_text().strip()
    out, new = {}, 0
    for q in picks:
        res, paid = fetch(q, a.gl, a.hl, key)
        out[q] = res["urls"]
        new += paid
        if paid:
            time.sleep(1)
    (runlib.SNAPSHOTS / a.snapshot / f"serp_{a.ce}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"CE {a.ce}: {len(out)} queries saved, {new} paid searches used")


if __name__ == "__main__":
    main()
