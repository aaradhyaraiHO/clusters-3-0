"""Automated checks and the per-CE scorecard for the validation across CE types (thoughts/shared/clusters-3.0/bakeoff/
validation_plan.md).

Per CE, from a snapshot's search_term_pairs / keyword_totals / gsc_terms and the Jev mapping runs:
  mechanics      every search has exactly one row in the mapping; cluster sums of clicks, spend and CM1 equal the CE's
                 search-term totals (the search-term rows are the main numbers, per the Perf rule of mapping only at
                 search-term level)
  visibility     search-term spend / complete keyword spend: the part of spend Google shows as search terms
  quality        paid clicks and organic impressions with no cluster; AI Max share of clicks; share of clicks Jev placed
                 with probability under LOW_PROB (the review queue)
  accuracy       wrong-cluster share of paid clicks and organic impressions on the CE's labelled test set, if reviewed
Writes scorecard.csv to the run and prints it.

Sampling: --sample draws each CE's blind test set (100 paid searches by clicks, 100 organic queries by impressions)
into test_sets/<ce>.csv for labelling; it never looks at any mapping.

Usage: python validate.py --snapshot 20261030_validation_v1 --ces ... --pair-mapping <run> --organic-mapping <run>
       python validate.py --snapshot 20261030_validation_v1 --ces ... --sample
"""
import numpy as np
import pandas as pd

import runlib

LOW_PROB = 0.6
GATES = {"paid_wrong": 0.05, "organic_wrong": 0.10}
TEST_DIR = runlib.HERE / "test_sets"
PER_SOURCE = 100
SEED = 4242


def weighted_pick(df, weight, k):
    """k rows without replacement, more likely the heavier they are (Efraimidis-Spirakis keys u^(1/w)); pandas' own
    weighted sample refuses when a few searches carry most of the weight."""
    rng = np.random.default_rng(SEED)
    keys = rng.random(len(df)) ** (1 / df[weight].clip(lower=1e-9).to_numpy())
    return df.iloc[np.argsort(-keys)[:k]]


def sample(snap, ces):
    TEST_DIR.mkdir(exist_ok=True)
    pairs = pd.read_csv(snap / "pair_terms.csv", dtype={"ce": str})
    gsc = pd.read_csv(snap / "gsc_terms.csv", dtype={"ce": str})
    for ce in ces:
        if ce == "189":
            vatican_from_labelled_sets()
            continue
        parts = []
        p = pairs[(pairs["ce"] == ce) & (pairs["clicks"] > 0)]
        if len(p):
            parts.append(weighted_pick(p, "clicks", PER_SOURCE)
                         .assign(source="paid", weight=lambda d: d["clicks"])[["term", "source", "weight"]])
        o = gsc[(gsc["ce"] == ce) & (gsc["impressions"] > 0)]
        if len(o):
            parts.append(weighted_pick(o, "impressions", PER_SOURCE)
                         .assign(source="organic", weight=lambda d: d["impressions"])[["term", "source", "weight"]])
        t = pd.concat(parts).drop_duplicates(["term", "source"]).reset_index(drop=True)
        t.index.name = "id"
        t["label"] = ""
        t.to_csv(TEST_DIR / f"{ce}.csv")
        print(f"CE {ce}: {len(t)} test searches ({(t['source'] == 'paid').sum()} paid, {(t['source'] == 'organic').sum()} organic)")


def vatican_from_labelled_sets():
    """Vatican already has two hand-labelled sets (eval_testset.py); reuse them, with labels as cluster names."""
    import eval_testset as ev
    sets = [ev.load_test("189", 1), ev.load_test("189", 2)]
    t = pd.concat(sets)[["term", "source", "weight", "gold"]].drop_duplicates(["term", "source"]).reset_index(drop=True)
    t["label"] = t["gold"].map(lambda g: "|".join(ev.CODES.get(c, c) for c in g.split("|")))
    t.index.name = "id"
    t.drop(columns="gold").to_csv(TEST_DIR / "189.csv")
    print(f"CE 189: {len(t)} labelled test searches from the two existing Vatican sets")


def mapping(runs, ce):
    """The CE's assignments from the first of the comma-separated runs that has them."""
    for run in (runs or "").split(","):
        path = runlib.RUNS / run.strip() / "outputs" / f"assignments_{ce}.csv"
        if run.strip() and path.exists():
            return pd.read_csv(path, low_memory=False)
    return None


