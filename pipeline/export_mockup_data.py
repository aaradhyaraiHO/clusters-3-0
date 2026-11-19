"""Export one CE's cluster table (and its drill-downs) as JSON for the Clusters 3.0 table mockup.

Usage: python export_mockup_data.py --ce 189 --table-run <cluster_table run_id> --mapping-run <mapping run_id>
       --snapshot <snapshot id> --sources-run <cluster_sources run_id> --out <file.json> [--template template.html --html out.html]
Every number in the mockup comes from these runs; the JSON records which ones.
"""
import argparse
import json

import numpy as np
import pandas as pd

import runlib


def num(x, nd=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def main():
    p = argparse.ArgumentParser()
    for a in ["--ce", "--table-run", "--mapping-run", "--snapshot", "--sources-run", "--out"]:
        p.add_argument(a, required=True)
    p.add_argument("--template")
    p.add_argument("--html")
    a = p.parse_args()
    out_t = runlib.RUNS / a.table_run / "outputs"
    snap = runlib.SNAPSHOTS / a.snapshot
    t = pd.read_csv(out_t / f"cluster_table_{a.ce}.csv")
    st = pd.read_csv(out_t / f"search_terms_mapped_{a.ce}.csv", dtype={"ad_group_id": str})
    pages = pd.read_csv(out_t / f"pages_{a.ce}.csv")
    # Trust pages (about us, legal) carry no search intent; the mapper still matches their focus keyword to something.
    pages = pages[pages["page_type"] != "Trust"].copy()
    pages["path"] = pages["path"].fillna("")
    pages["url"] = [u[: len(u) - len(pth) - 1] + "/" + pth if pth else u + "/" for u, pth in zip(pages["uid"], pages["path"])]
    kw = pd.read_csv(snap / "cluster_keywords.csv", dtype={"ce": str})
    kw = kw[kw["ce"] == a.ce]
    log = pd.read_csv(snap / "rebuild_log.csv", dtype={"ce": str})
    log = log[log["ce"] == a.ce]
    asg = pd.read_csv(runlib.RUNS / a.mapping_run / "outputs" / f"assignments_{a.ce}.csv", usecols=["term", "E_how"])
    st = st.merge(asg.drop_duplicates("term"), on="term", how="left")
    orders = pd.read_csv(snap / "orders_by_landing.csv", dtype={"ce": str})
    orders = orders[orders["ce"] == a.ce]
    metrics = pd.read_csv(runlib.LEDGER)
    out_s = runlib.RUNS / a.sources_run / "outputs"
    sources_snapshot = json.loads((runlib.RUNS / a.sources_run / "config.json").read_text())["snapshot"]
    ce_ex = pd.read_csv(runlib.SNAPSHOTS / sources_snapshot / "experiences.csv", dtype={"ce": str})
    ce_ex = ce_ex[(ce_ex["ce"] == a.ce) & ~ce_ex["experience_name"].str.contains(r"\[DUMMY|Test ILF", regex=True)].copy()
    ce_ex["live"] = ce_ex["is_available"].astype(str).eq("True") & ce_ex["is_hidden"].astype(str).eq("False")
    src = pd.read_csv(out_s / f"cluster_sources_{a.ce}.csv").set_index("cid")
    sup = pd.read_csv(out_s / f"supply_{a.ce}.csv", dtype={"experience_id": str})
    ent = pd.read_csv(out_s / f"entities_{a.ce}.csv", dtype={"entity_id": str})
    org = pd.read_csv(out_s / f"organic_{a.ce}.csv")
    seeded = set(log.loc[log["action"] == "add_cluster", "to"])
    names = t.set_index("cid")["name"]

    rows = []
    for _, r in t.iterrows():
        c = r["cid"]
        k = kw[kw["cid"] == c].sort_values("vol", ascending=False)
        s = st[st["cid"] == c]
        terms = (s.groupby("term").agg(clicks=("clicks", "sum"), spend=("spend", "sum"), how=("E_how", "first"))
                 .sort_values("clicks", ascending=False).head(8).reset_index())
        ags = (s.groupby(["ad_group_id", "ad_group_name", "campaign_name"]).agg(clicks=("clicks", "sum"), spend=("spend", "sum"), conv=("conv", "sum"))
               .sort_values("clicks", ascending=False).head(8).reset_index())
        ag_terms = (s.groupby(["ad_group_id", "term"]).agg(clicks=("clicks", "sum"), spend=("spend", "sum"), conv=("conv", "sum"))
                    .reset_index().sort_values("clicks", ascending=False))
        pg = pages[pages["cid"] == c].sort_values("revenue", ascending=False)
        changes = log[(log["to"] == r["name"]) | (log["from"] == r["name"]) | (log.get("cluster") == r["name"])]
        moved_in = int(((changes["action"] == "move") & (changes["to"] == r["name"])).sum())
        moved_out = int(((changes["action"] == "move") & (changes["from"] == r["name"])).sum())
        retyped = changes[changes["action"] == "retype"]
        sr = src.loc[c] if c in src.index else pd.Series(dtype=object)
        sx = sup[sup["cid"] == c].sort_values(["live", "revenue_usd"], ascending=False)
        ex_ = ent[ent["cid"] == c]
        oq = org[org["cid"] == c].sort_values("clicks", ascending=False)
        vol, vol_source = num(r["vol_top"], 0), "eos"
        if vol is None and pd.notna(sr.get("vol_fill")):
            vol, vol_source = num(sr["vol_fill"], 0), sr["vol_source"]
        rows.append({
            "id": c, "name": r["name"], "type": r["t"], "seeded": r["name"] in seeded,
            "n_kw": int(r["n_kw"]), "vol": vol, "vol_source": vol_source if vol is not None else None, "focus_kw": r["focus_kw"] if isinstance(r["focus_kw"], str) else None,
            "impr": num(r["impr"], 0), "clicks": num(r["clicks"], 0), "conv": num(r["conv"], 1),
            "on_topic": num(sr.get("on_topic_share"), 2), "spend": num(r["spend"]), "google_value": num(r["conv_value"]),
            "paid_revenue": num(r["paid_revenue"]), "paid_orders": num(r["paid_orders"], 1),
            "coverage": r["coverage"] if isinstance(r["coverage"], str) else "None", "routing_share": num(r["routing_share"], 3),
            "top_ag_purity": num(r["top_ag_purity"], 3), "n_ad_groups": num(r["n_ad_groups"], 0),
            "ai_max_share": num(r["ai_max_clicks"] / r["clicks"], 3) if r["clicks"] and not np.isnan(r["clicks"]) else None,
            "top_ad_group": r["top_ad_group"] if isinstance(r["top_ad_group"], str) else None,
            "page_revenue": num(r["revenue"]), "page_orders": num(r["orders"], 0), "pct_ce_revenue": num(r["pct_ce_revenue"], 4),
            "keywords": [{"kw": x["kw"], "vol": num(x["vol"], 0)} for _, x in k.head(8).iterrows()],
            "terms": [{"term": x["term"], "clicks": int(x["clicks"]), "spend": num(x["spend"]), "how": x["how"]} for _, x in terms.iterrows()],
            "ad_groups": [{"name": x["ad_group_name"], "campaign": x["campaign_name"], "clicks": int(x["clicks"]), "spend": num(x["spend"]),
                           "conv": num(x["conv"], 1),
                           "terms": [{"term": y["term"], "clicks": int(y["clicks"]), "spend": num(y["spend"]), "conv": num(y["conv"], 1)}
                                     for _, y in ag_terms[ag_terms["ad_group_id"] == x["ad_group_id"]].head(5).iterrows()]}
                          for _, x in ags.iterrows()],
            "pages": [{"path": x["url"], "type": x["page_sub_type"],
                       "collection": None if pd.isna(x["collection_id"]) else str(x["collection_id"]).split(".")[0],
                       "noindex": bool(x["any_noindex"]), "revenue": num(x["revenue"]), "orders": num(x["orders"], 0)}
                      for _, x in pg.iterrows()],
            "supply": {"n": int(sx["experience_id"].nunique()), "live": int(sx["live"].sum()), "revenue": num(sx["revenue_usd"].sum()),
                       "orders": int(sx["orders"].sum()),
                       "experiences": [{"name": x["experience_name"], "live": bool(x["live"]), "revenue": num(x["revenue_usd"]), "orders": int(x["orders"])}
                                       for _, x in sx.head(8).iterrows()]},
            "entity": {"status": sr.get("entity_status", "CE collection"),
                       "items": [{"type": x["entity_type"], "id": x["entity_id"], "name": x["name"], "active": str(x["is_active"]) == "True"}
                                 for _, x in ex_.iterrows()]},
            "organic": {"clicks": num(sr.get("organic_clicks"), 0), "impr": num(sr.get("organic_impr"), 0),
                        "position": num(sr.get("organic_position"), 1), "queries": int(num(sr.get("organic_queries"), 0) or 0),
                        "top": [{"term": x["term"], "clicks": int(x["clicks"]), "impr": int(x["impressions"]), "position": num(x["avg_position"], 1),
                                 "how": x["E_how"], "page": x["top_page"]} for _, x in oq.head(8).iterrows()]},
            "changes": {"moved_in": moved_in, "moved_out": moved_out,
                        "retyped": None if retyped.empty else f"{retyped.iloc[0]['from']} → TRANSACTIONAL ({retyped.iloc[0]['why']})",
                        "why_added": None if r["name"] not in seeded else log.loc[(log["action"] == "add_cluster") & (log["to"] == r["name"]), "why"].iloc[0]},
        })

    unmapped_organic = org[org["cid"].isna()].sort_values("clicks", ascending=False).head(12)
    unmapped_terms = (st[st["cid"].isna()].groupby("term").agg(clicks=("clicks", "sum"), spend=("spend", "sum"))
                      .sort_values("clicks", ascending=False).head(12).reset_index())
    page_no_cluster = pages[pages["cid"].isna()].sort_values("revenue", ascending=False)
    m = metrics[metrics["ce"].astype(str) == a.ce]

    def metric(run_prefix, name, method=None):
        q = m[m["run_id"].str.startswith(run_prefix) & (m["metric"] == name)]
        if method:
            q = q[q["method"] == method]
        return None if q.empty else round(float(q["value"].iloc[-1]), 1)

    host_rev = orders.assign(host=orders["landing_path"].fillna("").str.split("/").str[0].replace("", "(no landing page)"))
    data = {
        "ce": {"id": a.ce, "name": "Vatican Museums" if a.ce == "189" else a.ce, "window": "30 Jul – 27 Oct 2026",
               "revenue": num(orders["revenue_usd"].sum()), "orders": int(orders["orders"].sum()),
               "paid_spend": num(st["spend"].sum()), "paid_clicks": int(st["clicks"].sum()),
               "paid_clicks_mapped": num(st.loc[st["cid"].notna(), "clicks"].sum() / st["clicks"].sum(), 3),
               "ai_max_share": num(st.loc[st["match_type"] == "AI_MAX", "clicks"].sum() / st["clicks"].sum(), 3),
               "paid_revenue": metric(a.table_run[:15], "paid_revenue_usd_total"),
               "paid_revenue_attributed": metric(a.table_run[:15], "pct_paid_revenue_attributed_to_cluster"),
               "organic_clicks": int(org["clicks"].sum()),
               "organic_clicks_mapped": num(org.loc[org["cid"].notna(), "clicks"].sum() / org["clicks"].sum(), 3),
               "products_live": int(ce_ex["live"].sum()), "products_total": int(len(ce_ex)),
               "revenue_by_host": host_rev.groupby("host")["revenue_usd"].sum().sort_values(ascending=False).head(6).round(0).to_dict()},
        "before_after": {
            "right_intent": [metric("20261028-182437", "pct_clicks_intent_correct", "layered D0.85"), metric("20261028-183143", "pct_clicks_intent_correct", "layered E0.85")],
            "landing": [metric("20261028-182437", "pct_landing_clicks_in_landing_cluster", "layered D0.85"), metric("20261028-183143", "pct_landing_clicks_in_landing_cluster", "layered E0.85")],
            "unmapped": [metric("20261028-182437", "pct_clicks_unmapped", "layered D0.85"), metric("20261028-183143", "pct_clicks_unmapped", "layered E0.85")],
            "paid_rev_attributed": [metric("20261028-181030", "pct_paid_revenue_attributed_to_cluster"), metric("20261028-183154", "pct_paid_revenue_attributed_to_cluster")],
            "dedicated": [metric("20261028-181030", "n_clusters_dedicated_ad_group"), metric("20261028-183154", "n_clusters_dedicated_ad_group")],
            "rebuild": log.groupby("action").size().to_dict(),
        },
        "clusters": rows,
        "unmapped_organic": [{"term": x["term"], "clicks": int(x["clicks"]), "impr": int(x["impressions"]), "position": num(x["avg_position"], 1)}
                             for _, x in unmapped_organic.iterrows()],
        "unmapped_terms": [{"term": x["term"], "clicks": int(x["clicks"]), "spend": num(x["spend"])} for _, x in unmapped_terms.iterrows()],
        "pages_no_cluster": [{"path": x["url"], "type": x["page_sub_type"], "focus": x["text"], "revenue": num(x["revenue"])}
                             for _, x in page_no_cluster.iterrows()],
        "change_log": [{"action": x["action"], "keyword": x["keyword"] if isinstance(x["keyword"], str) else None,
                        "from": x["from"] if isinstance(x["from"], str) else None, "to": x["to"] if isinstance(x["to"], str) else None,
                        "why": x["why"] if isinstance(x["why"], str) else None} for _, x in log.iterrows()],
        "sources": {"table_run": a.table_run, "mapping_run": a.mapping_run, "snapshot": a.snapshot, "sources_run": a.sources_run},
    }
    with open(a.out, "w") as f:
        json.dump(data, f, ensure_ascii=False, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else str(o))
    print(f"{len(rows)} clusters -> {a.out}")
    if a.template and a.html:
        payload = json.dumps(data, ensure_ascii=False, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else str(o))
        # "</" inside an inline <script> would close the tag early
        page = open(a.template).read().replace("__DATA__", payload.replace("</", "<\\/"), 1)
        with open(a.html, "w") as f:
            f.write(page)
        print(f"page -> {a.html}")


if __name__ == "__main__":
    main()
