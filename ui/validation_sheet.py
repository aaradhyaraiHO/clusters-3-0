"""A Google Sheet for content (Harsha, Krupa) to check the clusters' quality: one tab per CE with its seeds, its
clusters with their keywords under them, and each cluster's page decisions; a Checks tab with every CE's automatic
checks; a Read me tab.

  python3 validation_sheet.py                 creates the sheet in the signed-in Drive and prints its link
  python3 validation_sheet.py --dry-run DIR   writes the payloads to DIR instead

Reads each CE's exported data (<out>/<data>.json, drawer.json, page_decisions.json) from ces.json and the pipeline's
run summary (snapshots/ce_<CE>/pipeline.json). Writes through the gws CLI; nothing is shared.
"""
import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPELINE = Path("/Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0/scripts/clusters_3_0")
GWS = "/opt/homebrew/bin/gws"
# The clusters prompt's negative keywords (pipeline negative_keywords.json): a clustered keyword containing one is a miss.
NEGATIVE = json.loads((PIPELINE / "negative_keywords.json").read_text())


def negatives(ce):
    return list(dict.fromkeys(NEGATIVE["all"] + NEGATIVE.get("by_ce", {}).get(str(ce), [])))


def negative_re(ce):
    return re.compile(r"\b(" + "|".join(re.escape(n) for n in negatives(ce)) + r")\b")


INTENT = {"TRANSACTIONAL": "Transactional", "PLANNING": "Planning", "INFORMATIONAL": "Informational"}
MAPPING = {"existing_page": "Existing page", "no_existing_page": "No existing page", "needs_review": "Not sure"}
REVIEW_HEAD = ["Right? (Y/N)", "Comment"]


def gws(*args, body=None):
    cmd = [GWS, *args] + (["--json", json.dumps(body, ensure_ascii=False)] if body is not None else [])
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"gws failed: {' '.join(args[:3])}: {out.stderr[-400:]}")
    text = out.stdout[out.stdout.find("{"):]
    return json.loads(text) if text else {}


def tab_name(name, used):
    base = re.sub(r"[\[\]\*\?/\\:]", " ", name)[:31].strip()
    n, t = 2, base
    while t in used:
        t = f"{base[:27]} ({n})"
        n += 1
    used.add(t)
    return t


def ce_rows(key, cfg, prompts_rev):
    out = HERE / cfg["out"]
    data = json.loads((out / cfg["data"]).read_text())
    drawer = json.loads((out / "drawer.json").read_text())["clusters"]
    research = data.get("research") or {"source": "eos", "seeds": [], "vendors": []}
    clusters = [c for c in data["clusters"]]
    by_id = {c["id"]: c for c in clusters}
    name_of = lambda cid: by_id[cid]["name"] if cid in by_id else ""
    own = research.get("source") != "eos" and research.get("seeds")
    rows, fmt = [], {"section": [], "cluster": [], "head": []}

    def add(r, kind=None):
        rows.append(r)
        if kind:
            fmt[kind].append(len(rows) - 1)

    add([data["ce"]["name"], f"CE {cfg.get('eos_id', key)}", data["ce"].get("host", cfg["host"]),
         "Keywords: our seeds prompt + Keyword Planner" if own else "Keywords: EOS's keyword list (the seeds prompt has not run for this CE)",
         f"Prompts doc revision {prompts_rev}", f"Built {date.today():%d %b %Y}"], "section")
    add([])
    add(["SEEDS" if own else "SEEDS: none yet for this CE"], "section")
    if own:
        add(["Seed", "Intent", "Searches / mo", "Status", "Led to cluster", *REVIEW_HEAD], "head")
        for s in sorted(research["seeds"], key=lambda s: -(s.get("vol") or 0)):
            add([s["kw"], s.get("category") or "", s.get("vol"), s.get("status") or "", name_of(s.get("cid")), "", ""])
    if research.get("vendors"):
        add([])
        add(["VENDOR SEEDS"], "section")
        add(["Vendor", "Source", "Searches / mo", "Products live", "Led to cluster", *REVIEW_HEAD], "head")
        for v in sorted(research["vendors"], key=lambda v: -(v.get("vol") or 0)):
            add([v["name"], v.get("source") or "", v.get("vol"), v.get("live"), name_of(v.get("cid")), "", ""])
    add([])
    add(["NEGATIVE KEYWORDS: a keyword containing one is left out of every cluster"], "section")
    add(["Negative keywords", "", "", "", "", *REVIEW_HEAD], "head")
    add([", ".join(negatives(cfg.get("eos_id", key))), "", "", "", "", "", ""])
    add([])
    add(["CLUSTERS, with their keywords under each"], "section")
    add(["Cluster / keyword", "Intent", "Searches / mo", "Focus keyword", "Page mapping (prompt)", "Existing page",
         "Separate page (prompt)", "Page type (prompt)", "Cluster right? (Y/N)", "Page type right? (Y/N)", "Comment"], "head")
    order = {"TRANSACTIONAL": 0, "PLANNING": 1, "INFORMATIONAL": 2}
    real = [c for c in clusters if not str(c["name"]).startswith("Other")]
    other = [c for c in clusters if str(c["name"]).startswith("Other")]
    for c in sorted(real, key=lambda c: (order.get(c["type"], 3), -(c.get("vol") or 0))) + other:
        ai = c.get("page_ai") or {}
        sep = ai.get("separate_page") or ("n/a: it has a page" if ai.get("mapping") == "existing_page" else "")
        add([c["name"], INTENT.get(c["type"], c["type"]), c.get("vol"), c.get("focus_kw") or "", MAPPING.get(ai.get("mapping"), ai.get("mapping") or ""),
             ai.get("existing_page_url") or "", sep, ai.get("page_type") or "", "", "", ""], "cluster")
        for w in sorted(drawer.get(c["id"], {}).get("keywords", []), key=lambda w: -(w.get("vol") or 0)):
            add(["    " + w["kw"], "", w.get("vol"), "", "", "", "", "", "", "", ""])
    return rows, fmt, data, drawer, research


