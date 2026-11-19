"""Keyword-graph clustering: build a CE's clusters from its keywords with an algorithm instead of a prompt.

  1. Universe   the CE's research keywords; for an existing CE optionally also its top paid search terms
  2. Families   spelling, plural, word-order and typo variants collapse into one family with one volume
  3. Noise      competitor and OTA keywords are set aside before grouping
  4. Graph      families are linked by meaning (multilingual embeddings) and shared words; an existing CE also links
                families whose searches reach the same ad groups and organic pages. Links across intents are damped.
  5. Groups     Louvain community detection; head-term families are pinned together; tiny groups roll into a
                neighbour or into "Other <intent>"
  6. Output     a derived snapshot whose cluster_keywords.csv has the EOS shape, so polyfuzz_mapping.py and
                cluster_scorecard.py score it exactly like EOS's own clusters

Modes: --mode new uses keyword text only (a CE with no history); --mode existing adds behaviour links.

Usage: python graph_cluster.py --snapshot 20261028_v4_connected --universe 20261028_v2_full_plus \
           --out-snapshot 20261029_graph_existing --mode existing --add-terms 400 --model <dir> [--ces 189,325]
"""
import argparse
import json
import re
import shutil
import urllib.parse
import uuid

import networkx as nx
import numpy as np
import pandas as pd
from rapidfuzz import fuzz

import ce_config
import cluster_fix
import cluster_scorecard as sc
import polyfuzz_mapping as pm
import runlib

# Translation groups that hold for any CE. ce_config also has Vatican-specific groups (sistine, chapel, garden).
GENERIC_CANON = {w: g for g in ("ticket", "official", "visit", "tour", "hours") for w in ce_config.EQUIV_GROUPS[g]}
INTENT_GROUPS = {"ticket", "tour", "visit", "official", "hours"}
NAME_DF_MIN = 0.03    # translations of the CE name are only looked for among words this common
NAME_COS = 0.75       # a word this close in meaning to a CE-name word is that word in another language
# Product formats the scorecard lexicon does not list; each is something a customer buys
EXTRA_PLANNING = (r"dress|wear|rule|allowed|forbidden|queue|\bwait|crowd|best time|best day|when to|weather|accessib|wheelchair|"
                  r"layout|entrance|where is|location|address|how long|duration|sunday|today|closed|\bopen")
SERP_WEIGHT = 0.5      # share of a link's weight taken from shared Google results when both families have them
SERP_FULL = 4          # shared top-10 URLs that count as full evidence of one page
SERP_MIN_SHARED = 3    # shared URLs that create a link on their own
ID_COVER, ID_OWN = 0.3, 0.6  # identifier word: in 30%+ of the cluster's families, and 60%+ of its uses in this cluster
SHARED_VOL_MIN = 10000  # below this, a shared volume tier is too common to suggest variants
SHARED_VOL_COS = 0.55
SHARED_VOL_STRONG = 0.80  # meaning this close makes two same-tier keywords variants even without a shared word
NAME_SPELL_MIN = 50   # a translation of a name word shares at least this much spelling with it
EXTRA_TRANSACTIONAL = r"\bpass(es)?\b|\bcard\b|skip|fast track|private|\bvip\b|night|evening|audio|small group|combo|deal|discount|student|reduced|cruise|boat|flight"
TYPO_RATIO = 92       # two families whose word sets read this alike are one family (misspellings)
KNN = 12              # links kept per family before weighting
MIN_COS = 0.45        # weaker meaning links are not considered at all
CROSS_INTENT = 0.35   # a link between a buying, a planning and an informational family keeps this share of its weight
DISJOINT = 0.6        # two families with their own words but none in common keep this share of their weight
MIN_BEHAVIOUR = 5     # clicks a family needs before its behaviour vector counts
ROLL_FAMILIES, ROLL_VOLUME, ROLL_LINK = 3, 500, 0.5

COARSE = {"official_site": "T", "combo": "T", "gaudi_house": "T", "tour": "T", "tickets": "T", "free_entry": "P",
          "hours": "P", "getting_there": "P", "parking": "P", "map": "P", "bare_name": "I"}
