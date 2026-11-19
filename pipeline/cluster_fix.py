"""Rebuild EOS clusters algorithmically (no new LLM run) and write them as a new derived snapshot.

Fixes, each traced to a finding (scoping doc Walkthrough / Krupa's audits):
  1. scope filter     drop competitor-brand keywords (Tiqets, GetYourGuide, Klook ... sit inside EOS clusters)
  2. re-assignment    a keyword moves to another cluster only when that cluster's name fits it clearly better
                      (embedding margin), instead of substring identifiers ("tour" = French tower, "line" = queues)
  3. missing clusters seeded from evidence: hand-judged leftover demand and live pages with no cluster
  4. intent           a cluster whose keywords are mostly ticket/booking terms is TRANSACTIONAL
  5. volume           cluster volume = top keyword's volume (variants share one bucketed volume)
  6. empties          clusters left with no keywords are dropped
Identifiers become the cluster's own keywords (exact phrases), so the identifier rule can no longer misfire on a
single generic word.

Usage: python cluster_fix.py --snapshot 20261028_v2_full_plus --out-snapshot 20261028_v3_rebuilt --model <dir> [--ces 189,325]
"""
import argparse
import json
import re
import shutil
import uuid

import numpy as np
import pandas as pd

import polyfuzz_mapping as pm
import runlib

COMPETITORS = r"\b(tiqets|getyourguide|get your guide|gyg|klook|viator|musement|civitatis|tripadvisor|city wonders|walks of italy|headout|go city|isango|awesomenz)\b"
TICKET_WORDS = r"ticket|tickets|biglietti|entradas|billet|eintritt|entry|admission|booking|book|price|cost|skip the line|tour|tours|pass|reserv"
MARGIN = 0.06  # how much better another cluster's name must fit before a keyword moves
STOP = {"the", "and", "for", "with", "from", "how", "what", "can", "you", "are", "does", "near", "best", "visit", "visiting", "rome", "roma", "city"}
GENERIC = {  # attraction-name words: shared by every cluster of the CE, so they say nothing about fit
    "189": STOP | {"vatican", "vaticano", "vatikan", "museum", "museums", "musei", "vaticani", "museo", "museos", "vaticanos"},
    "325": STOP | {"park", "parc", "parque", "parco", "guell", "barcelona", "gaudi"},
}

# Missing clusters with evidence. Seeds are real searches/pages from the runs; volumes only where Keyword Planner gave one.
SEEDED = {
    "189": [
        ("Official Site & Official Tickets", "TRANSACTIONAL",
         [("vatican museums official site", None), ("musei vaticani sito ufficiale", None), ("museivaticani va", None),
          ("vatican tickets official website", None), ("pagina oficial vaticano", None), ("vatican official tickets", 480)],
         "official-site searches: 14.5% of judged leftover clicks (run 20261028-165528)"),
        ("Papal Audience & Masses", "TRANSACTIONAL",
         [("papal audience", None), ("audiencia papal", None), ("papal audience tickets", None), ("vatican mass", None),
          ("vatican easter mass", None)], "new cluster in hand judgement + live /papal-audience, /vatican-mass pages"),
        ("Castel Gandolfo & Apostolic Palace", "TRANSACTIONAL",
         [("castel gandolfo", None), ("castel gandolfo tickets", None), ("apostolic palace castel gandolfo", None),
          ("villa barberini", None)], "5 live pages, no EOS cluster (run 20261028-181030)"),
        ("Guided Tours In Your Language", "TRANSACTIONAL",
         [("vatikan führung deutsch", None), ("tour vaticano en español", None), ("vatican tours in italian", None),
          ("wycieczka po watykanie z polskim przewodnikiem", None), ("rondleiding vaticaan nederlands", None)],
         "new cluster in hand judgement (DE, ES, PL, NL) + live /best-tours-in-italian page"),
        ("Necropolis, Scavi & Grottoes", "TRANSACTIONAL",
         [("vatican necropolis", None), ("scavi tour", None), ("vatican grottoes", None), ("vatican necropolis tour", None)],
         "live pages with no cluster; St Peter's-side demand in hand judgement"),
    ],
    "325": [
        ("Official Site & Official Tickets", "TRANSACTIONAL",
         [("park guell official site", 1900), ("park guell official website", 1000), ("park guell official tickets", 1600),
          ("parc guell sito ufficiale", 720), ("park güell sitio oficial", 20)], "23.0K paid clicks, no cluster (Reference tab)"),
        ("Combos (Sagrada Família, Casa Batlló)", "TRANSACTIONAL",
         [("sagrada familia and park guell tickets", 390), ("sagrada familia and park guell", 140), ("park guell and sagrada familia", 110),
          ("park guell casa batllo", 140), ("sagrada familia park guell tour", 10)], "433 paid clicks, no cluster (Reference tab)"),
        ("Free Entry", "PLANNING",
         [("park guell free entry", 1000), ("park guell free", 480), ("parque guell gratis", 110)], "1,590 searches/month, no cluster"),
    ],
}


