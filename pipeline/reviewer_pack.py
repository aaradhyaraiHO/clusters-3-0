"""Reviewer pack: one tab per CE in the bake-off sheet where BGM, Perf and Krupa correct the drafted test labels, plus a
"Review · cluster lists" tab to judge each cluster list itself.

Each CE tab lists the CE's current blind test set (paid and organic searches, weight = paid clicks or organic
impressions) with the drafted label and an empty "Reviewer label" (dropdown of that CE's clusters + NONE). Jev's answer
is not shown, so reviewers are not anchored on the system being tested; rows where the draft and Jev disagree are marked
"check first". A tab whose Reviewer label column already holds entries is never overwritten (use --force to replace).

Usage: python reviewer_pack.py [--sheet-id ID] [--force]
"""
import argparse
import json

import pandas as pd

import runlib
from upload_workbook import gws, write

SHEET = "1Q1vxM04_OUR3McrkI2ws6dDbezXKiUZ2aXlzu6aM5gc"
S, R = runlib.SNAPSHOTS, runlib.RUNS
# ce: (test-set folder, cluster snapshot, descriptions file, paid Jev runs, organic Jev runs)
V1_PAID = "20261030-105755_jev_classify_20261030_validation_v1,20261030-110828_jev_classify_20261030_validation_v1"
V1_ORG = "20261030-110139_jev_classify_20261030_validation_v1,20261030-110150_jev_classify_20261030_validation_v1"
V22 = ("test_sets_v22", "20261104_validation_v22", None, "20261104-144333_jev_classify_20261104_validation_v22",
       "20261104-144833_jev_classify_20261104_validation_v22")
V23 = ("test_sets_v23", "20261104_validation_v23", None, "20261104-163625_jev_classify_20261104_validation_v23",
       "20261104-163816_jev_classify_20261104_validation_v23")
CES = {"189": ("test_sets", "20261030_validation_v1", "cluster_descriptions_189.csv", V1_PAID, V1_ORG),
       "325": ("test_sets", "20261030_validation_v1", None, V1_PAID, V1_ORG),
       "243": ("test_sets", "20261030_validation_v1", None, V1_PAID, V1_ORG),
       "257": ("test_sets", "20261030_validation_v1", None, V1_PAID, V1_ORG),
       "3945": V22, "2743": V22, "261": V22, "2010": V22, "2640": V22, "1695": V23, "3176": V23}
HEADER = ["#", "Search", "Source", "Clicks (paid) / impressions (organic)", "Draft label (AI)", "Priority",
          "Reviewer label", "Reviewer note"]
LIST_HEADER = ["CE", "CE name", "Cluster", "Parent", "Intent", "Definition", "Example keywords", "List version",
               "Reviewer verdict", "Reviewer note"]
VERDICTS = ["OK", "Merge with another", "Split", "Rename", "Remove", "Wrong intent"]


def jev_answers(runs, ce):
    out = {}
    for r in runs.split(","):
        f = R / r / "outputs" / f"assignments_{ce}.csv"
        if f.exists():
            a = pd.read_csv(f, low_memory=False)
            out.update({t: n for t, n in zip(a["term"], a["D_name"]) if t not in out})
    return out