TYPE = {"T": "TRANSACTIONAL", "P": "PLANNING", "I": "INFORMATIONAL"}


def singular(w):
    if len(w) > 4 and w.endswith("es") and w[:-2].endswith(("ss", "x", "ch", "sh")):
        return w[:-2]
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def words(text):
    return [GENERIC_CANON.get(singular(w), singular(w)) for w in pm.norm(text).split() if w not in ce_config.STOP and len(w) > 1]


def load_universe(universe_snap, snap, ce, add_terms):
    kw = pd.read_csv(runlib.SNAPSHOTS / universe_snap / "cluster_keywords.csv", dtype={"ce": str})
    kw = kw[(kw["ce"] == ce) & kw["kw"].notna()].groupby("kw", as_index=False)["vol"].max().assign(source="research")
    if add_terms:
        st = pd.read_csv(runlib.SNAPSHOTS / snap / "search_terms.csv", dtype={"ce": str})
        st = st[(st["ce"] == ce) & ~st["term"].isin(kw["kw"])].nlargest(add_terms, "clicks")
        # Paid terms have no Keyword Planner volume; monthly impressions stand in, as a lower bound.
        kw = pd.concat([kw, pd.DataFrame({"kw": st["term"], "vol": (st["impr"] / 3).round(), "source": "paid_term"})])
    return kw.reset_index(drop=True)


def build_families(kw):
    kw = kw.assign(toks=kw["kw"].map(words))
    kw["key"] = kw["toks"].map(lambda t: " ".join(sorted(set(t))))
    fam = (kw.sort_values("vol", ascending=False).groupby("key", sort=False)
           .agg(rep=("kw", "first"), vol=("vol", "max"), members=("kw", list), source=("source", "first")).reset_index())
    # Typos: merge families whose sorted word sets are near-identical, into the larger one
    parent = list(range(len(fam)))
    keys = fam["key"].tolist()
    for i in range(len(fam)):
        for j in range(i):
            if parent[j] == j and abs(len(keys[i]) - len(keys[j])) <= 2 and len(keys[i]) >= 8 and fuzz.ratio(keys[i], keys[j]) >= TYPO_RATIO:
                parent[i] = j
                break
    fam["root"] = parent
    fam = (fam.groupby("root").agg(key=("key", "first"), rep=("rep", "first"), vol=("vol", "max"),
                                   members=("members", lambda s: sum(s, [])), source=("source", "first")).reset_index(drop=True))
    return fam


CYR_GRK = str.maketrans({**dict(zip("абвгдезийклмнопрстуфхцчшщыэюяёъь", "abvgdeziiklmnoprstufhcchsyeuae\u0000\u0000")),
                          **dict(zip("αβγδεζηθικλμνξοπρστυφχψωάέήίόύώς", "avgdeziuiklmnxoprstufhpoaeiioyos"))})


def translit(word):
    """Cyrillic and Greek letters spelled in Latin, so "ватикан" reads as "vatikan" in a spelling comparison."""
    return word.translate(CYR_GRK).replace("\u0000", "")


def name_words(ce_name, city, fam, model):
    """Words that only name the attraction: the CE's name and city, plus their translations and spellings found by
    meaning (vaticani, vatikan, musei). Intent words in the CE name ("Eiffel Tower Tickets") stay intent words."""
    base = {w for w in words(f"{ce_name} {city}") if w not in INTENT_GROUPS}
    df = pd.Series([w for k in fam["key"] for w in set(k.split())]).value_counts() / len(fam)
    cand = [w for w in df[df >= NAME_DF_MIN].index if w not in base and w not in INTENT_GROUPS]
    if not cand or not base:
        return base
    eb = model.encode(sorted(base), normalize_embeddings=True)
    ec = model.encode(cand, normalize_embeddings=True)
    close = (ec @ eb.T).max(axis=1)
    spelled = [max(fuzz.ratio(translit(w), b) for b in base) for w in cand]
    # A translation looks alike too (vaticani, vatikan, musei); "gaudi" is close in meaning to "park guell" but is
    # a different place, so meaning alone never makes a name word.
    return base | {w for w, c, s in zip(cand, close, spelled) if s >= 85 or (c >= NAME_COS and s >= NAME_SPELL_MIN)}


