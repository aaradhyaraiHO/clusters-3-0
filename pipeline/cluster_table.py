"""Build the Clusters 3.0 table: one row per EOS cluster, one column group per data source (Parag's spec).

  Demand          EOS keyword research        keywords, volume (top keyword's monthly volume, not the sum), intent type
  Paid coverage   Google Ads ad groups        ad groups serving the cluster's search terms, top ad group's share
                                              (routing share), dedicated or shared, AI Max share of clicks
  Paid perf.      Google Ads search terms     impressions, clicks, spend, conversions, conversion value (Google-reported)
  Paid revenue    Orders -> gclid -> clicks   Headout revenue of paid orders via booking attribution logs and
                                              google_ads_click_stats (targeted keyword or ad group), not Google-reported
  Setup           Payload microbrand pages    pages mapped to the cluster (type, subtype, collection, noIndex)
  Results         Orders (fct_orders_lambda)  orders and revenue landing on the cluster's pages, all channels

Each group comes from one source and is exact on its own terms. Search terms map to clusters through the layered
mapper (mapping run); pages map to clusters with the same mapper applied to their focus keyword.

Usage: python cluster_table.py --snapshot 20261028_v2_full_plus --mapping-run <run_id> --model <dir> [--ces 189]
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

import polyfuzz_mapping as pm
import runlib

LOCALE = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")
HOSTS = {"189": "www.thevaticantickets.com", "325": "www.parkguell-tickets.com"}


def page_text(r):
    fk = str(r["focus_keyword_en"] or "")
    fk = re.sub(r":-.*$", "", fk).strip()  # drop CMS uniqueness suffixes like ":-R2HB-FKW_SUFFIX"
    if not fk or fk.startswith("MISSING_FKW") or fk == "nan":
        fk = r["uid"].split(".")[-1].replace("-", " ")  # fall back to the slug
    return fk


def path_of_uid(uid, host):
    rest = uid[len(host):].lstrip(".")
    return rest.replace(".", "/")


def path_of_landing(lp, host):
    if not isinstance(lp, str) or not lp.startswith(host):
        return None
    segs = [s for s in lp[len(host):].split("/") if s]
    if segs and LOCALE.match(segs[0]):
        segs = segs[1:]
    return "/".join(segs)


def map_texts(texts, kw_ce, cc, model, pf_min=0.8, emb_min=0.85, use_identifiers=True):
    """Layered mapper on arbitrary texts: identifier rule -> PolyFuzz >= pf_min -> embeddings >= emb_min.

    Pages skip the identifier rule: their focus keywords are short, so single-word identifiers ("line", "tour",
    "tickets") misfire the same way they do in EOS ("/vatican-tours" landed in Virtual Tours via "vatican 3d tour").
    """
    norm = [pm.norm(t) for t in texts]
    out = pd.DataFrame({"text": texts, "tn": norm})
    out["cid"] = out["tn"].map(lambda x: pm.current_rule(x, cc)) if use_identifiers else None
    out["how"] = np.where(out["cid"].notna(), "identifier", None)
    pf = pm.polyfuzz_match(out["tn"].unique(), kw_ce, cc).drop_duplicates("tn").set_index("tn")
    fill = out["cid"].isna() & out["tn"].map(pf["score"]).ge(pf_min)
    out.loc[fill, "cid"] = out.loc[fill, "tn"].map(pf["cid"])
    out.loc[fill, "how"] = "polyfuzz"
    rest = out.loc[out["cid"].isna(), "text"].unique()
    if len(rest):
        em = pm.embed_match(rest, kw_ce, cc, model).set_index("tn")
        fill = out["cid"].isna() & out["text"].map(em["e_score"]).ge(emb_min)
        out.loc[fill, "cid"] = out.loc[fill, "text"].map(em["E_raw"])
        out.loc[fill, "how"] = "embedding"
    return out


def build(run, ce, mapping_run, model):
    kw = pd.read_csv(run.input("cluster_keywords.csv"), dtype={"ce": str})
    kw = kw[kw["ce"] == ce]
    kw_all = kw.copy()  # clusters are ordered the same way as in the mapping run (rank, then stored order)
    kw_all["order"] = range(len(kw_all))
    cl = (kw_all.groupby("cid", sort=False)
          .agg(name=("name", "first"), t=("t", "first"), rank=("rank", "first"), ids=("ids", "first"), order=("order", "min"),
               n_kw=("kw", "count"), vol_top=("vol", "max"),
               focus_kw=("kw", lambda s: s.loc[kw_all.loc[s.index, "vol"].idxmax()] if kw_all.loc[s.index, "vol"].notna().any() else None))
          .reset_index())
    cl["ids"] = cl["ids"].map(lambda x: [pm.norm(i) for i in __import__("json").loads(x)] if isinstance(x, str) else [])
    cl["sort_key"] = cl.apply(lambda r: (0, r["rank"]) if pd.notna(r["rank"]) else (1, r["order"]), axis=1)
    cc = cl.sort_values("sort_key").assign(ce=ce)
    cc_ = cc[["cid", "ids"]]

    # --- paid: search terms x ad group, mapped through the mapping run's term -> cluster assignment
    path = run.upstream(mapping_run, f"assignments_{ce}.csv")
    method = next(c for c in ["E0.85", "D0.85"] if c in pd.read_csv(path, nrows=0).columns)  # newest mapper available
    asg = pd.read_csv(path, usecols=["term", method]).drop_duplicates("term").rename(columns={method: "D0.85"})
    st = pd.read_csv(run.input("search_terms_by_adgroup.csv"), dtype={"ce": str, "ad_group_id": str})
    st = st[st["ce"] == ce].merge(asg, on="term", how="left").rename(columns={"D0.85": "cid"})
    run.record(ce, "cluster table", "uses_mapper_E", float(method == "E0.85"))
    st["is_ai_max"] = st["match_type"].eq("AI_MAX")
    ag_tot = st.groupby("ad_group_id")["clicks"].sum()

    paid = st[st["cid"].notna()].groupby("cid").agg(
        impr=("impr", "sum"), clicks=("clicks", "sum"), spend=("spend", "sum"), conv=("conv", "sum"), conv_value=("conv_value", "sum"),
        n_ad_groups=("ad_group_id", "nunique"), ai_max_clicks=("clicks", lambda s: s[st.loc[s.index, "is_ai_max"]].sum()))
    top = (st[st["cid"].notna()].groupby(["cid", "ad_group_id", "ad_group_name"])["clicks"].sum().reset_index()
           .sort_values("clicks", ascending=False).drop_duplicates("cid").set_index("cid"))
    paid["top_ad_group"] = top["ad_group_name"]
    paid["routing_share"] = top["clicks"] / paid["clicks"]  # share of the cluster's clicks served by its top ad group
    paid["top_ag_purity"] = top["clicks"] / top["ad_group_id"].map(ag_tot)  # share of that ad group's clicks from this cluster
    paid["coverage"] = np.select([paid["top_ag_purity"] >= 0.5, paid["clicks"] > 0], ["Dedicated", "Shared"], "None")

    # --- paid revenue (Headout's own, amount_revenue_usd): order -> booking -> gclid -> Google Ads click
    #     keyword clicks: the targeted keyword maps to a cluster like a search term does (exact term match, else the
    #     layered mapper); keyword-less clicks (mostly AI Max): the ad group's revenue is split by its search-term
    #     click mix; orders without a matched click stay unattributed.
    po = pd.read_csv(run.input("paid_orders_by_click.csv"), dtype={"ce": str, "ad_group_id": str})
    po = po[po["ce"] == ce].copy()
    term_cid = asg.set_index("term")["D0.85"]
    kws = po["keyword_text"].dropna().unique()
    known = {k: term_cid.get(k) for k in kws if k in term_cid.index and pd.notna(term_cid.get(k))}
    rest = [k for k in kws if k not in known]
    if rest:
        km = map_texts(rest, kw, cc_.assign(ce=ce), model, pf_min=0.7, emb_min=0.85)
        known.update({t: c for t, c in zip(km["text"], km["cid"]) if pd.notna(c)})
    po["cid"] = po["keyword_text"].map(known)
    with_kw = po[po["keyword_text"].notna()]
    rev_kw = with_kw.groupby("cid")[["orders", "revenue_usd"]].sum()
    no_kw = po[(po["match_status"] == "matched") & po["keyword_text"].isna()].groupby("ad_group_id")[["orders", "revenue_usd"]].sum()
    mix = st[st["cid"].notna()].groupby(["ad_group_id", "cid"])["clicks"].sum()
    mix = (mix / mix.groupby(level=0).transform("sum")).rename("w").reset_index()
    spread = mix.merge(no_kw.reset_index(), on="ad_group_id")
    rev_spread = spread.assign(orders=spread["orders"] * spread["w"], revenue_usd=spread["revenue_usd"] * spread["w"]).groupby("cid")[["orders", "revenue_usd"]].sum()
    paid_rev = rev_kw.add(rev_spread, fill_value=0).rename(columns={"orders": "paid_orders", "revenue_usd": "paid_revenue"})
    paid = paid.join(paid_rev, how="left") if len(paid) else paid
    paid["paid_rev_per_spend"] = paid["paid_revenue"] / paid["spend"]
    tot_paid_rev = po["revenue_usd"].sum()

    # --- setup: microbrand pages mapped to clusters by their focus keyword
    host = HOSTS[ce]
    pages = pd.read_csv(run.input("mb_pages.csv"), dtype={"ce": str, "collection_id": str})
    pages = pages[(pages["ce"] == ce) & pages["status_en"].eq("published")].copy()
    pages["text"] = pages.apply(page_text, axis=1)
    pages["path"] = pages["uid"].map(lambda u: path_of_uid(u, host))
    if len(pages):
        pmap = map_texts(pages["text"].tolist(), kw, cc_.assign(ce=ce), model, pf_min=0.75, emb_min=0.8, use_identifiers=False)
        pages["cid"] = pmap["cid"].to_numpy()
        pages["how"] = pmap["how"].to_numpy()
    else:
        pages["cid"], pages["how"] = None, None

    # --- results: orders landing on each page, all channels
    orders = pd.read_csv(run.input("orders_by_landing.csv"), dtype={"ce": str})
    orders = orders[orders["ce"] == ce].copy()
    orders["path"] = orders["landing_path"].map(lambda p: path_of_landing(p, host))
    by_path = orders.dropna(subset=["path"]).groupby("path").agg(orders=("orders", "sum"), revenue=("revenue_usd", "sum"))
    pages = pages.merge(by_path, left_on="path", right_index=True, how="left").fillna({"orders": 0, "revenue": 0})
    res = pages[pages["cid"].notna()].groupby("cid").agg(
        pages=("path", lambda s: " · ".join("/" + p if p else "/ (home)" for p in s)),
        page_types=("page_sub_type", lambda s: ", ".join(sorted(set(map(str, s))))),
        noindex_pages=("any_noindex", "sum"), orders=("orders", "sum"), revenue=("revenue", "sum"))

    ce_rev = orders["revenue_usd"].sum()
    table = cc.drop(columns=["ids", "sort_key", "order", "ce"]).set_index("cid").join(paid).join(res)
    table["pct_ce_revenue"] = table["revenue"] / ce_rev
    table = table.reset_index().sort_values(["t", "clicks"], ascending=[False, False])
    table.to_csv(run.out / f"cluster_table_{ce}.csv", index=False)
    pages.to_csv(run.out / f"pages_{ce}.csv", index=False)
    st.to_csv(run.out / f"search_terms_mapped_{ce}.csv", index=False)

    tot_clicks = st["clicks"].sum()
    mb_rev = orders.loc[orders["path"].notna(), "revenue_usd"].sum()
    rec = lambda m, v: run.record(ce, "cluster table", m, v)  # noqa: E731
    rec("pct_paid_clicks_in_a_cluster", 100 * st.loc[st["cid"].notna(), "clicks"].sum() / tot_clicks)
    rec("pct_paid_clicks_ai_max", 100 * st.loc[st["is_ai_max"], "clicks"].sum() / tot_clicks)
    rec("n_clusters", len(table))
    rec("n_clusters_with_paid_clicks", (table["clicks"] > 0).sum())
    rec("n_clusters_dedicated_ad_group", (table["coverage"] == "Dedicated").sum())
    rec("median_routing_share", 100 * table["routing_share"].median())
    rec("n_published_mb_pages", len(pages))
    rec("n_pages_mapped_to_cluster", pages["cid"].notna().sum())
    rec("n_clusters_with_a_page", table["pages"].notna().sum())
    rec("pct_ce_revenue_landing_on_microbrand", 100 * mb_rev / ce_rev)
    rec("pct_ce_revenue_on_pages_mapped_to_clusters", 100 * res["revenue"].sum() / ce_rev if len(res) else 0)
    rec("paid_revenue_usd_total", tot_paid_rev)
    rec("pct_paid_revenue_matched_to_click", 100 * po.loc[po["match_status"] == "matched", "revenue_usd"].sum() / tot_paid_rev)
    rec("pct_paid_revenue_with_keyword", 100 * with_kw["revenue_usd"].sum() / tot_paid_rev)
    rec("pct_paid_revenue_attributed_to_cluster", 100 * table["paid_revenue"].sum() / tot_paid_rev)
    return table, pages, ce_rev, mb_rev


def main():
    a = runlib.args("cluster_table", {"--mapping-run": {"required": True}, "--model": {"required": True}})
    run = runlib.Run("cluster_table", a.snapshot, {"ces": a.ces, "mapping_run": a.mapping_run, "embed_model": Path(a.model).name,
                                                   "volume": "top keyword (max)", "dedicated_rule": "top ad group >= 50% of its clicks from the cluster",
                                                   "page_mapper": "identifier -> polyfuzz>=0.8 -> embeddings>=0.85 on page focus keyword"})
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(a.model)
    pd.set_option("display.width", 250, "display.max_colwidth", 40, "display.max_columns", 30)
    for ce in a.ces.split(","):
        table, pages, ce_rev, mb_rev = build(run, ce, a.mapping_run, model)
        cols = ["name", "t", "vol_top", "coverage", "routing_share", "clicks", "spend", "paid_revenue", "paid_rev_per_spend", "conv_value", "revenue", "pct_ce_revenue"]
        print(f"\n=== CE {ce}: revenue ${ce_rev:,.0f}, on microbrand ${mb_rev:,.0f}")
        print(table[cols].round(2).to_string(index=False))
        print("\nunmapped pages:", pages.loc[pages["cid"].isna(), ["path", "text", "revenue"]].to_string(index=False))
    run.close()


if __name__ == "__main__":
    main()
