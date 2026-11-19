"""Add a Summary tab (headline lines, live head-to-head formulas, CE x approach pivots) to the bake-off workbook and tidy
the raw tabs. Rerunnable: the Summary tab is rebuilt each time.

Usage: python format_workbook.py --sheet-id <id>
"""
import argparse
import json

import pandas as pd

from upload_workbook import WB, gws

SUMMARY = [
    "Existing CEs: the algorithm with the CE's top 400 paid terms puts the most paid clicks in the right-intent cluster on all 8 CEs with paid data (Vatican 81.0% vs EOS 69.9%).",
    "It holds up on unseen searches too: ahead of EOS on 6 of 7 CEs by 7 to 28 points (Montserrat 79.1% vs 51.3%). Eiffel is the exception (69.3% vs 72.8%).",
    "New CEs (research keywords only): EOS stays ahead on balance. The algorithm wins Vatican and Milford Sound on unseen searches but trails on Park Güell (37.9% vs 62.6%) and Moulin Rouge (61.7% vs 79.0%).",
    "The prototype Cluster Tool trails EOS on all 4 CEs where both exist (Eiffel 65.2% vs 78.6%). Adding Google top-10 overlap (SERP) changed cluster shapes but not scores.",
    "Best so far (Vatican only): the hybrid keeps EOS's cluster list, adds an official-site cluster and lets the algorithm place keywords and paid terms. It scores 92.3% / 79.7% unseen and keeps every EOS intent. A hand check puts about 8% of top-40 clicks in the wrong cluster (16% before the fixes). Next: the other 7 CEs.",
]
HOW_TO_READ = ("Right-intent % = share of paid clicks landing in a cluster whose main intent matches the search. Unseen = searches outside the CE's "
               "research keywords and top 400 paid terms. These scores measure search-term mapping, not page fit, until Krupa's answer keys are in. "
               "Everything below reads live from the Hit rates tab.")
# (title, Hit rates column offset, number format, higher is better)
PIVOTS = [
    ("Right-intent % — all paid searches", 8, "0.0", True),
    ("Right-intent % — unseen searches", 12, "0.0", True),
    ("Landing % — name-only and ticket searches in the landing cluster", 9, "0.0", True),
    ("No cluster % — paid clicks the mapper could not place", 10, "0.0", False),
    ("Clusters per CE", 4, "0", None),
    ("Largest cluster's share of keywords %", 5, "0.0", False),
]
PIVOT_ROWS = 17
GREEN, RED, WHITE = {"red": 0.72, "green": 0.88, "blue": 0.80}, {"red": 0.96, "green": 0.78, "blue": 0.76}, {"red": 1, "green": 1, "blue": 1}
# (short label, Approach value in Hit rates); the first is the baseline the gap columns subtract
H2H = [("EOS", "EOS prompts"), ("Algorithm new-CE", "Algorithm, new-CE"), ("Algorithm existing-CE", "Algorithm, existing-CE (+400 paid terms)"),
       ("Hybrid", "Hybrid (EOS list + algorithm assignment)")]
H2H_COLS = (["CE"] + [f"{label} (all)" for label, _ in H2H] + [f"{label} (unseen)" for label, _ in H2H]
            + [f"{label} minus EOS (unseen)" for label, _ in H2H[1:]])
WIDE = len(H2H_COLS)
# (header, Clusters tab column, pixel width, number format). Columns are positional against export_workbook.py's clusters.csv
# order: D Cluster, E Intent type, F Keywords, G Volume, M % of CE paid clicks. SORT(..., 4, ...) sorts on Volume.
CE_VIEW_COLS = [("Cluster", "D", 230, None), ("Intent", "E", 115, None), ("Keywords", "F", 75, "0"), ("Volume", "G", 95, "#,##0"),
                ("% of paid clicks", "M", 80, "0.0")]
CE_VIEW_HEADER_ROW = 5