def coarse_intent(text):
    t = pm.norm(text)
    if re.search(EXTRA_TRANSACTIONAL, t):
        return "T"
    if re.search(EXTRA_PLANNING, t):
        return "P"
    return COARSE[sc.tag(text)]


def drop_competitors(fam):
    """Competitor spellings ("tiqets vatican museum") leave their family; a family is noise only when nothing else is
    left. Before 3 Nov 2026 one competitor member made the whole family noise, and shared-volume merging had put
    "tiqets vatican museum" into the 90,500 "vatican museum tickets" family, so Vatican lost its main ticket keywords."""
    comp = lambda m: bool(re.search(cluster_fix.COMPETITORS, m.lower()))
    clean = fam["members"].map(lambda ms: [m for m in ms if not comp(m)])
    fam = fam.assign(noise=clean.map(len).eq(0), members=[c if c else ms for c, ms in zip(clean, fam["members"])])
    fam["rep"] = [ms[0] if comp(rep) and not noise else rep for rep, ms, noise in zip(fam["rep"], fam["members"], fam["noise"])]
    return fam


def merge_shared_volume(fam, emb):
    """Keyword Planner gives close variants one bucketed volume ("sistine", "sixtus", "sixteenth chapel" all 450,000).
    Families that share an identical large volume, a word of their own and similar meaning are one family."""
    parent = list(range(len(fam)))

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    big = fam[fam["vol"] >= SHARED_VOL_MIN]
    for _, grp in big.groupby("vol"):
        idx = grp.index.tolist()
        for x in range(len(idx)):
            for y in range(x):
                i, j = idx[x], idx[y]
                # Volumes are rounded to fixed tiers (90,500; 135,000; 301,000…), so a shared tier alone can be chance.
                # Variants share a word of their own, or are near-identical in meaning ("efi tower" / "eiffel tower").
                cos = float(emb[i] @ emb[j])
                if (fam.at[i, "own"] & fam.at[j, "own"] and cos >= SHARED_VOL_COS) or cos >= SHARED_VOL_STRONG:
                    parent[find(i)] = find(j)
    roots = [find(i) for i in range(len(fam))]
    if roots == list(range(len(fam))):
        return fam, emb
    fam = fam.assign(root=roots)
    keep = sorted(set(roots))
    merged = (fam.groupby("root").agg(key=("key", "first"), rep=("rep", "first"), vol=("vol", "max"),
                                      members=("members", lambda s: sum(s, [])), source=("source", "first"),
                                      own=("own", lambda s: set().union(*s))).reindex(keep).reset_index(drop=True))
    return merged, emb[keep]


def behaviour_vectors(snap, ce, fam):
    """Click distribution over ad groups (paid) and ranking pages (organic) for each family's exact-match terms."""
    path = runlib.SNAPSHOTS / snap / "search_terms_by_adgroup.csv"
    if not path.exists():
        return {}
    st = pd.read_csv(path, dtype={"ce": str, "ad_group_id": str})
    st = st[st["ce"] == ce]
    paid = st.groupby(["term", "ad_group_id"])["clicks"].sum().reset_index().rename(columns={"ad_group_id": "slot"})
    gsc_path = runlib.SNAPSHOTS / snap / "gsc_terms.csv"
    parts = [paid.assign(slot="ag:" + paid["slot"])]
    if gsc_path.exists():
        g = pd.read_csv(gsc_path, dtype={"ce": str})
        g = g[g["ce"] == ce][["term", "top_page", "clicks"]].rename(columns={"top_page": "slot"})
        parts.append(g.assign(slot="pg:" + g["slot"].astype(str)))
    beh = pd.concat(parts)
    member_of = {m: i for i, ms in enumerate(fam["members"]) for m in ms}
    beh["fam"] = beh["term"].map(member_of)
    beh = beh[beh["fam"].notna()]
    mat = beh.pivot_table(index="fam", columns="slot", values="clicks", aggfunc="sum", fill_value=0)
    mat = mat[mat.sum(axis=1) >= MIN_BEHAVIOUR]
    vecs = mat.div(np.linalg.norm(mat.values, axis=1), axis=0)
    return {int(i): v for i, v in zip(vecs.index, vecs.values)}


