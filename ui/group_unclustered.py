"""Group the paid searches no cluster takes, so Opportunities can say which belong in an existing cluster and which
look like a new one. Writes hybrid/unclustered_groups_189.json.

Run with the pipeline's environment (it has the embedding model):
  <clusters_3_0>/.env-clusters/venv/bin/python group_unclustered.py <clusters_3_0> [189|3945]
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

ROOT = Path(sys.argv[1])
HERE = Path(__file__).resolve().parent
CE = int(sys.argv[2]) if len(sys.argv) > 2 else 189
sys.path.insert(0, str(ROOT))
import cluster_fix  # noqa: E402  (COMPETITORS lives in the pipeline)

if CE == 189:
    SNAP, RUNS, OUT = ROOT / "snapshots" / "20261029_capture_v2", ROOT / "runs", HERE / "hybrid"
    CLUSTERS = ROOT / "snapshots" / "20261103_hybrid_11ce_v2" / "cluster_keywords.csv"
    PAIR_RUN = "20261103-171359_jev_classify_20261030_validation_v1"
    OWN_BRAND = r"\b(thevaticantickets|the vatican tickets)\b"
else:
    # Every other CE from ces.json (pull_ce.py, map_ce.py, prepare_ce.py). Own brand = the site's name, with or without
    # dashes, so searches for the site itself are not read as a new cluster.
    CFG = json.loads((HERE / "ces.json").read_text())["ces"][str(CE)]
    SNAP, RUNS, OUT = HERE / CFG["out"], HERE / "pipeline_local" / "runs", HERE / CFG["out"]
    CLUSTERS = HERE / "pipeline_local" / "snapshots" / CFG["snapshot"] / "cluster_keywords.csv"
    PAIR_RUN = CFG["runs"]["pairs"]
    site = re.sub(r"^www\.|\.[a-z.]+$", "", CFG["host"])
    OWN_BRAND = rf"\b({re.escape(site)}|{re.escape(site.replace('-', ' '))} com)\b"
MODEL = ROOT / ".env-clusters" / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
MIN_CLICKS = 10
# Cosine distance at which two searches stop being the same intent: 0.3 keeps the dress-code searches across
# languages together while ticket searches and Petersdom searches stay apart (0.45 merged them).
MERGE_DISTANCE = 0.3
# A group at least this close to one of a real cluster's keywords is a mapping miss; below it, a new intent. Every
# Vatican search sits near some Vatican keyword, so the bar is high.
BELONGS_SIM = 0.8

norm = lambda s: " ".join(str(s).lower().split())

terms = pd.read_csv(SNAP / "search_terms_by_adgroup.csv")
terms = terms[terms["ce"] == CE].assign(k=lambda d: d["term"].map(norm))
mapped = pd.read_csv(RUNS / PAIR_RUN / "outputs" / f"assignments_{CE}.csv", low_memory=False)
mapped = mapped.assign(k=mapped["term"].map(norm)).drop_duplicates("k").set_index("k")["D0.85"]
terms["cid"] = terms["k"].map(mapped)
loose = terms[terms["cid"].isna()].groupby("k").agg(clicks=("clicks", "sum"), spend=("spend", "sum"),
                                                      cv=("conv_value", "sum"), ai=("match_type", lambda m: (m == "AI_MAX").mean()))
loose = loose[loose["clicks"] >= MIN_CLICKS].sort_values("clicks", ascending=False)

kw = pd.read_csv(CLUSTERS)
kw = kw[kw["ce"] == CE]
names = kw.drop_duplicates("cid").set_index("cid")["name"]

# Competitor and own-brand searches are flagged by name, not grouped by meaning (their meaning is "Vatican tickets").
loose["kind"] = np.where(loose.index.str.contains(cluster_fix.COMPETITORS), "competitor",
                         np.where(loose.index.str.contains(OWN_BRAND), "brand", ""))
named = loose[loose["kind"] != ""]
loose = loose[loose["kind"] == ""]
kw = kw[~kw["name"].str.startswith("Other")]

model = SentenceTransformer(str(MODEL))
emb = model.encode(loose.index.tolist(), normalize_embeddings=True, batch_size=64)
kw_emb = model.encode(kw["kw"].tolist(), normalize_embeddings=True, batch_size=64)

# Fewer than two searches cannot be grouped; each stands alone.
labels = AgglomerativeClustering(n_clusters=None, distance_threshold=MERGE_DISTANCE, metric="cosine",
                                 linkage="average").fit_predict(emb) if len(loose) > 1 else np.arange(len(loose))
loose["g"] = labels

groups = [{"kind": kind, "label": rows.index[0], "terms": rows.index[:6].tolist(), "n": int(len(rows)),
           "clicks": int(rows["clicks"].sum()), "spend": round(float(rows["spend"].sum()), 2), "cv": round(float(rows["cv"].sum()), 2),
           "ai": round(float((rows["ai"] * rows["clicks"]).sum() / rows["clicks"].sum()), 3), "near": None}
          for kind, rows in named.groupby("kind")]
for g, rows in loose.groupby("g"):
    idx = [loose.index.get_loc(k) for k in rows.index]
    centre = emb[idx].mean(axis=0)
    centre /= np.linalg.norm(centre)
    sims = kw_emb @ centre
    best = int(np.argmax(sims))
    kind = "belongs" if sims[best] >= BELONGS_SIM else "new"
    top = rows.sort_values("clicks", ascending=False)
    groups.append({"kind": kind, "label": top.index[0], "terms": top.index[:6].tolist(), "n": int(len(rows)),
                   "clicks": int(rows["clicks"].sum()), "spend": round(float(rows["spend"].sum()), 2),
                   "cv": round(float(rows["cv"].sum()), 2),
                   "ai": round(float((rows["ai"] * rows["clicks"]).sum() / rows["clicks"].sum()), 3),
                   "near": {"cid": kw["cid"].iloc[best], "name": names[kw["cid"].iloc[best]],
                            "kw": kw["kw"].iloc[best], "sim": round(float(sims[best]), 3)}})

groups.sort(key=lambda x: -x["clicks"])
out = {"ce": CE, "run": PAIR_RUN, "min_clicks": MIN_CLICKS, "unclustered_clicks": int(terms.loc[terms["cid"].isna(), "clicks"].sum()),
       "all_clicks": int(terms["clicks"].sum()), "groups": groups}
(OUT / f"unclustered_groups_{CE}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(f"{len(loose) + len(named)} searches in {len(groups)} groups;",
      ", ".join(f"{k} {sum(1 for x in groups if x['kind'] == k)}" for k in ("belongs", "new", "competitor", "brand")))
