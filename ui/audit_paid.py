"""Build the paid-data audit tables for one or more CEs: what the tool shows next to what Google Ads holds.

  python3 audit_paid.py <out_dir> <google_campaigns.csv> <google_keywords.csv> <bq_dir> 3945 189

<bq_dir> holds adgroups.csv (ad-group-level stats), terms.csv (search terms, same window) and served.csv (which keyword
served each of the tool's keywords as a search in the last 30 days), from the queries in the sheet's SQL tab.

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
    out_dir, gfile, kfile, bq, ces = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4]), sys.argv[5:]
    ag_bq = pd.read_csv(bq / "adgroups.csv", dtype={"ce": str, "ad_group_id": str})
    terms_bq = pd.read_csv(bq / "terms.csv", dtype={"ce": str})
    served = pd.read_csv(bq / "served.csv", dtype={"ce": str})
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
        "10 Bid status": ["CE", "Cluster", "Keyword", "Searches / mo", "Tool says", "Live as", "BigQuery: exact keyword live today",
                          "BigQuery: exact keyword in account, not live", "Google served this search (last 30 days): by which keyword", "Verdict", "Why"],
        "2 Nothing lost": ["CE", "Metric", "Keyword totals (tool input)", "Split across clusters", "Sum of the tool's clusters",
                           "In catch-all clusters the tool hides (Other)", "In no cluster", "Unaccounted (input − clusters − hidden − no cluster)", "Keywords split", "Keywords whose split ≠ 100%"],
        "3 Hidden searches": ["CE", "Metric", "Keyword totals", "Visible search terms", "Share visible", "Visible and placed in a cluster",
                              "Share of visible placed"],
        "4 Search-term labels": ["CE", "Search term", "Clicks", "Cost", "Conv value", "Tool's cluster", "Placed by",
                                 "Ad group serving most clicks", "Right cluster? (Y/N)", "Should be", "Reviewer", "Note"],
        "5 Ad groups": ["CE", "Campaign", "Ad group", "Ad group id", "Status", "Identifier (last part of the name)", "Tool clicks", "Tool cost",
                        "Tool conv value", "BigQuery clicks (keyword level)", "BigQuery cost (keyword level)", "BigQuery conv value (keyword level)",
                        "BigQuery clicks (ad group level)", "BigQuery cost (ad group level)", "BigQuery conv value (ad group level)",
                        "Tool vs BigQuery: clicks off", "Cost off", "Conv value off", "Clicks tied to no keyword", "Main cluster of its clicks",
                        "Main cluster's share", "Other clusters"],
        "6 Clusters": ["CE", "Cluster", "Type", "Tool clicks", "Tool cost", "Tool conv value", "Tool ROI", "Visible search terms",
                       "Tool visible clicks", "Tool visible cost", "Tool visible conv value", "BigQuery clicks (same search terms)", "BigQuery cost",
                       "BigQuery conv value", "Clicks off", "Cost off", "Conv value off", "Hidden share of clicks", "Top ad group"],
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

        # 10. Bid status: every keyword the tool shows, against Google's keyword snapshot and the searches it served
        drw = json.loads((HERE / cfg["out"] / "drawer.json").read_text())["clusters"]
        ks = pd.read_csv(HERE / cfg["out"] / f"keyword_status_{ce}.csv")
        en = lambda s: s.eq("ENABLED")
        live_set = set(ks.loc[en(ks["keyword_status"]) & en(ks["ad_group_status"]) & en(ks["campaign_status"]), "keyword"])
        acct_set = set(ks.loc[ks["ad_group_status"].ne("REMOVED") & ks["campaign_status"].ne("REMOVED"), "keyword"]) - live_set
        words = lambda s: frozenset(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in str(s).lower().split())
        acct_words = {words(k) for k in acct_set}
        sv = served[served["ce"] == ce]
        label = {"bid": "Bid", "variant": "Bid as a close variant", "paused": "Paused", "none": "Not in account"}
        seen = set()
        for cid, x in drw.items():
            for w in x.get("keywords", []):
                kw = w["kw"].lower()
                if kw in seen or "bid" not in w:
                    continue
                seen.add(kw)
                st, as_ = w["bid"], (w.get("as") or "").lower()
                ev = sv[sv["term"] == kw].sort_values(["impr", "clicks"], ascending=False)
                evtxt = "; ".join(f"{b} ({m.lower()}, {int(i)} impr)" for b, m, i in zip(ev["served_by"].fillna("?"), ev["match_type"], ev["impr"]))[:300]
                close = ev[ev["match_type"].isin(["NEAR_EXACT", "NEAR_PHRASE"]) & (ev["served_by"].fillna("") != kw) & ev["served_by"].isin(live_set)]
                live, acct = kw in live_set, kw in acct_set
                if st == "bid":
                    v, why = ("Verified", "exact keyword is live") if live else ("Contradicted", "exact keyword is not live")
                elif st == "variant":
                    if live:
                        v, why = "Contradicted", "the exact keyword is live: should read Bid"
                    elif as_ in live_set:
                        v, why = "Verified", f"“{as_}” is live" + (f"; Google served this search through it" if (ev["served_by"] == as_).any() else "")
                    else:
                        v, why = "Contradicted", f"“{as_}” is not live"
                elif st == "paused":
                    if live:
                        v, why = "Contradicted", "the exact keyword is live"
                    elif acct or words(kw) in acct_words:
                        v, why = "Verified", "in the account, not live"
                    else:
                        v, why = "Check", "no paused keyword with the same words found"
                else:
                    if live or acct:
                        v, why = "Contradicted", "the exact keyword is in the account"
                    elif len(close):
                        v, why = "Contradicted", f"Google served it as a close variant of “{close['served_by'].iloc[0]}”"
                    else:
                        v, why = "Verified", "not in the account" + (f"; Google still served it through {ev['served_by'].iloc[0]} ({ev['match_type'].iloc[0].lower()})" if len(ev) else "")
                tabs["10 Bid status"].append([lab, names.get(cid, ""), w["kw"], w.get("vol") or "", label[st], w.get("as") or "",
                                              "Y" if live else "N", "Y" if acct else "N", evtxt, v, why])

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

        # 5. Ad groups: the tool's keyword totals by ad group, against BigQuery at keyword and at ad-group level
        agt = tot.groupby("ag")[["clicks", "spend", "conv_value"]].sum()
        agk = gkw[gkw["ce"] == ce].assign(ag=lambda d: d["kw_key"].str.split("~").str[0]).groupby("ag")[["clicks", "spend", "conv_value"]].sum()
        aga = ag_bq[ag_bq["ce"] == ce].set_index("ad_group_id")[["clicks", "spend", "conv_value"]]
        ag_ids = [a for a in (set(agt.index[agt["clicks"] > 0]) | set(aga.index[aga["clicks"] > 0]))]
        ag_ids.sort(key=lambda a: -float(aga["clicks"].get(a, agt["clicks"].get(a, 0))))
        mix = spread.groupby(["ag", "cid"])["clicks"].sum()
        meta = ads.set_index("ad_group_id")
        val = lambda df, a, c: round(float(df[c].get(a, 0)), 2)
        for ag in ag_ids:
            m = mix.get(ag, pd.Series(dtype=float)).sort_values(ascending=False) if ag in mix.index.get_level_values(0) else pd.Series(dtype=float)
            tot_m = m.sum()
            name = meta["ad_group_name"].get(ag, "")
            r = len(tabs["5 Ad groups"]) + 1
            tabs["5 Ad groups"].append([lab, meta["campaign_name"].get(ag, ""), name, ag, meta["ad_group_status"].get(ag, ""),
                                        str(name).split(" - ")[-1] if name else "",
                                        val(agt, ag, "clicks"), val(agt, ag, "spend"), val(agt, ag, "conv_value"),
                                        val(agk, ag, "clicks"), val(agk, ag, "spend"), val(agk, ag, "conv_value"),
                                        val(aga, ag, "clicks"), val(aga, ag, "spend"), val(aga, ag, "conv_value"),
                                        f"=ABS(G{r}-J{r})", f"=ROUND(ABS(H{r}-K{r}),2)", f"=ROUND(ABS(I{r}-L{r}),2)",
                                        f'=IF(M{r}=0,"",1-J{r}/M{r})', cn(m.index[0]) if len(m) else "(no cluster)",
                                        round(float(m.iloc[0] / tot_m), 3) if tot_m else "",
                                        ", ".join(f"{cn(c)} {v / tot_m:.0%}" for c, v in m.iloc[1:4].items()) if tot_m else ""])

        # 6. Clusters, and their visible search terms for the Google Ads search terms report
        vis_c = terms[terms["cid"].notna()].groupby("cid").agg(n=("term", "nunique"), clicks=("clicks", "sum"), spend=("spend", "sum"),
                                                                conv_value=("conv_value", "sum"))
        top_ag_c = terms[terms["cid"].notna()].groupby(["cid", "ag"])["clicks"].sum().sort_values(ascending=False)
        # BigQuery's search terms today, placed with the tool's own term → cluster placement
        place = terms.dropna(subset=["cid"]).drop_duplicates("term").set_index("term")["cid"]
        tb = terms_bq[terms_bq["ce"] == ce].assign(cid=lambda d: d["term"].map(place)).dropna(subset=["cid"]).groupby("cid")[["clicks", "spend", "conv_value"]].sum()
        order = sorted(data["clusters"], key=lambda c: -(c.get("clicks") or 0))
        for c in order:
            v = vis_c.loc[c["id"]] if c["id"] in vis_c.index else None
            b = tb.loc[c["id"]] if c["id"] in tb.index else None
            ta = top_ag_c.get(c["id"])
            r = len(tabs["6 Clusters"]) + 1
            tabs["6 Clusters"].append([lab, c["name"], c["type"].title(), c.get("clicks") or 0, c.get("spend") or 0, c.get("google_value") or 0,
                                       f'=IF(E{r}=0,"",F{r}/E{r})', int(v.n) if v is not None else 0, int(v.clicks) if v is not None else 0,
                                       round(float(v.spend), 2) if v is not None else 0, round(float(v.conv_value), 2) if v is not None else 0,
                                       int(b.clicks) if b is not None else 0, round(float(b.spend), 2) if b is not None else 0,
                                       round(float(b.conv_value), 2) if b is not None else 0,
                                       f"=ABS(I{r}-L{r})", f'=IF(M{r}=0,"",ABS(J{r}/M{r}-1))', f'=IF(N{r}=0,"",ABS(K{r}/N{r}-1))',
                                       f'=IF(D{r}=0,"",1-I{r}/D{r})', agname.get(ta.index[0], "") if ta is not None and len(ta) else ""])
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
