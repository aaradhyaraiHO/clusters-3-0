"""Propose new clusters from search terms that no EOS cluster absorbs (Clusters 3.0 discovery step).

Usage: python bertopic_discovery.py --snapshot <id> --mapping-run <run_id> --model <dir> [--ces 189] [--pool leftovers|all]
  leftovers - terms the layered mapper (D0.85) leaves unmapped: candidates for NEW clusters
  all       - every paid term, clustered bottom-up: compare against EOS clusters for seed gaps
Reads assignments_<ce>.csv from the mapping run. Writes topics_<ce>_<pool>.csv and discovery_<ce>_*.csv to this run.
Topics are ranked by clicks, so a small group of high-spend terms outranks a big group of zero-click terms.
"""
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
from bertopic import BERTopic  # noqa: E402
from sklearn.cluster import AgglomerativeClustering  # noqa: E402
from hdbscan import HDBSCAN  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from sklearn.feature_extraction.text import CountVectorizer  # noqa: E402
from umap import UMAP  # noqa: E402

import runlib  # noqa: E402

OUT = None  # set from the run in main()
RUN = None


def run_main():
    global OUT, RUN
    args = runlib.args("discovery", {"--mapping-run": {"required": True}, "--model": {"required": True},
                                     "--pool": {"default": "leftovers", "choices": ["leftovers", "all"]}})
    RUN = runlib.Run("discovery", args.snapshot, {"ces": args.ces, "mapping_run": args.mapping_run, "pool": args.pool,
                                                   "embed_model": Path(args.model).name, "umap_random_state": 42,
                                                   "match_min": 0.75, "likely_min": 0.65, "merge_dist": 0.25})
    OUT = RUN.out
    for ce in args.ces.split(","):
        main(ce, args.model, args.pool, RUN.upstream(args.mapping_run, f"assignments_{ce}.csv"))
    RUN.close()


def main(ce, model_dir, pool, assignments_path):
    a = pd.read_csv(assignments_path)
    docs = a[a["D0.85"].isna()] if pool == "leftovers" else a
    docs = docs.reset_index(drop=True)
    texts = docs["term"].astype(str).tolist()
    emb_model = SentenceTransformer(model_dir)
    emb = emb_model.encode(texts, normalize_embeddings=True, batch_size=128)
    min_size = 5 if len(texts) < 800 else 10
    model = BERTopic(
        embedding_model=emb_model,
        umap_model=UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=42),
        hdbscan_model=HDBSCAN(min_cluster_size=min_size, metric="euclidean", cluster_selection_method="eom", prediction_data=True),
        vectorizer_model=CountVectorizer(ngram_range=(1, 2), min_df=2),
        min_topic_size=min_size,
    )
    topics, _ = model.fit_transform(texts, emb)
    docs["topic"] = topics
    labels = {r.Topic: r.Name for r in model.get_topic_info().itertuples()}
    agg = (docs.groupby("topic")
           .agg(terms=("term", "count"), clicks=("clicks", "sum"), spend=("spend", "sum"), conv=("conv", "sum"),
                top_terms=("term", lambda s: " | ".join(docs.loc[s.index].sort_values("clicks", ascending=False)["term"].head(6))))
           .reset_index())
    agg["label"] = agg["topic"].map(labels)
    agg["pct_clicks"] = (100 * agg["clicks"] / agg["clicks"].sum()).round(1)
    if pool == "all":  # which EOS cluster the layered mapper sent each topic's clicks to
        mapped = docs.assign(cl=docs["D_name"].fillna("(unmapped)"))
        dom = mapped.groupby(["topic", "cl"])["clicks"].sum().reset_index().sort_values("clicks").drop_duplicates("topic", keep="last")
        agg["mostly_mapped_to"] = agg["topic"].map(dom.set_index("topic")["cl"])
    agg = agg.sort_values("clicks", ascending=False)
    agg.round(0).to_csv(OUT / f"topics_{ce}_{pool}.csv", index=False)
    docs[["term", "clicks", "spend", "conv", "topic"]].to_csv(OUT / f"term_topics_{ce}_{pool}.csv", index=False)
    RUN.record(ce, f"bertopic {pool}", "n_terms", len(docs))
    RUN.record(ce, f"bertopic {pool}", "pct_of_ce_clicks", 100 * docs["clicks"].sum() / a["clicks"].sum())
    RUN.record(ce, f"bertopic {pool}", "n_topics", (agg["topic"] != -1).sum())
    RUN.record(ce, f"bertopic {pool}", "pct_clicks_outliers", agg.loc[agg["topic"] == -1, "pct_clicks"].sum())
    pd.set_option("display.width", 250, "display.max_colwidth", 110)
    cols = ["topic", "terms", "clicks", "pct_clicks", "spend", "conv", "top_terms"] + (["mostly_mapped_to"] if pool == "all" else [])
    print(agg[cols].head(25).to_string(index=False))
    if pool == "leftovers":
        merge_and_match(ce, docs, emb, emb_model)


