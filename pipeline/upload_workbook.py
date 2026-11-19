"""Upload the export_workbook.py CSVs into one Google Sheet with the gws CLI (creates it, or refreshes --sheet-id).

Usage: python upload_workbook.py [--sheet-id <id>]
"""
import argparse
import csv
import json
import subprocess
from pathlib import Path

WB = Path(__file__).parent / ".env-clusters" / "workbook"
GWS = "/opt/homebrew/bin/gws"
CHUNK = 2000
TABS = [("README", None), ("Hit rates", "hit_rates.csv"), ("Clusters", "clusters.csv"), ("Keywords", "keywords.csv"),
        ("Search terms", "search_terms.csv"), ("Demand capture", "capture.csv"), ("Uncaptured searches", "uncaptured.csv"),
        ("Cluster ad-group coverage", "cluster_adgroups.csv"), ("Ad groups", "adgroups.csv"), ("Ad group x cluster", "adgroup_x_cluster.csv")]
README = [
    ["Clusters 3.0: clustering bake-off workbook (29 Oct 2026)"],
    [""],
    ["What this is", "Every cluster, keyword and paid search term from the bake-off, for every CE and every approach, with the hit rates. Built by scripts/clusters_3_0/export_workbook.py from frozen snapshots and versioned runs (branch worktree-clusters-3-0)."],
    [""],
    ["Tab", "Contents"],
    ["Hit rates", "One row per CE x approach: keyword and cluster counts, largest cluster's share of keywords, and the paid-click hit rates (all searches and unseen searches). Rows starting 'Experiment:' are earlier Vatican versions."],
    ["Clusters", "One row per cluster: approach, name, intent type, keyword count, top keyword and volume, identifiers, paid clicks and spend mapped to it, its share of the CE's paid clicks, and the intent most of those clicks have."],
    ["Keywords", "One row per CE x keyword: its volume and the cluster it sits in under each approach (blank = the approach does not have that keyword)."],
    ["Search terms", "One row per CE x paid search term (30 Jul to 27 Oct 2026, 2+ clicks): clicks, spend, the search's intent, the cluster it maps to under each approach, and whether it counts as unseen."],
    ["Demand capture", "Vatican only so far, on the hybrid clusters; monthly = 30 Jul to 27 Oct 2026 divided by 3. Keyword Planner volume counts one figure per spelling-variant family and each bucketed volume of 10,000+ once per cluster (Keyword Planner gives 'sistine chapel' and nine variants the same 450,000). Paid columns are complete Google Ads keyword totals (they reconcile with the account), spread over clusters by the searches each keyword actually served. Demand = the largest of Keyword Planner volume, paid eligible impressions (impressions / impression share) and organic impressions, with the source named. Paid capture = paid impressions / demand (equal to impression share when eligible impressions set demand). Organic click capture = organic clicks / demand. Value at stake = missed impressions x conversion value per impression, an upper bound. 'No cluster' holds searches the mapper could not place."],
    ["Uncaptured searches", "Paid searches (3+ impressions) and organic queries that no cluster takes, or that land in Other, grouped by spelling variants and then by meaning, largest first. Each is a missing cluster, a translation the mapper missed, or off-topic demand."],
    [""],
    ["Cluster ad-group coverage", "Vatican only. One row per cluster: which ad groups serve its paid clicks, from complete keyword totals split by the searches each keyword served. Ad groups are named '<intent> - <match> - <language> - <sub-theme>' and repeated in every language and region campaign, so coverage is given per theme (Tickets, Generic, Tours, Tickets · Sistine Chapel, ...) and per single ad group. Reach = the top theme's (or ad group's) share of the cluster's clicks; focus = the cluster's share of that theme's (or ad group's) clicks. Dedicated = focus 50%+; Shared = served only by themes mostly about other clusters; White space = under 5 paid clicks a month."],
    ["Ad groups", "One row per active ad group: clicks, spend, CM1 (Google-attributed), Paid ROI, its main and second cluster with their share of its clicks, how many clusters it serves (5%+ of its clicks), Focused (main cluster 50%+) or Mixed."],
    ["Ad group x cluster", "One row per ad group x cluster pair with impressions, clicks, spend and CM1 per month and each side's share. The 'Theme x cluster' pivot reads from it."],
    [""],
    ["Approach", "What it is"],
    ["EOS prompts", "EOS keyword research clusters as they are: from the EOS database for Vatican, Park Guell, Eiffel, Great Barrier Reef and Milford Sound; from Krupa's KWR Testing sheets for the other six."],
    ["Cluster Tool (prototype prompts)", "The prototype Cluster Tool's output from Krupa's KWR Testing sheets (7 CEs)."],
    ["EOS + hand-tuned repair", "28 Oct rebuild of EOS clusters for Vatican and Park Guell with hand-written rules (competitor filter, keyword moves, retyping, seeded clusters)."],
    ["Hybrid (EOS list + algorithm assignment)", "hybrid_assign.py: EOS's clusters stay fixed (names, intents, granularity); the algorithm places every research keyword and the top 400 paid terms. Spelling variants follow their siblings' EOS cluster, name-only searches go to the head cluster, everything else joins the cluster its 7 most similar EOS-placed families vote for. Vatican only so far."],
    ["Algorithm, new-CE", "graph_cluster.py on the research keywords only: variant families, competitor filter, meaning + shared-word graph, Louvain groups, generated identifiers. No CE-specific setup."],
    ["Algorithm, new-CE + SERP", "As above, plus shared Google top-10 results (SerpApi) for the top 100 keyword families. Moulin Rouge and Eiffel only."],
    ["Algorithm, existing-CE (+400 paid terms)", "As new-CE, with the CE's top 400 paid search terms added to the keyword list."],
    [""],
    ["Measure", "Definition"],
    ["Right-intent %", "Share of paid clicks landing in a cluster whose main intent matches the search's own intent (multilingual intent word list). Unmapped clicks count as wrong."],
    ["Landing %", "Share of name-only and ticket searches landing in the CE's landing cluster."],
    ["No cluster %", "Share of paid clicks the mapper cannot place in any cluster."],
    ["Unseen", "Searches outside the CE's EOS research keywords and its top 400 paid terms, the same set for every approach. Shows whether an approach generalises beyond what it was given."],
    ["Mapper", "Every approach is scored with the same search-term mapper (identifiers, then fuzzy text, then meaning; column D0.85) and no CE-specific rules."],
    [""],
    ["Caveats", "Unseen samples are small for the Great Barrier Reef (832 clicks), Milford Sound (2,281) and Montserrat (678); Sydney has none. Seine, Harry Potter walking tours and Cappadocia have no paid data, so only their clusters are shown. The Vatican experiment rows were scored on an earlier search-term pull, so their unseen click base differs slightly (89,512 vs 84,311)."],
]


