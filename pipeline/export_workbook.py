"""Export every bake-off result into one workbook: hit rates, clusters, keyword assignments and search-term assignments
for every CE and every approach. Writes one CSV per tab into .env-clusters/workbook/ (local); upload_workbook.py puts
them in a Google Sheet.

Hit rates use the bake-off mapper (D0.85: identifiers -> fuzzy -> meaning, no CE-specific rules). "Unseen" leaves out
each CE's EOS research keywords and its top 400 paid terms, the same set for every approach.
"""
import json
from pathlib import Path

import pandas as pd

import cluster_scorecard as sc
import runlib

OUT = Path(__file__).parent / ".env-clusters" / "workbook"
COL = "D0.85"
CE_NAMES = pd.read_csv(runlib.SNAPSHOTS / "20261029_bakeoff_v1" / "ce_names.csv", dtype={"ce": str}).set_index("ce")["name"]

# approach -> (snapshot holding its clusters, {ce: mapping run}) ; CEs without a mapping run have clusters only
APPROACHES = {
    "EOS prompts": ("20261029_bakeoff_v1", {
        **{ce: "20261029-112221_mapping_20261029_bakeoff_v0" for ce in ("189", "243", "2743", "3945", "325")},
        **{ce: "20261029-113235_mapping_20261029_bakeoff_v1" for ce in ("257", "3176", "1695")}}),
    "Hybrid (EOS list + algorithm assignment)": ("20261029_arm_hybrid_eos_v5", {"189": "20261029-144857_mapping_20261029_arm_hybrid_eos_v5"}),
    "Cluster Tool (prototype prompts)": ("20261029_bakeoff_v1_clustertool",
                                         {ce: "20261029-113235_mapping_20261029_bakeoff_v1_clustertool" for ce in ("243", "257", "3176", "1695")}),
    "EOS + hand-tuned repair": ("20261028_v3_rebuilt", {"189": "20261029-111757_mapping_20261028_v3_rebuilt"}),
    "Algorithm, new-CE": (None, {
        **{ce: "20261029-113054_mapping_20261029_arm_graph_new_v3_5ce" for ce in ("189", "243", "2743", "3945", "325")},
        **{ce: "20261029-113249_mapping_20261029_arm_graph_new_v3_sheet3" for ce in ("257", "3176", "1695")}}),
    "Algorithm, new-CE + SERP": ("20261029_arm_graph_new_serp_2ce",
                                 {ce: "20261029-114543_mapping_20261029_arm_graph_new_serp_2ce" for ce in ("257", "243")}),
    "Algorithm, existing-CE (+400 paid terms)": (None, {
        **{ce: "20261029-112238_mapping_20261029_arm_graph_exist400_v2_5ce" for ce in ("189", "243", "2743", "3945", "325")},
        **{ce: "20261029-113249_mapping_20261029_arm_graph_exist400_v3_sheet3" for ce in ("257", "3176", "1695")}}),
}
# Approaches whose clusters are split over several snapshots
SNAPSHOTS_OF = {
    "Algorithm, new-CE": {**{ce: "20261029_arm_graph_new_v3_5ce" for ce in ("189", "243", "2743", "3945", "325")},
                          **{ce: "20261029_arm_graph_new_v3_sheet3" for ce in ("257", "3176", "1695")},
                          **{ce: "20261029_arm_graph_new_v3_nopaid" for ce in ("261", "2010", "2640")}},
    "Algorithm, existing-CE (+400 paid terms)": {**{ce: "20261029_arm_graph_exist400_v2_5ce" for ce in ("189", "243", "2743", "3945", "325")},
                                                 **{ce: "20261029_arm_graph_exist400_v3_sheet3" for ce in ("257", "3176", "1695")}},
}
VATICAN_EXPERIMENTS = {
    "Algorithm, no identifiers (29 Oct, v1)": ("20261029_arm_graph_new_noids", "20261029-111818_mapping_20261029_arm_graph_new_noids"),
    "Algorithm + identifiers (29 Oct, v1)": ("20261029_arm_graph_new_ids", "20261029-111818_mapping_20261029_arm_graph_new_ids"),
    "Algorithm + identifiers, e5 model (thresholds not re-tuned)": ("20261029_arm_graph_new_ids_e5", "20261029-111946_mapping_20261029_arm_graph_new_ids_e5"),
}


