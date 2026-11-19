"""Which ad groups serve each cluster, and which clusters each ad group serves, from the same keyword spreading as
capture_analysis.py (complete keyword totals, split by the searches each keyword served).

Coverage per cluster, on paid clicks (the window divided by 3 for monthly figures):
  top ad group      the ad group with the most of the cluster's clicks
  reach             top ad group's clicks in this cluster / all the cluster's clicks
  focus             top ad group's clicks in this cluster / all the top ad group's clicks
  Dedicated         focus >= FOCUS_DEDICATED: an ad group mostly about this cluster serves it
  Shared            the cluster is served, but only by ad groups mostly about something else
  White space       fewer than WHITE_SPACE_CLICKS paid clicks a month
The same coverage is also measured per ad group theme. Vatican's ad groups are named "<intent> - <match> - <language> -
<sub-theme>" ("Tickets - Exact - Spanish - Sistine Chapel") and repeated in every language and region campaign, so one
cluster touches hundreds of ad groups and the account's real structure is the theme ("Tickets · Sistine Chapel").

Writes cluster_adgroups.csv, adgroups.csv and adgroup_x_cluster.csv to the run and the workbook folder.

Usage: python adgroup_grid.py --snapshot 20261029_capture_v2 --ces 189 --pair-mapping <run> --keyword-mapping <run>
"""
import pandas as pd

import capture_analysis as ca
import runlib

FOCUS_DEDICATED = 0.5
WHITE_SPACE_CLICKS = 5
SERVING_SHARE = 0.05   # an ad group counts as serving a cluster from this share of the cluster's clicks
MONTHS = ca.MONTHS


def theme(ad_group_name):
    """Intent plus sub-theme from "<intent> - <match> - <language> - <sub-theme>"; "All" as the sub-theme adds nothing."""
    parts = [x.strip() for x in str(ad_group_name).split(" - ")]
    if len(parts) < 4:
        return parts[0]
    return parts[0] if parts[3].lower() == "all" else f"{parts[0]} · {parts[3]}"


