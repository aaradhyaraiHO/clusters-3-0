"""Build the paid-data audit tables for one or more CEs: what the tool shows next to what Google Ads holds.

  python3 audit_paid.py <out_dir> <google_campaigns.csv> <google_keywords.csv> 3945 189

Reads the export's working (audit_spread_<CE>.csv, audit_terms_<CE>.csv), the snapshot's keyword totals and ad groups,
the built cluster data, and Google's campaign-level totals (google_campaigns.csv, from the SQL in the sheet's SQL tab).
Writes tabs.json: one table per sheet tab, with formulas for every comparison so the sheet recomputes when a reviewer
types in a number from the Google Ads UI.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = Path.home() / "analytics" / ".claude" / "worktrees" / "clusters-3-0" / "scripts" / "clusters_3_0"
LABEL = {"189": "Vatican", "3945": "Milford Sound"}
TOP_TERMS, TOP_AGS, TOP_CLUSTERS = 100, 3, 5


def inputs(ce):
    cfg = json.loads((HERE / "ces.json").read_text())["ces"][ce]
    out = HERE / cfg["out"]
    snap = ROOT / "snapshots" / "20261029_capture_v2" if ce == "189" else out
    tot = pd.read_csv(snap / "keyword_totals.csv")
    if "ce" in tot:
        tot = tot[tot["ce"].astype(str) == ce]
    ads = pd.read_csv(snap / "ad_groups.csv", dtype={"ad_group_id": str}).drop_duplicates("ad_group_id")
    if "ce" in ads:
        ads = ads[ads["ce"].astype(str) == ce]
    tot = tot.assign(ag=tot["kw_key"].str.split("~").str[0]).merge(ads, left_on="ag", right_on="ad_group_id", how="left")
    spread = pd.read_csv(out / f"audit_spread_{ce}.csv").assign(ag=lambda d: d["kw_key"].str.split("~").str[0])
    terms = pd.read_csv(out / f"audit_terms_{ce}.csv", dtype={"ag": str})
    data = json.loads((out / cfg["data"]).read_text())
    names = {c["id"]: c["name"] for c in data["clusters"]}
    return cfg, tot, ads, spread, terms, data, names


def col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    out_dir, gfile, kfile, ces = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4:]
    gkw = pd.read_csv(kfile, dtype={"ce": str})
    google = pd.read_csv(gfile, dtype={"ce": str})
    google = google[google["network"] == "SEARCH"]
    tabs = {k: [] for k in ["1 CE totals", "1b Keyword totals", "10 Bid status", "2 Nothing lost", "3 Hidden searches", "4 Search-term labels", "5 Ad groups",
                            "6 Clusters", "6b Cluster search terms"]}
    H = {
        "1 CE totals": ["CE", "Campaign", "Campaign id", "Google clicks (campaign level)", "Google cost", "Google conv value",
                        "Google clicks (keyword level)", "Google cost (keyword level)", "Google conv value (keyword level)",
                        "Tool clicks (in clusters)", "Tool cost (in clusters)", "Tool conv value (in clusters)", "Clusters vs Google: clicks", "Cost", "Conv value",
                        "Checked in Google Ads UI (Y)", "UI clicks", "UI cost", "Note", "Tool header clicks", "Tool header cost", "Tool header conv value"],
        "1b Keyword totals": ["CE", "Keyword id (ad group~criterion)", "Keyword", "Tool impressions", "Tool clicks", "Tool cost", "Tool conv value",
                              "BigQuery impressions", "BigQuery clicks", "BigQuery cost", "BigQuery conv value",
                              "Clicks off (abs)", "Cost off (abs)", "Conv value off (abs)"],
        "10 Bid status": ["CE", "Cluster", "Keyword", "Searches / mo", "Tool says", "Live as", "Google Ads UI says (Bid / Close variant / Paused / Not in account)",
                          "Match? (Y/N)", "Reviewer", "Note"],
        "2 Nothing lost": ["CE", "Metric", "Keyword totals (tool input)", "Split across clusters", "Sum of the tool's clusters",
                           "In catch-all clusters the tool hides (Other)", "In no cluster", "Unaccounted (input − clusters − hidden − no cluster)", "Keywords split", "Keywords whose split ≠ 100%"],
        "3 Hidden searches": ["CE", "Metric", "Keyword totals", "Visible search terms", "Share visible", "Visible and placed in a cluster",
                              "Share of visible placed"],
        "4 Search-term labels": ["CE", "Search term", "Clicks", "Cost", "Conv value", "Tool's cluster", "Placed by",
                                 "Ad group serving most clicks", "Right cluster? (Y/N)", "Should be", "Reviewer", "Note"],
        "5 Ad groups": ["CE", "Campaign", "Ad group", "Ad group id", "Status", "Identifier (last part of the name)", "Tool clicks",
                        "Tool impressions", "Tool cost", "Tool conv value", "Main cluster of its clicks", "Main cluster's share",
                        "Other clusters", "Check this one?", "UI clicks", "UI cost", "UI conv value", "Clicks gap (abs)",
                        "Cost gap (abs)", "Conv value gap (abs)", "Reviewer", "Note"],
        "6 Clusters": ["CE", "Cluster", "Type", "Tool clicks", "Tool impressions", "Tool cost", "Tool conv value", "Tool ROI",
                       "Visible search terms", "Visible clicks", "Visible cost", "Visible conv value", "Hidden share of clicks",
                       "Top ad group", "Check this one?", "UI clicks (its terms)", "UI cost", "UI conv value",
                       "Clicks gap vs visible (abs)", "Cost gap vs visible (abs)", "Reviewer", "Note"],
        "6b Cluster search terms": ["CE", "Cluster", "Search term", "Clicks", "Cost", "Conv value", "Ad group serving most clicks"],
    }
    for k in tabs:
        tabs[k].append(H[k])

    for ce in ces:
        lab = LABEL.get(ce, ce)
        cfg, tot, ads, spread, terms, data, names = inputs(ce)
        cn = lambda c: names.get(c, "(not a cluster in the tool)" if isinstance(c, str) else "(no cluster)")
        agname = ads.set_index("ad_group_id")["ad_group_name"].to_dict()

        # 1. CE totals by campaign
        g = google[google["ce"] == ce].groupby(["campaign_name", "campaign_id"], as_index=False)[
            ["clicks", "spend", "conv_value", "kw_clicks", "kw_spend", "kw_conv_value"]].sum()
        t = tot.groupby("campaign_name")[["clicks", "spend", "conv_value"]].sum()
        hdr_f = HERE / cfg["out"] / f"campaign_totals_{ce}.csv"
        hdr = pd.read_csv(hdr_f) if hdr_f.exists() else pd.DataFrame(columns=["campaign_name", "network", "clicks", "spend", "conv_value"])
        hdr = hdr[hdr["network"] == "SEARCH"].groupby("campaign_name")[["clicks", "spend", "conv_value"]].sum()
        camps = sorted(set(g["campaign_name"]) | set(t.index), key=lambda n: -float(g.loc[g["campaign_name"] == n, "clicks"].sum() or t["clicks"].get(n, 0)))
        for n in camps:
            gr = g[g["campaign_name"] == n]
            r = len(tabs["1 CE totals"]) + 1
            gv = lambda c: float(gr[c].sum()) if len(gr) else 0
            tv = lambda c: float(t[c].get(n, 0))
            tabs["1 CE totals"].append([lab, n, str(gr["campaign_id"].iloc[0]) if len(gr) else "", gv("clicks"), round(gv("spend"), 2),
                                        round(gv("conv_value"), 2), gv("kw_clicks"), round(gv("kw_spend"), 2), round(gv("kw_conv_value"), 2),
                                        tv("clicks"), round(tv("spend"), 2), round(tv("conv_value"), 2),
                                        f'=IF(D{r}=0,"",J{r}/D{r}-1)', f'=IF(E{r}=0,"",K{r}/E{r}-1)', f'=IF(F{r}=0,"",L{r}/F{r}-1)', "", "", "", "",
                                        float(hdr["clicks"].get(n, 0)), round(float(hdr["spend"].get(n, 0)), 2), round(float(hdr["conv_value"].get(n, 0)), 2)])

        # 1b. Every keyword against BigQuery now, same window
        gk = gkw[gkw["ce"] == ce].set_index("kw_key")
        kwname = tot.set_index("kw_key")["keyword"].to_dict()
        for x in tot.sort_values("clicks", ascending=False).itertuples():
            b = gk.loc[x.kw_key] if x.kw_key in gk.index else None
            r = len(tabs["1b Keyword totals"]) + 1
            tabs["1b Keyword totals"].append([lab, x.kw_key, kwname.get(x.kw_key, ""), int(x.impr), int(x.clicks), round(x.spend, 2), round(x.conv_value, 2),
                                              int(b.impr) if b is not None else 0, int(b.clicks) if b is not None else 0,
                                              round(float(b.spend), 2) if b is not None else 0, round(float(b.conv_value), 2) if b is not None else 0,
                                              f"=ABS(E{r}-I{r})", f"=ROUND(ABS(F{r}-J{r}),2)", f"=ROUND(ABS(G{r}-K{r}),2)"])

        # 10. Bid status: a sample across the four states, for a reviewer to check in Google Ads
        drw = json.loads((HERE / cfg["out"] / "drawer.json").read_text())["clusters"]
        seen, by_state = set(), {}
        for cid, x in drw.items():
            for w in x.get("keywords", []):
                if w["kw"] in seen or "bid" not in w:
                    continue
                seen.add(w["kw"])
                by_state.setdefault(w["bid"], []).append((names.get(cid, ""), w))
        label = {"bid": "Bid", "variant": "Bid as a close variant", "paused": "Paused", "none": "Not in account"}
        for st, n_ in [("variant", 8), ("bid", 4), ("paused", 4), ("none", 4)]:
            for cname, w in sorted(by_state.get(st, []), key=lambda y: -(y[1].get("vol") or 0))[:n_]:
                tabs["10 Bid status"].append([lab, cname, w["kw"], w.get("vol") or "", label[st], w.get("as") or "", "", "", "", ""])

        # 2. Nothing lost: input = split + no cluster = clusters shown
        sp = spread.groupby("kw_key")[["clicks", "impr", "spend", "conv_value", "w_clicks"]].sum()
        kt = tot.set_index("kw_key")[["clicks", "impr", "spend", "conv_value"]]
        clusters = pd.DataFrame(data["clusters"])
        bad_split = int(((sp["w_clicks"] - 1).abs() > 0.001).sum())
        for metric, k, ck in [("Clicks", "clicks", "clicks"), ("Impressions", "impr", "impr"), ("Cost", "spend", "spend"), ("Conv value", "conv_value", "google_value")]:
            inp = float(kt[k].sum())
            split = float(sp[k].sum())
            shown = float(clusters[ck].fillna(0).sum())
            none = float((kt[k] - sp[k].reindex(kt.index).fillna(0)).clip(lower=0).sum())
            r = len(tabs["2 Nothing lost"]) + 1
            hidden = float(spread.loc[~spread["cid"].isin(names), k].sum())
            tabs["2 Nothing lost"].append([lab, metric, round(inp, 2), round(split, 2), round(shown, 2), round(hidden, 2), round(none, 2), f"=ROUND(C{r}-E{r}-F{r}-G{r},2)",
                                           len(sp), bad_split])

        # 3. Hidden searches
        vis = terms[["clicks", "spend", "conv_value"]].sum()
        placed = terms[terms["cid"].notna()][["clicks", "spend", "conv_value"]].sum()
        for metric, k in [("Clicks", "clicks"), ("Cost", "spend"), ("Conv value", "conv_value")]:
            r = len(tabs["3 Hidden searches"]) + 1
            tabs["3 Hidden searches"].append([lab, metric, round(float(kt[k].sum()), 2), round(float(vis[k]), 2), f"=IF(C{r}=0,\"\",D{r}/C{r})",
                                              round(float(placed[k]), 2), f"=IF(D{r}=0,\"\",F{r}/D{r})"])

        # 4. Search-term labels: the top terms by clicks
        by_term = terms.groupby("term").agg(clicks=("clicks", "sum"), spend=("spend", "sum"), conv_value=("conv_value", "sum"),
                                            cid=("cid", "first"), how=("how", "first"))
        top_ag = terms.sort_values("clicks", ascending=False).drop_duplicates("term").set_index("term")["ag"]
        for term, x in by_term.sort_values("clicks", ascending=False).head(TOP_TERMS).iterrows():
            tabs["4 Search-term labels"].append([lab, term, int(x.clicks), round(x.spend, 2), round(x.conv_value, 2), cn(x.cid),
                                                 "" if pd.isna(x.how) else x.how, agname.get(top_ag.get(term), ""), "", "", "", ""])

        # 5. Ad groups
        agt = tot.groupby("ag").agg(clicks=("clicks", "sum"), impr=("impr", "sum"), spend=("spend", "sum"), conv_value=("conv_value", "sum"))
        agt = agt[agt["clicks"] > 0].sort_values("clicks", ascending=False)
        mix = spread.groupby(["ag", "cid"])["clicks"].sum()
        meta = ads.set_index("ad_group_id")
        for i, (ag, x) in enumerate(agt.iterrows()):
            m = mix.get(ag, pd.Series(dtype=float)).sort_values(ascending=False) if ag in mix.index.get_level_values(0) else pd.Series(dtype=float)
            tot_m = m.sum()
            main = cn(m.index[0]) if len(m) else "(no cluster)"
            others = ", ".join(f"{cn(c)} {v / tot_m:.0%}" for c, v in m.iloc[1:4].items()) if tot_m else ""
            name = meta["ad_group_name"].get(ag, "")
            r = len(tabs["5 Ad groups"]) + 1
            tabs["5 Ad groups"].append([lab, meta["campaign_name"].get(ag, ""), name, ag, meta["ad_group_status"].get(ag, ""),
                                        str(name).split(" - ")[-1] if name else "", int(x.clicks), int(x.impr), round(x.spend, 2),
                                        round(x.conv_value, 2), main, round(float(m.iloc[0] / tot_m), 3) if tot_m else "", others,
                                        "Yes" if i < TOP_AGS else "", "", "", "",
                                        f'=IF(O{r}="","",ABS(G{r}/O{r}-1))', f'=IF(P{r}="","",ABS(I{r}/P{r}-1))',
                                        f'=IF(Q{r}="","",IF(Q{r}=0,"",ABS(J{r}/Q{r}-1)))', "", ""])

        # 6. Clusters, and their visible search terms for the Google Ads search terms report
        vis_c = terms[terms["cid"].notna()].groupby("cid").agg(n=("term", "nunique"), clicks=("clicks", "sum"), spend=("spend", "sum"),
                                                                conv_value=("conv_value", "sum"))
        top_ag_c = terms[terms["cid"].notna()].groupby(["cid", "ag"])["clicks"].sum().sort_values(ascending=False)
        order = sorted(data["clusters"], key=lambda c: -(c.get("clicks") or 0))
        for i, c in enumerate(order):
            v = vis_c.loc[c["id"]] if c["id"] in vis_c.index else None
            ta = top_ag_c.get(c["id"])
            r = len(tabs["6 Clusters"]) + 1
            tabs["6 Clusters"].append([lab, c["name"], c["type"].title(), c.get("clicks") or 0, c.get("impr") or 0, c.get("spend") or 0,
                                       c.get("google_value") or 0, f'=IF(F{r}=0,"",G{r}/F{r})',
                                       int(v.n) if v is not None else 0, int(v.clicks) if v is not None else 0,
                                       round(float(v.spend), 2) if v is not None else 0, round(float(v.conv_value), 2) if v is not None else 0,
                                       f'=IF(D{r}=0,"",1-J{r}/D{r})', agname.get(ta.index[0], "") if ta is not None and len(ta) else "",
                                       "Yes" if i < TOP_CLUSTERS else "", "", "", "",
                                       f'=IF(P{r}="","",ABS(J{r}/P{r}-1))', f'=IF(Q{r}="","",ABS(K{r}/Q{r}-1))', "", ""])
        ct = terms[terms["cid"].notna() & (terms["clicks"] > 0)]
        ctt = ct.groupby(["cid", "term"]).agg(clicks=("clicks", "sum"), spend=("spend", "sum"), conv_value=("conv_value", "sum")).reset_index()
        ctop = ct.sort_values("clicks", ascending=False).drop_duplicates(["cid", "term"]).set_index(["cid", "term"])["ag"]
        for x in ctt.sort_values(["cid", "clicks"], ascending=[True, False]).itertuples():
            tabs["6b Cluster search terms"].append([lab, cn(x.cid), x.term, int(x.clicks), round(x.spend, 2), round(x.conv_value, 2),
                                                    agname.get(ctop.get((x.cid, x.term)), "")])

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "tabs.json").write_text(json.dumps(tabs, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print({k: len(v) - 1 for k, v in tabs.items()})


if __name__ == "__main__":
    main()