def agrees(label, pick):
    parts = str(label).split("|")
    return (pd.notna(pick) and pick in parts) or (pd.isna(pick) and "NONE" in parts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sheet-id", default=SHEET)
    p.add_argument("--force", action="store_true", help="overwrite tabs that already hold reviewer labels")
    a = p.parse_args()
    names = pd.read_csv(S / "20261030_validation_v1" / "ce_names.csv", dtype={"ce": str}).set_index("ce")["name"]
    meta = gws("sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": a.sheet_id, "fields": "sheets.properties(sheetId,title)"}))
    tab_ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    tabs, lists, options = {}, [LIST_HEADER], {}
    for ce, (tdir, snap, desc_file, paid_runs, org_runs) in CES.items():
        kw = pd.read_csv(S / snap / "cluster_keywords.csv", dtype={"ce": str})
        kw = kw[(kw["ce"] == ce) & ~kw["name"].str.startswith("Other (")]
        desc_path = runlib.HERE / desc_file if desc_file else S / snap / "cluster_descriptions.csv"
        desc = pd.read_csv(desc_path, dtype={"ce": str}) if desc_path.exists() else pd.DataFrame(columns=["ce", "name", "description"])
        desc = desc[desc["ce"] == ce] if "ce" in desc else desc
        dmap = dict(zip(desc["name"], desc["description"]))
        version = {"test_sets": "EOS list, algorithm keywords", "test_sets_v22": "Prompt v2.2", "test_sets_v23": "Prompt v2.3"}[tdir]
        for name, g in kw.groupby("name", sort=False):
            ex = g.sort_values("vol", ascending=False)["kw"].drop_duplicates().head(5)
            parent = g["parent"].iloc[0] if "parent" in g and pd.notna(g["parent"].iloc[0]) else ""
            lists.append([ce, names.get(ce, ce), name, parent, g["t"].iloc[0], dmap.get(name, ""), "; ".join(ex), version, "", ""])
        options[ce] = list(dict.fromkeys(kw["name"])) + ["NONE"]
        t = pd.read_csv(runlib.HERE / tdir / f"{ce}.csv")
        paid, org = jev_answers(paid_runs, ce), jev_answers(org_runs, ce)
        t["pick"] = [(paid if s == "paid" else org).get(term) for term, s in zip(t["term"], t["source"])]
        t["priority"] = ["" if agrees(l, p) else "check first" for l, p in zip(t["label"], t["pick"])]
        t = t.sort_values(["priority", "weight"], ascending=[False, False])
        rows = [HEADER] + [[i + 1, r.term, r.source, int(r.weight), r.label, r.priority, "", ""] for i, r in enumerate(t.itertuples())]
        short = names.get(ce, ce).replace("Tickets", "").replace("Cruises", "").strip()[:22]
        tabs[f"Review {ce} · {short}"] = (ce, rows)
    all_tabs = {"Review · cluster lists": (None, lists), "Review · options": (None, None), **tabs}
    new = [t for t in all_tabs if t not in tab_ids]
    if new:
        res = gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": a.sheet_id}), body={"requests": [
            {"addSheet": {"properties": {"title": t, "gridProperties": {"frozenRowCount": 1}, "hidden": t == "Review · options"}}} for t in new]})
        tab_ids.update({r["addSheet"]["properties"]["title"]: r["addSheet"]["properties"]["sheetId"] for r in res["replies"]})
    # Dropdown sources: one column per CE on a hidden tab (a dropdown needs one contiguous range)
    order = list(options)
    width = max(len(v) for v in options.values())
    opt_rows = [order] + [[options[ce][i] if i < len(options[ce]) else "" for ce in order] for i in range(width)]
    requests = []
    for tab, (ce, rows) in all_tabs.items():
        if rows is None:
            rows = opt_rows
        if tab.startswith("Review ") and ce and not a.force:
            got = gws("sheets", "spreadsheets", "values", "get", "--params", json.dumps({"spreadsheetId": a.sheet_id, "range": f"'{tab}'!G2:G"}))
            if isinstance(got, dict) and any(v and v[0] for v in got.get("values", [])):
                print(f"{tab}: has reviewer labels, left as is")
                continue
        requests.append({"updateSheetProperties": {"properties": {"sheetId": tab_ids[tab], "gridProperties": {
            "rowCount": len(rows) + 10, "columnCount": max(12, max(len(r) for r in rows))}}, "fields": "gridProperties(rowCount,columnCount)"}})
        gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": a.sheet_id}), body={"requests": requests[-1:]})
        write(a.sheet_id, tab, rows)
        sid = tab_ids[tab]
        if ce:
            col = chr(ord("A") + order.index(ce))
            requests.append({"setDataValidation": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": len(rows), "startColumnIndex": 6, "endColumnIndex": 7},
                             "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"='Review · options'!${col}$2:${col}${len(options[ce]) + 1}"}]},
                                      "strict": True, "showCustomUi": True}}})
            requests.append({"addConditionalFormatRule": {"index": 0, "rule": {"ranges": [{"sheetId": sid, "startRowIndex": 1, "endRowIndex": len(rows), "startColumnIndex": 0, "endColumnIndex": 8}],
                             "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=$F2="check first"'}]},
                                             "format": {"backgroundColor": {"red": 1, "green": 0.95, "blue": 0.8}}}}}})
        if tab == "Review · cluster lists":
            requests.append({"setDataValidation": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": len(rows), "startColumnIndex": 8, "endColumnIndex": 9},
                             "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in VERDICTS]}, "strict": True, "showCustomUi": True}}})
        if tab != "Review · options":
            requests.append({"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                             "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93}}},
                             "fields": "userEnteredFormat(textFormat,backgroundColor)"}})
            requests.append({"autoResizeDimensions": {"dimensions": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 8}}})
        print(f"{tab}: {len(rows) - 1} rows")
    fmt = [r for r in requests if "updateSheetProperties" not in r]
    if fmt:
        gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": a.sheet_id}), body={"requests": fmt})
    print(f"https://docs.google.com/spreadsheets/d/{a.sheet_id}/edit")


if __name__ == "__main__":
    main()