def accuracy(ce, paid_map, organic_map):
    path = TEST_DIR / f"{ce}.csv"
    if not path.exists():
        return {}
    t = pd.read_csv(path)
    t = t[t["label"].fillna("").str.strip() != ""]
    out = {}
    for source, m in (("paid", paid_map), ("organic", organic_map)):
        s = t[t["source"] == source]
        if not len(s) or m is None:
            continue
        pred = s["term"].map(m.drop_duplicates("term").set_index("term")["D_name"]).fillna("NONE")
        ok = [p in {x.strip() for x in str(lab).split("|")} for p, lab in zip(pred, s["label"])]
        out[f"{source}_labelled"] = len(s)
        out[f"{source}_wrong"] = round(1 - s.loc[ok, "weight"].sum() / s["weight"].sum(), 3)
    return out


def main():
    a = runlib.args("validate", {"--pair-mapping": {"default": None}, "--organic-mapping": {"default": None},
                                 "--vatican-pair-mapping": {"default": None}, "--vatican-organic-mapping": {"default": None},
                                 "--sample": {"action": "store_true"},
                                 "--test-dir": {"default": "test_sets", "help": "folder of labelled test sets (test_sets_v2 for prompt v2 lists)"}})
    snap = runlib.SNAPSHOTS / a.snapshot
    ces = a.ces.split(",")
    global TEST_DIR
    TEST_DIR = runlib.HERE / a.test_dir
    if a.sample:
        sample(snap, ces)
        return
    run = runlib.Run("validate", a.snapshot, {"ces": a.ces, "pair_mapping": a.pair_mapping, "organic_mapping": a.organic_mapping,
                                              "low_prob": LOW_PROB, "gates": GATES})
    pairs = pd.read_csv(snap / "search_term_pairs.csv", dtype={"ce": str})
    kw = pd.read_csv(snap / "keyword_totals.csv", dtype={"ce": str})
    gsc = pd.read_csv(snap / "gsc_terms.csv", dtype={"ce": str})
    names = pd.read_csv(snap / "ce_names.csv", dtype={"ce": str}).set_index("ce")["name"]
    rows = []
    for ce in ces:
        pm = mapping(a.vatican_pair_mapping if ce == "189" and a.vatican_pair_mapping else a.pair_mapping, ce)
        om = mapping(a.vatican_organic_mapping if ce == "189" and a.vatican_organic_mapping else a.organic_mapping, ce)
        r = {"CE": ce, "CE name": names[ce]}
        p = pairs[pairs["ce"] == ce]
        if len(p) and pm is not None:
            terms = p.groupby("term")[["clicks", "spend", "conv_value", "impr"]].sum()
            m = pm.drop_duplicates("term").set_index("term")
            r["searches_missing_from_mapping"] = int((~terms.index.isin(m.index)).sum())
            r["searches_mapped_twice"] = int(pm["term"].duplicated().sum())
            joined = terms.join(m[["D_name", "prob"]], how="left")
            by_cluster = joined.groupby(joined["D_name"].fillna("NONE"))[["clicks", "spend", "conv_value"]].sum()
            r["cluster_sums_match"] = bool((by_cluster.sum() - terms[["clicks", "spend", "conv_value"]].sum()).abs().max() < 0.01)
            r["visible_share_of_keyword_spend"] = round(terms["spend"].sum() / kw.loc[kw["ce"] == ce, "spend"].sum(), 3)
            r["paid_clicks_no_cluster"] = round(joined.loc[joined["D_name"].isna(), "clicks"].sum() / terms["clicks"].sum(), 3)
            r["paid_clicks_low_confidence"] = round(joined.loc[joined["prob"] < LOW_PROB, "clicks"].sum() / terms["clicks"].sum(), 3)
            r["ai_max_click_share"] = round(p.loc[p["match_type"] == "AI_MAX", "clicks"].sum() / p["clicks"].sum(), 3)
        g = gsc[gsc["ce"] == ce]
        if len(g) and om is not None:
            gj = g.set_index("term").join(om.drop_duplicates("term").set_index("term")[["D_name", "prob"]], how="left")
            r["organic_impr_no_cluster"] = round(gj.loc[gj["D_name"].isna(), "impressions"].sum() / gj["impressions"].sum(), 3)
            r["organic_impr_low_confidence"] = round(gj.loc[gj["prob"] < LOW_PROB, "impressions"].sum() / gj["impressions"].sum(), 3)
        r.update(accuracy(ce, pm, om))
        r["passes"] = all(r.get(k, 0) < v for k, v in GATES.items()) if any(k in r for k in GATES) else None
        rows.append(r)
        for k, v in r.items():
            if isinstance(v, (int, float, bool)) and k != "CE":
                run.record(ce, "validate", k, float(v))
    card = pd.DataFrame(rows)
    card.to_csv(run.out / "scorecard.csv", index=False)
    print(card.to_string(index=False))
    run.close()


if __name__ == "__main__":
    main()