def snapshot_for(approach, ce):
    if approach in SNAPSHOTS_OF:
        return SNAPSHOTS_OF[approach].get(ce)
    return APPROACHES[approach][0]


def clusters_of(snapshot, ce):
    if snapshot is None:
        return pd.DataFrame()
    k = pd.read_csv(runlib.SNAPSHOTS / snapshot / "cluster_keywords.csv", dtype={"ce": str})
    return k[k["ce"] == ce]


def unseen_exclusion(ce):
    eos = clusters_of("20261029_bakeoff_v1", ce)
    terms = pd.read_csv(runlib.SNAPSHOTS / "20261029_bakeoff_v1" / "search_terms.csv", dtype={"ce": str})
    return set(eos["kw"].dropna()) | set(terms[terms["ce"] == ce].nlargest(400, "clicks")["term"])


def assignments(mapping, ce):
    a = pd.read_csv(runlib.RUNS / mapping / "outputs" / f"assignments_{ce}.csv", low_memory=False, usecols=lambda c: c in ("term", "clicks", "spend", COL))
    a["intent"] = a["term"].map(sc.tag)
    return a


def rates(a):
    right, landing = sc.intent_correct(a, COL)
    clicks = a["clicks"].sum()
    return right, landing, (100 * a.loc[a[COL].isna(), "clicks"].sum() / clicks) if clicks else None, clicks