def serp_strength(a, b):
    """0 with no shared top-10 URL, 1 from SERP_FULL shared URLs up (the industry rule treats 3-4 as one page)."""
    return min(1.0, len(a & b) / SERP_FULL)


def norm_url(u):
    p = urllib.parse.urlparse(u)
    return (p.netloc.removeprefix("www.") + p.path.rstrip("/")).lower() if p.scheme.startswith("http") else None


def serp_by_family(fam, serp):
    """Top-10 URL sets for families with a fetched query (the family's representative or any member)."""
    out = {}
    for i, ms in enumerate(fam["members"]):
        for m in ms:
            if m in serp:
                urls = {norm_url(u) for u in serp[m]} - {None}
                if urls:
                    out[i] = urls
                    break
    return out


def cluster_ce(ce, fam, emb, beh, resolution, names, serp=None):
    fam["own"] = fam["key"].map(lambda k: set(k.split()) - names)
    fam, emb = merge_shared_volume(fam, emb)
    urls = serp_by_family(fam, serp) if serp else {}
    fam["intent"] = fam["rep"].map(coarse_intent)
    fam = drop_competitors(fam)
    fam["head"] = fam["own"].map(len).eq(0) & ~fam["noise"]
    live = fam.index[~fam["noise"]].tolist()
    liveset = set(live)

    sim = emb @ emb.T
    g = nx.Graph()
    g.add_nodes_from(live)
    for i in live:
        order = [j for j in np.argsort(-sim[i]) if j != i and j in liveset][:KNN]
        for j in order:
            cos = float(sim[i, j])
            if cos < MIN_COS:
                break
            a, b = fam.at[i, "own"], fam.at[j, "own"]
            lex = len(a & b) / len(a | b) if (a or b) else 1.0
            if beh is not None and i in beh and j in beh:
                w = 0.45 * cos + 0.25 * lex + 0.30 * float(beh[i] @ beh[j])
            else:
                w = 0.6 * cos + 0.4 * lex
            if fam.at[i, "intent"] != fam.at[j, "intent"] and not (fam.at[i, "head"] or fam.at[j, "head"]):
                w *= CROSS_INTENT
            if a and b and not (a & b):
                w *= DISJOINT
            if i in urls and j in urls:
                # Shared Google results are direct evidence for "one page", so they are not damped by intent guesses
                w = (1 - SERP_WEIGHT) * w + SERP_WEIGHT * serp_strength(urls[i], urls[j])
            if w > g.get_edge_data(i, j, {"weight": 0})["weight"]:
                g.add_edge(i, j, weight=w)
    # Families that share SERP_MIN_SHARED+ top-10 URLs are linked even when their wording looks unrelated
    fetched = sorted(urls)
    for x, i in enumerate(fetched):
        for j in fetched[:x]:
            if i in liveset and j in liveset and len(urls[i] & urls[j]) >= SERP_MIN_SHARED and not g.has_edge(i, j):
                g.add_edge(i, j, weight=SERP_WEIGHT * serp_strength(urls[i], urls[j]))
    comms = nx.community.louvain_communities(g, weight="weight", resolution=resolution, seed=42)
    label = {n: k for k, c in enumerate(comms) for n in c}

    heads = fam.index[fam["head"]].tolist()
    if heads:
        head_comm = pd.Series({k: fam.loc[[n for n in c if n in heads], "vol"].sum() for k, c in enumerate(comms)}).idxmax()
        for n in heads:
            label[n] = head_comm

    fam["comm"] = pd.Series([label.get(n, -1) for n in fam.index], index=fam.index, dtype=object)
    # Roll tiny groups into their best-linked neighbour, or into "Other <intent>"
    for _ in range(3):
        size = fam[~fam["noise"]].groupby("comm").agg(n=("rep", "size"), v=("vol", "sum"))
        small = size[(size["n"] < ROLL_FAMILIES) & (size["v"] < ROLL_VOLUME)].index
        for k in small:
            nodes = fam.index[fam["comm"] == k]
            link = {}
            for n in nodes:
                for m, d in g[n].items():
                    if fam.at[m, "comm"] != k:
                        link[fam.at[m, "comm"]] = link.get(fam.at[m, "comm"], 0) + d["weight"]
            target = max(link, key=link.get) if link and max(link.values()) >= ROLL_LINK else f"other_{fam.loc[nodes, 'intent'].mode()[0]}"
            fam.loc[nodes, "comm"] = target
    fam.loc[fam["noise"], "comm"] = "noise"
    return fam


