"""Current mapping: one "Map <ce> · <name>" tab per CE in the bake-off sheet, side by side in three blocks:
  A-H  clusters: parent, intent, keywords, focus keyword and its volume, paid clicks, organic impressions, definition
  J-L  keywords: every keyword of the CE's current list with its volume and cluster
  N-R  searches: paid searches (clicks) and organic queries (impressions) with the cluster Jev placed them in and its
       confidence; the top 2,000 of each by weight
Sources per CE are the lists and Jev runs the scorecard uses (validation_plan.md). Re-running replaces these tabs only.
Usage: python mapping_tabs.py [--sheet-id ID]
"""
import argparse
import json

import pandas as pd

import runlib
from upload_workbook import gws, write

SHEET = "1Q1vxM04_OUR3McrkI2ws6dDbezXKiUZ2aXlzu6aM5gc"
S, R = runlib.SNAPSHOTS, runlib.RUNS
TOP = 2000
V1 = "jev_classify_20261030_validation_v1"
# ce: (list label, cluster snapshot, descriptions, keyword source, paid run(s), organic run(s))
ATTR = ("EOS names, keywords placed by the algorithm", "20261103_hybrid_11ce_v2", None, "hybrid",
        f"20261030-110828_{V1}", f"20261030-110150_{V1}")
V22 = ("Prompt v2.2, keywords placed by Jev", "20261104_validation_v22", "20261104_validation_v22",
       "20261104-143921_jev_classify_20261104_validation_v22", "20261104-144333_jev_classify_20261104_validation_v22",
       "20261104-144833_jev_classify_20261104_validation_v22")
V23 = ("Prompt v2.3, keywords placed by Jev", "20261104_validation_v23", "20261104_validation_v23",
       "20261104-163549_jev_classify_20261104_validation_v23", "20261104-163625_jev_classify_20261104_validation_v23",
       "20261104-163816_jev_classify_20261104_validation_v23")
CES = {"189": ("EOS names + seed clusters, keywords placed by the algorithm", "20261103_hybrid_11ce_v2", "desc189", "hybrid",
               "20261103-171359_jev_classify_20261030_validation_v1", "20261103-171421_jev_classify_20261030_validation_v1"),
       "325": ATTR, "243": ATTR, "257": ATTR, "3945": V22, "2743": V22, "261": V22, "2010": V22, "2640": V22,
       "1695": V23, "3176": V23}


def run_file(run, ce):
    f = R / run / "outputs" / f"assignments_{ce}.csv"
    return pd.read_csv(f, low_memory=False) if f.exists() else None


