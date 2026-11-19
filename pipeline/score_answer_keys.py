"""Score cluster lists against the answer keys (answer_checks.csv, from thoughts/shared/clusters-3.0/bakeoff/answer_keys.md).

Every list is scored on the same keywords: the CE's EOS keywords (competitor ones included) plus the hybrid's added
paid terms (snapshots/20261030_validation_v2/eos_keywords.csv). A keyword a list does not place counts as "no cluster".
Lists compared:
  EOS as-is       EOS clusters with EOS's own keyword placement (20261029_bakeoff_v1)
  Hybrid          EOS cluster names, keywords placed by the algorithm (20261103_hybrid_11ce_v2)
  prompt lists    e.g. Prompt v2.1 / v2.2, keywords placed by Jev with the cluster definitions (--prompt-lists)
Competitor and reseller keywords are unplaced in every list (the agreed clean-up on top of EOS).

Check types (patterns match the keyword text, lowercased, accents removed; volumes weigh each keyword, floor 10):
  has             a cluster is named after the demand, or holds it as at least half of its own volume
  separate        the two demands' main clusters differ
  single          the two demands' main clusters share a root (a parent and its sub-clusters count as one)
  exclude         at most 10% of the demand's volume sits in any cluster
  not_cluster     no cluster is mostly this demand
  head            the demand's main cluster is the one holding the head keyword (column b)
  in              the demand's main cluster is named like column b (e.g. guided tours in other languages)
  intent          the demand's main cluster has one of the listed intents
  fkw             the demand's main cluster's top keyword matches the expected focus keyword
  purity          the demand's main cluster is at least `value` this demand by volume
  max_share       no cluster holds more than `value` of the placed keywords
  head_share      the cluster holding the head keyword (column b) holds under `value` of the placed keywords
  max_singletons  at most `value` clusters with one keyword and under 500 searches
A check whose demand has no keyword in the set is "no data" and is left out of the pass rate.

Usage: python score_answer_keys.py --snapshot 20261030_validation_v2 --ces 3945,2743,...
       --prompt-lists "Prompt v2.1=20261030_validation_v2:<run>,<run>;Prompt v2.2=20261104_validation_v22:<run>"
"""
import re
import unicodedata
import warnings

import pandas as pd

import cluster_fix
import runlib

warnings.filterwarnings("ignore", "This pattern is interpreted as a regular expression")