def identifiers(fam, ids_on):
    """Each cluster's distinctive words, in every spelling seen in its keywords. A word qualifies when it appears in
    at least ID_COVER of the cluster's families and at least ID_OWN of all families using it sit in this cluster;
    name words and words spread across clusters never qualify. The head and Other clusters get none."""
    if not ids_on:
        return {}
    live = fam[fam["comm"] != "noise"]
    use = live.assign(w=live["own"].map(list)).explode("w").dropna(subset=["w"])
    per = use.groupby(["comm", "w"]).size().rename("n").reset_index()
    per["cover"] = per["n"] / per["comm"].map(live.groupby("comm").size())
    per["owned"] = per["n"] / per.groupby("w")["n"].transform("sum")
    pick = per[(per["cover"] >= ID_COVER) & (per["owned"] >= ID_OWN)]
    surface = {}
    for ms in live["members"]:
        for m in ms:
            for t in pm.norm(m).split():
                key = GENERIC_CANON.get(singular(t), singular(t))
                surface.setdefault(key, set()).add(t)
    out = {}
    for comm, g in pick.groupby("comm"):
        if str(comm).startswith("other_") or live.loc[live["comm"] == comm, "head"].any():
            continue
        out[comm] = sorted({s for w in g["w"] for s in surface.get(w, {w}) if len(s) > 2})
    return out


def to_cluster_rows(ce, fam, ids_on=True):
    rows = []
    ids = identifiers(fam, ids_on)
    # Identifier matching is first-match in stored order, so the narrowest clusters come first
    order = fam[fam["comm"] != "noise"].groupby("comm").size().sort_values().index.tolist()
    for rank, comm in enumerate(order, start=1):
        f = fam[fam["comm"] == comm]
        top = f.sort_values("vol", ascending=False)
        intent = f.groupby("intent")["vol"].sum().idxmax()
        if str(comm).startswith("other_"):
            name, intent = f"Other ({TYPE[str(comm)[-1]].lower()})", str(comm)[-1]
        elif f["head"].any():
            name = f"{top.iloc[0]['rep']} (head term)"
        else:
            name = top.iloc[0]["rep"]
        cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ce}|{name}"))
        for _, r in f.iterrows():
            for m in r["members"]:
                rows.append({"ce": ce, "cid": cid, "rank": rank if comm in ids else None, "t": TYPE[intent], "name": name,
                             "ids": json.dumps(ids.get(comm, []), ensure_ascii=False), "kw": m, "vol": r["vol"]})
    return pd.DataFrame(rows)


def health(ce, fam, rows, run, method):
    by = rows.groupby("cid")["kw"].size()
    run.record(ce, method, "n_clusters", len(by))
    run.record(ce, method, "largest_cluster_share_kw", 100 * by.max() / by.sum())
    run.record(ce, method, "singleton_clusters", int((by == 1).sum()))
    run.record(ce, method, "competitor_kw_removed", int(fam.loc[fam["noise"], "members"].map(len).sum()))
    run.record(ce, method, "families_per_keyword", len(fam) / max(1, fam["members"].map(len).sum()))


