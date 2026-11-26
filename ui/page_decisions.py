"""The prompts doc's three page prompts for one CE, in the doc's order:

  python page_decisions.py <clusters_3_0> <ces.json key>

1. page_mapping.md: does an existing page of the CE already cover each cluster (existing_page / no_existing_page /
   needs_review)?
2. separate_page.md: for the clusters no existing page covers, does each need a page of its own (yes / no / not_sure)?
3. page_type.md: for the clusters that get a page of their own, which page type, with every cluster of the CE as context.

Inputs come from the CE's tool folder: the exported clusters (type, focus keyword, keywords, supply), its Payload pages
(pages_<CE>.csv), its products and their operators (the proposed assortment) and page_facts.json (category). The prompt
text is used as synced from the doc (pipeline prompts/eos/), with the doc's {{ }} inputs filled. Writes
page_decisions.json in the CE's folder; export_hybrid.py reads it. A step whose inputs and prompt have not changed since
the last run is not sent again.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1])
KEY = sys.argv[2]
sys.path.insert(0, str(ROOT))
from run_ce_pipeline import MODEL, call_llm  # noqa: E402  (the pipeline's model and its API / CLI fallback)

PROMPTS = ROOT / "prompts" / "eos"
CFG = json.loads((HERE / "ces.json").read_text())["ces"][KEY]
OUT = HERE / CFG["out"]
HOST = CFG["host"]
INTENT = {"TRANSACTIONAL": "Transactional", "PLANNING": "Planning", "INFORMATIONAL": "Informational"}


def page_url(uid):
    # A Payload uid is the host and path joined by dots: www.site.com.about -> https://www.site.com/about/. A page may
    # sit on another site than the CE's own (ces.json page_prefixes).
    m = re.match(r"^(www\.[a-z0-9-]+\.(?:co\.[a-z]{2}|com\.[a-z]{2}|[a-z]{2,3}))(?=\.|$)", uid)
    host = m.group(1) if m else HOST
    return f"https://{host}/" + "".join(p + "/" for p in uid[len(host):].split(".") if p)


def eligibility(cl):
    """separate_page.md's supply_status: Transactional clusters only; "NA" for the rest."""
    if cl["type"] != "TRANSACTIONAL":
        return "NA"
    s = cl.get("supply") or {}
    if s.get("live") or (cl.get("checks") or {}).get("supply"):
        return "supply_available"
    return "supply_not_available" if s.get("n") else "no_unique_experience"


def fill(name, values):
    text = (PROMPTS / name).read_text()
    for k, v in values.items():
        text = text.replace("{{ " + k + " }}", v)
    system, _, message = text.rpartition("Prompt:")
    return system, "Prompt:" + message


def ask(name, values, wrap):
    system, message = fill(name, values)
    message += f'\n\nReturn only {{"{wrap}": [...]}}, where the array is the JSON array the output format defines. No other text.'
    answer = call_llm(system, message, "auto")
    return answer.get(wrap, []) if isinstance(answer, dict) else answer


