"""Connect the cluster table's missing column groups: supply, Headout entity, organic search, and demand for seeded clusters.

  Supply      dim_experiences (+ 90-day orders)    experiences whose name holds every intent word of one of the cluster's
                                                    keywords (translated to canonical form); many-to-many
  HO entity   dim_collections descendants of the   the CE's child collections and child POIs whose name words all appear in
              CE collection, dim_pois children     one of the cluster's keywords; none -> the cluster lives on the CE collection
  Organic     Search Console keyword x page        organic queries mapped by an earlier mapping run on gsc_terms.csv
  Demand      seed_volumes.csv, else impressions   seeded clusters have no EOS volume: a known Keyword Planner/EOS volume
                                                    when there is one, else the larger of paid and organic monthly
                                                    impressions of the cluster's own keywords (a lower bound, flagged)

Usage: python cluster_sources.py --snapshot 20261028_v4_connected --gsc-mapping-run <run_id> [--ces 189]
"""
import re

import numpy as np
import pandas as pd

import ce_config
import polyfuzz_mapping as pm
import runlib

WINDOW_MONTHS = 3
# Collections reached only through an experience's mapping are other CEs (Colosseum) or campaigns (Black Friday):
# only the CE's own subtree and its child POIs count as places a cluster can live.
ENTITY_SOURCES = {"descendant", "child_poi"}
# An entity belongs to a cluster only when this share of the cluster's keywords name it: one stray keyword
# ("sistine chapel official website") must not tie the Official site cluster to the Sistine Chapel collection
ENTITY_SHARE = 0.25
ORGANIC_MAPPER = "D0.85"  # the bake-off mapper, no CE-specific rules; the same column capture_analysis.py reads
# Name words that describe a product format, not a place or intent of its own
NAME_GENERIC = {"combo", "general", "info", "visiting", "head", "term"}


def singular(w):
    if w in ce_config.EQUIV_GROUPS or len(w) <= 3 or w.endswith("ss"):
        return w
    if w.endswith("es") and w[:-2].endswith(("ss", "x", "ch", "sh", "o")):
        return w[:-2]
    return w[:-1] if w.endswith("s") else w


def toks(text, ce):
    return {singular(w) for w in pm.content_tokens(pm.norm(text), ce)}


def name_parts(name):
    """'Night / After-Hours / Evening Tours' -> ['Night', 'After-Hours', 'Evening Tours']."""
    return [x for x in re.split(r"\s*(?:[&/+(),:]|\band\b)\s*", name) if x.strip()]


def contains(needle, hay):
    return bool(needle) and all(pm.token_in(t, hay) for t in needle)