def checks_row(key, cfg, data, drawer, research):
    clusters = [c for c in data["clusters"] if not str(c["name"]).startswith("Other")]
    kws = {}
    for c in data["clusters"]:
        for w in drawer.get(c["id"], {}).get("keywords", []):
            kws.setdefault(w["kw"], set()).add(c["id"])
    seeds = research.get("seeds") or []
    ce_id = cfg.get("eos_id", key)
    neg = negative_re(ce_id)
    pipe = PIPELINE / "snapshots" / f"ce_{ce_id}" / "pipeline.json"
    agree = ""
    if pipe.exists():
        ra = (json.loads(pipe.read_text()).get("cluster") or {}).get("run_agreement")
        agree = ", ".join(f"{x:.0%}" for x in ra) if isinstance(ra, list) else ra or ""
    focus_in = sum(1 for c in clusters if c.get("focus_kw") and c["focus_kw"] in {w["kw"] for w in drawer.get(c["id"], {}).get("keywords", [])})
    ai = [c.get("page_ai") or {} for c in clusters]
    no_page = [a for a in ai if a.get("mapping") == "no_existing_page"]
    pct = lambda a, b: f"{a / b:.0%}" if b else "n/a"
    return [data["ce"]["name"], cfg.get("eos_id", key),
            "yes" if research.get("source") != "eos" and seeds else "no (EOS list)",
            sum(1 for s in seeds if s.get("status", "").startswith("kept")), sum(1 for s in seeds if s.get("status") == "kept, no searches"),
            sum(1 for s in seeds if not s.get("status", "").startswith("kept")), len(research.get("vendors") or []),
            len(negatives(ce_id)), sum(1 for k in kws if neg.search(k)),
            len(clusters), len(kws), sum(1 for v in kws.values() if len(v) > 1), agree, pct(focus_in, len(clusters)),
            pct(sum(1 for a in ai if a.get("mapping")), len(ai)), pct(sum(1 for a in no_page if a.get("separate_page")), len(no_page)),
            pct(sum(1 for a in ai if a.get("page_type")), len(ai))]


CHECKS_HEAD = ["CE", "CE id", "Seeds prompt ran", "Seeds kept", "of which no searches", "Seeds left out (should be 0)",
               "Vendor seeds", "Negative keywords", "Clustered keywords containing one (should be 0)", "Clusters", "Keywords",
               "Keywords in 2+ clusters (should be 0)", "Clustering runs agreement", "Focus keyword inside its cluster",
               "Page mapping answered", "Separate page answered (clusters with no page)", "Page type answered"]