def main():
    OUT.mkdir(exist_ok=True)
    ces = list(CE_NAMES.index)
    hit, clus, kw_rows, term_parts = [], [], {}, []
    for ce in ces:
        excl = unseen_exclusion(ce)
        term_frame = None
        for approach, (_, maps) in APPROACHES.items():
            snap = snapshot_for(approach, ce)
            k = clusters_of(snap, ce)
            if k.empty:
                continue
            sizes = k.dropna(subset=["kw"]).groupby("cid")["kw"].nunique()
            row = {"CE": ce, "CE name": CE_NAMES[ce], "Approach": approach, "Keywords": int(k["kw"].nunique()),
                   "Clusters": int(k["cid"].nunique()), "Largest cluster % of keywords": round(100 * sizes.max() / sizes.sum(), 1) if len(sizes) else None,
                   "Single-keyword clusters": int((sizes == 1).sum())}
            names = k.drop_duplicates("cid").set_index("cid")
            a = assignments(maps[ce], ce) if ce in maps else None
            if a is not None:
                r_all = rates(a)
                r_un = rates(a[~a["term"].isin(excl)])
                row.update({"Paid clicks scored": int(r_all[3]), "Right-intent % (all)": round(r_all[0], 1), "Landing % (all)": round(r_all[1], 1),
                            "No cluster % (all)": round(r_all[2], 1), "Unseen clicks": int(r_un[3]),
                            "Right-intent % (unseen)": round(r_un[0], 1) if r_un[3] else None,
                            "Landing % (unseen)": round(r_un[1], 1) if r_un[3] else None,
                            "No cluster % (unseen)": round(r_un[2], 1) if r_un[3] else None, "Mapping run": maps[ce]})
                m = a[a[COL].notna()]
                per = m.groupby(COL).agg(clicks=("clicks", "sum"), spend=("spend", "sum"))
                by_intent = m.groupby([COL, "intent"])["clicks"].sum().reset_index()
                per["main_intent"] = by_intent.sort_values("clicks", ascending=False).drop_duplicates(COL).set_index(COL)["intent"]
                tf = a[["term", "clicks", "spend", "intent"]].copy() if term_frame is None else term_frame
                tf[approach] = a[COL].map(names["name"])
                term_frame = tf
            else:
                per = pd.DataFrame(columns=["clicks", "spend", "main_intent"])
            row["Clusters snapshot"] = snap
            hit.append(row)
            total = a["clicks"].sum() if a is not None else None
            for cid, g in k.dropna(subset=["kw"]).groupby("cid", sort=False):
                top = g.sort_values("vol", ascending=False).iloc[0]
                clus.append({"CE": ce, "CE name": CE_NAMES[ce], "Approach": approach, "Cluster": names.at[cid, "name"], "Intent type": names.at[cid, "t"],
                             "Keywords": int(g["kw"].nunique()), "Volume": g.drop_duplicates("kw")["vol"].sum(),
                             "Top keyword": top["kw"], "Top volume": top["vol"],
                             "Identifiers": ", ".join(json.loads(names.at[cid, "ids"])) if isinstance(names.at[cid, "ids"], str) and names.at[cid, "ids"].startswith("[") else "",
                             "Paid clicks mapped": int(per["clicks"].get(cid, 0)) if a is not None else None,
                             "Paid spend mapped": round(float(per["spend"].get(cid, 0)), 2) if a is not None else None,
                             "% of CE paid clicks": round(100 * per["clicks"].get(cid, 0) / total, 2) if total else None,
                             "Main search intent": per["main_intent"].get(cid) if a is not None else None})
            for _, r in k.dropna(subset=["kw"]).iterrows():
                kw_rows.setdefault((ce, r["kw"]), {"CE": ce, "CE name": CE_NAMES[ce], "Keyword": r["kw"], "Volume": r["vol"]})[approach] = names.at[r["cid"], "name"]
        if term_frame is not None:
            term_frame.insert(0, "CE name", CE_NAMES[ce])
            term_frame.insert(0, "CE", ce)
            term_frame["Unseen"] = ~term_frame["term"].isin(excl)
            term_parts.append(term_frame.sort_values("clicks", ascending=False))
    # Vatican experiments
    excl = unseen_exclusion("189")
    for label, (snap, mapping) in VATICAN_EXPERIMENTS.items():
        a = assignments(mapping, "189")
        r_all, r_un = rates(a), rates(a[~a["term"].isin(excl)])
        k = clusters_of(snap, "189")
        hit.append({"CE": "189", "CE name": CE_NAMES["189"], "Approach": f"Experiment: {label}", "Keywords": int(k["kw"].nunique()),
                    "Clusters": int(k["cid"].nunique()), "Paid clicks scored": int(r_all[3]), "Right-intent % (all)": round(r_all[0], 1),
                    "Landing % (all)": round(r_all[1], 1), "No cluster % (all)": round(r_all[2], 1), "Unseen clicks": int(r_un[3]),
                    "Right-intent % (unseen)": round(r_un[0], 1), "Landing % (unseen)": round(r_un[1], 1), "No cluster % (unseen)": round(r_un[2], 1),
                    "Mapping run": mapping, "Clusters snapshot": snap})
    pd.DataFrame(hit).to_csv(OUT / "hit_rates.csv", index=False)
    pd.DataFrame(clus).to_csv(OUT / "clusters.csv", index=False)
    kw = pd.DataFrame(list(kw_rows.values()))
    kw.to_csv(OUT / "keywords.csv", index=False)
    terms = pd.concat(term_parts).rename(columns={"term": "Search term", "clicks": "Paid clicks", "spend": "Spend", "intent": "Search intent"})
    terms.to_csv(OUT / "search_terms.csv", index=False)
    for f in sorted(OUT.glob("*.csv")):
        print(f.name, sum(1 for _ in f.open()) - 1, "rows")


if __name__ == "__main__":
    main()
