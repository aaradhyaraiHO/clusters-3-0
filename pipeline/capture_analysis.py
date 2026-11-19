"""How much of each cluster's demand Headout already captures, in paid and organic, and which searches no cluster covers.

Per cluster, monthly (the 90-day window divided by 3):
  Keyword Planner   volume of the cluster's research keywords. Keyword Planner gives spelling variants one bucketed
                    volume ("sistine chapel", "sixtus chapel" and eight more all read 450,000), so a volume of 10,000+
                    is counted once per cluster however many keywords carry it.
  paid              Google Ads keyword totals (complete: impressions, clicks, spend, conversion value, eligible impressions
                    and impressions lost to rank), spread over clusters by the searches each keyword actually served:
                    clicks by those searches' clicks, spend by their spend, CM1 by their CM1, impression measures by
                    their impressions.
                    A broad "vatican" keyword's numbers follow its searches instead of its own text. Keywords with no
                    visible searches (about 1% of impressions) fall back to their own text.
  demand            the largest of Keyword Planner volume, paid eligible impressions and organic impressions, with the
                    source named; each undercounts in its own way, so the largest is the safest floor
  capture           paid impressions, and organic clicks, as a share of demand (organic impressions can set demand, so
                    they only decide the "No organic presence" flag)
  at stake          missed paid impressions x the cluster's CM1 per impression: an upper bound, since winning those
                    auctions needs higher bids and lower positions convert less
  CM1               Google Ads conversion value, which is CM1 uploaded through the Transactions_ECL_CM1 (+ _App)
                    conversion actions, so it is CM1 as Google attributes it to clicks
  organic           Search Console queries mapped to the cluster: impressions, clicks, impression-weighted position
Searches no cluster takes (paid and organic, plus the hybrid's Other groups) are grouped into variant families, then
joined by meaning into search-term clusters.

Usage: python capture_analysis.py --snapshot 20261029_capture_v1 --ces 189 --pair-mapping <run> --organic-mapping <run>
       --keyword-mapping <run> --families-run <hybrid_assign run>
"""
import pandas as pd
from sklearn.cluster import AgglomerativeClustering

import graph_cluster as gc
import runlib

COL = "D0.85"
MONTHS = 3
MODEL = ".env-clusters/models/paraphrase-multilingual-MiniLM-L12-v2"
GROUP_DISTANCE = 0.35  # cosine distance under which two unplaced search families are one search-term cluster
LOW_SHARE = 0.3         # Vatican runs near 35% impression share everywhere, so only clear outliers below it are flagged
LOW_ORGANIC = 0.05      # organic impressions below this share of demand count as no organic presence
NO_CLUSTER = "No cluster (see Uncaptured searches)"
WB = runlib.HERE / ".env-clusters" / "workbook"
PAID = ["impr", "clicks", "spend", "conv_value", "eligible", "lost_rank", "impr_with_share"]


def assignments(run, ce):
    return pd.read_csv(runlib.RUNS / run / "outputs" / f"assignments_{ce}.csv", low_memory=False)


def planner_volume(snap, ce, families_run):
    """Keyword Planner volume per cluster: one figure per variant family, and one per bucketed volume of 10,000+."""
    research = pd.read_csv(runlib.SNAPSHOTS / "20261029_bakeoff_v0" / "cluster_keywords.csv", dtype={"ce": str})
    vol = research[research["ce"] == ce].groupby("kw")["vol"].max()
    fam = pd.read_csv(runlib.RUNS / families_run / "outputs" / f"families_{ce}.csv")
    fam["research_vol"] = fam["members"].map(lambda ms: max([vol.get(m, 0) for m in ms.split(" | ")] + [0]))
    names = pd.read_csv(runlib.SNAPSHOTS / snap / "cluster_keywords.csv", dtype={"ce": str})
    fam["cid"] = fam["rep"].map(names[names["ce"] == ce].drop_duplicates("kw").set_index("kw")["cid"])
    fam = fam[fam["research_vol"] > 0]
    big = fam[fam["research_vol"] >= gc.SHARED_VOL_MIN].drop_duplicates(["cid", "research_vol"])
    small = fam[fam["research_vol"] < gc.SHARED_VOL_MIN]
    return pd.concat([big, small]).groupby("cid")["research_vol"].sum().rename("planner")


