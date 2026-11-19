"""Score a CE's EOS clusters against paid search demand (Clusters 3.0 quality rubric).

Usage: python cluster_scorecard.py --snapshot <id> --mapping-run <run_id> [--ces 325]
       (reads assignments_<ce>.csv from the mapping run's outputs)

Rubric, per EOS cluster:
  R1 one intent     - share of the cluster's paid clicks whose tagged intent is the cluster's main intent
  R2 intent type    - cluster_type vs the intent its paid terms actually show (e.g. INFORMATIONAL but 80% ticket terms)
  R3 focus keyword  - stored focus keyword missing, or top-volume keyword differs from top paid term
  R4 volume         - share of summed volume that is repeated variants (same volume, same cluster)
Per CE:
  R5 coverage       - paid clicks by intent that land in no cluster, or in a cluster of the wrong intent

Intents are tagged with a multilingual lexicon (below), so the reference is customer behaviour, not another clustering run.
Outputs: out/scorecard_<ce>.csv, out/intent_demand_<ce>.csv
"""
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

import runlib

OUT = None  # set from the run in main()

# intent -> words/phrases (normalised: lowercase, no accents). First match wins, so order is niche-first.
LEXICON = [
    ("official_site", r"official|oficial|officiel|ufficial|offiziell|oficjaln|sito|site|website|web|pagina|strona|www|online|公式|공식"),
    ("combo", r"sagrada|batllo|pedrera|casa mila|combo|\+"),
    ("gaudi_house", r"casa museu|casa museo|gaudi house|house of gaudi|casa gaudi|gaudi museum|museu gaudi"),
    ("tour", r"\btours?\b|guided|guide|visita guiada|visita guidata|visite guidee|fuhrung|rondleiding|wycieczka"),
    ("free_entry", r"\bfree\b|gratis|gratuit|gratuito|kostenlos|darmowe"),
    ("hours", r"hours|horario|orari|horaires|offnungszeiten|opening|times|timings"),
    ("getting_there", r"how to get|como llegar|metro|\bbus\b|train|getting|address|direccion|location"),
    ("parking", r"parking|aparcamiento|parcheggio"),
    ("map", r"\bmap\b|mapa|mappa|plan\b"),
    ("tickets", r"ticket|biglietti|biglietto|billet|entrad|entree|ingress|eintritt|bilet|bilhete|bilete|jegy|kaart|toegang|entry|admission|"
                r"book|reserv|prenot|予約|예약|"
                r"price|precio|prezzo|prix|preis|cost|チケット|入場|입장|티켓|εισιτηρ|билет|门票|票"),
]
LEX = [(name, re.compile(pat)) for name, pat in LEXICON]
EOS_TYPE_FOR_INTENT = {"official_site": "TRANSACTIONAL", "combo": "TRANSACTIONAL", "gaudi_house": "TRANSACTIONAL",
                       "tour": "TRANSACTIONAL", "tickets": "TRANSACTIONAL", "free_entry": "PLANNING", "hours": "PLANNING",
                       "getting_there": "PLANNING", "parking": "PLANNING", "map": "PLANNING", "bare_name": "INFORMATIONAL"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", s)  # recompose Hangul/kana after stripping Latin accents


def tag(term):
    t = norm(term)
    for name, rx in LEX:
        if rx.search(t):
            return name
    return "bare_name"  # only the attraction / city name, in some language


LANDING = {"bare_name", "tickets"}  # name-only searches convert like ticket searches, so both belong on the landing cluster


def intent_correct(a, col):
    """Share of all paid clicks landing in a cluster whose main intent matches the term's intent (unmapped = wrong)."""
    ref = a["intent"].where(~a["intent"].isin(LANDING), "landing")
    m = a[a[col].notna()]
    if m.empty:  # e.g. identifier-only mapping on clusters that carry no identifiers
        return 0.0, 0.0
    main_int = m.assign(ref=ref).groupby(col).apply(lambda d: d.groupby("ref")["clicks"].sum().idxmax())
    ok = a[col].notna() & (a[col].map(main_int) == ref)
    landing = ref == "landing"
    return 100 * a.loc[ok, "clicks"].sum() / a["clicks"].sum(), 100 * a.loc[ok & landing, "clicks"].sum() / a.loc[landing, "clicks"].sum()


def main():
    global OUT
    args = runlib.args("scorecard", {"--mapping-run": {"required": True, "help": "run_id of the mapping run to score"}})
    run = runlib.Run("scorecard", args.snapshot, {"ces": args.ces, "mapping_run": args.mapping_run, "landing_intents": sorted(LANDING),
                                                   "lexicon": [n for n, _ in LEXICON]})
    OUT = run.out
    for ce in args.ces.split(","):
        score_ce(run, ce, args.mapping_run)
    run.close()


def score_ce(run, ce, mapping_run):
    a = pd.read_csv(run.upstream(mapping_run, f"assignments_{ce}.csv"))
    kw = pd.read_csv(run.input("cluster_keywords.csv"), dtype={"ce": str})
    kw = kw[kw["ce"] == ce]
    a["intent"] = a["term"].map(tag)
    final = next(c for c in ["E0.85", "D0.85", "C0.7"] if c in a)  # newest mapper the mapping run produced
    clusters = kw.groupby("cid").agg(name=("name", "first"), t=("t", "first"), n_kw=("kw", "count"),
                                     vol_sum=("vol", "sum"), vol_max=("vol", "max"),
                                     top_kw=("kw", lambda s: s.loc[kw.loc[s.index, "vol"].idxmax()] if kw.loc[s.index, "vol"].notna().any() else s.iloc[0]))
    # R4: repeated-variant volume = sum minus one copy per distinct volume value (variants share bucketed volume)
    dedup = kw.groupby("cid")["vol"].apply(lambda v: v.drop_duplicates().sum())
    clusters["dup_vol_pct"] = (100 * (1 - dedup / clusters["vol_sum"])).round(0)

    rows = []
    for method, col in [("current", "A"), ("layered", final)]:
        g = a[a[col].notna()].groupby(col)
        for cid, d in g:
            by_int = d.groupby("intent")["clicks"].sum().sort_values(ascending=False)
            main_int = by_int.index[0]
            rows.append({"cid": cid, "method": method, "paid_clicks": int(d["clicks"].sum()), "paid_conv": round(d["conv"].sum()),
                         "main_intent": main_int, "R1_one_intent_pct": round(100 * by_int.iloc[0] / by_int.sum()),
                         "intent_mix": "; ".join(f"{k} {100 * v / by_int.sum():.0f}%" for k, v in by_int.head(4).items()),
                         "top_paid_term": d.sort_values("clicks", ascending=False)["term"].iloc[0]})
    sc = pd.DataFrame(rows).merge(clusters.reset_index(), on="cid", how="right")
    sc["R2_type_ok"] = sc.apply(lambda r: None if pd.isna(r["main_intent"]) else EOS_TYPE_FOR_INTENT.get(r["main_intent"]) == r["t"], axis=1)
    sc = sc.sort_values(["method", "paid_clicks"], ascending=[True, False])
    sc.to_csv(OUT / f"scorecard_{ce}.csv", index=False)

    # R5: paid demand by intent, and where the current rule sends it
    a["A_type"] = a["A"].map(clusters["t"]).fillna("UNMAPPED")
    dem = a.pivot_table(index="intent", columns="A_type", values="clicks", aggfunc="sum", fill_value=0)
    dem["clicks"] = dem.sum(axis=1)
    dem["spend"] = a.groupby("intent")["spend"].sum().round()
    dem["conv"] = a.groupby("intent")["conv"].sum().round()
    dem["pct_clicks"] = (100 * dem["clicks"] / dem["clicks"].sum()).round(1)
    dem = dem.sort_values("clicks", ascending=False)
    dem.to_csv(OUT / f"intent_demand_{ce}.csv")

    pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 60)
    print("== Paid demand by intent, and which EOS cluster type the current rule sends it to (clicks)")
    print(dem.to_string())
    print("\n== Scorecard (current rule)")
    cols = ["name", "t", "n_kw", "vol_sum", "vol_max", "dup_vol_pct", "paid_clicks", "main_intent", "R1_one_intent_pct", "R2_type_ok", "intent_mix", "top_paid_term", "top_kw"]
    print(sc[sc["method"].ne("layered")][cols].to_string(index=False))

    vol = kw.dropna(subset=["vol"])
    run.record(ce, "eos", "n_clusters", kw["cid"].nunique())
    run.record(ce, "eos", "n_keywords", vol.shape[0])
    run.record(ce, "eos", "n_empty_clusters", (kw.groupby("cid")["kw"].count() == 0).sum())
    run.record(ce, "eos", "pct_volume_repeated_variants", 100 * (1 - dedup.sum() / clusters["vol_sum"].sum()))
    for method, col in [("A current rule", "A"), (f"layered {final}", final)]:
        ic, land = intent_correct(a, col)
        run.record(ce, method, "pct_clicks_intent_correct", ic)
        run.record(ce, method, "pct_landing_clicks_in_landing_cluster", land)
        run.record(ce, method, "pct_clicks_unmapped", 100 * a.loc[a[col].isna(), "clicks"].sum() / a["clicks"].sum())
    for intent, r in dem.iterrows():
        run.record(ce, "paid demand", f"pct_clicks_intent_{intent}", r["pct_clicks"])


if __name__ == "__main__":
    main()