def tab_rows(ce, spec, name):
    label, snap, desc_src, kw_src, paid_run, org_run = spec
    meta = pd.read_csv(S / snap / "cluster_keywords.csv", dtype={"ce": str})
    meta = meta[(meta["ce"] == ce) & ~meta["name"].str.startswith("Other (")]
    if desc_src == "desc189":
        desc = pd.read_csv(runlib.HERE / "cluster_descriptions_189.csv")
    elif desc_src:
        desc = pd.read_csv(S / desc_src / "cluster_descriptions.csv", dtype={"ce": str})
        desc = desc[desc["ce"] == ce]
    else:
        desc = pd.DataFrame(columns=["name", "description"])
    dmap = dict(zip(desc["name"], desc["description"]))
    if kw_src == "hybrid":
        kw = meta[["kw", "vol", "name"]].rename(columns={"kw": "keyword", "name": "cluster"})
    else:
        a = run_file(kw_src, ce)
        kw = a[["term", "vol", "D_name"]].rename(columns={"term": "keyword", "D_name": "cluster"})
    kw = kw.drop_duplicates("keyword").sort_values(["cluster", "vol"], ascending=[True, False], na_position="last")
    paid, org = run_file(paid_run, ce), run_file(org_run, ce)
    searches = []
    for src, a, w in (("paid", paid, "clicks"), ("organic", org, "impressions")):
        if a is None or w not in a:
            continue
        a = a[a[w].fillna(0) > 0].sort_values(w, ascending=False).head(TOP)
        searches.append(pd.DataFrame({"search": a["term"], "source": src, "weight": a[w], "cluster": a["D_name"], "prob": a["prob"]}))
    s = pd.concat(searches) if searches else pd.DataFrame(columns=["search", "source", "weight", "cluster", "prob"])
    names = list(dict.fromkeys(meta["name"]))
    parent = meta.drop_duplicates("name").set_index("name")["parent"] if "parent" in meta else pd.Series(dtype=str)
    intent = meta.drop_duplicates("name").set_index("name")["t"]
    clusters = []
    for n in names:
        k = kw[kw["cluster"] == n]
        top = k.sort_values("vol", ascending=False).head(1)
        clusters.append([n, "" if pd.isna(parent.get(n)) else parent.get(n, ""), intent.get(n, ""), len(k),
                         top["keyword"].iloc[0] if len(top) else "", int(top["vol"].iloc[0]) if len(top) and pd.notna(top["vol"].iloc[0]) else "",
                         int(s.loc[(s["source"] == "paid") & (s["cluster"] == n), "weight"].sum()),
                         int(s.loc[(s["source"] == "organic") & (s["cluster"] == n), "weight"].sum()), dmap.get(n, "")])
    clusters.append(["No cluster", "", "", int(kw["cluster"].isna().sum()), "", "",
                     int(s.loc[(s["source"] == "paid") & s["cluster"].isna(), "weight"].sum()),
                     int(s.loc[(s["source"] == "organic") & s["cluster"].isna(), "weight"].sum()), "searches Jev placed nowhere"])
    head = [[f"{name} (CE {ce}) · {label}"] + [""] * 17,
            ["Cluster", "Parent", "Intent", "Keywords", "Focus keyword", "Focus volume / mo", "Paid clicks (90d)",
             "Organic impressions (90d)", "Definition", "", "Keyword", "Volume / mo", "Cluster", "", "Search", "Paid or organic",
             "Clicks / impressions", "Cluster (Jev)", "Confidence"]]
    kw_rows = [[r.keyword, "" if pd.isna(r.vol) else int(r.vol), r.cluster if pd.notna(r.cluster) else "No cluster"] for r in kw.itertuples()]
    s_rows = [[r.search, r.source, int(r.weight), r.cluster if pd.notna(r.cluster) else "No cluster",
               "" if pd.isna(r.prob) else round(float(r.prob), 2)] for r in s.itertuples()]
    n = max(len(clusters), len(kw_rows), len(s_rows))
    body = []
    for i in range(n):
        c = clusters[i] if i < len(clusters) else [""] * 9
        k = kw_rows[i] if i < len(kw_rows) else [""] * 3
        q = s_rows[i] if i < len(s_rows) else [""] * 5
        body.append(c + [""] + k + [""] + q)
    return head + body


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sheet-id", default=SHEET)
    a = p.parse_args()
    names = pd.read_csv(S / "20261030_validation_v1" / "ce_names.csv", dtype={"ce": str}).set_index("ce")["name"]
    meta = gws("sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": a.sheet_id, "fields": "sheets.properties(sheetId,title)"}))
    tab_ids = {t["properties"]["title"]: t["properties"]["sheetId"] for t in meta["sheets"]}
    tabs = {}
    for ce, spec in CES.items():
        short = names.get(ce, ce).replace("Tickets", "").replace("Cruises", "").strip()[:22]
        tabs[f"Map {ce} · {short}"] = tab_rows(ce, spec, names.get(ce, ce))
    new = [t for t in tabs if t not in tab_ids]
    if new:
        res = gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": a.sheet_id}), body={"requests": [
            {"addSheet": {"properties": {"title": t, "gridProperties": {"frozenRowCount": 2}}}} for t in new]})
        tab_ids.update({r["addSheet"]["properties"]["title"]: r["addSheet"]["properties"]["sheetId"] for r in res["replies"]})
    fmt = []
    for tab, rows in tabs.items():
        sid = tab_ids[tab]
        gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": a.sheet_id}), body={"requests": [
            {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"rowCount": len(rows) + 10, "columnCount": 20, "frozenRowCount": 2}},
                                       "fields": "gridProperties(rowCount,columnCount,frozenRowCount)"}}]})
        write(a.sheet_id, tab, rows)
        fmt += [{"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 2},
                                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}}, "fields": "userEnteredFormat.textFormat"}},
                {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 19},
                                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93}}}, "fields": "userEnteredFormat.backgroundColor"}},
                {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 8, "endIndex": 9},
                                               "properties": {"pixelSize": 380}, "fields": "pixelSize"}},
                {"autoResizeDimensions": {"dimensions": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 8}}},
                {"autoResizeDimensions": {"dimensions": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 10, "endIndex": 19}}}]
        print(f"{tab}: {len(rows) - 2} rows")
    gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": a.sheet_id}), body={"requests": fmt})
    print(f"https://docs.google.com/spreadsheets/d/{a.sheet_id}/edit")


if __name__ == "__main__":
    main()