def main():
    a = runlib.args("graph_cluster", {"--universe": {"required": True}, "--out-snapshot": {"required": True},
                                      "--mode": {"choices": ["new", "existing"], "required": True},
                                      "--add-terms": {"type": int, "default": 0}, "--resolution": {"type": float, "default": 1.0},
                                      "--model": {"required": True},
                                      "--prefix": {"default": "", "help": "text the model expects before each input, e.g. 'query: ' for e5"},
                                      "--no-ids": {"action": "store_true", "help": "write clusters without identifiers"},
                                      "--serp": {"action": "store_true", "help": "use serp_<ce>.json in the snapshot (serp_fetch.py) where present"}})
    params = {"ces": a.ces, "universe": a.universe, "mode": a.mode, "add_terms": a.add_terms, "resolution": a.resolution,
              "knn": KNN, "min_cos": MIN_COS, "cross_intent": CROSS_INTENT, "disjoint": DISJOINT, "name_df_min": NAME_DF_MIN, "name_cos": NAME_COS,
              "typo_ratio": TYPO_RATIO, "roll": [ROLL_FAMILIES, ROLL_VOLUME, ROLL_LINK], "out_snapshot": a.out_snapshot,
              "model": a.model.rstrip("/").split("/")[-1], "prefix": a.prefix, "identifiers": not a.no_ids, "serp": a.serp, "serp_weight": SERP_WEIGHT, "serp_full": SERP_FULL,
              "serp_min_shared": SERP_MIN_SHARED,
              "id_cover": ID_COVER, "id_own": ID_OWN}
    run = runlib.Run("graph_cluster", a.snapshot, params)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(a.model)
    src, dst = runlib.SNAPSHOTS / a.snapshot, runlib.SNAPSHOTS / a.out_snapshot
    dst.mkdir(exist_ok=True)
    for f in src.iterdir():
        if f.is_file() and f.name not in ("cluster_keywords.csv", "manifest.json", "rebuild_log.csv"):
            shutil.copy(f, dst / f.name)
    method = f"graph {a.mode}" + (f" +{a.add_terms} terms" if a.add_terms else "")
    ce_names = pd.read_csv(src / "ce_names.csv", dtype={"ce": str}).set_index("ce")
    parts = []
    for ce in a.ces.split(","):
        kw = load_universe(a.universe, a.snapshot, ce, a.add_terms if a.mode == "existing" else 0)
        fam = build_families(kw)
        emb = model.encode([a.prefix + r for r in fam["rep"]], normalize_embeddings=True, batch_size=64)
        beh = behaviour_vectors(a.snapshot, ce, fam) if a.mode == "existing" else None
        names = name_words(ce_names.at[ce, "name"], ce_names.at[ce, "city"], fam, model)
        run.record(ce, method, "name_words", len(names), " ".join(sorted(names)))
        serp_path = src / f"serp_{ce}.json"
        serp = json.loads(serp_path.read_text()) if a.serp and serp_path.exists() else None
        run.record(ce, method, "serp_queries", len(serp or {}))
        fam = cluster_ce(ce, fam, emb, beh, a.resolution, names, serp)
        rows = to_cluster_rows(ce, fam, ids_on=not a.no_ids)
        health(ce, fam, rows, run, method)
        parts.append(rows)
        fam.drop(columns=["own"]).assign(members=fam["members"].map(" | ".join)).to_csv(run.out / f"families_{ce}.csv", index=False)
        summary = rows.groupby(["cid", "name", "t"]).agg(n_kw=("kw", "size"), vol_top=("vol", "max")).reset_index().sort_values("vol_top", ascending=False)
        summary.to_csv(run.out / f"clusters_{ce}.csv", index=False)
        print(f"\n=== CE {ce}: {len(kw)} keywords -> {len(fam)} families -> {summary.shape[0]} clusters "
              f"({int(fam['noise'].sum())} competitor families removed; behaviour vectors: {0 if beh is None else len(beh)})")
        print(summary.head(45).to_string(index=False))
    pd.concat(parts).to_csv(dst / "cluster_keywords.csv", index=False)
    (dst / "manifest.json").write_text(json.dumps({"snapshot": a.out_snapshot, "derived_from": a.snapshot, "how": "graph_cluster.py",
                                                   "run": run.id, "params": params}, indent=2))
    run.close()


if __name__ == "__main__":
    main()