def build(run, ce, gsc_run):
    kw = pd.read_csv(run.input("cluster_keywords.csv"), dtype={"ce": str})
    kw = kw[(kw["ce"] == ce) & kw["kw"].notna()].copy()
    kw["toks"] = kw["kw"].map(lambda k: frozenset(toks(k, ce)))
    clusters = kw.groupby("cid", sort=False).agg(name=("name", "first"), t=("t", "first"), vol_top=("vol", "max")).reset_index()
    # A keyword links supply and entities only through an anchor: a word of the cluster's own (curated) name. Ticket and
    # tour words anchor only the CE's tickets and tours clusters, so generic keywords sitting in another cluster
    # ("vatican guided tour" inside Vatican Gardens) do not pull every tour product into it.
    cfg = ce_config.CE[ce]
    generic_names = toks(cfg["tickets"], ce) | toks(cfg["tours"], ce)
    anchors = {r["cid"]: toks(r["name"], ce) - (set() if r["name"] in (cfg["tickets"], cfg["tours"]) else generic_names)
               for _, r in clusters.iterrows()}
    keysets = kw.groupby("cid")["toks"].agg(lambda s: {k for k in s if k})
    keysets = {c: {k for k in ks if k & anchors[c]} for c, ks in keysets.items()}
    # On-topic share: keywords that carry an anchor word. Undefined for the head term (its subject is the CE name, which
    # is stripped as generic) and for catch-all clusters.
    topic_anchor = {c: a - NAME_GENERIC for c, a in anchors.items()}
    kw["on_topic"] = [bool(t & topic_anchor[c]) for t, c in zip(kw["toks"], kw["cid"])]
    undefined = clusters.loc[clusters["name"].eq(cfg["head"]) | clusters["name"].str.startswith("Other"), "cid"]
    on_topic = kw.groupby("cid")["on_topic"].mean().drop(index=undefined, errors="ignore").rename("on_topic_share")
    # EOS keyword lists can be thin or misplaced (the night-tour keywords sit in Vatican Gardens), so each part of the
    # curated cluster name is a set too: "Night / After-Hours / Evening Tours" -> {night}, {after, hour}, {evening}.
    for _, r in clusters.iterrows():
        drop = NAME_GENERIC | (set() if r["name"] in (cfg["tickets"], cfg["tours"]) else generic_names)
        parts = {frozenset(toks(x, ce) - drop) for x in name_parts(r["name"])}
        keysets.setdefault(r["cid"], set()).update(x for x in parts if x)

    # --- supply
    ex = pd.read_csv(run.input("experiences.csv"), dtype={"ce": str, "experience_id": str})
    ex = ex[(ex["ce"] == ce) & ~ex["experience_name"].str.contains(r"\[DUMMY|Test ILF", regex=True)].copy()
    ex["live"] = ex["is_available"].astype(str).eq("True") & ex["is_hidden"].astype(str).eq("False")
    ex["toks"] = ex["experience_name"].map(lambda n: toks(n, ce))
    sup = [{"cid": c, **e} for c, ks in keysets.items() for e in ex.to_dict("records") if any(contains(k, e["toks"]) for k in ks)]
    sup = pd.DataFrame(sup).drop(columns="toks") if sup else pd.DataFrame(columns=["cid", "experience_id", "experience_name", "live", "orders", "revenue_usd"])
    supply = sup.groupby("cid").agg(n_experiences=("experience_id", "nunique"), n_live=("live", "sum"),
                                    supply_orders=("orders", "sum"), supply_revenue=("revenue_usd", "sum"))

    # --- Headout entity
    en = pd.read_csv(run.input("entities.csv"), dtype={"ce": str, "entity_id": str})
    en = en[(en["ce"] == ce) & en["source"].map(lambda s: bool(set(str(s).split(",")) & ENTITY_SOURCES))].copy()
    en["toks"] = en["name"].map(lambda n: toks(n, ce))
    ent = [{"cid": c, **e} for c, ks in keysets.items() for e in en.to_dict("records")
           if ks and sum(contains(e["toks"], k) for k in ks) / len(ks) >= ENTITY_SHARE]
    ent = pd.DataFrame(ent).drop(columns="toks") if ent else pd.DataFrame(columns=["cid", "entity_type", "entity_id", "name", "is_active"])
    has_col = ent[(ent["entity_type"] == "collection") & ent["is_active"].astype(str).eq("True")].groupby("cid").size()
    has_poi = ent[ent["entity_type"] == "poi"].groupby("cid").size()

    # --- organic
    g = pd.read_csv(run.upstream(gsc_run, f"assignments_{ce}.csv"),
                    usecols=["term", "clicks", "impressions", "avg_position", "top_page", ORGANIC_MAPPER]).rename(columns={ORGANIC_MAPPER: "cid"})
    g["pos_x_impr"] = g["avg_position"] * g["impressions"]
    org = g[g["cid"].notna()].groupby("cid").agg(organic_clicks=("clicks", "sum"), organic_impr=("impressions", "sum"),
                                                 pos_x_impr=("pos_x_impr", "sum"), organic_queries=("term", "nunique"))
    org["organic_position"] = org.pop("pos_x_impr") / org["organic_impr"]
    run.record(ce, f"organic {ORGANIC_MAPPER}", "pct_organic_clicks_mapped", 100 * g.loc[g["cid"].notna(), "clicks"].sum() / g["clicks"].sum())
    run.record(ce, f"organic {ORGANIC_MAPPER}", "organic_clicks_total", g["clicks"].sum())

    # --- demand for clusters without EOS volume
    seeds = pd.read_csv(run.input("seed_volumes.csv"))
    seed_vol = dict(zip(seeds["kw"].str.lower(), seeds["vol"]))
    st = pd.read_csv(run.input("search_terms.csv"), dtype={"ce": str})
    paid_impr = st[st["ce"] == ce].groupby("term")["impr"].sum()
    org_impr = g.groupby("term")["impressions"].sum()
    est = []
    for _, c in clusters[clusters["vol_top"].isna()].iterrows():
        words = kw.loc[kw["cid"] == c["cid"], "kw"].str.lower()
        known = [seed_vol[w] for w in words if w in seed_vol]
        if known:
            est.append({"cid": c["cid"], "vol_fill": max(known), "vol_source": "volume"})
            continue
        monthly = max([paid_impr.get(w, 0) for w in words] + [org_impr.get(w, 0) for w in words]) / WINDOW_MONTHS
        est.append({"cid": c["cid"], "vol_fill": round(monthly) if monthly else None, "vol_source": "impressions" if monthly else None})
    est = pd.DataFrame(est, columns=["cid", "vol_fill", "vol_source"]).set_index("cid")

    out = (clusters.set_index("cid").join([supply, org, est, on_topic]).assign(
        child_collections=lambda d: d.index.map(has_col).fillna(0).astype(int),
        child_pois=lambda d: d.index.map(has_poi).fillna(0).astype(int)))
    on_ce = out["name"].isin([ce_config.CE[ce][k] for k in ("head", "tickets", "tours")])  # these live on the CE collection by design
    out["entity_status"] = np.select([on_ce, out["child_collections"] > 0, out["child_pois"] > 0], ["CE collection", "Child collection", "POI only"], "CE collection")
    out = out.reset_index()

    tr = out["t"] == "TRANSACTIONAL"
    run.record(ce, "supply", "n_transactional_clusters_without_live_supply", int((tr & out["n_live"].fillna(0).eq(0)).sum()))
    run.record(ce, "entity", "n_clusters_child_collection", int((out["entity_status"] == "Child collection").sum()))
    run.record(ce, "entity", "n_clusters_poi_only", int((out["entity_status"] == "POI only").sum()))
    run.record(ce, "demand", "n_seeded_without_any_demand_figure", int((out["vol_top"].isna() & out["vol_fill"].isna()).sum()))

    out.to_csv(run.out / f"cluster_sources_{ce}.csv", index=False)
    sup.to_csv(run.out / f"supply_{ce}.csv", index=False)
    ent.to_csv(run.out / f"entities_{ce}.csv", index=False)
    g.drop(columns="pos_x_impr").to_csv(run.out / f"organic_{ce}.csv", index=False)
    return out