def merge_and_match(ce, docs, emb, emb_model, match_min=0.75, likely_min=0.65, merge_dist=0.25):
    """Fold each topic into the EOS cluster its terms point at, or keep it as a new-cluster candidate.

    Vote: every term finds its nearest EOS keyword (multilingual embeddings, so "capilla sixtina entradas" can
    reach "sistine chapel tickets"); a topic goes to the cluster that gets most of its clicks, if those terms'
    similarity averages >= match_min. Topics that match nothing are merged with each other across languages
    (average-linkage on topic centres) and reported as new-cluster candidates, ranked by spend.
    """
    kw = pd.read_csv(RUN.input("cluster_keywords.csv"), dtype={"ce": str})
    kw = kw[(kw["ce"] == ce) & kw["kw"].notna()].reset_index(drop=True)
    names = kw.groupby("cid")["name"].first()
    kemb = emb_model.encode(kw["kw"].astype(str).tolist(), normalize_embeddings=True, batch_size=128)
    docs = docs[docs["topic"] != -1].copy()
    idx = docs.index.to_numpy()
    sims = emb[idx] @ kemb.T
    docs["near_cid"] = kw["cid"].to_numpy()[sims.argmax(axis=1)]
    docs["near_kw"] = kw["kw"].to_numpy()[sims.argmax(axis=1)]
    docs["near_sim"] = sims.max(axis=1)
    unit = lambda m: m / np.linalg.norm(m, axis=-1, keepdims=True)  # noqa: E731

    rows, unmatched = [], []
    for t, d in docs.groupby("topic"):
        votes = d.groupby("near_cid")["clicks"].sum().sort_values(ascending=False)
        cid = votes.index[0]
        v = d[d["near_cid"] == cid]
        score = np.average(v["near_sim"], weights=v["clicks"].clip(lower=1))
        share = votes.iloc[0] / votes.sum()
        if score >= match_min and share >= 0.5:
            rows.append({"cluster": names[cid], "topic": t, **summ(d), "match": round(float(score), 2), "vote_share": round(float(share), 2)})
        else:
            unmatched.append(t)

    known = pd.DataFrame(rows)
    if len(known):
        known = (known.groupby("cluster").agg(topics=("topic", "count"), terms=("terms", "sum"), clicks=("clicks", "sum"),
                                              spend=("spend", "sum"), conv=("conv", "sum"), match=("match", "mean"))
                 .reset_index().sort_values("spend", ascending=False))
        known["missing_language_seeds"] = known["cluster"].map(
            lambda c: " | ".join(docs[docs["topic"].isin([r["topic"] for r in rows if r["cluster"] == c])]
                                 .sort_values("clicks", ascending=False)["term"].head(8)))
        known["verdict"] = "existing cluster: add these seeds"

    new = pd.DataFrame()
    if unmatched:
        w = docs["clicks"].clip(lower=1)
        cent = unit(np.vstack([np.average(emb[docs.index[docs["topic"] == t]], axis=0, weights=w[docs["topic"] == t]) for t in unmatched]))
        grp = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                      distance_threshold=merge_dist).fit_predict(cent) if len(unmatched) > 1 else [0]
        g = dict(zip(unmatched, grp))
        nd = docs[docs["topic"].isin(unmatched)].assign(group=lambda d: d["topic"].map(g))
        def verdict(d):
            near = names[d.groupby("near_cid")["clicks"].sum().idxmax()]
            sim = np.average(d["near_sim"], weights=d["clicks"].clip(lower=1))
            # 0.65-0.75: cross-language matches land here; the guess is often right but needs a person to confirm
            return near, sim, (f"LIKELY existing: {near} (confirm)" if sim >= likely_min else "NEW cluster candidate: review")

        new = pd.DataFrame([{"group": k, "topics": d["topic"].nunique(), **summ(d),
                             "nearest_existing": f"{verdict(d)[0]} ({verdict(d)[1]:.2f})", "verdict": verdict(d)[2],
                             "proposed_seeds": " | ".join(d.sort_values("clicks", ascending=False)["term"].head(8))}
                            for k, d in nd.groupby("group")]).sort_values("spend", ascending=False)

    total = docs["clicks"].sum()
    RUN.record(ce, "embedding vote", "pct_leftover_clicks_matched_existing", 100 * known["clicks"].sum() / total if len(known) else 0)
    RUN.record(ce, "embedding vote", "pct_leftover_clicks_likely_existing",
               100 * new.loc[new["verdict"].str.startswith("LIKELY"), "clicks"].sum() / total if len(new) else 0)
    RUN.record(ce, "embedding vote", "pct_leftover_clicks_new_candidate",
               100 * new.loc[new["verdict"].str.startswith("NEW"), "clicks"].sum() / total if len(new) else 0)
    known.round(2).to_csv(OUT / f"discovery_{ce}_existing.csv", index=False)
    new.round(2).to_csv(OUT / f"discovery_{ce}_new.csv", index=False)
    pd.set_option("display.width", 300, "display.max_colwidth", 140)
    print(f"\n== Topics that belong to EXISTING clusters (language / seed gaps): {len(rows)} topics -> {len(known)} clusters")
    print(known.to_string(index=False))
    print(f"\n== NEW cluster candidates: {len(unmatched)} topics -> {len(new)} groups after cross-language merge")
    print(new.drop(columns=["group"]).to_string(index=False) if len(new) else "(none)")


def summ(d):
    return {"terms": len(d), "clicks": int(d["clicks"].sum()), "spend": round(d["spend"].sum()), "conv": round(d["conv"].sum())}


if __name__ == "__main__":
    run_main()
