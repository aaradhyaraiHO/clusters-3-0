"""Put one CE's inputs in the shapes export_hybrid.py reads, in its folder from ces.json.

Sources: the CE's pipeline_local snapshot (map_ce.py: hybrid clusters, Google Ads and Search Console rows) and its
pull_ce.py pulls. Pages map to clusters by meaning here because the pipeline's page mapper needs a cluster_sources run
these CEs do not have.

Run with the pipeline's environment (it has the embedding model):
  <clusters_3_0>/.env-clusters/venv/bin/python prepare_ce.py <clusters_3_0> <ce>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

ROOT = Path(sys.argv[1])
HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "ces.json").read_text())["ces"][sys.argv[2]]
OUT = HERE / CFG["out"]
SNAP = HERE / "pipeline_local" / "snapshots" / CFG["snapshot"]
CE, HOST = int(sys.argv[2]), CFG["host"]
MODEL = ROOT / ".env-clusters" / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
# A page joins the cluster whose keywords it is closest to only at this score or above (0.6 meaning + 0.4 shared words,
# as the hybrid assigner scores); below it the page stays unmapped rather than land in a loosely related cluster.
PAGE_SIM = 0.55
# The CE's own name is in nearly every page and keyword, so it is removed before comparing; left in, "about" and
# "maps" pages matched Underwater Observatory on "milford sound" alone.
NAME_WORDS = set(CFG["name_words"]) | {"the", "to", "in", "of", "and", "a"}
strip = lambda t: " ".join(w for w in str(t).lower().replace("-", " ").split() if w not in NAME_WORDS)

# Pages, mapped to clusters, with orders that landed on them.
kw = pd.read_csv(SNAP / "cluster_keywords.csv")
pages = pd.read_csv(OUT / f"pages_{CE}.csv", dtype={"collection_id": str})
pages = pages[pages["status_en"] == "published"].copy()
# A page's host: the CE's own, or another site that holds a section for it (ces.json page_prefixes).
pages["host"] = pages["uid"].str.extract(r"^(www\.[a-z0-9-]+\.(?:co\.[a-z]{2}|com\.[a-z]{2}|[a-z]{2,3}))(?=\.|$)")[0].fillna(HOST)
pages["path"] = [u[len(h):].replace(".", "/").strip("/") for u, h in zip(pages["uid"], pages["host"])]
model = SentenceTransformer(str(MODEL))
kw_text = kw["kw"].map(strip)
kw_emb = model.encode(kw_text.tolist(), normalize_embeddings=True, batch_size=64)
page_text = (pages["focus_keyword_en"].fillna("").str.split(",").str[0] + " " + pages["path"].str.replace("/", " ")).map(strip)
page_emb = model.encode(page_text.tolist(), normalize_embeddings=True, batch_size=64)
jac = lambda a, b: len(set(a.split()) & set(b.split())) / len(set(a.split()) | set(b.split())) if (a or b) else 0.0
# A CE with no microbrand pages yet (a new CE) has nothing to match.
sims = (0.6 * (page_emb @ kw_emb.T) + 0.4 * np.array([[jac(p_, k_) for k_ in kw_text] for p_ in page_text])
        if len(pages) else np.zeros((0, len(kw))))
head = kw.loc[(kw["name"] == CFG.get("head")) | kw["name"].str.contains("Head Term", case=False), "cid"].iloc[0]
real = ~kw["name"].str.startswith("Other").to_numpy()
pages["cid"], pages["how"] = None, None
for i, (_, row) in enumerate(pages.iterrows()):
    if row["page_type"] == "Theme":
        pages.loc[row.name, ["cid", "how"]] = [head, "home"]
        continue
    s = np.where(real, sims[i], -1)
    best = int(np.argmax(s))
    if s[best] >= PAGE_SIM:
        pages.loc[row.name, ["cid", "how"]] = [kw["cid"].iloc[best], "meaning"]
orders = pd.read_csv(OUT / f"orders_by_landing_{CE}.csv")
orders["key"] = orders["landing_path"].str.replace(HOST, "", regex=False).str.strip("/")
by_page = orders.groupby("key")[["count_orders", "sum_revenue_usd"]].sum()
pages["orders"] = pages["path"].map(by_page["count_orders"]).fillna(0)
pages["revenue"] = pages["path"].map(by_page["sum_revenue_usd"]).fillna(0)
pages["page_sub_type"] = pages["page_type"]
pages["text"] = pages["focus_keyword_en"]
pages.to_csv(OUT / f"pages_mapped_{CE}.csv", index=False)

# Google Ads rows in the export's file shapes.
ad_groups = pd.read_csv(SNAP / "ad_groups.csv")
camps = pd.read_csv(OUT / f"campaign_troas_{CE}.csv")[["campaign_name", "campaign_status"]].drop_duplicates("campaign_name")
ad_groups = ad_groups.merge(camps, on="campaign_name", how="left")
ad_groups.to_csv(OUT / "ad_groups.csv", index=False)
pairs = pd.read_csv(SNAP / "search_term_pairs.csv")
pairs.groupby(["kw_key", "term"], as_index=False)[["impr", "clicks", "spend", "conv_value"]].sum().to_csv(OUT / "keyword_search_terms.csv", index=False)
totals = pd.read_csv(SNAP / "keyword_totals.csv")
totals.to_csv(OUT / "keyword_totals.csv", index=False)
shares = totals.groupby("keyword").agg(match_types=("keyword_match_type", lambda m: ",".join(sorted(set(m)))), impr=("impr", "sum")).reset_index()
shares.insert(0, "ce", CE)
shares.to_csv(OUT / "keyword_shares.csv", index=False)
by_ag = pairs.assign(ad_group_id=pairs["kw_key"].str.split("~").str[0].astype("int64"))
by_ag = by_ag.merge(ad_groups[["ad_group_id", "ad_group_name", "ad_group_status", "campaign_name"]], on="ad_group_id", how="left")
by_ag.groupby(["ce", "campaign_name", "ad_group_id", "ad_group_name", "ad_group_status", "match_type", "term"], as_index=False)[
    ["impr", "clicks", "spend", "conv", "conv_value"]].sum().to_csv(OUT / "search_terms_by_adgroup.csv", index=False)
lpr = pd.read_csv(OUT / f"landing_page_results_{CE}.csv")
lpr = lpr.merge(ad_groups[["ad_group_id", "ad_group_name"]], on="ad_group_id", how="left")
lpr["host"] = lpr["landing_url"].str.extract(r"^https?://([^/?#]+)")[0]
lpr["top_path"] = "/" + lpr["landing_url"].str.extract(r"^https?://[^/]+/?([^?#]*)")[0].fillna("").str.strip("/")
lpr.groupby(["campaign_name", "ad_group_name", "host", "top_path"], as_index=False)[["clicks", "spend"]].sum().to_csv(OUT / "landing_pages.csv", index=False)
print(f"{pages['cid'].notna().sum()} of {len(pages)} pages mapped; {len(pairs)} search-term rows; {len(totals)} keywords")
