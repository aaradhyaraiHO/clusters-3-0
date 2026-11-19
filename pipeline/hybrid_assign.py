"""Hybrid option: EOS decides the cluster list, the algorithm assigns keywords and paid terms to it.

  EOS clusters (names, intent types, granularity) stay fixed. The CE's keyword universe (EOS research keywords, plus
  the top paid terms in existing-CE mode) is grouped into graph_cluster.py's variant families, then:
    1. a family with EOS-placed members joins the EOS cluster holding most of their volume (variants follow their
       spelling, so "sixtus chapel" goes wherever "sistine chapel" went);
    2. name-only families join the head cluster;
    3. every other family (paid terms, EOS "Other / Unassigned") joins the EOS cluster its NEIGHBOURS most similar
       placed families vote for (meaning + shared words, damped across intent types); if even the closest placed
       family is below ASSIGN_MIN it goes to "Other (<intent>)".
    4. a buying family EOS placed in an informational or planning cluster is re-voted among the buying clusters;
    5. when no EOS cluster is about the official site, official-site buying searches get a cluster of their own;
    6. seed clusters (--seeds: intents EOS left out, each with a few keywords) take the families holding their
       keywords, overriding EOS, and then gather translations and variants through the same neighbour vote.
  Identifiers are generated from the result exactly as graph_cluster.py does.

Usage: python hybrid_assign.py --snapshot 20261029_bakeoff_v0 --clusters-from 20261029_bakeoff_v0 --out-snapshot <id>
       --ces 189 --add-terms 400 --model .env-clusters/models/paraphrase-multilingual-MiniLM-L12-v2
"""
import json
import re
import shutil
import uuid
from collections import Counter

import numpy as np
import pandas as pd

import cluster_fix
import graph_cluster as gc
import runlib

ASSIGN_MIN = 0.45   # same floor graph_cluster.py uses for a meaning link (MIN_COS)
NEIGHBOURS = 7      # anchored families that vote on an unplaced family's cluster
SEED_OFFICIAL = "seed_official"
LETTER = {"TRANSACTIONAL": "T", "PLANNING": "P", "INFORMATIONAL": "I"}


def is_other(name):
    return bool(re.match(r"other\b", str(name).strip().lower()))


