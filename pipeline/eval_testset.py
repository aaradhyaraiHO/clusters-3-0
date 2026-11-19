"""Score a mapping against the hand-labelled Vatican test set: 100 paid searches (click-weighted) and 100 organic queries
(impression-weighted), drawn from searches no fix was tuned on, labelled without seeing any mapper's answer.

A label lists every acceptable cluster ("TE|HEAD"); NONE means no cluster fits, so leaving the search unmapped is right.
Gates: under 5% of paid clicks and under 10% of organic impressions in a wrong cluster.

Never tune a rule on these 200 searches: they only measure. Fixes come from other samples.

Usage: python eval_testset.py --paid-mapping <run> --organic-mapping <run> [--ce 189]
"""
import argparse

import pandas as pd

import runlib

CODES = {
    "TE": "Vatican Museums Tickets & Entry", "HEAD": "Vatican Museums (Musei Vaticani) - Head Term",
    "OFF": "Official site & official tickets", "SG": "Sistine Chapel (General)", "ST": "Sistine Chapel Tickets & Tours",
    "SART": "Sistine Chapel Art & Ceiling (Michelangelo)", "SHR": "Sistine Chapel Hours & Rules",
    "SKIP": "Skip-the-Line / Fast Track Entry", "TOUR": "Guided Tours (Vatican Museums)",
    "COMBO": "Combo: Vatican Museums + St Peter's Basilica", "DRESS": "Dress Code, Rules & Restrictions",
    "LOC": "Location, Entrance & Getting In", "HOURS": "Opening Hours & Timings (Vatican Museums)", "PRICE": "Prices & Costs",
    "GTT": "Vatican Gardens Tours & Tickets", "ADAM": "Creation of Adam (Sistine Chapel)", "HIST": "History & Background",
    "MAP": "Map & Layout", "RAPH": "Raphael Rooms (Stanze di Raffaello)", "HIGH": "Highlights & Must-See",
    "PASS": "Passes & City Passes (Vatican)", "AUDIO": "Audio Guide & Self-Guided", "DISC": "Discount / Reduced / Student Tickets",
    "STAIR": "Vatican Museums Spiral Staircase (Bramante Staircase)", "ARTC": "Art & Collections (Vatican Museums)",
    # Clusters EOS lacks; added by the hybrid's seeded clusters
    "CITY": "Vatican City (the state)", "PETER": "St Peter's Basilica", "POPE": "Pope & papal events",
    "CASTEL": "Castel Gandolfo", "BRAND": "Brand & trust",
}
GATES = {"paid": 0.05, "organic": 0.10}
HERE = runlib.HERE


def load_test(ce, which=1):
    stem = "test_set" if which == 1 else f"test_set{which}"
    t = pd.read_csv(runlib.SNAPSHOTS / "20261029_hybrid_sources" / f"{stem}_{ce}_unlabelled.csv")
    label_file = f"test_labels_{ce}.txt" if which == 1 else f"test{which}_labels_{ce}.txt"
    labels = dict(line.split(" ", 1) for line in (HERE / label_file).read_text().split("\n") if line.strip())
    t["gold"] = t["id"].astype(str).map(labels).str.strip()
    assert t["gold"].notna().all(), "unlabelled test rows"
    t["ok_names"] = t["gold"].map(lambda g: {CODES.get(c) for c in g.split("|")} if g else set())
    t["none_ok"] = t["gold"].str.split("|").map(lambda cs: "NONE" in cs)
    return t


def score(t, mapping_by_source):
    rows, wrong = [], []
    for source, run in mapping_by_source.items():
        a = pd.read_csv(runlib.RUNS / run / "outputs" / f"assignments_{t.attrs['ce']}.csv", low_memory=False).drop_duplicates("term").set_index("term")
        s = t[t["source"] == source].copy()
        # Landing in an "Other" group means no cluster took the search
        s["pred"] = s["term"].map(a["D_name"]).where(lambda x: ~x.astype(str).str.startswith("Other"))
        s["ok"] = s.apply(lambda r: (pd.isna(r["pred"]) and r["none_ok"]) or (r["pred"] in r["ok_names"]), axis=1)
        err = 1 - s.loc[s["ok"], "weight"].sum() / s["weight"].sum()
        rows.append({"source": source, "searches": len(s), "wrong searches": int((~s["ok"]).sum()),
                     "wrong share of weight": round(err, 3), "gate": GATES[source], "passes": err < GATES[source]})
        wrong.append(s.loc[~s["ok"], ["source", "term", "weight", "gold", "pred"]])
    return pd.DataFrame(rows), pd.concat(wrong).sort_values("weight", ascending=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--paid-mapping", required=True)
    p.add_argument("--organic-mapping", required=True)
    p.add_argument("--ce", default="189")
    p.add_argument("--test", type=int, default=1, help="which hand-labelled test set: 1 or 2")
    a = p.parse_args()
    t = load_test(a.ce, a.test)
    t.attrs["ce"] = a.ce
    summary, wrong = score(t, {"paid": a.paid_mapping, "organic": a.organic_mapping})
    print(summary.to_string(index=False))
    print(wrong.to_string(index=False, max_colwidth=44))


if __name__ == "__main__":
    main()