def grid(sid, r0, r1, c0, c1):
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def scale(rng, higher_better, midpoint=None):
    lo, hi = (RED, GREEN) if higher_better else (GREEN, RED)
    mid = {"type": "NUMBER", "value": str(midpoint)} if midpoint is not None else {"type": "PERCENTILE", "value": "50"}
    return {"addConditionalFormatRule": {"index": 0, "rule": {"ranges": [rng], "gradientRule": {
        "minpoint": {"type": "MIN", "color": lo}, "midpoint": {**mid, "color": WHITE}, "maxpoint": {"type": "MAX", "color": hi}}}}}


def cell_fmt(rng, fmt, fields):
    return {"repeatCell": {"range": rng, "cell": {"userEnteredFormat": fmt}, "fields": fields}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sheet-id", required=True)
    sheet_id = p.parse_args().sheet_id
    params = json.dumps({"spreadsheetId": sheet_id})

    def batch(requests):
        return gws("sheets", "spreadsheets", "batchUpdate", "--params", params, body={"requests": requests})

    meta = gws("sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": sheet_id, "fields": "sheets.properties(sheetId,title,gridProperties)"}))
    tabs = {s["properties"]["title"]: s["properties"] for s in meta["sheets"]}
    if "Summary" in tabs:
        batch([{"deleteSheet": {"sheetId": tabs["Summary"]["sheetId"]}}])
    res = batch([{"addSheet": {"properties": {"title": "Summary", "index": 0, "gridProperties": {"rowCount": 160, "columnCount": WIDE + 2, "hideGridlines": True}}}}])
    sid = res["replies"][0]["addSheet"]["properties"]["sheetId"]
    hit_id = tabs["Hit rates"]["sheetId"]

    hits = pd.read_csv(WB / "hit_rates.csv")
    main = hits[~hits["Approach"].str.startswith("Experiment")]
    approaches = sorted(main["Approach"].unique())
    paid_ces = sorted(main.loc[main["Right-intent % (all)"].notna(), "CE name"].unique())

    values = [["Clusters 3.0 · clustering bake-off — summary"], [""]] + [[f"{i}. {line}"] for i, line in enumerate(SUMMARY, 1)]
    values += [[""], [HOW_TO_READ], [""], ["Head-to-head with EOS (right-intent %)"], H2H_COLS]
    h2h_top = len(values)
    for i, ce in enumerate(paid_ces):
        r = h2h_top + i + 1

        def avg(col, approach, r=r):
            return f"=IFERROR(AVERAGEIFS('Hit rates'!${col}:${col},'Hit rates'!$B:$B,$A{r},'Hit rates'!$C:$C,\"{approach}\"),\"\")"
        n = len(H2H)
        base = col_letter(1 + n)
        gaps = [f'=IF(OR({base}{r}="",{col_letter(1 + n + k)}{r}=""),"",{col_letter(1 + n + k)}{r}-{base}{r})' for k in range(1, n)]
        values.append([ce] + [avg("I", a) for _, a in H2H] + [avg("M", a) for _, a in H2H] + gaps)
    h2h_end = len(values)
    pivot_top = h2h_end + 2
    for k, (title, _, _, _) in enumerate(PIVOTS):
        r = pivot_top + k * PIVOT_ROWS
        values += [[""]] * (r - len(values)) + [[title]]
    gws("sheets", "spreadsheets", "values", "update", "--params",
        json.dumps({"spreadsheetId": sheet_id, "range": "'Summary'!A1", "valueInputOption": "USER_ENTERED"}), body={"values": values})

    bold = {"textFormat": {"bold": True}}
    reqs = [
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 230}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": WIDE}, "properties": {"pixelSize": 115}, "fields": "pixelSize"}},
        cell_fmt(grid(sid, 0, 1, 0, 1), {"textFormat": {"bold": True, "fontSize": 14}}, "userEnteredFormat.textFormat"),
        cell_fmt(grid(sid, 8, 9, 0, WIDE), {"textFormat": {"italic": True, "foregroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}, "wrapStrategy": "WRAP"}, "userEnteredFormat(textFormat,wrapStrategy)"),
        {"mergeCells": {"range": grid(sid, 8, 9, 0, WIDE), "mergeType": "MERGE_ALL"}},
        cell_fmt(grid(sid, h2h_top - 2, h2h_top - 1, 0, 1), {"textFormat": {"bold": True, "fontSize": 11}}, "userEnteredFormat.textFormat"),
        cell_fmt(grid(sid, h2h_top - 1, h2h_top, 0, WIDE), {**bold, "wrapStrategy": "WRAP", "verticalAlignment": "BOTTOM",
                                                         "backgroundColor": {"red": 0.94, "green": 0.94, "blue": 0.93}}, "userEnteredFormat(textFormat,wrapStrategy,verticalAlignment,backgroundColor)"),
        cell_fmt(grid(sid, h2h_top, h2h_end, 1, WIDE), {"numberFormat": {"type": "NUMBER", "pattern": "0.0;-0.0"}}, "userEnteredFormat.numberFormat"),
        cell_fmt(grid(sid, h2h_top, h2h_end, 1 + 2 * len(H2H), WIDE), {"numberFormat": {"type": "NUMBER", "pattern": "+0.0;-0.0;0.0"}, **bold}, "userEnteredFormat(numberFormat,textFormat)"),
        scale(grid(sid, h2h_top, h2h_end, 1 + 2 * len(H2H), WIDE), True, midpoint=0),
    ]
    for i in range(len(SUMMARY)):
        reqs += [{"mergeCells": {"range": grid(sid, 2 + i, 3 + i, 0, WIDE), "mergeType": "MERGE_ALL"}},
                 cell_fmt(grid(sid, 2 + i, 3 + i, 0, WIDE), {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}, "userEnteredFormat(wrapStrategy,verticalAlignment)")]
    for k, (title, col, fmt, higher_better) in enumerate(PIVOTS):
        r = pivot_top + k * PIVOT_ROWS
        reqs += [
            cell_fmt(grid(sid, r, r + 1, 0, 1), {"textFormat": {"bold": True, "fontSize": 11}}, "userEnteredFormat.textFormat"),
            {"updateCells": {"start": {"sheetId": sid, "rowIndex": r + 1, "columnIndex": 0}, "fields": "pivotTable", "rows": [{"values": [{"pivotTable": {
                # An open-ended source range renders an empty pivot through the API; the tab's full grid covers whole columns
                "source": grid(hit_id, 0, tabs["Hit rates"]["gridProperties"]["rowCount"], 0, 17),
                "rows": [{"sourceColumnOffset": 1, "showTotals": False, "sortOrder": "ASCENDING"}],
                # Descending puts the hybrid and the EOS versions first, then the Cluster Tool, then the algorithm modes
                "columns": [{"sourceColumnOffset": 2, "showTotals": False, "sortOrder": "DESCENDING"}],
                "values": [{"summarizeFunction": "AVERAGE", "sourceColumnOffset": col, "name": title.split(" —")[0]}],
                # Condition filters (TEXT_NOT_CONTAINS, NOT_BLANK) render an empty pivot through the API, so filter by value lists
                "filterSpecs": [
                    {"columnOffsetIndex": 2, "filterCriteria": {"visibleValues": approaches}},
                    {"columnOffsetIndex": 1, "filterCriteria": {"visibleValues": sorted(main.loc[main.iloc[:, col].notna(), "CE name"].unique())}}],
            }}]}]}},
            cell_fmt(grid(sid, r + 1, r + 3, 0, 9), {"wrapStrategy": "WRAP", "verticalAlignment": "BOTTOM"}, "userEnteredFormat(wrapStrategy,verticalAlignment)"),
            cell_fmt(grid(sid, r + 3, r + PIVOT_ROWS - 1, 1, 9), {"numberFormat": {"type": "NUMBER", "pattern": fmt}}, "userEnteredFormat.numberFormat"),
        ]
        if higher_better is not None:
            reqs.append(scale(grid(sid, r + 3, r + PIVOT_ROWS - 1, 1, 9), higher_better))
        # A CE x approach pair with clusters but no paid scoring (Park Güell's hand-tuned repair) averages nothing: #DIV/0!
        reqs.append({"addConditionalFormatRule": {"index": 0, "rule": {"ranges": [grid(sid, r + 3, r + PIVOT_ROWS - 1, 1, 9)], "booleanRule": {
            "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f"=ISERROR(B{r + 4})"}]},
            "format": {"textFormat": {"foregroundColor": WHITE}, "backgroundColor": WHITE}}}}})
    for tab in ("Hit rates", "Clusters", "Keywords", "Search terms", "Demand capture", "Uncaptured searches",
                "Cluster ad-group coverage", "Ad groups", "Ad group x cluster"):
        t = tabs[tab]
        cols = t["gridProperties"]["columnCount"]
        reqs += [
            cell_fmt(grid(t["sheetId"], 0, 1, 0, cols), {**bold, "wrapStrategy": "WRAP", "verticalAlignment": "BOTTOM",
                                                        "backgroundColor": {"red": 0.94, "green": 0.94, "blue": 0.93}}, "userEnteredFormat(textFormat,wrapStrategy,verticalAlignment,backgroundColor)"),
            {"setBasicFilter": {"filter": {"range": {"sheetId": t["sheetId"]}}}},
            {"updateSheetProperties": {"properties": {"sheetId": t["sheetId"], "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 3 if tab != "Keywords" else 3}},
                                       "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}},
            {"updateDimensionProperties": {"range": {"sheetId": t["sheetId"], "dimension": "COLUMNS", "startIndex": 0, "endIndex": cols},
                                           "properties": {"pixelSize": 130}, "fields": "pixelSize"}},
        ]
    reqs += capture_formats(tabs)
    readme = tabs["README"]["sheetId"]
    reqs += [cell_fmt(grid(readme, 0, 40, 1, 2), {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}, "userEnteredFormat(wrapStrategy,verticalAlignment)"),
             {"updateDimensionProperties": {"range": {"sheetId": readme, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 260}, "fields": "pixelSize"}},
             {"updateDimensionProperties": {"range": {"sheetId": readme, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 700}, "fields": "pixelSize"}},
             cell_fmt(grid(readme, 0, 1, 0, 1), {"textFormat": {"bold": True, "fontSize": 14}}, "userEnteredFormat.textFormat")]
    batch(reqs)
    print(f"Summary tab built: {len(paid_ces)} head-to-head rows, {len(PIVOTS)} pivots")
    build_ce_view(sheet_id, tabs, batch, sorted(hits["CE name"].unique()), sorted(approaches, reverse=True))
    if "Ad group x cluster" in tabs:
        build_theme_pivot(tabs, batch)


def build_theme_pivot(tabs, batch):
    """Clusters down, ad group themes across, paid clicks per month, read live from the Ad group x cluster tab."""
    if "Theme x cluster" in tabs:
        batch([{"deleteSheet": {"sheetId": tabs["Theme x cluster"]["sheetId"]}}])
    res = batch([{"addSheet": {"properties": {"title": "Theme x cluster", "index": 3, "gridProperties": {"rowCount": 80, "columnCount": 20, "frozenRowCount": 2}}}}])
    sid = res["replies"][0]["addSheet"]["properties"]["sheetId"]
    source = tabs["Ad group x cluster"]
    header = pd.read_csv(WB / "adgroup_x_cluster.csv", nrows=0).columns.tolist()
    batch([
        {"updateCells": {"start": {"sheetId": sid, "rowIndex": 0, "columnIndex": 0}, "fields": "pivotTable", "rows": [{"values": [{"pivotTable": {
            "source": grid(source["sheetId"], 0, source["gridProperties"]["rowCount"], 0, len(header)),
            "rows": [{"sourceColumnOffset": header.index("Cluster"), "showTotals": True, "sortOrder": "DESCENDING",
                      "valueBucket": {"valuesIndex": 0}}],
            "columns": [{"sourceColumnOffset": header.index("Theme"), "showTotals": True, "sortOrder": "DESCENDING",
                         "valueBucket": {"valuesIndex": 0}}],
            "values": [{"summarizeFunction": "SUM", "sourceColumnOffset": header.index("Paid clicks / month"), "name": "Paid clicks / month"}]}}]}]}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 300}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 15}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
        cell_fmt(grid(sid, 0, 2, 0, 15), {"textFormat": {"bold": True}, "wrapStrategy": "WRAP"}, "userEnteredFormat(textFormat,wrapStrategy)"),
        cell_fmt(grid(sid, 2, 80, 1, 15), {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}, "userEnteredFormat.numberFormat"),
        scale(grid(sid, 2, 60, 1, 13), True),
    ])
    print("Theme x cluster pivot built")


def capture_formats(tabs):
    """Number formats and colour scales on the capture tabs, located by header so column order can change."""
    reqs = []
    for tab, csv_name in (("Demand capture", "capture.csv"), ("Uncaptured searches", "uncaptured.csv"),
                          ("Cluster ad-group coverage", "cluster_adgroups.csv"), ("Ad groups", "adgroups.csv"),
                          ("Ad group x cluster", "adgroup_x_cluster.csv")):
        if tab in tabs:
            reqs += tab_formats(tabs[tab], pd.read_csv(WB / csv_name, nrows=0).columns.tolist())
    return reqs


def tab_formats(t, header):
    sid, rows = t["sheetId"], t["gridProperties"]["rowCount"]
    reqs = []
    for i, name in enumerate(header):
        rng = grid(sid, 1, rows, i, i + 1)
        if name == "Paid ROI % (CM1 ÷ spend)":
            reqs.append(cell_fmt(rng, {"numberFormat": {"type": "PERCENT", "pattern": "0%"}}, "userEnteredFormat.numberFormat"))
        elif name.endswith("%") or name == "Paid impression share":
            reqs.append(cell_fmt(rng, {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}}, "userEnteredFormat.numberFormat"))
        elif "/ month" in name or name == "Google Ads keywords":
            reqs.append(cell_fmt(rng, {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}, "userEnteredFormat.numberFormat"))
        if name in ("Paid capture %", "Organic click capture %", "Paid impression share"):
            reqs.append(scale(rng, True))
        elif name == "CM1 at stake / month":
            reqs.append(scale(rng, False))
    return reqs


def col_letter(index):
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def build_ce_view(sheet_id, tabs, batch, ce_names, approaches):
    """One block of columns per approach, each listing the chosen CE's clusters; a dropdown in B1 picks the CE."""
    if "CE view" in tabs:
        batch([{"deleteSheet": {"sheetId": tabs["CE view"]["sheetId"]}}])
    width = len(CE_VIEW_COLS) + 1
    res = batch([{"addSheet": {"properties": {"title": "CE view", "index": 1, "gridProperties": {
        "rowCount": 120, "columnCount": width * len(approaches), "frozenRowCount": CE_VIEW_HEADER_ROW + 1, "hideGridlines": True}}}}])
    sid = res["replies"][0]["addSheet"]["properties"]["sheetId"]
    default_ce = "Vatican Museums" if "Vatican Museums" in ce_names else ce_names[0]
    rows = [["CE", default_ce], ["Pick a CE in B1. Each block lists that CE's clusters for one approach, largest search volume first. "
                                 "Blank % = the approach was not scored against paid clicks for this CE."], [""], [], [], [], []]
    for i, approach in enumerate(approaches):
        c = i * width
        clusters = f"Clusters!$B:$B,$B$1,Clusters!$C:$C,\"{approach}\""
        hit = f"'Hit rates'!$B:$B,$B$1,'Hit rates'!$C:$C,\"{approach}\""
        source = ",".join(f"Clusters!${col}$2:${col}" for _, col, _, _ in CE_VIEW_COLS)
        pad = [""] * (c - len(rows[3]))
        rows[3] += pad + [approach]
        rows[4] += [""] * (c - len(rows[4])) + [
            f"=IF(COUNTIFS({clusters})=0,\"Not run for this CE\",COUNTIFS({clusters})&\" clusters\""
            f"&IFERROR(\" · right-intent \"&TEXT(AVERAGEIFS('Hit rates'!$I:$I,{hit}),\"0.0\")&\"% all\",\"\")"
            f"&IFERROR(\", \"&TEXT(AVERAGEIFS('Hit rates'!$M:$M,{hit}),\"0.0\")&\"% unseen\",\"\"))"]
        rows[5] += [""] * (c - len(rows[5])) + [name for name, _, _, _ in CE_VIEW_COLS]
        rows[6] += [""] * (c - len(rows[6])) + [
            f"=IFERROR(SORT(FILTER({{{source}}},Clusters!$B$2:$B=$B$1,Clusters!$C$2:$C=\"{approach}\"),4,FALSE),\"\")"]
    gws("sheets", "spreadsheets", "values", "update", "--params",
        json.dumps({"spreadsheetId": sheet_id, "range": "'CE view'!A1", "valueInputOption": "USER_ENTERED"}), body={"values": rows})

    grey = {"red": 0.94, "green": 0.94, "blue": 0.93}
    reqs = [
        {"setDataValidation": {"range": grid(sid, 0, 1, 1, 2), "rule": {
            "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": name} for name in ce_names]}, "strict": True, "showCustomUi": True}}},
        cell_fmt(grid(sid, 0, 1, 0, 2), {"textFormat": {"bold": True, "fontSize": 13}}, "userEnteredFormat.textFormat"),
        cell_fmt(grid(sid, 0, 1, 1, 2), {"backgroundColor": {"red": 0.94, "green": 0.93, "blue": 1}}, "userEnteredFormat.backgroundColor"),
        cell_fmt(grid(sid, 1, 2, 0, 1), {"textFormat": {"italic": True, "foregroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}}, "userEnteredFormat.textFormat"),
    ]
    for i in range(len(approaches)):
        c = i * width
        reqs += [
            {"mergeCells": {"range": grid(sid, 3, 4, c, c + width - 1), "mergeType": "MERGE_ALL"}},
            {"mergeCells": {"range": grid(sid, 4, 5, c, c + width - 1), "mergeType": "MERGE_ALL"}},
            cell_fmt(grid(sid, 3, 4, c, c + width - 1), {"textFormat": {"bold": True, "fontSize": 11, "foregroundColor": WHITE},
                                                         "backgroundColor": {"red": 0.38, "green": 0.2, "blue": 0.8}}, "userEnteredFormat(textFormat,backgroundColor)"),
            cell_fmt(grid(sid, 4, 5, c, c + width - 1), {"textFormat": {"italic": True}}, "userEnteredFormat.textFormat"),
            cell_fmt(grid(sid, CE_VIEW_HEADER_ROW, CE_VIEW_HEADER_ROW + 1, c, c + width - 1), {"textFormat": {"bold": True}, "backgroundColor": grey,
                                                                                               "wrapStrategy": "WRAP"}, "userEnteredFormat(textFormat,backgroundColor,wrapStrategy)"),
        ]
        for j, (_, _, px, fmt) in enumerate(CE_VIEW_COLS):
            reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c + j, "endIndex": c + j + 1},
                                                       "properties": {"pixelSize": px}, "fields": "pixelSize"}})
            if fmt:
                reqs.append(cell_fmt(grid(sid, CE_VIEW_HEADER_ROW + 1, 120, c + j, c + j + 1), {"numberFormat": {"type": "NUMBER", "pattern": fmt}}, "userEnteredFormat.numberFormat"))
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c + width - 1, "endIndex": c + width},
                                                   "properties": {"pixelSize": 24}, "fields": "pixelSize"}})
        reqs.append(scale(grid(sid, CE_VIEW_HEADER_ROW + 1, 120, c + width - 2, c + width - 1), True))
    reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                                               "properties": {"pixelSize": 230}, "fields": "pixelSize"}})
    batch(reqs)
    print(f"CE view built: {len(approaches)} approach blocks, dropdown over {len(ce_names)} CEs")


if __name__ == "__main__":
    main()