def label(name):
    return re.sub(r"\(.*?\)", "", str(name)).replace("&", "and").replace("/", " ").strip()


def rebuild(kw, ce, model):
    kw = kw[(kw["ce"] == ce)].copy()
    log = []
    clusters = kw.groupby("cid", sort=False).agg(name=("name", "first"), t=("t", "first"), rank=("rank", "first")).reset_index()
    keys = kw.dropna(subset=["kw"]).copy()

    # 1. scope filter
    comp = keys["kw"].str.lower().str.contains(COMPETITORS, regex=True)
    for _, r in keys[comp].iterrows():
        log.append({"ce": ce, "action": "drop_competitor", "keyword": r["kw"], "from": r["name"], "to": None})
    keys = keys[~comp]

    # 3. seeded clusters (added before re-assignment so they can pull keywords too)
    for name, t, seeds, why in SEEDED.get(ce, []):
        cid = "seed-" + uuid.uuid5(uuid.NAMESPACE_URL, f"{ce}/{name}").hex[:12]
        clusters = pd.concat([clusters, pd.DataFrame([{"cid": cid, "name": name, "t": t, "rank": None}])], ignore_index=True)
        for s, v in seeds:
            keys = pd.concat([keys, pd.DataFrame([{"ce": ce, "cid": cid, "name": name, "t": t, "kw": s, "vol": v, "seeded": True}])], ignore_index=True)
        log.append({"ce": ce, "action": "add_cluster", "keyword": None, "from": None, "to": name, "why": why})

    # 2. re-assignment by cluster-name fit, with a margin so only clear misassignments move
    names = clusters.set_index("cid")["name"].map(label)
    nemb = model.encode(names.tolist(), normalize_embeddings=True)
    kemb = model.encode(keys["kw"].astype(str).tolist(), normalize_embeddings=True, batch_size=128)
    sims = kemb @ nemb.T
    cids = names.index.to_numpy()
    cur = np.array([np.where(cids == c)[0][0] for c in keys["cid"]])
    best = sims.argmax(axis=1)
    gain = sims[np.arange(len(keys)), best] - sims[np.arange(len(keys)), cur]
    seeded = keys["seeded"].fillna(False).astype(bool).to_numpy() if "seeded" in keys else np.zeros(len(keys), bool)
    # guard: the keyword must share a content word with the target cluster (its name or its own keywords), so a
    # vague semantic pull ("isaiah michelangelo" -> "Castel Gandolfo") can't move anything
    toks = lambda s: {w for w in pm.norm(s).split() if w not in GENERIC[ce] and len(w) > 2}  # noqa: E731
    cl_tokens = {c: toks(names[c]) | set().union(*[toks(k) for k in keys.loc[keys["cid"] == c, "kw"]]) for c in cids}
    shares = np.array([bool(toks(k) & cl_tokens[cids[b]]) for k, b in zip(keys["kw"], best)])
    move = ((best != cur) & (gain >= MARGIN) & ~seeded & shares).astype(bool)
    for i in np.where(move)[0]:
        log.append({"ce": ce, "action": "move", "keyword": keys.iloc[i]["kw"], "from": keys.iloc[i]["name"],
                    "to": names.iloc[best[i]], "why": f"name fit +{gain[i]:.2f}"})
    keys.loc[keys.index[move], "cid"] = cids[best[move]]
    keys["name"] = keys["cid"].map(clusters.set_index("cid")["name"])

    # 4. intent: mostly ticket/booking keywords -> transactional
    share = keys.assign(tk=keys["kw"].str.lower().str.contains(TICKET_WORDS, regex=True)).groupby("cid")["tk"].mean()
    for cid, s in share.items():
        row = clusters.index[clusters["cid"] == cid][0]
        if s >= 0.5 and clusters.at[row, "t"] != "TRANSACTIONAL":
            log.append({"ce": ce, "action": "retype", "keyword": None, "from": clusters.at[row, "t"], "to": "TRANSACTIONAL",
                        "why": f"{s:.0%} ticket/booking keywords", "cluster": clusters.at[row, "name"]})
            clusters.at[row, "t"] = "TRANSACTIONAL"
    keys["t"] = keys["cid"].map(clusters.set_index("cid")["t"])

    # 6. drop empty clusters; identifiers = own keywords; niche-first rank = fewer keywords first, head terms last
    counts = keys.groupby("cid").size()
    for _, r in clusters[~clusters["cid"].isin(counts.index)].iterrows():
        log.append({"ce": ce, "action": "drop_empty", "keyword": None, "from": r["name"], "to": None})
    clusters = clusters[clusters["cid"].isin(counts.index)].copy()
    vol_top = keys.groupby("cid")["vol"].max()
    clusters["rank"] = clusters["cid"].map(vol_top.fillna(0)).rank(method="first").astype(int)  # small clusters first
    ids = keys.groupby("cid")["kw"].apply(lambda s: json.dumps(sorted({pm.norm(k) for k in s if len(pm.norm(k).split()) >= 2})))
    keys["ids"] = keys["cid"].map(ids)
    keys["rank"] = keys["cid"].map(clusters.set_index("cid")["rank"])
    out = keys[["ce", "cid", "rank", "t", "name", "ids", "kw", "vol"]]
    return out, pd.DataFrame(log)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", required=True)
    p.add_argument("--out-snapshot", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--ces", default="189,325")
    a = p.parse_args()
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(a.model)
    src, dst = runlib.SNAPSHOTS / a.snapshot, runlib.SNAPSHOTS / a.out_snapshot
    dst.mkdir(exist_ok=True)
    for f in src.iterdir():  # every other input is unchanged
        if f.is_file() and f.name not in ("cluster_keywords.csv", "manifest.json"):
            shutil.copy(f, dst / f.name)
    kw = pd.read_csv(src / "cluster_keywords.csv", dtype={"ce": str})
    parts, logs = [], []
    for ce in a.ces.split(","):
        out, log = rebuild(kw, ce, model)
        parts.append(out)
        logs.append(log)
    pd.concat(parts).to_csv(dst / "cluster_keywords.csv", index=False)
    log = pd.concat(logs)
    log.to_csv(dst / "rebuild_log.csv", index=False)
    (dst / "manifest.json").write_text(json.dumps({
        "snapshot": a.out_snapshot, "derived_from": a.snapshot, "how": "cluster_fix.py", "margin": MARGIN,
        "changes": log.groupby(["ce", "action"]).size().rename("n").reset_index().to_dict("records")}, indent=2))
    pd.set_option("display.width", 220, "display.max_colwidth", 60)
    print(log.groupby(["ce", "action"]).size())
    print(log[log["action"] == "move"].head(40).to_string(index=False))


if __name__ == "__main__":
    main()