def main():
    a = runlib.args("cluster_sources", {"--gsc-mapping-run": {"required": True}})
    run = runlib.Run("cluster_sources", a.snapshot, {"ces": a.ces, "gsc_mapping_run": a.gsc_mapping_run, "organic_mapper": ORGANIC_MAPPER, "entity_share": ENTITY_SHARE,
                                                     "supply_rule": "experience name holds all intent words of one cluster keyword",
                                                     "entity_rule": "child collection / child POI name words all in one cluster keyword",
                                                     "entity_sources": sorted(ENTITY_SOURCES), "anchor_rule": "keyword must hold a word of the cluster name; ticket/tour words anchor only the tickets/tours clusters", "name_parts": "each part of the cluster name is a match set", "seed_demand": "seed_volumes.csv, else max monthly impressions"})
    pd.set_option("display.width", 250, "display.max_colwidth", 45)
    for ce in a.ces.split(","):
        if ce not in ce_config.CE:
            raise SystemExit(f"CE {ce} has no vocabulary in ce_config.py")
        out = build(run, ce, a.gsc_mapping_run)
        cols = ["name", "t", "n_live", "supply_revenue", "entity_status", "organic_clicks", "organic_position", "vol_fill", "vol_source"]
        print(f"\n=== CE {ce}")
        print(out[cols].round(1).to_string(index=False))
    run.close()


if __name__ == "__main__":
    main()
