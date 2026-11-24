"""Keyword research for a CE that EOS has not researched: the seeds prompt, then Keyword Planner, into the
eos_keywords.csv that run_ce_pipeline.py clusters.

  python research_ce.py 3097            then: python run_ce_pipeline.py 3097 --keywords own --runs 3

0. Vendor seeds: prompts/eos/vendor_seeds.md with the vendors on the CE's experiences (BigQuery) and a web search for
   the CE's operators, then prompts/eos/vendor_noise_filter.md; written to vendor_seeds.json.
1. Seeds: prompts/eos/seeds.md (synced from the prompts doc) with the CE's name, city, country and subcategory from
   ce_sources.csv; up to 80 seeds, each with its intent. Vendor seeds go to Keyword Planner with them.
2. Ideas: Google Keyword Planner (KeywordPlanIdeaService) on the seeds, 20 per request, English, every location, Google
   Search, the same basis as EOS's volumes. Seeds are kept with their own volume.
3. Keep: ideas that name the CE or a seed's own words (not a generic travel word alone), with 10+ searches a month,
   then the highest-volume ones up to MAX_KEYWORDS. EOS lists run about 200 keywords (Milford 199, Key West 207) and
   reach about 1,000 for a broad CE (Phi Phi 1,038).

Writes snapshots/ce_<CE>/eos_keywords.csv (ce, term, vol) and research.json (seeds, settings, counts). Keyword Planner
credentials come from the Google Ads tool's .env (GOOGLE_ADS_* variables); the account is any client account under
the MCC, since Keyword Planner volumes do not depend on it.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import runlib
from run_ce_pipeline import EFFORT, MODEL, bq, call_api, call_cli, call_llm, extract_json, has_api_credentials

HERE = Path(__file__).resolve().parent
SEEDS_PROMPT = HERE / "prompts" / "eos" / "seeds.md"
VENDOR_PROMPT = HERE / "prompts" / "eos" / "vendor_seeds.md"
VENDOR_FILTER = HERE / "prompts" / "eos" / "vendor_noise_filter.md"
ADS_ENV = Path.home() / "google-ads-mcp" / ".env"
ADS_PYTHON = Path.home() / "google-ads-mcp" / "venv" / "bin" / "python"
PLANNER_ACCOUNT = "8738486895"
MIN_VOLUME = 10
MAX_KEYWORDS = 1000
# Words that say what kind of product, not which one: an idea sharing only these with the seeds is not about the CE.
GENERIC = set("""tickets ticket tours tour cruise cruises day trip trips the and of to from in at near best top cheap price prices
cost book booking deals deal guided guide private group small half full city island islands park national things do visit
visiting what how is are a for with by on hotel hotels map weather review reviews""".split())
# What people add to an operator's name when they mean to book with it.
BOOKING = set("""reservation reservations reservations contact phone number website login promo code coupon discount voucher
gift card refund cancellation schedule hours open opening times rates booking online""".split())


def seeds_for(src, llm):
    text = SEEDS_PROMPT.read_text()
    filled = (text.replace("{{ ce_name.text }}", src["name"]).replace("{{ city.text }}", str(src["city"]))
              .replace("{{ country.text }}", str(src["country"])).replace("{{ subcategory.text }}", str(src["subcat"])))
    system, _, message = filled.rpartition("Prompt:")
    message = ("Prompt:" + message + '\n\nReturn only {"seeds": [...]}, where the array is the JSON array the output format '
               "defines. No other text.")
    answer = call_api(system, message) if llm == "api" or (llm == "auto" and has_api_credentials()) else call_cli(system, message)
    seeds = [{"keyword": s["keyword"].strip().lower(), "category": s.get("category")} for s in answer["seeds"] if s.get("keyword")]
    return seeds[:80]


LEGAL = re.compile(r"[\s,]*\b(co\.?,?\s*ltd\.?|company limited|pty\.?\s*ltd\.?|pte\.?\s*ltd\.?|ltd\.?|limited|inc\.?|llc|"
                   r"corporation|corp\.?|gmbh|s\.?a\.?s?|s\.?l\.?|b\.?v\.?)\s*$", re.I)


def searchable(name):
    """A vendor as people search for it: the trading name, without a legal suffix ("we love phuket co., ltd" -> "we love
    phuket", "addictive entertainment - trading as bunyip tour" -> "bunyip tour")."""
    name = re.split(r"\btrading as\b|\bt/a\b", name, flags=re.I)[-1]
    while (short := LEGAL.sub("", name)) != name:
        name = short
    return re.sub(r"\s+", " ", name.strip(" -,.")).lower()


def internal_vendors(ce):
    """Every vendor on the CE's experiences: the ones the CE owns and the ones its collection or a descendant lists.
    These are the prompt's vetted sheet rows, so they skip the web search's operator test."""
    if not ce.isdigit():
        return []
    rows = bq(f"""
        WITH parent AS (SELECT collection_id, descendant_collections
                        FROM `headout-analytics.analytics_reporting.dim_collections` WHERE collection_id = '{ce}'),
        ce_collections AS (SELECT collection_id FROM parent
                           UNION DISTINCT
                           SELECT descendant.collection_id FROM parent CROSS JOIN UNNEST(parent.descendant_collections) AS descendant),
        experiences AS (SELECT experience_id FROM `headout-analytics.analytics_reporting.dim_experiences` WHERE combined_entity_id = '{ce}'
                        UNION DISTINCT
                        SELECT listed.experience_id
                        FROM ce_collections
                        INNER JOIN `headout-analytics.analytics_reporting.dim_collections` AS listing USING (collection_id)
                        CROSS JOIN UNNEST(listing.experiences) AS listed)
        SELECT tours.vendor_name, LOGICAL_OR(COALESCE(dim_experiences.is_available, FALSE)) AS is_available
        FROM `headout-analytics.analytics_reporting.dim_variants` AS variants
        CROSS JOIN UNNEST(variants.tours) AS tour
        INNER JOIN `headout-analytics.analytics_reporting.dim_tour_profiles` AS tours ON tours.tour_id = tour.tour_id
        INNER JOIN `headout-analytics.analytics_reporting.dim_experiences` AS dim_experiences
            ON dim_experiences.experience_id = variants.experience_id
        WHERE variants.experience_id IN (SELECT experience_id FROM experiences) AND tours.vendor_name IS NOT NULL
        GROUP BY 1""")
    return [{"name": r["vendor_name"], "status": "active" if r["is_available"] in (True, "true") else "inactive"}
            for r in rows.to_dict("records")]


def fill(prompt, src, extra):
    text = (prompt.replace("{{ ce_name.text }}", src["name"]).replace("{{ city.text }}", str(src["city"]))
            .replace("{{ country.text }}", str(src["country"])).replace("{{ ce_id.text }}", str(src.name)))
    for key, value in extra.items():
        text = text.replace(key, value)
    return text


def vendors_for(src, sheet, llm):
    """The prompts doc's vendor flow: the vendor_seeds prompt (internal vendors plus a web search for operators), then
    the vendor_noise_filter prompt, which merges duplicates and drops resellers, shops and generic phrases."""
    rows = "\n".join(f'Vendor Name "{v["name"]}", Status "{v["status"]}"' for v in sheet) or "(no internal vendors)"
    found = call_web(fill(VENDOR_PROMPT.read_text(), src, {"{{ CE_vendors.rows }}": rows}),
                     f"CE: {src['name']}\nCity: {src['city']}\nCountry: {src['country']}\nCE ID: {src.name}\n\n"
                     f"Internal vendor rows:\n{rows}\n\nReturn only the JSON object the output format defines.")
    candidates = [{"name": v["keyword"], "source": v.get("source", "web")} for v in found.get("Vendor", []) if v.get("keyword")]
    if not candidates:
        return []
    listing = json.dumps(candidates, ensure_ascii=False)
    kept = call_llm(fill(VENDOR_FILTER.read_text(), src, {"{{ vendor_list.response }}": listing}),
                    f"Candidates:\n{listing}\n\nReturn only {{\"vendors\": [...]}}, where the array is the JSON array the output "
                    "format defines. No other text.", "auto")
    kept = kept.get("vendors", kept) if isinstance(kept, dict) else kept
    names = dict.fromkeys(searchable(v["keyword"]) for v in kept if v.get("keyword"))
    return [{"keyword": n, "category": "Vendor"} for n in names if n]


def call_web(system, message):
    """One prompt with web search. The Messages API's web search tool when there are API credentials, else the Claude
    Code CLI with its WebSearch and WebFetch tools."""
    if has_api_credentials():
        import anthropic
        msg = anthropic.Anthropic(max_retries=4).messages.create(
            model=MODEL, max_tokens=16000, system=system, messages=[{"role": "user", "content": message}],
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 12}])
        return extract_json("".join(b.text for b in msg.content if b.type == "text"))
    sysfile = Path(os.environ.get("TMPDIR", "/tmp")) / f"vendor_system_{os.getpid()}.md"
    sysfile.write_text(system)
    res = subprocess.run(["claude", "-p", "--output-format", "json", "--tools", "WebSearch,WebFetch",
                          "--allowedTools", "WebSearch,WebFetch", "--max-turns", "30", "--model", MODEL,
                          "--system-prompt-file", str(sysfile)], input=message, capture_output=True, text=True, timeout=1800)
    out = json.loads(res.stdout) if res.stdout.strip().startswith("{") else {}
    if out.get("is_error") or "result" not in out:
        raise SystemExit(f"vendor web search failed: {str(out.get('result') or res.stderr)[-800:]}")
    return extract_json(out["result"])