S = runlib.SNAPSHOTS
SPECS = {"EOS as-is": S / "20261029_bakeoff_v1" / "cluster_keywords.csv",
         "Hybrid": S / "20261103_hybrid_11ce_v2" / "cluster_keywords.csv"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    return " ".join(re.sub(r"[\W_]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).split())


def load_list(path, universe):
    kw = pd.read_csv(path, dtype={"ce": str})
    # EOS's "Others" / "Other (…)" hold unclaimed keywords: they count as no cluster
    kw = kw[~kw["name"].str.match(r"^Others?\b")].assign(k=lambda d: d["kw"].map(norm))
    parent = kw.drop_duplicates(["ce", "name"]).set_index(["ce", "name"])["parent"].to_dict() if "parent" in kw else {}
    meta = kw.drop_duplicates(["ce", "name"]).set_index(["ce", "name"])["t"].to_dict()
    placed = kw.drop_duplicates(["ce", "k"]).set_index(["ce", "k"])["name"]
    u = universe.assign(name=[placed.get((c, k)) for c, k in zip(universe["ce"], universe["k"])])
    return u, meta, parent


def load_prompt_list(snapshot, run, universe):
    meta_kw = pd.read_csv(S / snapshot / "cluster_keywords.csv", dtype={"ce": str})
    meta = meta_kw.drop_duplicates(["ce", "name"]).set_index(["ce", "name"])["t"].to_dict()
    parent = meta_kw.drop_duplicates(["ce", "name"]).set_index(["ce", "name"])["parent"].to_dict() if "parent" in meta_kw else {}
    rows = []
    for ce in universe["ce"].unique():
        for f in [runlib.RUNS / r / "outputs" / f"assignments_{ce}.csv" for r in run.split(",")]:
            if not f.exists():
                continue
            a = pd.read_csv(f, dtype={"ce": str}).assign(k=lambda d: d["term"].map(norm))
            rows.append(a[["ce", "k", "D_name"]].drop_duplicates(["ce", "k"]))
    a = pd.concat(rows).drop_duplicates(["ce", "k"]).set_index(["ce", "k"])["D_name"]
    u = universe[universe["ce"].isin({c for c, _ in a.index})]
    u = u.assign(name=[a.get((c, k)) for c, k in zip(u["ce"], u["k"])])
    return u.assign(name=u["name"].where(u["name"].notna(), None)), meta, parent


def root(ce, name, parent):
    seen = set()
    while name is not None and name not in seen:
        seen.add(name)
        p = parent.get((ce, name))
        if p is None or pd.isna(p) or (ce, p) not in parent:
            return name
        name = p
    return name


def main_cluster(m):
    placed = m[m["name"].notna()]
    if placed.empty:
        return None, 0.0
    by = placed.groupby("name")["w"].sum()
    return by.idxmax(), by.max() / m["w"].sum()


def run_check(c, u, meta, parent, ce):
    pat = lambda p: u["k"].str.contains(p, regex=True, na=False)
    placed = u[u["name"].notna()]
    size_w = placed.groupby("name")["w"].sum()
    if c.type in ("max_share", "head_share", "max_singletons"):
        n = placed.groupby("name").size()
        if c.type == "max_share":
            share = n.max() / n.sum()
            return share <= float(c.value), f"largest: {n.idxmax()} {share:.0%}"
        if c.type == "head_share":
            h = u.loc[u["k"] == norm(c.b), "name"]
            if h.empty or pd.isna(h.iloc[0]):
                return None, f"head keyword '{c.b}' not placed"
            share = n.get(h.iloc[0], 0) / n.sum()
            return share < float(c.value), f"{h.iloc[0]} {share:.0%}"
        single = [x for x in n[n == 1].index if size_w[x] < 500]
        return len(single) <= int(float(c.value)), f"{len(single)}: {', '.join(single[:4])}"
    m = u[pat(c.a)]
    if m.empty:
        return None, "no keyword matches"
    main, share = main_cluster(m)
    if c.type == "has":
        named = [x for x in meta if x[0] == ce and re.search(c.a, norm(x[1]))]
        if named:
            return True, f"named: {named[0][1]}"
        mw = m[m["name"].notna()].groupby("name")["w"].sum()
        own = (mw / size_w.reindex(mw.index)).sort_values(ascending=False)
        if len(own) and own.iloc[0] >= 0.5:
            return True, f"{own.index[0]} ({own.iloc[0]:.0%} of it)"
        return False, f"spread; most in {main} ({share:.0%})" if main else "no cluster"
    if c.type == "exclude":
        s = m.loc[m["name"].notna(), "w"].sum() / m["w"].sum()
        return s <= 0.10, f"{s:.0%} placed" + (f", most in {main}" if main else "")
    if c.type == "not_cluster":
        mw = m[m["name"].notna()].groupby("name")["w"].sum()
        own = mw / size_w.reindex(mw.index)
        bad = own[own >= 0.5]
        return bad.empty, f"dedicated: {bad.index[0]}" if len(bad) else "no dedicated cluster"
    if main is None:
        return False, "no cluster"
    if c.type in ("separate", "single"):
        mb = u[pat(c.b)]
        if mb.empty:
            return None, "no keyword matches b"
        main_b, share_b = main_cluster(mb)
        if c.type == "separate":
            return main != main_b, f"{main} / {main_b}"
        if main_b is None:
            return False, f"{main} / no cluster"
        return root(ce, main, parent) == root(ce, main_b, parent), f"{main} / {main_b}"
    if c.type == "head":
        h = u.loc[u["k"] == norm(c.b), "name"]
        if h.empty or pd.isna(h.iloc[0]):
            return None, f"head keyword '{c.b}' not placed"
        return root(ce, main, parent) == root(ce, h.iloc[0], parent), f"{main} / head: {h.iloc[0]}"
    if c.type == "in":
        return bool(re.search(c.b, norm(main))), main
    if c.type == "intent":
        t = meta.get((ce, main))
        return str(t) in str(c.value).split("|"), f"{main}: {t}"
    if c.type == "fkw":
        cl = placed[placed["name"] == main]
        top = cl.loc[cl["vol"] == cl["vol"].max(), "k"]
        ok = top.str.contains(c.value, regex=True).any()
        return bool(ok), f"{main}: {top.iloc[0]}" + (f" (+{len(top) - 1} at the same volume)" if len(top) > 1 else "")
    if c.type == "purity":
        cl = placed[placed["name"] == main]
        s = cl.loc[cl["k"].str.contains(c.a, regex=True), "w"].sum() / cl["w"].sum()
        return s >= float(c.value), f"{main}: {s:.0%} {c.check.split()[0].lower()}"
    raise SystemExit(f"unknown check type {c.type}")


def main():
    a = runlib.args("answer_keys", {"--lists": {"default": "", "help": "label=snapshot;... extra cluster_keywords lists to score"},
                                    "--prompt-lists": {"default": "", "help": "label=snapshot:jev_run[,jev_run];... prompt lists "
                                                                               "whose keywords Jev placed (eos_keywords.csv)"}})
    ces = a.ces.split(",")
    run = runlib.Run("answer_keys", a.snapshot, {"ces": a.ces, "prompt_lists": a.prompt_lists, "checks": "answer_checks.csv",
                                                 "competitor_cleanup": True})
    checks = pd.read_csv(runlib.HERE / "answer_checks.csv", dtype={"ce": str}).fillna({"b": "", "value": ""})
    universe = pd.read_csv(S / "20261030_validation_v2" / "eos_keywords.csv", dtype={"ce": str})
    universe = universe[universe["ce"].isin(ces)].assign(k=lambda d: d["term"].map(norm), w=lambda d: d["vol"].fillna(0).clip(lower=10))
    universe = universe.drop_duplicates(["ce", "k"])
    specs = dict(SPECS, **{l: S / snap / "cluster_keywords.csv" for l, snap in (x.split("=") for x in filter(None, a.lists.split(";")))})
    lists = {label: load_list(path, universe) for label, path in specs.items()}
    for spec in filter(None, a.prompt_lists.split(";")):
        label, src = spec.split("=")
        snapshot, runs = src.split(":")
        lists[label] = load_prompt_list(snapshot, runs, universe)
    # The agreed clean-up on top of EOS: competitor and reseller keywords sit in no cluster, whichever list placed them
    comp = universe["k"].str.contains(cluster_fix.COMPETITORS, regex=True)
    for label, (u, meta, parent) in lists.items():
        u.loc[u["k"].isin(set(universe.loc[comp, "k"])), "name"] = None
    rows = []
    for label, (u_all, meta, parent) in lists.items():
        for ce in ces:
            u = u_all[u_all["ce"] == ce]
            if u.empty or u["name"].notna().sum() == 0:
                continue
            for c in checks[checks["ce"].isin(["*", ce])].itertuples():
                ok, why = run_check(c, u, meta, parent, ce)
                rows.append({"ce": ce, "list": label, "id": c.id, "check": c.check, "type": c.type,
                             "result": "no data" if ok is None else "pass" if ok else "fail", "evidence": why})
    res = pd.DataFrame(rows)
    res.to_csv(run.out / "checks.csv", index=False)
    scored = res[res["result"] != "no data"]
    rate = scored.assign(p=scored["result"].eq("pass")).groupby(["ce", "list"])["p"].agg(["sum", "count"])
    rate["pass_rate"] = (100 * rate["sum"] / rate["count"]).round(1)
    for (ce, label), r in rate.iterrows():
        run.record(ce, label, "answer_key_pass_rate", r["pass_rate"], f"{int(r['sum'])}/{int(r['count'])}")
    print(rate["pass_rate"].unstack("list").to_string())
    run.close()


if __name__ == "__main__":
    main()