def assign_ce(ce, clusters, kw, emb_model, prefix, ce_name, city, seeds=None):
    eos = clusters[(clusters["ce"] == ce) & clusters["kw"].notna()]
    meta = eos.drop_duplicates("cid").set_index("cid")[["name", "t", "ids"]]
    placed = eos[~eos["name"].map(is_other)].set_index("kw")["cid"].to_dict()
    vol_of = kw.set_index("kw")["vol"].to_dict()

    fam = gc.build_families(kw)
    emb = emb_model.encode([prefix + r for r in fam["rep"]], normalize_embeddings=True, batch_size=64)
    names = gc.name_words(ce_name, city, fam, emb_model)
    fam["own"] = fam["key"].map(lambda k: set(k.split()) - names)
    fam, emb = gc.merge_shared_volume(fam, emb)
    fam["intent"] = fam["rep"].map(gc.coarse_intent)
    fam = gc.drop_competitors(fam)
    fam["head"] = fam["own"].map(len).eq(0) & ~fam["noise"]

    def vote(members):
        tally = Counter()
        for m in members:
            if m in placed:
                tally[placed[m]] += max(float(vol_of.get(m, 0) or 0), 1.0)
        return tally.most_common(1)[0][0] if tally else None

    fam["comm"] = fam["members"].map(vote).astype(object)
    fam["how"] = np.where(fam["comm"].notna(), "eos", None)
    letter_of = {c: LETTER.get(meta.at[c, "t"], "I") for c in meta.index}
    letter_of[SEED_OFFICIAL] = "T"
    live = ~fam["noise"]
    seed_meta = {}
    for n, r in enumerate((seeds if seeds is not None else pd.DataFrame()).itertuples()):
        comm = f"seedc_{n}"
        seed_meta[comm] = (r.name, r.type)
        letter_of[comm] = LETTER.get(r.type, "I")
        words = set(r.keywords.split("|"))
        fam.loc[live & fam["members"].map(lambda ms: bool(words & set(ms))), ["comm", "how"]] = [comm, "seed"]
    # EOS often has no cluster for "official site" searches (the official ticket office) and scatters them over the
    # head term, Discount and others; when none of its cluster names says "official", they get a cluster of their own.
    if not meta["name"].str.contains("official", case=False).any():
        official = live & ~fam["head"] & fam["intent"].eq("T") & fam["key"].map(lambda k: "official" in k.split())
        fam.loc[official, ["comm", "how"]] = [SEED_OFFICIAL, "seeded"]
    heads = fam[fam["comm"].notna() & live & fam["head"]]
    head_cid = heads.groupby("comm")["vol"].sum().idxmax() if len(heads) else None

    def nearest(i, pool):
        """The cluster most of family i's NEIGHBOURS closest pool families sit in (meaning + shared words, damped across
        intent types), or None when even the closest is below ASSIGN_MIN."""
        own = fam.at[i, "own"]
        says_official = "official" in fam.at[i, "key"].split()
        links = []
        for j, c in zip(pool, emb[pool] @ emb[i]):
            # The official-site cluster only takes searches that say "official" in some language; without this, plain
            # ticket searches in other languages drift to it because most official searches are not in English
            if fam.at[j, "comm"] == SEED_OFFICIAL and not says_official:
                continue
            other = fam.at[j, "own"]
            lex = len(own & other) / len(own | other) if (own or other) else 1.0
            w = 0.6 * float(c) + 0.4 * lex
            # Head-term families are damped too: exempting them pulled buying searches into the informational head
            if fam.at[j, "intent"] != fam.at[i, "intent"]:
                w *= gc.CROSS_INTENT
            links.append((w, fam.at[j, "comm"]))
        links.sort(key=lambda x: -x[0])
        top = links[:NEIGHBOURS]
        if not top or top[0][0] < ASSIGN_MIN:
            return None
        votes = Counter()
        for w, c in top:
            votes[c] += w
        return votes.most_common(1)[0][0]

    # A buying family EOS placed in an informational or planning cluster ("vatican museum official website" in the head
    # term) is re-voted among the buying clusters' families only.
    placed_mask = fam["comm"].notna() & live
    conflict = placed_mask & fam["intent"].eq("T") & fam["comm"].map(lambda c: letter_of.get(c, "T") != "T")
    buying_pool = fam.index[placed_mask & ~conflict & fam["comm"].map(lambda c: letter_of.get(c) == "T")].to_numpy()
    for i in fam.index[conflict]:
        target = nearest(i, buying_pool) if len(buying_pool) else None
        if target is not None:
            fam.at[i, "comm"], fam.at[i, "how"] = target, "revote"

    anchor_idx = fam.index[fam["comm"].notna() & live].to_numpy()
    for i in fam.index[fam["comm"].isna() & live]:
        if fam.at[i, "head"] and head_cid is not None:
            fam.at[i, "comm"], fam.at[i, "how"] = head_cid, "head"
            continue
        target = nearest(i, anchor_idx)
        fam.at[i, "comm"], fam.at[i, "how"] = (target, "nearest") if target is not None else (f"other_{fam.at[i, 'intent']}", "other")
    fam.loc[fam["noise"], ["comm", "how"]] = ["noise", "noise"]

    ids = gc.identifiers(fam, True)
    order = fam[fam["comm"] != "noise"].groupby("comm").size().sort_values().index.tolist()
    rows = []
    for rank, comm in enumerate(order, start=1):
        if str(comm).startswith("other_"):
            letter = str(comm)[-1]
            name, t, cid = f"Other ({gc.TYPE[letter].lower()})", gc.TYPE[letter], str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ce}|{comm}"))
        elif str(comm) in seed_meta:
            name, t = seed_meta[comm]
            cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ce}|{name}"))
        elif comm == SEED_OFFICIAL:
            name, t, cid = "Official site & official tickets", "TRANSACTIONAL", str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ce}|{comm}"))
        else:
            name, t, cid = meta.at[comm, "name"], meta.at[comm, "t"], comm
        eos_ids = json.loads(meta.at[comm, "ids"]) if comm in meta.index and str(meta.at[comm, "ids"]).startswith("[") else []
        cluster_ids = sorted(set(eos_ids) | set(ids.get(comm, [])))
        for _, r in fam[fam["comm"] == comm].iterrows():
            for m in r["members"]:
                rows.append({"ce": ce, "cid": cid, "rank": rank if cluster_ids else None, "t": t, "name": name,
                             "ids": json.dumps(cluster_ids, ensure_ascii=False), "kw": m, "vol": r["vol"]})
    return fam, pd.DataFrame(rows), eos