def spread_keywords(snap, ce, pair_mapping, keyword_mapping):
    """One row per keyword x cluster: the keyword's complete totals split by what its served searches did in each
    cluster. Each metric follows its own share (clicks by the searches' clicks, spend by their spend, CM1 by their CM1,
    impression measures by their impressions); when a keyword's searches show none of a metric, its impression shares
    stand in. Keywords with no visible searches (about 1% of impressions) fall back to their own text."""
    totals = pd.read_csv(snap / "keyword_totals.csv")
    pairs = pd.read_csv(snap / "keyword_search_terms.csv")
    pairs["cid"] = pairs["term"].map(assignments(pair_mapping, ce).set_index("term")[COL]).fillna(NO_CLUSTER)
    by = pairs.groupby(["kw_key", "cid"])[["impr", "clicks", "spend", "conv_value"]].sum()
    shares = by / by.groupby(level=0).transform("sum")
    for c in ("clicks", "spend", "conv_value"):
        shares[c] = shares[c].fillna(shares["impr"])
    shares = shares.add_prefix("w_").reset_index()
    by_text = assignments(keyword_mapping, ce).set_index("term")[COL]
    unseen = totals[~totals["kw_key"].isin(shares["kw_key"])]
    shares = pd.concat([shares, pd.DataFrame({"kw_key": unseen["kw_key"], "cid": unseen["keyword"].map(by_text).fillna(NO_CLUSTER),
                                              **{f"w_{c}": 1.0 for c in ("impr", "clicks", "spend", "conv_value")}})])
    spread = totals.merge(shares, on="kw_key")
    weight_of = {"impr": "w_impr", "eligible": "w_impr", "lost_rank": "w_impr", "impr_with_share": "w_impr",
                 "clicks": "w_clicks", "spend": "w_spend", "conv_value": "w_conv_value"}
    for c in PAID:
        spread[c] = spread[c].fillna(0) * spread[weight_of[c]]
    spread["w"] = spread["w_impr"]
    gap = (spread[PAID].sum() - totals[PAID].fillna(0).sum()).abs().max()
    assert gap < 1, f"paid totals do not reconcile after spreading (off by {gap})"
    return spread, pairs


def paid_by_cluster(snap, ce, pair_mapping, keyword_mapping):
    spread, pairs = spread_keywords(snap, ce, pair_mapping, keyword_mapping)
    out = spread.groupby("cid")[PAID].sum()
    out["keywords"] = spread[spread["w"] >= 0.5].groupby("cid").size()
    return out, pairs


def status(r):
    flags = []
    if r["paid_impr_month"] == 0:
        flags.append("No paid coverage")
    elif pd.notna(r["paid_impr_share"]) and r["paid_impr_share"] < LOW_SHARE:
        flags.append(f"Paid impression share under {LOW_SHARE:.0%}")
    if r["organic_presence"] < LOW_ORGANIC:
        flags.append("No organic presence")
    if r["planner_month"] < 0.5 * r["demand_month"]:
        flags.append("Keyword Planner volume under half of demand")
    return "; ".join(flags)


def uncaptured(ce, pairs, organic, other):
    p = pairs[pairs["cid"].isin(other | {NO_CLUSTER})].groupby("term")["impr"].sum().rename("paid_impr")
    o = organic[organic[COL].isna() | organic[COL].isin(other)].groupby("term").agg(
        organic_impr=("impressions", "sum"), organic_clicks=("clicks", "sum"))
    terms = pd.concat([p, o], axis=1).fillna(0)
    terms = terms[~terms.index.str.contains(gc.cluster_fix.COMPETITORS, case=False, regex=True)]
    terms["vol"] = terms["paid_impr"] + terms["organic_impr"]
    fam = gc.build_families(terms.reset_index().rename(columns={"index": "kw", "term": "kw"}).assign(source="search")[["kw", "vol", "source"]])
    return terms, fam[fam["vol"] >= 30].reset_index(drop=True)