def main():
    a = runlib.args("adgroup_grid", {"--pair-mapping": {"required": True}, "--keyword-mapping": {"required": True},
                                     "--tag": {"default": "", "help": "suffix for the workbook files"}})
    run = runlib.Run("adgroup_grid", a.snapshot, {"ces": a.ces, "pair_mapping": a.pair_mapping, "keyword_mapping": a.keyword_mapping,
                                                  "focus_dedicated": FOCUS_DEDICATED, "white_space_clicks": WHITE_SPACE_CLICKS,
                                                  "serving_share": SERVING_SHARE})
    snap = runlib.SNAPSHOTS / a.snapshot
    names = pd.read_csv(snap / "ce_names.csv", dtype={"ce": str}).set_index("ce")["name"]
    groups = pd.read_csv(snap / "ad_groups.csv", dtype=str).set_index("ad_group_id")
    groups["theme"] = groups["ad_group_name"].map(theme)
    groups["label"] = groups["campaign_name"].str.replace(r"\s*-\s*cid\d+$", "", regex=True) + " › " + groups["ad_group_name"]
    parts = {"clusters": [], "groups": [], "grid": []}
    for ce in a.ces.split(","):
        clusters = pd.read_csv(snap / "cluster_keywords.csv", dtype={"ce": str})
        cname = clusters[clusters["ce"] == ce].drop_duplicates("cid").set_index("cid")["name"].to_dict()
        cname[ca.NO_CLUSTER] = ca.NO_CLUSTER
        spread, _ = ca.spread_keywords(snap, ce, a.pair_mapping, a.keyword_mapping)
        spread["ad_group_id"] = spread["kw_key"].str.split("~").str[0]
        grid = spread.groupby(["ad_group_id", "cid"])[["impr", "clicks", "spend", "conv_value"]].sum().reset_index()
        grid = grid[grid["impr"] > 0]
        grid["group_share"] = grid["clicks"] / grid.groupby("ad_group_id")["clicks"].transform("sum")
        grid["cluster_share"] = grid["clicks"] / grid.groupby("cid")["clicks"].transform("sum")
        grid["Cluster"] = grid["cid"].map(cname)
        grid["Ad group"] = grid["ad_group_id"].map(groups["label"])
        grid["Theme"] = grid["ad_group_id"].map(groups["theme"])
        by_theme = grid.groupby(["Theme", "cid"])["clicks"].sum().reset_index()
        by_theme["theme_share"] = by_theme["clicks"] / by_theme.groupby("Theme")["clicks"].transform("sum")
        by_theme["cluster_share"] = by_theme["clicks"] / by_theme.groupby("cid")["clicks"].transform("sum")

        rows = []
        for cid, name in cname.items():
            g = grid[grid["cid"] == cid].sort_values("clicks", ascending=False)
            clicks = g["clicks"].sum() / MONTHS
            top = g.iloc[0] if len(g) else None
            if clicks < WHITE_SPACE_CLICKS or top is None:
                coverage = "White space"
            else:
                coverage = "Dedicated" if top["group_share"] >= FOCUS_DEDICATED else "Shared"
            t = by_theme[by_theme["cid"] == cid].sort_values("clicks", ascending=False)
            tt = t.iloc[0] if len(t) else None
            theme_cov = "White space" if coverage == "White space" else ("Dedicated" if tt["theme_share"] >= FOCUS_DEDICATED else "Shared")
            rows.append({"CE": ce, "CE name": names[ce], "Cluster": name,
                         "Theme coverage": theme_cov if cid != ca.NO_CLUSTER else "",
                         "Top theme": tt["Theme"] if tt is not None else "",
                         "Top theme reach %": round(tt["cluster_share"], 3) if tt is not None else None,
                         "Top theme focus %": round(tt["theme_share"], 3) if tt is not None else None,
                         "Themes (share of cluster clicks)": " | ".join(f"{r['Theme']} ({r['cluster_share']:.0%})" for _, r in t.head(3).iterrows()),
                         "Ad group coverage": coverage if cid != ca.NO_CLUSTER else "",
                         "Paid clicks / month": round(clicks), "Spend / month": round(g["spend"].sum() / MONTHS, 2),
                         "Top ad group": top["Ad group"] if top is not None else "",
                         "Top group reach %": round(top["cluster_share"], 3) if top is not None else None,
                         "Top group focus %": round(top["group_share"], 3) if top is not None else None,
                         "Ad groups serving": int((g["cluster_share"] >= SERVING_SHARE).sum()),
                         "Ad groups touching": len(g),
                         "Top 3 ad groups (share of cluster clicks)": " | ".join(
                             f"{r['Ad group']} ({r['cluster_share']:.0%})" for _, r in g.head(3).iterrows())})
        cl = pd.DataFrame(rows).sort_values("Paid clicks / month", ascending=False)
        parts["clusters"].append(cl)

        rows = []
        for gid, g in grid.groupby("ad_group_id"):
            g = g.sort_values("clicks", ascending=False)
            info = groups.loc[gid] if gid in groups.index else pd.Series(dtype=str)
            spend, value = g["spend"].sum(), g["conv_value"].sum()
            rows.append({"CE": ce, "CE name": names[ce], "Campaign": info.get("campaign_name", ""), "Ad group": info.get("ad_group_name", gid),
                         "Theme": info.get("theme", ""),
                         "Status": info.get("ad_group_status", ""), "Impressions / month": round(g["impr"].sum() / MONTHS),
                         "Paid clicks / month": round(g["clicks"].sum() / MONTHS), "Spend / month": round(spend / MONTHS, 2),
                         "CM1, Google-attributed / month": round(value / MONTHS, 2),
                         "Paid ROI % (CM1 ÷ spend)": round(value / spend, 2) if spend else None,
                         "Main cluster": g.iloc[0]["Cluster"], "Main cluster share %": round(g.iloc[0]["group_share"], 3),
                         "Second cluster": g.iloc[1]["Cluster"] if len(g) > 1 else "",
                         "Second cluster share %": round(g.iloc[1]["group_share"], 3) if len(g) > 1 else None,
                         "Clusters served": int((g["group_share"] >= SERVING_SHARE).sum()),
                         "Focus": "Focused" if g.iloc[0]["group_share"] >= FOCUS_DEDICATED else "Mixed"})
        parts["groups"].append(pd.DataFrame(rows).sort_values("Paid clicks / month", ascending=False))

        long = grid.assign(CE=ce, **{"CE name": names[ce]})
        long = long.assign(**{"Impressions / month": (long["impr"] / MONTHS).round(), "Paid clicks / month": (long["clicks"] / MONTHS).round(1),
                              "Spend / month": (long["spend"] / MONTHS).round(2), "CM1, Google-attributed / month": (long["conv_value"] / MONTHS).round(2),
                              "Share of ad group clicks %": long["group_share"].round(3), "Share of cluster clicks %": long["cluster_share"].round(3)})
        parts["grid"].append(long[["CE", "CE name", "Theme", "Ad group", "Cluster", "Impressions / month", "Paid clicks / month", "Spend / month",
                                   "CM1, Google-attributed / month", "Share of ad group clicks %", "Share of cluster clicks %"]]
                             .sort_values("Paid clicks / month", ascending=False))
        for cov, n in cl[cl["Theme coverage"] != ""]["Theme coverage"].value_counts().items():
            run.record(ce, "adgroup grid", f"clusters_{cov.lower().replace(' ', '_')}", int(n))
        print(f"\n=== CE {ce}")
        print(cl[["Cluster", "Paid clicks / month", "Theme coverage", "Top theme", "Top theme reach %", "Top theme focus %", "Ad groups touching"]]
              .to_string(index=False, max_colwidth=46))
        print(by_theme.groupby("Theme")["clicks"].sum().div(MONTHS).round().sort_values(ascending=False).to_string())
    for key, fname in (("clusters", "cluster_adgroups.csv"), ("groups", "adgroups.csv"), ("grid", "adgroup_x_cluster.csv")):
        out = pd.concat(parts[key])
        out.to_csv(run.out / fname, index=False)
        out.to_csv(ca.WB / (fname.replace(".csv", f"_{a.tag}.csv") if a.tag else fname), index=False)
    run.close()


if __name__ == "__main__":
    main()