def main():
    a = runlib.args("hybrid_assign", {"--clusters-from": {"required": True, "help": "snapshot whose cluster list stays fixed"},
                                      "--out-snapshot": {"required": True}, "--add-terms": {"type": int, "default": 400},
                                      "--model": {"required": True}, "--prefix": {"default": ""},
                                      "--seeds": {"default": None, "help": "CSV of seed clusters: name,type,keywords (pipe-separated)"}})
    params = {"ces": a.ces, "clusters_from": a.clusters_from, "add_terms": a.add_terms, "assign_min": ASSIGN_MIN,
              "neighbours": NEIGHBOURS, "seeds": a.seeds, "cross_intent": gc.CROSS_INTENT, "out_snapshot": a.out_snapshot,
              "model": a.model.rstrip("/").split("/")[-1]}
    run = runlib.Run("hybrid_assign", a.snapshot, params)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(a.model)
    src, dst = runlib.SNAPSHOTS / a.snapshot, runlib.SNAPSHOTS / a.out_snapshot
    dst.mkdir(exist_ok=True)
    for f in src.iterdir():
        if f.is_file() and f.name not in ("cluster_keywords.csv", "manifest.json", "rebuild_log.csv"):
            shutil.copy(f, dst / f.name)
    clusters = pd.read_csv(runlib.SNAPSHOTS / a.clusters_from / "cluster_keywords.csv", dtype={"ce": str})
    ce_names = pd.read_csv(src / "ce_names.csv", dtype={"ce": str}).set_index("ce")
    method = f"hybrid eos-list +{a.add_terms} terms"
    parts = []
    for ce in a.ces.split(","):
        kw = gc.load_universe(a.clusters_from, a.snapshot, ce, a.add_terms)
        seeds = pd.read_csv(a.seeds, dtype={"ce": str}) if a.seeds else None
        if seeds is not None and "ce" in seeds.columns:
            seeds = seeds[seeds["ce"] == ce]
        if seeds is not None:
            extra = [k for ks in seeds["keywords"] for k in ks.split("|") if k not in set(kw["kw"])]
            kw = pd.concat([kw, pd.DataFrame({"kw": extra, "vol": 0, "source": "seed"})], ignore_index=True)
        fam, rows, eos = assign_ce(ce, clusters, kw, model, a.prefix, ce_names.at[ce, "name"], ce_names.at[ce, "city"], seeds)
        parts.append(rows)
        for how, n in fam.groupby("how")["members"].apply(lambda s: s.map(len).sum()).items():
            run.record(ce, method, f"keywords_{how}", int(n))
        before = eos.groupby("name")["kw"].nunique().rename("eos_kw")
        after = rows.groupby("name").agg(hybrid_kw=("kw", "nunique"), hybrid_vol=("vol", "sum"))
        cmp = before.to_frame().join(after, how="outer").fillna(0).astype(int).sort_values("hybrid_vol", ascending=False)
        cmp.to_csv(run.out / f"compare_{ce}.csv")
        fam.drop(columns=["own"]).assign(members=fam["members"].map(" | ".join)).to_csv(run.out / f"families_{ce}.csv", index=False)
        print(f"\n=== CE {ce}: {len(kw)} keywords -> {len(fam)} families -> {rows['cid'].nunique()} clusters; "
              + ", ".join(f"{h} {int(n)}" for h, n in fam.groupby("how")["members"].apply(lambda s: s.map(len).sum()).items()))
        print(cmp.to_string())
    pd.concat(parts).to_csv(dst / "cluster_keywords.csv", index=False)
    (dst / "manifest.json").write_text(json.dumps({"snapshot": a.out_snapshot, "derived_from": a.snapshot, "how": "hybrid_assign.py",
                                                   "run": run.id, "params": params}, indent=2))
    run.close()


if __name__ == "__main__":
    main()