def ideas_for(seeds):
    """Keyword Planner runs in the Google Ads tool's Python (its venv holds the google-ads library and its .env the
    credentials); planner_ideas.py takes the seeds on stdin and prints {idea: monthly searches}."""
    res = subprocess.run([str(ADS_PYTHON), str(HERE / "planner_ideas.py"), str(ADS_ENV), PLANNER_ACCOUNT],
                         input=json.dumps(seeds), capture_output=True, text=True)
    if res.returncode:
        raise SystemExit(f"Keyword Planner failed:\n{res.stderr[-1500:]}")
    return json.loads(res.stdout)


def planner_csv(paths):
    """Keyword Planner's downloaded ideas (UTF-16, tab-separated, two title lines): keyword -> avg monthly searches."""
    found = {}
    for path in paths:
        df = pd.read_csv(path, sep="\t", encoding="utf-16", skiprows=2)
        vol = pd.to_numeric(df["Avg. monthly searches"].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
        for term, v in zip(df["Keyword"].astype(str).str.strip().str.lower(), vol):
            found[term] = max(found.get(term, 0), int(v))
    return found


def words(text):
    return [w for w in re.split(r"[^a-z0-9]+", str(text).lower()) if w]


def keep(ideas, seeds, name, vendors=()):
    """Ideas about the CE: they share a distinctive word with the CE's name or a seed, or name a vendor in full. A vendor's
    words are not anchors on their own: "see sight tours" would otherwise admit every idea with "see" in it."""
    anchors = {w for s in [name, *seeds] for w in words(s) if w not in GENERIC and len(w) > 2}
    vendor_words = [set(words(v)) - GENERIC or set(words(v)) for v in vendors]

    def about_vendor(t):
        # A vendor named in full, and nothing else but booking words: "papillon grand canyon" and "papillon reviews"
        # stay, "papillon dog" goes.
        tw = set(words(t))
        return any(vw <= tw and tw - vw <= GENERIC | BOOKING for vw in vendor_words)

    rows = [(t, v) for t, v in ideas.items() if v >= MIN_VOLUME and (anchors & set(words(t)) or about_vendor(t))]
    for s in [*seeds, *vendors]:
        if s not in dict(rows):
            rows.append((s, ideas.get(s, 0)))
    return sorted(rows, key=lambda r: -r[1])[:MAX_KEYWORDS], sorted(anchors)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ce")
    p.add_argument("--llm", choices=["auto", "api", "cli"], default="auto")
    p.add_argument("--stage", choices=["all", "seeds", "vendors", "finish"], default="all",
                   help="seeds: write seeds.json only; vendors: write vendor_seeds.json only; "
                        "finish: read Keyword Planner ideas from --ideas instead of the API")
    p.add_argument("--ideas", help="Keyword Planner's 'Download keyword ideas' CSV(s) for this CE, comma-separated")
    a = p.parse_args()
    src = pd.read_csv(HERE / "ce_sources.csv", dtype=str).set_index("ce")
    if a.ce not in src.index:
        raise SystemExit(f"CE {a.ce} is not in ce_sources.csv; add it with ce_sources_add.py")
    row = src.loc[a.ce].fillna("")
    snap = runlib.SNAPSHOTS / f"ce_{a.ce}"
    snap.mkdir(parents=True, exist_ok=True)
    vendor_file = snap / "vendor_seeds.json"
    if a.stage in ("all", "vendors"):
        sheet = internal_vendors(a.ce)
        vendors = vendors_for(row, sheet, a.llm)
        vendor_file.write_text(json.dumps({"internal": sheet, "vendors": vendors}, indent=1))
        print(f"research: {len(vendors)} vendor seeds ({len(sheet)} internal vendors before the filter): "
              + ", ".join(v["keyword"] for v in vendors))
        if a.stage == "vendors":
            return
    if a.stage == "finish":
        seeds = json.loads((snap / "seeds.json").read_text())
    else:
        seeds = seeds_for(row, a.llm)
        (snap / "seeds.json").write_text(json.dumps(seeds, indent=1))
        print(f"research: {len(seeds)} seeds from {SEEDS_PROMPT.name}")
        if a.stage == "seeds":
            return
    vendors = json.loads(vendor_file.read_text())["vendors"] if vendor_file.exists() else []
    vendors = [{"keyword": n, "category": "Vendor"} for n in dict.fromkeys(searchable(v["keyword"]) for v in vendors) if n]
    planner_seeds = [s["keyword"] for s in seeds] + [v["keyword"] for v in vendors]
    ideas = planner_csv(a.ideas.split(",")) if a.stage == "finish" else ideas_for(planner_seeds)
    kept, anchors = keep(ideas, [s["keyword"] for s in seeds], row["name"], [v["keyword"] for v in vendors])
    pd.DataFrame([{"ce": a.ce, "term": t, "vol": v} for t, v in kept]).to_csv(snap / "eos_keywords.csv", index=False)
    (snap / "research.json").write_text(json.dumps({
        "ce": a.ce, "at": datetime.now().isoformat(timespec="seconds"), "model": MODEL, "effort": EFFORT,
        "prompt": str(SEEDS_PROMPT.relative_to(HERE)), "planner": {"language": "English", "locations": "all", "network": "Google Search"},
        "min_volume": MIN_VOLUME, "max_keywords": MAX_KEYWORDS, "anchors": anchors, "seeds": seeds, "vendors": vendors,
        "ideas": len(ideas), "kept": len(kept)}, indent=1))
    print(f"research: {len(ideas)} Keyword Planner ideas, {len(kept)} kept ({sum(v for _, v in kept):,} searches a month)")


if __name__ == "__main__":
    sys.exit(main())
