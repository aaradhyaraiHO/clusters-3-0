"""Keyword research for a CE that EOS has not researched: the seeds prompt, then Keyword Planner, into the
eos_keywords.csv that run_ce_pipeline.py clusters.

  python research_ce.py 3097            then: python run_ce_pipeline.py 3097 --keywords own --runs 3

1. Seeds: prompts/eos/seeds.md (synced from the prompts doc) with the CE's name, city, country and subcategory from
   ce_sources.csv; up to 80 seeds, each with its intent.
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
from run_ce_pipeline import EFFORT, MODEL, call_cli, call_api, has_api_credentials

HERE = Path(__file__).resolve().parent
SEEDS_PROMPT = HERE / "prompts" / "eos" / "seeds.md"
ADS_ENV = Path.home() / "google-ads-mcp" / ".env"
ADS_PYTHON = Path.home() / "google-ads-mcp" / "venv" / "bin" / "python"
PLANNER_ACCOUNT = "8738486895"
MIN_VOLUME = 10
MAX_KEYWORDS = 1000
# Words that say what kind of product, not which one: an idea sharing only these with the seeds is not about the CE.
GENERIC = set("""tickets ticket tours tour cruise cruises day trip trips the and of to from in at near best top cheap price prices
cost book booking deals deal guided guide private group small half full city island islands park national things do visit
visiting what how is are a for with by on hotel hotels map weather review reviews""".split())


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


def keep(ideas, seeds, name):
    """Ideas about the CE: they share a distinctive word with the CE's name or a seed."""
    anchors = {w for s in [name, *seeds] for w in words(s) if w not in GENERIC and len(w) > 2}
    rows = [(t, v) for t, v in ideas.items() if v >= MIN_VOLUME and anchors & set(words(t))]
    for s in seeds:
        if s not in dict(rows):
            rows.append((s, ideas.get(s, 0)))
    return sorted(rows, key=lambda r: -r[1])[:MAX_KEYWORDS], sorted(anchors)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ce")
    p.add_argument("--llm", choices=["auto", "api", "cli"], default="auto")
    p.add_argument("--stage", choices=["all", "seeds", "finish"], default="all",
                   help="seeds: write seeds.json only; finish: read Keyword Planner ideas from --ideas instead of the API")
    p.add_argument("--ideas", help="Keyword Planner's 'Download keyword ideas' CSV(s) for this CE, comma-separated")
    a = p.parse_args()
    src = pd.read_csv(HERE / "ce_sources.csv", dtype=str).set_index("ce")
    if a.ce not in src.index:
        raise SystemExit(f"CE {a.ce} is not in ce_sources.csv; add it with ce_sources_add.py")
    row = src.loc[a.ce].fillna("")
    snap = runlib.SNAPSHOTS / f"ce_{a.ce}"
    snap.mkdir(parents=True, exist_ok=True)
    if a.stage == "finish":
        seeds = json.loads((snap / "seeds.json").read_text())
    else:
        seeds = seeds_for(row, a.llm)
        (snap / "seeds.json").write_text(json.dumps(seeds, indent=1))
        print(f"research: {len(seeds)} seeds from {SEEDS_PROMPT.name}")
        if a.stage == "seeds":
            return
    ideas = planner_csv(a.ideas.split(",")) if a.stage == "finish" else ideas_for([s["keyword"] for s in seeds])
    kept, anchors = keep(ideas, [s["keyword"] for s in seeds], row["name"])
    pd.DataFrame([{"ce": a.ce, "term": t, "vol": v} for t, v in kept]).to_csv(snap / "eos_keywords.csv", index=False)
    (snap / "research.json").write_text(json.dumps({
        "ce": a.ce, "at": datetime.now().isoformat(timespec="seconds"), "model": MODEL, "effort": EFFORT,
        "prompt": str(SEEDS_PROMPT.relative_to(HERE)), "planner": {"language": "English", "locations": "all", "network": "Google Search"},
        "min_volume": MIN_VOLUME, "max_keywords": MAX_KEYWORDS, "anchors": anchors, "seeds": seeds,
        "ideas": len(ideas), "kept": len(kept)}, indent=1))
    print(f"research: {len(ideas)} Keyword Planner ideas, {len(kept)} kept ({sum(v for _, v in kept):,} searches a month)")


if __name__ == "__main__":
    sys.exit(main())