def gws(*args, body=None):
    cmd = [GWS, *args]
    if body is not None:
        cmd += ["--json", json.dumps(body, ensure_ascii=False)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"gws failed: {out.stderr[-2000:] or out.stdout[-2000:]}")
    return json.loads(out.stdout) if out.stdout.strip().startswith("{") else out.stdout


def resize(sheet_id, tab_ids, tab, rows):
    # New tabs default to a 1,000 x 26 grid and writes past it are rejected, so size each tab to its data first
    gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": sheet_id}), body={"requests": [{
        "updateSheetProperties": {"properties": {"sheetId": tab_ids[tab], "gridProperties": {
            "rowCount": len(rows) + 10, "columnCount": max(26, max(len(r) for r in rows))}},
            "fields": "gridProperties(rowCount,columnCount)"}}]})


def write(sheet_id, tab, rows):
    # A narrower or shorter re-export would otherwise leave the previous upload's cells beside and below it
    gws("sheets", "spreadsheets", "values", "clear", "--params", json.dumps({"spreadsheetId": sheet_id, "range": f"'{tab}'"}), body={})
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start:start + CHUNK]
        gws("sheets", "spreadsheets", "values", "update",
            "--params", json.dumps({"spreadsheetId": sheet_id, "range": f"'{tab}'!A{start + 1}", "valueInputOption": "USER_ENTERED"}),
            body={"values": chunk})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sheet-id")
    p.add_argument("--tabs", nargs="*", help="only these tabs (default all)")
    a = p.parse_args()
    if a.sheet_id:
        sheet_id = a.sheet_id
    else:
        res = gws("sheets", "spreadsheets", "create", body={
            "properties": {"title": "Clusters 3.0 · clustering bake-off (29 Oct 2026)"},
            "sheets": [{"properties": {"title": t, "gridProperties": {"frozenRowCount": 1 if f else 0}}} for t, f in TABS]})
        sheet_id = res["spreadsheetId"]
        print(f"created {sheet_id}")
    meta = gws("sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": sheet_id, "fields": "sheets.properties(sheetId,title)"}))
    tab_ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    missing = [t for t, _ in TABS if t not in tab_ids and (not a.tabs or t in a.tabs)]
    if missing:
        res = gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": sheet_id}), body={"requests": [
            {"addSheet": {"properties": {"title": t, "gridProperties": {"frozenRowCount": 1}}}} for t in missing]})
        tab_ids.update({r["addSheet"]["properties"]["title"]: r["addSheet"]["properties"]["sheetId"] for r in res["replies"]})
    for tab, f in TABS:
        if a.tabs and tab not in a.tabs:
            continue
        rows = README if f is None else [r for r in csv.reader((WB / f).open(encoding="utf-8"))]
        resize(sheet_id, tab_ids, tab, rows)
        write(sheet_id, tab, rows)
        print(f"{tab}: {len(rows)} rows")
    print(f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit")


if __name__ == "__main__":
    main()