READ_ME = [["How to review"], [],
           ["Each CE has its own tab: its seeds, its vendor seeds, then every cluster with its keywords listed under it and the page prompts' answers for the cluster."],
           ["Mark Right? / Cluster right? / Page type right? with Y or N, and say why in Comment when it is N."],
           ["Cluster right?: the keywords under it are one intent, the name says that intent, and no keyword belongs in another cluster."],
           ["Page type right?: the page type the page_type prompt chose is the one content would build."],
           ["Page mapping: Existing page = the page_mapping prompt found a live page that covers it; No existing page = none does; Not sure = needs a person."],
           ["Separate page: the separate_page prompt's answer for clusters no existing page covers."],
           [], ["The Checks tab lists each CE's automatic checks; a value next to 'should be 0' that is not 0 is a problem to flag."],
           ["Searches / mo come from Google Keyword Planner, English, every location, Google Search."]]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", metavar="DIR")
    p.add_argument("--ces", help="comma-separated CE keys (ces.json); default every CE with a built page")
    a = p.parse_args()
    reg = json.loads((HERE / "ces.json").read_text())["ces"]
    if a.ces:
        reg = {k: reg[k] for k in a.ces.split(",")}
    manifest = PIPELINE / "prompts" / "eos" / "manifest.json"
    prompts_rev = json.loads(manifest.read_text()).get("synced_at", "")[:10] if manifest.exists() else "unknown"
    used, tabs, checks = {"Read me", "Checks"}, [], []
    for key, cfg in reg.items():
        if not (HERE / cfg["out"] / cfg["data"]).exists():
            continue
        rows, fmt, data, drawer, research = ce_rows(key, cfg, prompts_rev)
        tabs.append((tab_name(data["ce"]["name"], used), rows, fmt))
        checks.append(checks_row(key, cfg, data, drawer, research))
    all_tabs = [("Read me", READ_ME, {"section": [0]}), ("Checks", [CHECKS_HEAD] + checks, {"head": [0]})] + tabs
    if a.dry_run:
        d = Path(a.dry_run)
        d.mkdir(parents=True, exist_ok=True)
        for t, rows, fmt in all_tabs:
            (d / f"{re.sub(r'[^A-Za-z0-9]+', '_', t)}.json").write_text(json.dumps({"rows": rows, "fmt": fmt}, ensure_ascii=False, indent=0))
        print(f"dry run: {len(all_tabs)} tabs written to {d}")
        return
    sheet = gws("sheets", "spreadsheets", "create", body={
        "properties": {"title": f"Clusters 3.0 · content check · {date.today():%d %b %Y}"},
        "sheets": [{"properties": {"title": t, "gridProperties": {"frozenRowCount": 0 if t == "Read me" else 1}}} for t, _, _ in all_tabs]})
    sid = sheet["spreadsheetId"]
    ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in sheet["sheets"]}
    for t, rows, _ in all_tabs:
        width = max((len(r) for r in rows), default=1)
        vals = [[("" if v is None else v) for v in r] + [""] * (width - len(r)) for r in rows]
        gws("sheets", "spreadsheets", "values", "update",
            "--params", json.dumps({"spreadsheetId": sid, "range": f"'{t}'!A1", "valueInputOption": "RAW"}), body={"values": vals})
    reqs = []
    for t, rows, fmt in all_tabs:
        g = ids[t]
        for r in fmt.get("section", []):
            reqs.append({"repeatCell": {"range": {"sheetId": g, "startRowIndex": r, "endRowIndex": r + 1},
                                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 11}}}, "fields": "userEnteredFormat.textFormat"}})
        for r in fmt.get("head", []):
            reqs.append({"repeatCell": {"range": {"sheetId": g, "startRowIndex": r, "endRowIndex": r + 1},
                                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": .94, "green": .94, "blue": .94}}},
                                        "fields": "userEnteredFormat(textFormat,backgroundColor)"}})
        for r in fmt.get("cluster", []):
            reqs.append({"repeatCell": {"range": {"sheetId": g, "startRowIndex": r, "endRowIndex": r + 1},
                                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": .95, "green": .93, "blue": 1}}},
                                        "fields": "userEnteredFormat(textFormat,backgroundColor)"}})
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": g, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                                                   "properties": {"pixelSize": 320 if t != "Read me" else 900}, "fields": "pixelSize"}})
    for i in range(0, len(reqs), 400):
        gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": sid}), body={"requests": reqs[i:i + 400]})
    print(f"https://docs.google.com/spreadsheets/d/{sid}/edit")


if __name__ == "__main__":
    main()
