"""Bake-off option: TypeSafe Jev places each search in one cluster (or none) as a typed Choice with probabilities.

Each cluster is one option, described by its name and its highest-volume keywords; "none" covers searches about
anything else. Modes: "all" asks Jev about every search; "tail" keeps the exact-keyword / identifier placement (mapper
column A) and asks Jev only about the rest. Output mirrors polyfuzz_mapping.py's assignments file (term, D0.85, D_name)
so eval_testset.py and capture_analysis.py can read it.

The API key is read from .env-clusters/typesafe.key and never printed. Answers are cached per (search, option set).

Usage: python jev_classify.py --snapshot 20261029_capture_v3 --ces 189 --terms-file <csv> --base-mapping <run> --mode tail
"""
import hashlib
import http.client
import json
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request

import pandas as pd

import runlib

ENV = runlib.HERE / ".env-clusters"
CACHE = ENV / "jev_cache"
URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
EXAMPLES = 6
WORKERS = 8
NONE = "none"


def options(snap, ce, ce_name, descriptions=None):
    kw = pd.read_csv(runlib.SNAPSHOTS / snap / "cluster_keywords.csv", dtype={"ce": str})
    kw = kw[(kw["ce"] == ce) & ~kw["name"].str.startswith("Other")]
    crit, names = {}, {}
    for n, (cid, g) in enumerate(kw.groupby("cid", sort=False)):
        key = f"c{n:02d}"
        ex = g.sort_values("vol", ascending=False)["kw"].drop_duplicates().head(EXAMPLES)
        name = g["name"].iloc[0]
        what = f": {descriptions[name]}" if descriptions and name in descriptions else ""
        crit[key] = f"{name}{what}. Example searches: {'; '.join(ex)}"
        names[key] = (cid, g["name"].iloc[0])
    crit[NONE] = f"About none of these: another place or attraction, or unrelated to visiting the {ce_name}"
    return crit, names


def ask(term, crit, key, ce_name, city, context="organic", fresh=False):
    # Paid searches carry the ad's place; the context joins the cache key so organic answers are never reused for them
    digest = hashlib.sha1((term + json.dumps(crit, sort_keys=True) + ("" if context == "organic" else context)).encode()).hexdigest()
    path = CACHE / f"{digest}.json"
    if path.exists() and not fresh:
        return json.loads(path.read_text())
    state = (f"A Google search that triggered Headout's ad for {ce_name} in {city} (the ad targets this place): \"{term}\""
             if context == "paid" else f"A Google search typed by a traveller ({ce_name}, {city}): \"{term}\"")
    body = {"model": MODEL, "state": state,
            "questions": {"cluster": {"type": "choice", "instructions": "Which intent does this search belong to? Searches can be in any language.",
                                      "criteria": crit}}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt * 2)
                continue
            if e.code in (401, 403):
                raise SystemExit(f"Jev API {e.code}: check the key")
            return None
        except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError, OSError):
            # The sandbox proxy occasionally drops a CONNECT; retry, then leave the search unplaced rather than abort
            if attempt == 5:
                return None
            time.sleep(2 ** attempt * 2)
    if not fresh:
        CACHE.mkdir(exist_ok=True)
        path.write_text(json.dumps(out))
    return out


def main():
    a = runlib.args("jev_classify", {"--terms-file": {"required": True, "help": "CSV with a 'term' column (and optional weight columns)"},
                                     "--base-mapping": {"default": None, "help": "mapping run whose column A (exact keyword / identifier) is kept in tail mode"},
                                     "--mode": {"choices": ["all", "tail"], "default": "tail"},
                                     "--min-prob": {"type": float, "default": 0.0, "help": "below this probability the search stays unplaced"},
                                     "--descriptions": {"default": None, "help": "CSV name,description: one-line definition per cluster"},
                                     "--context": {"choices": ["organic", "paid"], "default": "organic",
                                                   "help": "paid: the searches triggered the CE's own ads, so they carry its place"},
                                     "--fresh": {"action": "store_true", "help": "ask Jev again without reading or writing the cache (stability test)"}})
    run = runlib.Run("jev_classify", a.snapshot, {"ces": a.ces, "model": MODEL, "mode": a.mode, "examples": EXAMPLES,
                                                  "min_prob": a.min_prob, "descriptions": a.descriptions, "context": a.context, "fresh": a.fresh, "base_mapping": a.base_mapping, "terms_file": a.terms_file})
    key = (ENV / "typesafe.key").read_text().strip()
    ces_csv = pd.read_csv(runlib.SNAPSHOTS / a.snapshot / "ce_names.csv", dtype={"ce": str}).set_index("ce")
    for ce in a.ces.split(","):
        desc = None
        if a.descriptions:
            d = pd.read_csv(a.descriptions, dtype={"ce": str})
            if "ce" in d.columns:
                d = d[d["ce"] == ce]
            desc = d.set_index("name")["description"].to_dict()
        ce_name, city = ces_csv.at[ce, "name"], ces_csv.at[ce, "city"]
        # The CE's own name and city: these were hardcoded to the Vatican Museums and Rome before 3 Nov 2026
        crit, names = options(a.snapshot, ce, ce_name, desc)
        terms = pd.read_csv(a.terms_file, dtype={"ce": str})
        if "ce" in terms.columns:
            terms = terms[terms["ce"] == ce]
        terms = terms.drop_duplicates("term").reset_index(drop=True)
        base = None
        if a.mode == "tail":
            b = pd.read_csv(runlib.RUNS / a.base_mapping / "outputs" / f"assignments_{ce}.csv", low_memory=False).drop_duplicates("term").set_index("term")
            base = terms["term"].map(b["A"])
        rows, calls, tokens = [], 0, 0
        cid_name = {cid: n for cid, n in names.values()}
        todo = [t for i, t in enumerate(terms["term"]) if base is None or pd.isna(base.iloc[i])]
        with ThreadPoolExecutor(WORKERS) as pool:
            answers = dict(zip(todo, pool.map(lambda t: ask(t, crit, key, ce_name, city, a.context, a.fresh), todo)))
        for i, term in enumerate(terms["term"]):
            if base is not None and pd.notna(base.iloc[i]):
                rows.append({"term": term, "D0.85": base.iloc[i], "D_name": cid_name.get(base.iloc[i]), "how": "identifier", "prob": None})
                continue
            out = answers[term]
            calls += 1
            if out is None:
                rows.append({"term": term, "D0.85": None, "D_name": None, "how": "jev_failed", "prob": None})
                continue
            tokens += out.get("usage", {}).get("input_tokens", 0)
            ans = out["answers"]["cluster"]
            pick, prob = ans["choice"], ans["probabilities"].get(ans["choice"])
            cid, name = names.get(pick, (None, None))
            if pick == NONE or (prob is not None and prob < a.min_prob):
                cid, name = None, None
            rows.append({"term": term, "D0.85": cid, "D_name": name, "how": "jev", "prob": prob})
        # Carry the input's own columns (clicks, impressions, position) so capture_analysis.py can read this file
        out = terms.drop(columns=[c for c in ("D0.85", "D_name") if c in terms.columns]).merge(pd.DataFrame(rows), on="term", how="left")
        out["ce"] = ce
        out.to_csv(run.out / f"assignments_{ce}.csv", index=False)
        run.record(ce, f"jev {a.mode}", "api_calls", calls)
        run.record(ce, f"jev {a.mode}", "input_tokens", tokens)
        print(f"CE {ce}: {len(out)} searches, {calls} Jev calls, {tokens:,} input tokens")
    run.close()


if __name__ == "__main__":
    main()