def group_uncaptured(ce, terms, fam, model):
    emb = model.encode(fam["rep"].tolist(), normalize_embeddings=True, batch_size=64)
    fam["group"] = AgglomerativeClustering(n_clusters=None, distance_threshold=GROUP_DISTANCE, metric="cosine",
                                           linkage="average").fit_predict(emb) if len(fam) > 1 else 0
    rows = []
    for _, f in fam.groupby("group"):
        t = terms.loc[[m for ms in f["members"] for m in ms if m in terms.index]].sort_values("vol", ascending=False)
        rows.append({"CE": ce, "Search-term cluster": t.index[0], "Intent": gc.TYPE[gc.coarse_intent(t.index[0])], "Searches": len(t),
                     "Paid impressions / month": round(t["paid_impr"].sum() / MONTHS),
                     "Organic impressions / month": round(t["organic_impr"].sum() / MONTHS),
                     "Organic clicks / month": round(t["organic_clicks"].sum() / MONTHS),
                     "Top searches": " | ".join(t.index[:6])})
    out = pd.DataFrame(rows)
    out["_total"] = out["Paid impressions / month"] + out["Organic impressions / month"]
    return out.sort_values("_total", ascending=False).drop(columns="_total")


def main():
    a = runlib.args("capture_analysis", {"--pair-mapping": {"required": True}, "--organic-mapping": {"required": True},
                                         "--keyword-mapping": {"required": True}, "--families-run": {"required": True},
                                         "--tag": {"default": "", "help": "suffix for the workbook files, so a test mapping doesn't overwrite them"}})
    run = runlib.Run("capture_analysis", a.snapshot, {"ces": a.ces, "mapper": COL, "pair_mapping": a.pair_mapping,
                                                      "organic_mapping": a.organic_mapping, "keyword_mapping": a.keyword_mapping,
                                                      "families_run": a.families_run, "group_distance": GROUP_DISTANCE,
                                                      "low_share": LOW_SHARE, "low_organic": LOW_ORGANIC})
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(str(runlib.HERE / MODEL))
    snap = runlib.SNAPSHOTS / a.snapshot
    names = pd.read_csv(snap / "ce_names.csv", dtype={"ce": str}).set_index("ce")["name"]
    cap_parts, gap_parts = [], []
    for ce in a.ces.split(","):
        clusters = pd.read_csv(snap / "cluster_keywords.csv", dtype={"ce": str})
        clusters = clusters[clusters["ce"] == ce].drop_duplicates("cid").set_index("cid")[["name", "t"]]
        clusters.loc[NO_CLUSTER] = [NO_CLUSTER, ""]
        paid, pairs = paid_by_cluster(snap, ce, a.pair_mapping, a.keyword_mapping)
        organic = assignments(a.organic_mapping, ce)
        organic["pos_x_impr"] = organic["avg_position"] * organic["impressions"]
        o = organic.assign(cid=organic[COL].fillna(NO_CLUSTER)).groupby("cid").agg(
            organic_impr=("impressions", "sum"), organic_clicks=("clicks", "sum"), pos=("pos_x_impr", "sum"))
        t = clusters.join([planner_volume(a.snapshot, ce, a.families_run), paid, o]).fillna(0)
        sources = pd.DataFrame({"Keyword Planner": t["planner"], "Paid eligible impressions": t["eligible"] / MONTHS,
                                "Organic impressions": t["organic_impr"] / MONTHS})
        missed = ((t["eligible"] - t["impr_with_share"]) / MONTHS).clip(lower=0)
        cap = pd.DataFrame({
            "CE": ce, "CE name": names[ce], "Cluster": t["name"], "Intent type": t["t"],
            "demand_month": sources.max(axis=1).round(),
            "demand_source": sources.idxmax(axis=1).where(sources.max(axis=1) > 0, ""),
            "planner_month": t["planner"].round(),
            "eligible_month": (t["eligible"] / MONTHS).round(),
            "paid_impr_month": (t["impr"] / MONTHS).round(),
            "paid_clicks_month": (t["clicks"] / MONTHS).round(),
            "spend_month": (t["spend"] / MONTHS).round(2),
            "conv_value_month": (t["conv_value"] / MONTHS).round(2),
            "value_per_spend": (t["conv_value"] / t["spend"]).where(t["spend"] > 0).round(2),
            "ads_keywords": t["keywords"].astype(int),
            "paid_impr_share": (t["impr_with_share"] / t["eligible"]).where(t["eligible"] > 0).round(3),
            "lost_rank_month": (t["lost_rank"] / MONTHS).round(),
            "missed_impr_month": missed.round(),
            "value_at_stake_month": (missed * t["conv_value"] / t["impr"]).where(t["impr"] > 0).fillna(0).round(),
            "organic_impr_month": (t["organic_impr"] / MONTHS).round(),
            "organic_clicks_month": (t["organic_clicks"] / MONTHS).round(),
            "organic_position": (t["pos"] / t["organic_impr"]).where(t["organic_impr"] > 0).round(1),
        })
        demand = cap["demand_month"].where(cap["demand_month"] > 0)
        cap["paid_capture"] = (cap["paid_impr_month"] / demand).fillna(0).round(3)
        # Organic impressions can set demand, so they cannot also measure capture; clicks can
        cap["organic_capture"] = (cap["organic_clicks_month"] / demand).fillna(0).round(4)
        cap["organic_presence"] = (cap["organic_impr_month"] / demand).fillna(0)
        cap["Status"] = cap.apply(status, axis=1).where(cap["Cluster"] != NO_CLUSTER, "")
        cap = cap.drop(columns="organic_presence").sort_values("demand_month", ascending=False)
        cap = pd.concat([cap[cap["Cluster"] != NO_CLUSTER], cap[cap["Cluster"] == NO_CLUSTER]])
        cap_parts.append(cap)
        other = set(clusters.index[clusters["name"].str.startswith("Other")])
        terms, fam = uncaptured(ce, pairs, organic, other)
        gaps = group_uncaptured(ce, terms, fam, model)
        gaps.insert(1, "CE name", names[ce])
        gap_parts.append(gaps)
        for name in ("demand_month", "planner_month", "eligible_month", "paid_impr_month", "spend_month", "conv_value_month",
                     "missed_impr_month", "value_at_stake_month", "organic_impr_month", "organic_clicks_month"):
            run.record(ce, "capture hybrid", name, float(cap[name].sum()))
        run.record(ce, "capture hybrid", "uncaptured_groups", len(gaps))
        print(f"\n=== CE {ce}: {len(cap)} rows, {len(gaps)} search-term clusters outside the clusters")
        print(cap.drop(columns=["CE", "CE name"]).to_string(index=False))
    headers = {"demand_month": "Demand / month", "demand_source": "Demand from", "planner_month": "Keyword Planner volume / month",
               "eligible_month": "Paid eligible impressions / month", "paid_impr_month": "Paid impressions / month",
               "paid_clicks_month": "Paid clicks / month", "spend_month": "Spend / month", "conv_value_month": "CM1, Google-attributed / month",
               "value_per_spend": "Paid ROI % (CM1 ÷ spend)", "ads_keywords": "Google Ads keywords", "paid_impr_share": "Paid impression share",
               "lost_rank_month": "Impressions lost to rank / month", "missed_impr_month": "Impressions missed / month",
               "value_at_stake_month": "CM1 at stake / month", "organic_impr_month": "Organic impressions / month",
               "organic_clicks_month": "Organic clicks / month", "organic_position": "Organic avg position",
               "paid_capture": "Paid capture %", "organic_capture": "Organic click capture %"}
    capture = pd.concat(cap_parts).rename(columns=headers)
    capture.to_csv(run.out / "capture.csv", index=False)
    capture.to_csv(WB / f"capture{'_' + a.tag if a.tag else ''}.csv", index=False)
    gaps = pd.concat(gap_parts)
    gaps.to_csv(run.out / "uncaptured.csv", index=False)
    gaps.to_csv(WB / f"uncaptured{'_' + a.tag if a.tag else ''}.csv", index=False)
    run.close()


if __name__ == "__main__":
    main()
