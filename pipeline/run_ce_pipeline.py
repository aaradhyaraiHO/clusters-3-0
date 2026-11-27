"""One automatic run per CE: keywords -> clusters -> placement -> scorecard.

Steps (each writes into snapshots/ce_<ce>/; --from <step> resumes):
  pull     EOS keywords (BigQuery clusters_3_0_eos_keywords_clean, competitors removed), the CE's paid search terms
           (Google Ads, last 90 days to the latest partition) and organic queries (Search Console: headout.com pages
           matching page_regex, plus the CE's microbrand sites). CE metadata comes from ce_sources.csv.
  cluster  Harsha's EOS clusters prompt (prompts/eos/clusters.md, synced from the prompts doc by sync_prompts.py) on the keywords: the Messages API
           (claude-opus-5-5, effort medium, 64K output, JSON only) when credentials exist, else `claude -p` with the same
           settings; --runs N keeps the run whose clusters agree most with the others.
  convert  harsha_to_clusters.py: cluster list, EOS-style keyword assignment, one definition per cluster.
  place    jev_classify.py: every keyword (no cut), paid search (--context paid, no cut) and organic query (cut 0.5)
           placed into a cluster by meaning.
  score    scorecard.json: clusters, share of keyword volume / paid clicks / organic impressions with no cluster,
           low-confidence share, and what EOS-style assignment would have left unclaimed.
Usage: python run_ce_pipeline.py 3945 [--from cluster] [--runs 3]
Needs: bq signed in (gcloud auth login), the TypeSafe key in .env-clusters/typesafe.key, and ANTHROPIC_API_KEY / `ant auth\nlogin` (or `claude` signed in for the CLI fallback).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

import runlib

STEPS = ["pull", "cluster", "convert", "place", "judge", "score", "export"]
HERE = runlib.HERE
PROMPTS = {"original": HERE / "prompts" / "eos" / "clusters.md",
           "patched": HERE / "prompts" / "eos_harsha_2026-11-18" / "clusters_patched.md"}
PROMPT = PROMPTS["original"]
PY = sys.executable
D = "headout-dev.dbt_aaradhya"


def bq(sql):
    # bq runs on a copy of the gcloud config (the sandbox cannot write the original); refresh it every run so a new
    # `gcloud auth login` is picked up instead of an expired copy
    # One copy per process: CEs run in parallel, and a shared copy is deleted under another run's feet.
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"gcloud_{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(Path.home() / ".config" / "gcloud", tmp, symlinks=True, ignore=shutil.ignore_patterns("virtenv", "logs"))
    res = subprocess.run(["bq", "query", "--use_legacy_sql=false", "--location=EU", "--project_id=headout-dev", "--format=csv",
                          "--max_rows=10000000", "--quiet"], input=sql, capture_output=True, text=True,
                         env={**os.environ, "CLOUDSDK_CONFIG": str(tmp)})
    if res.returncode or res.stdout.startswith("ERROR"):
        raise SystemExit(f"bq failed (run `gcloud auth login` if it says reauthentication):\n{(res.stderr or res.stdout)[-1500:]}")
    from io import StringIO
    return pd.read_csv(StringIO(res.stdout), dtype={"ce": str}) if res.stdout.strip() else pd.DataFrame()


def pull(ce, src, snap, keywords="eos"):
    if keywords == "own":
        # research_ce.py wrote the keyword list (seeds prompt + Keyword Planner) for a CE EOS has not researched.
        if not (snap / "eos_keywords.csv").exists():
            raise SystemExit(f"CE {ce}: run research_ce.py first, or use --keywords eos")
        kw = pd.read_csv(snap / "eos_keywords.csv", dtype={"ce": str})
    else:
        kw = eos_keywords(ce)
        kw.dropna(subset=["term"]).to_csv(snap / "eos_keywords.csv", index=False)
    pull_searches(ce, src, snap, kw)


def eos_keywords(ce):
    kw = bq(f"""SELECT ce_id AS ce, keyword AS term, MAX(volume) AS vol FROM `{D}.clusters_3_0_eos_keywords_clean`
                WHERE ce_id = '{ce}' AND NOT is_competitor GROUP BY 1, 2""")
    if kw.empty:
        old = pd.read_csv(runlib.SNAPSHOTS / "20261030_validation_v2" / "eos_keywords.csv", dtype={"ce": str})
        kw = old[old["ce"] == ce]
        if kw.empty:
            raise SystemExit(f"CE {ce} has no EOS keyword research in BigQuery: run research_ce.py, then --keywords own")
        print(f"pull: no EOS list in BigQuery for {ce}; using the keyword set from the validation snapshot")
    return kw


def pull_searches(ce, src, snap, kw):
    window = """(SELECT MAX(_PARTITIONTIME) FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`
                 WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY))"""
    paid = bq(f"""
        WITH latest AS (SELECT {window} AS t),
        campaigns AS (
            SELECT DISTINCT campaign_id FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`
            WHERE _PARTITIONTIME = (SELECT t FROM latest) AND REGEXP_EXTRACT(campaign_name, r'cid(\\d+)\\b') = '{ce}')
        SELECT '{ce}' AS ce, LOWER(stats.search_term_view_search_term) AS term, SUM(stats.metrics_impressions) AS impr,
            SUM(stats.metrics_clicks) AS clicks, ROUND(SUM(stats.metrics_cost_micros) / 1e6, 2) AS spend,
            ROUND(SUM(stats.metrics_conversions), 2) AS conv, ROUND(SUM(stats.metrics_conversions_value), 2) AS conv_value
        FROM `segment-data.google_adwords_prepaid.p_ads_SearchQueryStats_6251119615` AS stats
        INNER JOIN campaigns USING (campaign_id)
        WHERE stats._PARTITIONTIME BETWEEN TIMESTAMP_SUB((SELECT t FROM latest), INTERVAL 90 DAY) AND (SELECT t FROM latest)
              AND stats.segments_ad_network_type = 'SEARCH'
        GROUP BY 1, 2 HAVING impr >= 3 OR clicks > 0""")
    # A CE with no campaigns (or no Search Console pages) still gets the file with its columns, so later steps read 0 rows.
    if paid.empty:
        paid = pd.DataFrame(columns=["ce", "term", "impr", "clicks", "spend", "conv", "conv_value"])
    paid.to_csv(snap / "pair_terms.csv", index=False)
    sites = [s for s in str(src.get("gsc_sites") or "").split() if s]
    site_list = ", ".join(f"'{s}'" for s in ["https://www.headout.com/", *sites])
    rx = src["page_regex"]
    org = bq(f"""
        SELECT '{ce}' AS ce, LOWER(keyword) AS term, SUM(count_clicks) AS clicks, SUM(count_impressions) AS impressions,
            ROUND(SAFE_DIVIDE(SUM(avg_position * count_impressions), SUM(count_impressions)), 1) AS avg_position,
            SUM(IF(site != 'https://www.headout.com/', count_clicks, 0)) AS clicks_microbrand,
            ARRAY_AGG(page ORDER BY count_clicks DESC LIMIT 1)[OFFSET(0)] AS top_page, 0 AS spend, 0 AS conv
        FROM `headout-analytics.analytics_staging.stg_search_console__keyword_page_performance`
        WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 92 DAY) AND search_type = 'web' AND site IN ({site_list})
              AND (REGEXP_CONTAINS(page, r'{rx}') OR (site != 'https://www.headout.com/' AND REGEXP_CONTAINS(site, r'{rx}')))
              -- English pages only: no language folder such as /it/ or /pt-br/ (ui/english.py). Paid searches are filtered by
              -- language in the UI export, search terms first, so every campaign is pulled.
              AND (NOT REGEXP_CONTAINS(page, r'^https?://[^/]+/[a-z]{{2}}(-[a-z]{{2,4}})?(/|$)')
                   OR REGEXP_CONTAINS(page, r'^https?://[^/]+/en(/|$)'))
        GROUP BY 1, 2 HAVING SUM(count_clicks) > 0 OR SUM(count_impressions) >= 50""")
    if org.empty:
        org = pd.DataFrame(columns=["ce", "term", "clicks", "impressions", "avg_position", "clicks_microbrand", "top_page", "spend", "conv"])
    org.to_csv(snap / "gsc_terms.csv", index=False)
    pd.DataFrame([{"ce": ce, "name": src["name"], "city": src["city"]}]).to_csv(snap / "ce_names.csv", index=False)
    print(f"pull: {len(kw)} keywords, {len(paid)} paid searches, {len(org)} organic queries")


MODEL = "claude-opus-5-5"
EFFORT = "medium"
MAX_TOKENS = 64000
# The prompt asks for a reasoning trace per cluster, but its OUTPUT FORMAT is JSON only; the trace made answers run for
# an hour or more. This instruction resolves the contradiction in favour of the output format.
JSON_ONLY = ("Output only the final JSON object {\"keywordsClusters\": [...]} defined in OUTPUT FORMAT. Do not write any "
             "reasoning trace, step tables, checklists or explanation, even where the instructions above ask for one.")


def extract_json(text):
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise SystemExit(f"no JSON in the model's answer: {text[:300]}")
    return json.loads(m.group(0))


def call_api(system, message):
    """The Messages API, as EOS calls the prompt: Harsha's prompt as system, the CE input as the user message."""
    import anthropic
    client = anthropic.Anthropic(max_retries=4)
    with client.beta.messages.stream(
        model=MODEL, max_tokens=MAX_TOKENS, system=system,
        output_config={"effort": EFFORT},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        messages=[{"role": "user", "content": message}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise SystemExit(f"the model declined: {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise SystemExit(f"answer cut off at {MAX_TOKENS} tokens")
    return extract_json("".join(b.text for b in msg.content if b.type == "text"))


def call_cli(system, message):
    """Fallback without API credentials: the Claude Code CLI, one tool-less turn with the same model and effort."""
    sysfile = Path(os.environ.get("TMPDIR", "/tmp")) / f"system_{os.getpid()}.md"
    sysfile.write_text(system)
    for attempt in range(3):
        res = subprocess.run(["claude", "-p", "--output-format", "json", "--tools", "", "--max-turns", "1",
                              "--model", MODEL, "--effort", EFFORT, "--system-prompt-file", str(sysfile)],
                             input=message, capture_output=True, text=True, timeout=3600,
                             env={**os.environ, "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(MAX_TOKENS)})
        out = json.loads(res.stdout) if res.stdout.strip().startswith("{") else {}
        if not out.get("is_error") and "result" in out:
            return extract_json(out["result"])
        # network blips (ENOTFOUND, 5xx) clear on retry; an expired login does not
        if "authenticate" in str(out.get("result", "")) or attempt == 2:
            raise SystemExit(f"claude -p failed (sign in with `claude` if the token expired): {str(out.get('result') or res.stderr)[-800:]}")
        time.sleep(30 * (attempt + 1))


def has_api_credentials():
    try:
        import anthropic
        anthropic.Anthropic().models.retrieve(MODEL)
        return True
    except Exception:
        return False


def call_llm(system, message, llm):
    if llm == "api" or (llm == "auto" and has_api_credentials()):
        return call_api(system, message)
    return call_cli(system, message)


def call_prompt(pack, llm):
    message = ("INPUT (JSON):\n" + json.dumps(pack, ensure_ascii=False)
               + "\n\nReturn ONLY the output JSON object {\"keywordsClusters\": [...]} as specified, no other text.")
    if llm == "api" or (llm == "auto" and has_api_credentials()):
        print(f"cluster: Messages API, {MODEL}, effort {EFFORT}, prompt {PROMPT.name}")
        return call_api(PROMPT.read_text() + "\n\n" + JSON_ONLY, message)
    print(f"cluster: no API credentials; Claude Code CLI, {MODEL}, effort {EFFORT}, prompt {PROMPT.name}")
    return call_cli(PROMPT.read_text() + "\n\n" + JSON_ONLY, message)


def pair_agreement(a, b):
    """Share of shared keywords that two runs' EOS-style assignments put together the same way (pairwise)."""
    import itertools
    from harsha_to_clusters import claims, norm

    def assign(run, kws):
        cl = sorted([c for c in run["keywordsClusters"] if c.get("primaryKeyword")], key=lambda c: c["rank"])
        return {k: next((c["name"] for c in cl if any(claims(i, k) for i in c.get("identifiers") or [])), None) for k in kws}
    kws = [norm(k) for k in pack_keywords]
    ma, mb = assign(a, kws), assign(b, kws)
    pairs = list(itertools.combinations([k for k in kws if ma[k] and mb[k]], 2))[:20000]
    return sum((ma[x] == ma[y]) == (mb[x] == mb[y]) for x, y in pairs) / max(1, len(pairs))


def negatives(ce):
    """The clusters prompt's negative keywords for a CE: negative_keywords.json's terms for every CE, plus its own."""
    n = json.loads((HERE / "negative_keywords.json").read_text())
    return list(dict.fromkeys(n["all"] + n.get("by_ce", {}).get(str(ce), [])))


def cluster(ce, src, snap, runs, llm):
    global pack_keywords
    kw = pd.read_csv(snap / "eos_keywords.csv").sort_values("vol", ascending=False)
    pack = {"ceName": src["name"], "ceCity": src["city"], "ceCountry": src["country"], "ceSubcat": src["subcat"],
            "negativeKeywords": negatives(ce), "keywordData": [{"keyword": t, "searchVolume": int(v) if pd.notna(v) else 0}
                                                    for t, v in zip(kw["term"], kw["vol"])]}
    pack_keywords = [k["keyword"] for k in pack["keywordData"]]
    (snap / "inputs").mkdir(exist_ok=True)
    (snap / "outputs").mkdir(exist_ok=True)
    (snap / "inputs" / f"{ce}.json").write_text(json.dumps(pack, ensure_ascii=False))
    outs = []
    for r in range(runs):
        outs.append(call_prompt(pack, llm))
        (snap / "outputs" / f"{ce}.run{r + 1}.json").write_text(json.dumps(outs[-1], ensure_ascii=False, indent=1))
        print(f"cluster: run {r + 1}: {len(outs[-1]['keywordsClusters'])} clusters")
    best, agree = 0, {}
    if runs > 1:
        score = [sum(pair_agreement(outs[i], outs[j]) for j in range(runs) if j != i) / (runs - 1) for i in range(runs)]
        best = max(range(runs), key=lambda i: score[i])
        agree = {"run_agreement": [round(s, 3) for s in score]}
        print(f"cluster: agreement between runs {agree['run_agreement']}; keeping run {best + 1}")
    shutil.copy(snap / "outputs" / f"{ce}.run{best + 1}.json", snap / "outputs" / f"{ce}.json")
    return agree


def runs_from(stdout):
    # A placeholder CE id ("10 - Phuket") puts spaces in the snapshot name, so the run id is read up to its colon.
    return re.findall(r"run (\d{8}-\d{6}_jev_classify_[^:\n]+):", stdout)


def place(ce, snap):
    name, ids = snap.name, {}
    base = [PY, "jev_classify.py", "--snapshot", name, "--ces", ce, "--mode", "all", "--descriptions", str(snap / "cluster_descriptions.csv")]
    jobs = {"keywords": ["--terms-file", str(snap / "eos_keywords.csv")],
            "paid": ["--terms-file", str(snap / "pair_terms.csv"), "--context", "paid"],
            "organic": ["--terms-file", str(snap / "gsc_terms.csv"), "--min-prob", "0.5"]}
    for kind, extra in jobs.items():
        if kind != "keywords" and len(pd.read_csv(snap / extra[1])) == 0:
            print(f"place: no {kind} searches")
            continue
        # Run ids are stamped to the second (runlib); a cached run can finish within the same second as the next starts.
        time.sleep(1.1)
        res = subprocess.run(base + extra, capture_output=True, text=True, cwd=HERE)
        if res.returncode:
            raise SystemExit(f"place {kind} failed:\n{res.stderr[-1500:]}")
        ids[kind] = runs_from(res.stdout)[-1]
        print(f"place: {kind} -> {ids[kind]}")
    return ids


JUDGE = """You check how searches were sorted into intent clusters for a travel product (a Headout CE).
You get the cluster list (name and definition) and a numbered list of searches, each with the cluster it was put in
("NONE" = no cluster). Paid searches triggered the CE's own ads, so they already carry the CE's place.
For each search decide: "ok" if the assigned cluster is right (or one of two equally right answers); otherwise give the
right cluster name exactly as listed, or "NONE" if the search belongs to no cluster (another attraction or city,
unrelated). Judge by meaning in any language. Output only JSON: {"verdicts": [{"i": <number>, "v": "ok" | <cluster name> | "NONE"}]}"""


def weighted_pick(df, w, n, seed=7):
    import numpy as np
    df = df[df[w].fillna(0) > 0]
    if len(df) <= n:
        return df
    keys = np.random.default_rng(seed).random(len(df)) ** (1 / df[w].to_numpy(dtype=float))
    return df.assign(_k=keys).nlargest(n, "_k").drop(columns="_k")


def judge(ce, snap, state, llm, n=100):
    """Estimated accuracy of one run: a second model (Claude) checks a weighted sample of Jev's placements."""
    desc = pd.read_csv(snap / "cluster_descriptions.csv", dtype={"ce": str})
    desc = desc[desc["ce"] == ce]
    clusters = "\n".join(f"- {r.name}: {r.description}" for r in desc.itertuples())
    out = {}
    for kind, w in (("paid", "clicks"), ("organic", "impressions")):
        run = state.get("place", {}).get(kind)
        if not run:
            continue
        a = pd.read_csv(runlib.RUNS / run / "outputs" / f"assignments_{ce}.csv", low_memory=False).drop_duplicates("term")
        s = weighted_pick(a, w, n).reset_index(drop=True)
        rows = "\n".join(f"{i}. [{kind}] {t} -> {c if pd.notna(c) else 'NONE'}" for i, (t, c) in enumerate(zip(s["term"], s["D_name"])))
        res = call_llm(JUDGE, f"CLUSTERS:\n{clusters}\n\nSEARCHES:\n{rows}", llm)
        v = {int(x["i"]): x["v"] for x in res.get("verdicts", [])}
        s["verdict"] = [v.get(i, "ok") for i in range(len(s))]
        s["ok"] = s["verdict"].eq("ok") | (s["verdict"].eq("NONE") & s["D_name"].isna())
        s.to_csv(snap / f"judge_{kind}.csv", index=False)
        out[f"{kind}_judged_wrong"] = round(float(1 - (s[w] * s["ok"]).sum() / s[w].sum()), 4)
        out[f"{kind}_judged_n"] = len(s)
        print(f"judge: {kind} {out[f'{kind}_judged_wrong']:.1%} wrong (by {w}, {len(s)} checked)")
    return out


def score(ce, snap, state):
    out = {"ce": ce}
    kw = pd.read_csv(snap / "cluster_keywords.csv", dtype={"ce": str})
    out["clusters"] = int(kw.loc[kw["name"] != "Others", "name"].nunique())
    eos_left = kw[kw["name"] == "Others"]
    out["eos_style_unclaimed_keywords"] = int(len(eos_left))
    for kind, w in (("keywords", "vol"), ("paid", "clicks"), ("organic", "impressions")):
        run = state.get("place", {}).get(kind)
        if not run:
            continue
        a = pd.read_csv(runlib.RUNS / run / "outputs" / f"assignments_{ce}.csv", low_memory=False)
        a[w] = a[w].fillna(0)
        tot = a[w].sum() or 1
        out[f"{kind}_{w}_no_cluster"] = round(float(a.loc[a["D_name"].isna(), w].sum() / tot), 4)
        out[f"{kind}_{w}_low_confidence"] = round(float(a.loc[a["prob"].fillna(0) < 0.6, w].sum() / tot), 4)
        out[f"{kind}_jev_failed"] = int((a["how"] == "jev_failed").sum())
    out.update(state.get("cluster", {}))
    out.update(state.get("judge", {}))
    out["prompt"] = PROMPT.name
    (snap / "scorecard.json").write_text(json.dumps(out, indent=2))
    print("score:", json.dumps(out, indent=1))


def export(ce, snap, state):
    """The contract the UI reads: snapshots/ce_<ce>/final/ (or ce_<ce>_<prompt>/final/).
      clusters.csv   ce, cluster, type, level, definition, focus_keyword, focus_volume, keywords, volume (once per spelling group)
      keywords.csv   ce, keyword, volume, cluster, confidence           (every EOS keyword, placed by Jev)
      paid.csv       ce, search, impr, clicks, spend, conv, conv_value, cluster, confidence   (90 days)
      organic.csv    ce, search, clicks, impressions, avg_position, top_page, cluster, confidence
      scorecard.json copy of the run's scorecard
    "cluster" is empty when the search belongs to no cluster."""
    fin = snap / "final"
    fin.mkdir(exist_ok=True)
    meta = pd.read_csv(snap / "cluster_keywords.csv", dtype={"ce": str})
    meta = meta[meta["name"] != "Others"].drop_duplicates("name")[["name", "t", "rank"]]
    desc = pd.read_csv(snap / "cluster_descriptions.csv", dtype={"ce": str}).set_index("name")["description"]
    out = {}
    for kind, run in state.get("place", {}).items():
        a = pd.read_csv(runlib.RUNS / run / "outputs" / f"assignments_{ce}.csv", low_memory=False).drop_duplicates("term")
        a = a.rename(columns={"term": "keyword" if kind == "keywords" else "search", "D_name": "cluster", "prob": "confidence"})
        keep = {"keywords": ["keyword", "vol"], "paid": ["search", "impr", "clicks", "spend", "conv", "conv_value"],
                "organic": ["search", "clicks", "impressions", "avg_position", "top_page"]}[kind]
        a = a[[c for c in keep if c in a] + ["cluster", "confidence"]].rename(columns={"vol": "volume"})
        a.insert(0, "ce", ce)
        a.to_csv(fin / f"{kind}.csv", index=False)
        out[kind] = a
    # A CE with no paid or organic searches still gets the file with its columns, so the UI reads 0 rows.
    for kind, cols in {"paid": ["ce", "search", "impr", "clicks", "spend", "conv", "conv_value", "cluster", "confidence"],
                       "organic": ["ce", "search", "clicks", "impressions", "avg_position", "top_page", "cluster", "confidence"]}.items():
        if kind not in out:
            pd.DataFrame(columns=cols).to_csv(fin / f"{kind}.csv", index=False)
    kw = out.get("keywords", pd.DataFrame(columns=["keyword", "volume", "cluster"]))
    rows = []
    for r in meta.itertuples():
        k = kw[kw["cluster"] == r.name].sort_values("volume", ascending=False)
        rows.append({"ce": ce, "cluster": r.name, "type": r.t, "level": r.rank, "definition": desc.get(r.name, ""),
                     "focus_keyword": k["keyword"].iloc[0] if len(k) else "", "focus_volume": int(k["volume"].iloc[0]) if len(k) and pd.notna(k["volume"].iloc[0]) else 0,
                     "keywords": len(k), "volume": int(k["volume"].fillna(0).drop_duplicates().sum())})
    pd.DataFrame(rows).to_csv(fin / "clusters.csv", index=False)
    if (snap / "scorecard.json").exists():
        shutil.copy(snap / "scorecard.json", fin / "scorecard.json")
    print(f"export: {len(rows)} clusters -> {fin.relative_to(HERE)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ce")
    p.add_argument("--from", dest="start", choices=STEPS, default="pull")
    p.add_argument("--llm", choices=["auto", "api", "cli"], default="auto",
                   help="api: Anthropic Messages API (needs ANTHROPIC_API_KEY or `ant auth login`); cli: `claude -p`; auto: API when credentials exist")
    p.add_argument("--prompt", choices=list(PROMPTS), default="original", help="Harsha's prompt as written, or with the Clusters 3.0 overrides")
    p.add_argument("--keywords", choices=["eos", "own"], default="eos",
                   help="eos: EOS's keyword research from the MMP tool; own: research_ce.py's list for a CE EOS has not researched")
    p.add_argument("--runs", type=int, default=1, help="prompt runs; with 3, keep the run that agrees most with the others")
    a = p.parse_args()
    srcs = pd.read_csv(HERE / "ce_sources.csv", dtype={"ce": str}).fillna("").set_index("ce")
    if a.ce not in srcs.index:
        raise SystemExit(f"add CE {a.ce} to ce_sources.csv (name, city, country, subcat from the prompt's playbooks, page_regex)")
    src = srcs.loc[a.ce].to_dict()
    global PROMPT
    PROMPT = PROMPTS[a.prompt]
    snap = runlib.SNAPSHOTS / (f"ce_{a.ce}" if a.prompt == "original" else f"ce_{a.ce}_{a.prompt}")
    snap.mkdir(exist_ok=True)
    state_file = snap / "pipeline.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    for step in STEPS[STEPS.index(a.start):]:
        print(f"== {step}", flush=True)
        if step == "pull":
            pull(a.ce, src, snap, a.keywords)
        elif step == "cluster":
            state["cluster"] = cluster(a.ce, src, snap, a.runs, a.llm)
        elif step == "convert":
            res = subprocess.run([PY, "harsha_to_clusters.py", "--prompt-snapshot", snap.name, "--base", snap.name,
                                  "--out-snapshot", snap.name, "--ces", a.ce], capture_output=True, text=True, cwd=HERE)
            if res.returncode:
                raise SystemExit(res.stderr[-1500:])
            print("convert:", res.stdout.strip())
        elif step == "place":
            state["place"] = place(a.ce, snap)
        elif step == "judge":
            state["judge"] = judge(a.ce, snap, state, a.llm)
        elif step == "score":
            score(a.ce, snap, state)
        elif step == "export":
            export(a.ce, snap, state)
        state_file.write_text(json.dumps(state, indent=2))
    print(f"done: snapshots/{snap.name}/scorecard.json")


if __name__ == "__main__":
    main()
