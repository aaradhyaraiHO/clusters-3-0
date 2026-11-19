"""Build the per-cluster drawer data: every keyword, every search (paid and organic joined on the text), the Google Ads
keywords we target, ad groups, products.

Usage: python3 export_drawer_data.py <clusters_3_0 dir that holds runs/ and snapshots/>
Writes drawer.json next to this file.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1])
CE = 189
# Must match the runs named in vatican.json's "sources", or the drawer and the table disagree.
TABLE_RUN = "20261028-183154_cluster_table_20261028_v3_rebuilt"
MAPPING_RUN = "20261028-183057_mapping_20261028_v3_rebuilt"
SOURCES_RUN = "20261028-200541_cluster_sources_20261028_v4_connected"
SNAPSHOT = "20261028_v3_rebuilt"
# Targeted Google Ads keywords (keyword report). This pull has no manifest; it is taken as the same 90-day window.
TARGET_SNAPSHOT = "20261029_capture_v1"
TOP_SEARCHES = 150

norm = lambda s: " ".join(str(s).lower().split())

kw = pd.read_csv(ROOT / "snapshots" / SNAPSHOT / "cluster_keywords.csv")
kw = kw[kw["ce"] == CE].assign(k=lambda d: d["kw"].map(norm))
paid_all = pd.read_csv(ROOT / "runs" / TABLE_RUN / "outputs" / f"search_terms_mapped_{CE}.csv")
ag_total = paid_all.groupby("ad_group_id")["clicks"].sum()
paid = paid_all.dropna(subset=["cid"])
paid = paid.assign(k=paid["term"].map(norm), ai_clicks=paid["clicks"].where(paid["is_ai_max"].astype(str) == "True", 0))
how = (pd.read_csv(ROOT / "runs" / MAPPING_RUN / "outputs" / f"assignments_{CE}.csv", usecols=["term", "E_how"])
       .assign(k=lambda d: d["term"].map(norm)).drop_duplicates("k").set_index("k")["E_how"])
org = pd.read_csv(ROOT / "runs" / SOURCES_RUN / "outputs" / f"organic_{CE}.csv").dropna(subset=["cid"]).assign(k=lambda d: d["term"].map(norm))
sup = pd.read_csv(ROOT / "runs" / SOURCES_RUN / "outputs" / f"supply_{CE}.csv")

# A targeted keyword belongs to a cluster when it is one of the cluster's EOS keywords, or else where the search-term mapper
# puts the same text. "Active" = it had impressions in the window; the pull carries no enabled / paused status.
assign = (pd.read_csv(ROOT / "runs" / MAPPING_RUN / "outputs" / f"assignments_{CE}.csv", usecols=["term", "E_name", "E_how"])
          .assign(k=lambda d: d["term"].map(norm)).drop_duplicates("k").set_index("k"))
name_to_cid = dict(zip(kw["name"], kw["cid"]))
kw_to_cid = dict(zip(kw["k"], kw["cid"]))


def target_cid(k):
    if k in kw_to_cid:
        return kw_to_cid[k]
    if k in assign.index and assign.at[k, "E_how"] != "unmapped":
        return name_to_cid.get(assign.at[k, "E_name"])
    return None


tsnap = ROOT / "snapshots" / TARGET_SNAPSHOT
shares = pd.read_csv(tsnap / "keyword_shares.csv")
shares = shares[(shares["ce"] == CE) & (shares["impr"] > 0)].assign(k=lambda d: d["keyword"].map(norm))
shares["cid"] = shares["k"].map(target_cid)
totals = pd.read_csv(tsnap / "keyword_totals.csv").assign(k=lambda d: d["keyword"].map(norm),
                                                          ad_group_id=lambda d: d["kw_key"].str.split("~").str[0])
totals = totals[totals["k"].isin(set(shares["k"]))]
by_kw = totals.groupby("k").agg(clicks=("clicks", "sum"), spend=("spend", "sum"), cm1=("conv_value", "sum"), groups=("ad_group_id", "nunique"))
shares = shares.join(by_kw, on="k")
targeted_match = dict(zip(shares["k"], shares["match_types"]))

# Where each ad group's paid clicks land: Google Ads landing-page stats for cid189 search campaigns, 30 Jul - 27 Oct,
# pulled to landing_pages.csv (campaign x ad group x host, with the top path). A cluster's landing mix is its clicks in
# each ad group spread over that ad group's hosts.
lp = pd.read_csv(HERE / "landing_pages.csv")
# Final URLs carry a "{ignore}" tracking placeholder, and www / bare host are the same site.
lp["host"] = lp["host"].str.replace(r"^www\.", "", regex=True)
lp["top_path"] = lp["top_path"].str.replace("{ignore}", "", regex=False)
lp = lp.groupby(["campaign_name", "ad_group_name", "host", "top_path"], as_index=False)[["clicks", "spend"]].sum()
lp["ag_share"] = lp["clicks"] / lp.groupby(["campaign_name", "ad_group_name"])["clicks"].transform("sum")
ag_landing = (lp.sort_values("clicks", ascending=False).drop_duplicates(["campaign_name", "ad_group_name"])
              .set_index(["campaign_name", "ad_group_name"])["top_path"])

# Which targeted keyword caught each search term, per ad group: the keyword with the most impressions on that term in
# that ad group. Clicks Google flags as AI Max had no keyword behind them.
kst = pd.read_csv(tsnap / "keyword_search_terms.csv").merge(pd.read_csv(tsnap / "keyword_totals.csv")[["kw_key", "keyword"]], on="kw_key", how="left")
kst = kst.assign(k=kst["term"].map(norm), ag=kst["kw_key"].str.split("~").str[0])
caught_by = kst.sort_values("impr", ascending=False).drop_duplicates(["k", "ag"]).set_index(["k", "ag"])["keyword"]


def ag_label(name, campaign):
    # Vatican ad groups are "<intent> - <match> - <language> - <sub-theme>"; the flow reads theme and language.
    p = str(name).split(" - ")
    theme = p[0] + ("" if len(p) < 4 or p[3] == "All" else " · " + p[3])
    return f"{theme} · {p[2]}" if len(p) > 2 else str(name)


def land_label(path, own_paths):
    path = str(path)
    # A language copy ("/es/sistine-chapel/") of the cluster's own page counts as its own page; the root is "".
    bare = re.sub(r"^/[a-z]{2}/", "/", path).rstrip("/")
    if bare in own_paths:
        return "its own page"
    return "home page" if re.fullmatch(r"/([a-z]{2}/)?", path) else "other page"



def page_kind(url):
    path = "/" + str(url).split("/", 3)[3] if str(url).count("/") >= 3 else "/"
    if "/blog/" in path:
        return "Blog"
    # A bare host or a language root ("/it/") is the site's home page.
    return "Home page" if len(path.strip("/")) <= 5 and "-" not in path else "Dedicated page"


r = lambda v, d=0: None if pd.isna(v) else round(float(v), d) if d else int(round(float(v)))
cid_name = dict(zip(kw["cid"], kw["name"]))
targeted_all = set(shares["k"])
# The Perf request lists a search as an "add keyword" candidate only above this many clicks in the 90 days, so the ask
# names terms worth an ad group's time.
MIN_TERM_CLICKS = 20
pages_tbl = pd.read_csv(ROOT / "runs" / TABLE_RUN / "outputs" / f"pages_{CE}.csv")
own_paths = {}
if {"cid", "path"} <= set(pages_tbl.columns):
    for c_, pth in zip(pages_tbl["cid"], pages_tbl["path"]):
        # Paths are stored without the host; an empty path is the site root.
        own_paths.setdefault(c_, set()).add("" if pd.isna(pth) else "/" + str(pth).strip("/"))
out = {"counts": {"keywords": int(len(kw)), "paid_terms": int(paid["k"].nunique()), "organic_queries": int(org["k"].nunique())}, "clusters": {}}

for cid in kw["cid"].unique():
    k = kw[kw["cid"] == cid]
    p = paid[paid["cid"] == cid]
    o = org[org["cid"] == cid]
    pt = p.groupby("k").agg(term=("term", "first"), clicks=("clicks", "sum"), spend=("spend", "sum"), cm1=("conv_value", "sum"),
                            ai=("ai_clicks", "sum"), groups=("ad_group_id", "nunique"))
    ot = o.groupby("k").agg(oterm=("term", "first"), oclicks=("clicks", "sum"), impr=("impressions", "sum"),
                            pos=("avg_position", "mean"), page=("top_page", "first"), ohow=("E_how", "first"))
    s = pt.join(ot, how="outer")
    s["term"] = s["term"].fillna(s["oterm"])
    s["is_kw"] = s.index.isin(set(k["k"]))
    s["how"] = pd.Series(s.index.map(how), index=s.index).fillna(s["ohow"])
    s["weight"] = s["clicks"].fillna(0) + s["oclicks"].fillna(0)
    s = s.sort_values("weight", ascending=False)
    top = s.head(TOP_SEARCHES)

    ag = p.groupby(["ad_group_id", "ad_group_name", "campaign_name"]).agg(clicks=("clicks", "sum"), spend=("spend", "sum"), cm1=("conv_value", "sum"),
                                                                        terms=("k", "nunique")).reset_index().sort_values("clicks", ascending=False)
    ag["share"] = ag["clicks"] / ag["ad_group_id"].map(ag_total)
    pages = o.groupby("top_page")["clicks"].sum().sort_values(ascending=False)
    top_page = pages.index[0] if len(pages) and pages.iloc[0] > 0 else None
    sp = sup[sup["cid"] == cid].sort_values(["live", "revenue_usd"], ascending=False)
    tg = shares[shares["cid"] == cid].sort_values("impr", ascending=False)
    eos_vol = k["vol"].fillna(0)
    targeted_eos = k["k"].isin(set(shares["k"]))
    # Share of the cluster's demand we bid on: EOS keyword volume that is also a targeted keyword. Clusters whose
    # keywords carry no volume fall back to the share of keywords.
    vol_share = (eos_vol[targeted_eos].sum() / eos_vol.sum()) if eos_vol.sum() else (targeted_eos.mean() if len(k) else 0)
    tg_by_ag = totals[totals["k"].isin(set(tg["k"]))]

    # Paid status flow: search term -> keyword that caught it -> ad group -> landing page, sized by paid clicks.
    fl = p.assign(agk=p["ad_group_id"].astype("int64").astype(str), ai=p["is_ai_max"].astype(str) == "True")
    fl["kw"] = [("AI Max, no keyword" if a else caught_by.get((t, g), "keyword not found")) for t, g, a in zip(fl["k"], fl["agk"], fl["ai"])]
    fl["agl"] = [ag_label(n, cn) for n, cn in zip(fl["ad_group_name"], fl["campaign_name"])]
    fl["land"] = [land_label(ag_landing.get((cn, n), ""), own_paths.get(cid, set())) for cn, n in zip(fl["campaign_name"], fl["ad_group_name"])]
    keep = lambda col, n: fl.groupby(col)["clicks"].sum().sort_values(ascending=False).head(n).index
    tk, kk, ak = keep("term", 7), keep("kw", 7), keep("agl", 6)
    fl["t2"] = fl["term"].where(fl["term"].isin(tk), "other searches")
    fl["k2"] = fl["kw"].where(fl["kw"].isin(kk) | fl["kw"].isin(["AI Max, no keyword"]), "other keywords")
    fl["a2"] = fl["agl"].where(fl["agl"].isin(ak), "other ad groups")
    flow = []
    for a, b, sa, sb in [("t2", "k2", "t", "k"), ("k2", "a2", "k", "a"), ("a2", "land", "a", "l")]:
        for (x, y), v in fl.groupby([a, b])["clicks"].sum().items():
            if v > 0:
                flow.append([sa + ":" + x, sb + ":" + y, int(v)])
    caught = (fl.groupby(["term", "kw", "agl", "land"]).agg(clicks=("clicks", "sum"), spend=("spend", "sum"))
              .reset_index().sort_values("clicks", ascending=False).head(60))
    # Impression share over the cluster's targeted keywords; CM1 at stake prices the searches lost to rank at the
    # cluster's own CM1 per impression.
    eligible = tg["eligible"].sum()
    imp_share = {"sis": r(tg["impr_with_share"].sum() / eligible, 3) if eligible else None,
                 "lost": r(tg["lost_rank"].sum() / eligible, 3) if eligible else None,
                 "stake": r(tg["lost_rank"].sum() * tg["cm1"].sum() / tg["impr"].sum(), 2) if eligible and tg["impr"].sum() else None}
    land = (p.groupby(["campaign_name", "ad_group_name"])["clicks"].sum().rename("cl").reset_index()
            .merge(lp, on=["campaign_name", "ad_group_name"]))
    land["est"] = land["cl"] * land["ag_share"]
    by_host = land.groupby("host")["est"].sum().sort_values(ascending=False)
    by_path = land.groupby(["host", "top_path"])["est"].sum().sort_values(ascending=False)
    land_total = by_host.sum()

    # Evidence for the Perf request. Dedicated ad groups (50%+ of their clicks from this cluster) are where new keywords
    # go and where other clusters' searches become negatives.
    ded = ag[ag["share"] >= 0.5]
    home = (ded if len(ded) else ag).head(1)
    untargeted = pt[~pt.index.isin(targeted_all) & (pt["clicks"] >= MIN_TERM_CLICKS)].sort_values("clicks", ascending=False)
    in_ded = paid_all[paid_all["ad_group_id"].isin(set(ded["ad_group_id"])) & paid_all["cid"].notna() & (paid_all["cid"] != cid)]
    neg = (in_ded.assign(k=in_ded["term"].map(norm)).groupby(["k", "cid"]).agg(term=("term", "first"), clicks=("clicks", "sum"),
                                                                           spend=("spend", "sum"), groups=("ad_group_id", "nunique"))
           .reset_index().sort_values("clicks", ascending=False))
    neg = neg[neg["clicks"] >= MIN_TERM_CLICKS]
    camps = p.groupby("campaign_name")["clicks"].sum().sort_values(ascending=False)
    shared_ags = ag[ag["share"] < 0.1].head(5)
    perf = {
        "home_ad_group": None if home.empty else {"name": home.iloc[0]["ad_group_name"], "campaign": home.iloc[0]["campaign_name"],
                                                  "dedicated": bool(len(ded))},
        "untargeted": [{"term": x.term, "clicks": r(x.clicks), "spend": r(x.spend, 2), "cm1": r(x.cm1, 2)} for x in untargeted.head(10).itertuples()],
        "untargeted_spend": r(untargeted["spend"].sum(), 2), "untargeted_clicks": r(untargeted["clicks"].sum()),
        "eos_untargeted": [{"kw": x.kw, "vol": r(x.vol)} for x in k[~k["k"].isin(targeted_all)].sort_values("vol", ascending=False).head(5).itertuples()],
        "campaigns": [{"name": c, "share": r(v / camps.sum(), 3)} for c, v in camps.head(5).items()] if camps.sum() else [],
        "negatives": [{"term": x.term, "clicks": r(x.clicks), "spend": r(x.spend, 2), "belongs": cid_name.get(x.cid, "another cluster")}
                      for x in neg.head(8).itertuples()],
        "negatives_spend": r(neg["spend"].sum(), 2),
        "shared_ad_groups": [{"name": x.ad_group_name, "campaign": x.campaign_name, "clicks": r(x.clicks), "share": r(x.share, 3)}
                             for x in shared_ags.itertuples()],
    }

    out["clusters"][cid] = {
        "keywords": [{"kw": x.kw, "vol": r(x.vol), "clicks": r(s.loc[x.k, "clicks"]) if x.k in s.index else None,
                      "oclicks": r(s.loc[x.k, "oclicks"]) if x.k in s.index else None,
                      "pos": r(s.loc[x.k, "pos"], 1) if x.k in s.index else None, "targeted": targeted_match.get(x.k)}
                     for x in k.sort_values("vol", ascending=False).itertuples()],
        "searches": [{"term": x.term, "kw": bool(x.is_kw), "clicks": r(x.clicks), "spend": r(x.spend, 2), "cm1": r(x.cm1, 2),
                      "ai": r(x.ai), "groups": r(x.groups), "oclicks": r(x.oclicks), "impr": r(x.impr), "pos": r(x.pos, 1),
                      "page": None if pd.isna(x.page) else str(x.page).replace("https://", ""),
                      "how": None if pd.isna(x.how) else x.how} for x in top.itertuples()],
        # An ad group is dedicated to the cluster when 50%+ of its clicks come from the cluster; the table's coverage
        # bands (50% / 10%) read the share of the cluster's clicks that land in such ad groups.
        "dedicated": {"groups": int((ag["share"] >= 0.5).sum()), "of": int(len(ag)),
                      "share": r(ag.loc[ag["share"] >= 0.5, "clicks"].sum() / ag["clicks"].sum(), 3) if ag["clicks"].sum() else None},
        "targeted": {"n": int(len(tg)), "vol_share": r(vol_share, 3), "eos_targeted": int(targeted_eos.sum()),
                     "list": [{"kw": x.keyword, "match": x.match_types, "impr": r(x.impr), "clicks": r(x.clicks), "spend": r(x.spend, 2),
                               "cm1": r(x.cm1, 2), "sis": r(x.impr_with_share / x.eligible, 3) if x.eligible else None,
                               "lost": r(x.lost_rank / x.eligible, 3) if x.eligible else None, "groups": r(x.groups),
                               "eos": x.k in kw_to_cid and kw_to_cid[x.k] == cid} for x in tg.head(60).itertuples()]},
        "impression_share": imp_share,
        "perf": perf,
        "flow": flow,
        "caught": [{"term": x.term, "kw": x.kw, "ag": x.agl, "land": x.land, "clicks": r(x.clicks), "spend": r(x.spend, 2)} for x in caught.itertuples()],
        "landing": {"hosts": [{"host": h, "share": r(v / land_total, 3)} for h, v in by_host.items() if v / land_total >= 0.001],
                    "pages": [{"host": h, "path": pth, "share": r(v / land_total, 3)} for (h, pth), v in by_path.head(8).items()]} if land_total else None,
        "ranking_page": None if top_page is None else {"url": str(top_page).replace("https://", ""), "kind": page_kind(top_page),
                                                       "share": r(pages.iloc[0] / pages.sum(), 3)},
        "search_totals": {"n": int(len(s)), "paid_terms": int(pt.shape[0]), "organic_queries": int(ot.shape[0]),
                          "rest_clicks": r(s["clicks"].iloc[TOP_SEARCHES:].sum()), "rest_oclicks": r(s["oclicks"].iloc[TOP_SEARCHES:].sum())},
        "ad_groups": [{"name": x.ad_group_name, "campaign": x.campaign_name, "clicks": r(x.clicks), "spend": r(x.spend, 2),
                       "cm1": r(x.cm1, 2), "terms": int(x.terms), "share": r(x.share, 3),
                       "landing": lp[(lp["campaign_name"] == x.campaign_name) & (lp["ad_group_name"] == x.ad_group_name)].sort_values("clicks", ascending=False)
                                  .apply(lambda y: f"{y.host}{y.top_path}", axis=1).head(2).tolist(),
                       "label": ag_label(x.ad_group_name, x.campaign_name),
                       "targeted": tg_by_ag[tg_by_ag["ad_group_id"] == str(int(x.ad_group_id))].sort_values("impr", ascending=False).drop_duplicates("k")["keyword"].head(8).tolist(),
                       "top_terms": [{"term": t.term, "clicks": r(t.clicks), "spend": r(t.spend, 2)} for t in
                                     p[p["ad_group_id"] == x.ad_group_id].groupby("k").agg(term=("term", "first"), clicks=("clicks", "sum"),
                                                                                      spend=("spend", "sum")).sort_values("clicks", ascending=False).head(10).itertuples()]}
                      for x in ag.head(30).itertuples()],
        "ad_group_count": int(len(ag)),
        "products": [{"name": x.experience_name, "live": bool(x.live), "orders": r(x.orders), "revenue": r(x.revenue_usd)} for x in sp.itertuples()],
    }

(HERE / "drawer.json").write_text(json.dumps(out, separators=(",", ":")))
print(f"{len(out['clusters'])} clusters, {out['counts']} -> {HERE / 'drawer.json'}")