def digest(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def main():
    data = json.loads((OUT / CFG["data"]).read_text())
    drawer = json.loads((OUT / "drawer.json").read_text())["clusters"]
    clusters = [c for c in data["clusters"] if not str(c["name"]).startswith("Other")]
    facts = json.loads((OUT / "page_facts.json").read_text()) if (OUT / "page_facts.json").exists() else {}

    exp_file = OUT / f"experiences_{KEY}.csv"
    exp = pd.read_csv(exp_file, dtype=str) if exp_file.exists() else pd.DataFrame(columns=["experience_name", "vendors", "live", "orders"])
    exp = exp[exp["live"].fillna("").str.lower().eq("true")] if len(exp) else exp
    exp = exp.assign(o=pd.to_numeric(exp.get("orders"), errors="coerce").fillna(0)).sort_values("o", ascending=False).head(40)
    assortment = "; ".join(f"{x.experience_name} (operator: {x.vendors})" if isinstance(x.vendors, str) and x.vendors else str(x.experience_name)
                           for x in exp.itertuples()) or "none listed"

    pages_file = OUT / f"pages_{KEY}.csv"
    pg = pd.read_csv(pages_file, dtype=str) if pages_file.exists() else pd.DataFrame(columns=["uid"])
    pg = pg[pg["page_type"] != "Trust"] if "page_type" in pg else pg
    pages = [{k: v for k, v in {"uid": x.uid, "pageType": x.page_type, "noIndex": str(x.any_noindex).lower() == "true", "url": page_url(x.uid),
                                "status": "live" if x.status_en == "published" else x.status_en, "focusKeyword": x.focus_keyword_en,
                                "poiId": x.poi_id, "collectionId": x.collection_id, "subAttractionType": x.page_sub_type}.items()
              if isinstance(v, bool) or (isinstance(v, str) and v and v != "nan")}
             for x in pg.itertuples()]

    def cluster_data(c, extra=None):
        kws = [{"keyword": w["kw"], "searchVolume": int(w.get("vol") or 0)} for w in drawer.get(c["id"], {}).get("keywords", [])]
        kws = sorted(kws, key=lambda w: -w["searchVolume"])[:21]
        row = {"cluster_name": c["name"], "intent": INTENT.get(c["type"], c["type"].title()), "eligibility_notes": eligibility(c),
               "primaryKeyword": {"keyword": c.get("focus_kw") or "", "searchVolume": int(c.get("vol") or 0)},
               "keywordData": [w for w in kws if w["keyword"] != c.get("focus_kw")][:20]}
        return {**row, **(extra or {})}

    ce = {"ce_name.text": CFG["name"], "category.text": str(facts.get("category") or ""),
          "subcategory.text": str(facts.get("subcategory") or ""), "proposed_assortment.text": assortment}
    by_name = {c["name"]: c for c in clusters}
    out_file = OUT / "page_decisions.json"
    prev = json.loads(out_file.read_text()) if out_file.exists() else {}
    steps = prev.get("steps", {})

    def run(step, prompt, values, wrap):
        h = digest((PROMPTS / prompt).read_text(), values, MODEL)
        if steps.get(step, {}).get("hash") == h:
            print(f"{step}: unchanged, kept the last answers")
            return steps[step]["answers"]
        answers = ask(prompt, values, wrap)
        steps[step] = {"hash": h, "answers": answers}
        print(f"{step}: {len(answers)} answers")
        return answers

    # 1. Existing pages.
    mapping = run("page_mapping", "page_mapping.md",
                  {**ce, "existing_pages.text": json.dumps(pages, ensure_ascii=False),
                   "clusters_data.text": json.dumps([cluster_data(c) for c in clusters], ensure_ascii=False)}, "mappings")
    mapped = {m.get("cluster_name"): m for m in mapping if m.get("cluster_name") in by_name}
    # 2. A page of its own, for the clusters no existing page covers.
    open_ = [c for c in clusters if mapped.get(c["name"], {}).get("status") == "no_existing_page"]
    sep = run("separate_page", "separate_page.md",
              {**ce, "clusters_data.text": json.dumps([cluster_data(c) for c in open_], ensure_ascii=False)}, "decisions") if open_ else []
    sep_of = {s.get("cluster_name"): s.get("separate_page") for s in sep}
    # 3. Page type for the ones that get a page, every cluster passed as context.
    need = {c["name"] for c in open_ if sep_of.get(c["name"]) == "yes"}
    types = run("page_type", "page_type.md",
                {**ce, "clusters_data.text": json.dumps([cluster_data(c, {"needs_page_type": c["name"] in need}) for c in clusters], ensure_ascii=False)},
                "page_types") if need else []
    type_of = {t.get("cluster_name"): t.get("page_type") for t in types}

    result = {}
    for c in clusters:
        m = mapped.get(c["name"], {})
        result[c["id"]] = {"mapping": m.get("status"), "existing_page_url": m.get("existing_page_url"),
                           "separate_page": sep_of.get(c["name"]), "page_type": type_of.get(c["name"])}
    out_file.write_text(json.dumps({"model": MODEL, "prompts": str(PROMPTS), "steps": steps, "clusters": result}, indent=1, ensure_ascii=False))
    counts = pd.Series([v["mapping"] for v in result.values()]).value_counts().to_dict()
    print(f"page decisions: mapping {counts}; own page yes {len(need)} of {len(open_)}; page types {len(type_of)}")


if __name__ == "__main__":
    main()
