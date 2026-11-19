"""Prototype: map Google Ads search terms to EOS keyword clusters.

Compares three methods on Vatican Museums (189) and Park Güell (325), last 90 days:
  A  current rule  - first cluster (rank order, else stored order) whose identifier
                     appears as a whole word in the search term
  B  polyfuzz      - nearest cluster keyword/identifier by TF-IDF char 3-grams, kept if score >= threshold
  C  hybrid        - A, then B for terms A leaves unmapped

  D  layered       - C, then multilingual embeddings (needs --model) for terms C leaves unmapped

Usage: python polyfuzz_mapping.py --snapshot <id> [--ces 189,325] [--model <sentence-transformers dir>]
Inputs: snapshots/<id>/search_terms.csv, cluster_keywords.csv
Outputs: runs/<run_id>/outputs/ summary.csv, assignments_<ce>.csv, review/disagreement/unmapped samples
Metrics (results.csv): pct_clicks/spend/conv_mapped and pct_clicks_to_transactional per CE x method
"""
import json
import re
import sys
import unicodedata
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from polyfuzz import PolyFuzz  # noqa: E402
from polyfuzz.models import TFIDF  # noqa: E402

import ce_config  # noqa: E402
import runlib  # noqa: E402

OUT = None  # set from the run in main()
THRESHOLDS = [0.6, 0.7, 0.8]
REVIEW_THRESHOLD = 0.8  # spelling match that D accepts before trying meaning; 0.7 let 'vaticano maps' into Gallery of Maps
FIXED_PHRASE_SHARE = 0.4  # a one-word identifier inside one outside phrase this often ("last minute") stops placing searches
FIXED_PHRASE_MIN = 3  # searches needed before that test applies
FUNCTION_WORDS = {"it", "is", "much", "do", "be", "at", "on", "this", "an"}  # "it cost", "is open" stay in the cluster's sense

EMBED_THRESHOLDS = [0.75, 0.85]
EMBED_MODEL = None  # set in __main__ when a local model path is given: python polyfuzz_mapping.py <model_dir>


def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    # Letters of every script count: an a-z-only pattern turns Cyrillic, Greek or Arabic searches into empty strings
    return re.sub(r"[\W_]+", " ", s).strip()


def singular(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def distinctive_ids(clusters, kw, terms):
    """A one-word identifier places a search by the identifier rule only when the CE's own searches use it in the
    cluster's sense. It is dropped when one neighbouring word pair covers FIXED_PHRASE_SHARE or more of the searches
    containing it and that pair is not the cluster's own (in its keywords or name, or made only of their words and stopwords): "last" sits in "last minute" (not "last
    judgment"), "creation" in "création du vatican" (not "creation of adam"), "guide" in "get your guide". Words used
    in the cluster's sense ("map" in "vatican city map") keep. Phrases are kept as they are."""
    out = []
    for ce, cid, name, ids in zip(clusters["ce"], clusters["cid"], clusters["name"], clusters["ids"]):
        vocab = " | ".join([norm(k) for k in kw.loc[(kw["ce"] == ce) & (kw["cid"] == cid), "kw"]] + ids + [norm(name)])
        own = {singular(w) for w in vocab.split()} | ce_config.STOP | FUNCTION_WORDS
        searches = terms.loc[terms["ce"] == ce, "tn"].drop_duplicates()
        keep = []
        for i in ids:
            if " " in i:
                keep.append(i)
                continue
            pairs = []
            for tn in searches[searches.map(lambda x: f" {i} " in f" {x} ")]:
                w = tn.split()
                pairs.append({" ".join(w[k:k + 2]) for k in range(len(w) - 1) if i in w[k:k + 2]})
            if len(pairs) < FIXED_PHRASE_MIN:
                keep.append(i)
                continue
            counts = pd.Series([b for p in pairs for b in p]).value_counts()
            fixed = [b for b, n in counts.items() if n / len(pairs) >= FIXED_PHRASE_SHARE and f" {b} " not in f" {vocab} "
                     and not {singular(w) for w in b.split()} <= own]
            if not fixed:
                keep.append(i)
        out.append(keep)
    return out

def load(run, terms_file="search_terms.csv"):
    terms = pd.read_csv(run.input(terms_file), dtype={"ce": str})
    terms["tn"] = terms["term"].map(norm)
    kw = pd.read_csv(run.input("cluster_keywords.csv"), dtype={"ce": str})
    kw["order"] = range(len(kw))
    clusters = (
        kw.groupby(["ce", "cid"], sort=False)
        .agg(rank=("rank", "first"), t=("t", "first"), name=("name", "first"), ids=("ids", "first"), order=("order", "min"))
        .reset_index()
    )
    clusters["ids"] = clusters["ids"].map(lambda x: [norm(i) for i in json.loads(x)] if isinstance(x, str) else [])
    # the identifier rule uses only distinctive ids; PolyFuzz and embeddings still match against every id
    clusters["rule_ids"] = distinctive_ids(clusters, kw, terms)
    # niche first: explicit rank ascending, unranked clusters after in stored order
    clusters["sort_key"] = clusters.apply(lambda r: (0, r["rank"]) if pd.notna(r["rank"]) else (1, r["order"]), axis=1)
    clusters = clusters.sort_values("sort_key").reset_index(drop=True)
    return terms, kw, clusters


def current_rule(tn, ce_clusters):
    """Among clusters with a matching identifier, skip a match that another cluster's matching identifier contains
    ("line" gives way to "skip the line"); of the rest the identifier with most words wins ("vatican tickets" over the
    Last Judgment's "last"), then the narrowest cluster (stored order)."""
    padded = f" {tn} "
    hits = [(cid, [i for i in ids if i and f" {i} " in padded]) for cid, ids in zip(ce_clusters["cid"], ce_clusters["rule_ids"])]
    hits = [(cid, ids) for cid, ids in hits if ids]
    best, best_words = None, 0
    for cid, ids in hits:
        longer = [j for other, oids in hits if other != cid for j in oids]
        kept = [i for i in ids if not any(f" {i} " in f" {j} " and i != j for j in longer)]
        words = max((len(i.split()) for i in kept), default=0)
        if words > best_words:
            best, best_words = cid, words
    return best


def polyfuzz_match(term_list, kw_ce, ce_clusters):
    # target vocabulary = every cluster keyword + every identifier, each labelled with its cluster
    vocab = pd.concat([
        pd.DataFrame({"text": kw_ce["kw"].map(norm), "cid": kw_ce["cid"]}),
        pd.DataFrame([(i, c["cid"]) for _, c in ce_clusters.iterrows() for i in c["ids"]], columns=["text", "cid"]),
    ]).dropna()
    vocab = vocab[vocab["text"] != ""].drop_duplicates("text")
    model = PolyFuzz(TFIDF(n_gram_range=(3, 3), min_similarity=0, clean_string=False))
    model.match(list(term_list), list(vocab["text"]))
    m = model.get_matches().rename(columns={"From": "tn", "To": "match", "Similarity": "score"})
    return m.merge(vocab.rename(columns={"text": "match"}), on="match", how="left")


def embed_match(term_list, kw_ce, ce_clusters, model):
    # multilingual sentence embeddings: nearest cluster keyword/identifier by cosine similarity
    vocab = pd.concat([
        pd.DataFrame({"text": kw_ce["kw"].astype(str), "cid": kw_ce["cid"]}),
        pd.DataFrame([(i, c["cid"]) for _, c in ce_clusters.iterrows() for i in c["ids"]], columns=["text", "cid"]),
    ]).dropna()
    vocab = vocab[vocab["text"] != ""].drop_duplicates("text")
    tv = model.encode(list(term_list), normalize_embeddings=True, batch_size=128)
    vv = model.encode(list(vocab["text"]), normalize_embeddings=True, batch_size=128)
    sims = tv @ vv.T
    best = sims.argmax(axis=1)
    return pd.DataFrame({"tn": list(term_list), "e_match": vocab["text"].to_numpy()[best],
                         "e_score": sims.max(axis=1).round(3), "E_raw": vocab["cid"].to_numpy()[best]})


def content_tokens(tn, ce):
    """Intent-bearing words, translated to a canonical form (biglietti -> ticket, cappella -> chapel)."""
    import ce_config
    return {ce_config.CANON.get(w, w) for w in str(tn).split() if w not in ce_config.generic(ce) and len(w) > 1}


def token_in(tok, toks):
    from rapidfuzz import fuzz
    return tok in toks or (len(tok) >= 4 and any(len(t) >= 4 and fuzz.ratio(tok, t) >= 85 for t in toks))


def guard_ok(term_tn, match_tn, ce, allow_cross_language):
    """Reject a match when the matched keyword has a content word the search lacks ("vatican 3d tour" vs "vatican tours").
    Searches sharing no content word with the keyword are a different language: allowed only for embedding matches."""
    kt, tt = content_tokens(match_tn, ce), content_tokens(term_tn, ce)
    if not kt:
        return True
    if not any(token_in(k, tt) for k in kt):
        return allow_cross_language
    return all(token_in(k, tt) for k in kt)


def head_rule(tn, ce, name_to_cid):
    """Name-only search -> head cluster; name + ticket words only -> tickets cluster."""
    import ce_config
    cfg, toks = ce_config.CE[ce], str(tn).split()
    rest = [w for w in toks if w not in ce_config.STOP | ce_config.CITY | cfg["name"]]
    if not any(w in cfg["name"] for w in toks):
        return None
    if not rest:
        return name_to_cid.get(cfg["head"])
    if all(w in ce_config.TICKET for w in rest):
        return name_to_cid.get(cfg["tickets"])
    if all(w in ce_config.TOUR | ce_config.TICKET for w in rest) and cfg.get("tours"):
        return name_to_cid.get(cfg["tours"])
    return None


def share(df, mask):
    tot = df[["clicks", "spend", "conv"]].sum()
    sub = df.loc[mask, ["clicks", "spend", "conv"]].sum()
    return {k: round(100 * sub[k] / tot[k], 1) if tot[k] else None for k in ["clicks", "spend", "conv"]}


def main():
    global OUT, EMBED_MODEL
    a = runlib.args("mapping", {"--model": {"default": None, "help": "local sentence-transformers model dir for method D"},
                                "--terms": {"default": "search_terms.csv", "help": "terms file in the snapshot (gsc_terms.csv maps organic queries)"}})
    run = runlib.Run("mapping", a.snapshot, {"ces": a.ces, "polyfuzz": "TF-IDF char 3-grams", "polyfuzz_thresholds": THRESHOLDS,
                                             "review_threshold": REVIEW_THRESHOLD, "embed_thresholds": EMBED_THRESHOLDS,
                                             "embed_model": a.model and Path(a.model).name, "terms": a.terms})
    OUT = run.out
    if a.model:
        from sentence_transformers import SentenceTransformer
        EMBED_MODEL = SentenceTransformer(a.model)
    terms, kw, clusters = load(run, a.terms)
    rows = []
    for ce in a.ces.split(","):
        t = terms[terms["ce"] == ce].copy()
        cc = clusters[clusters["ce"] == ce]
        ctype = dict(zip(cc["cid"], cc["t"]))
        cname = dict(zip(cc["cid"], cc["name"]))
        # A search that is itself one of a cluster's keywords goes there before any identifier is tried: the head term's
        # "musei vaticani" would otherwise take "musei vaticani biglietti", a Tickets keyword
        exact = kw[kw["ce"] == ce].assign(tn=lambda d: d["kw"].map(norm)).drop_duplicates("tn").set_index("tn")["cid"]
        t["A"] = t["tn"].map(exact).fillna(t["tn"].map(lambda x: current_rule(x, cc)))
        pf = polyfuzz_match(t["tn"].unique(), kw[kw["ce"] == ce], cc).drop_duplicates("tn")
        t = t.merge(pf[["tn", "match", "score", "cid"]].rename(columns={"cid": "B_raw"}), on="tn", how="left")

        def record(method, col):
            mapped = t[col].notna()
            trans = t[col].map(ctype).eq("TRANSACTIONAL")
            rows.append({"ce": ce, "method": method, "terms_mapped": int(mapped.sum()),
                         **{f"pct_{k}_mapped": v for k, v in share(t, mapped).items()},
                         "pct_clicks_to_transactional": share(t, trans)["clicks"]})

        record("A current rule", "A")
        for th in THRESHOLDS:
            t[f"B{th}"] = t["B_raw"].where(t["score"] >= th)
            t[f"C{th}"] = t["A"].fillna(t[f"B{th}"])
            record(f"B polyfuzz >= {th}", f"B{th}")
            record(f"C hybrid >= {th}", f"C{th}")

        if EMBED_MODEL is not None:
            rest = t.loc[t[f"C{REVIEW_THRESHOLD}"].isna(), "term"].unique()
            em = embed_match(rest, kw[kw["ce"] == ce], cc, EMBED_MODEL).rename(columns={"tn": "term"})
            t = t.merge(em, on="term", how="left")
            for th in EMBED_THRESHOLDS:
                t[f"D{th}"] = t[f"C{REVIEW_THRESHOLD}"].fillna(t["E_raw"].where(t["e_score"] >= th))
                record(f"D hybrid + embeddings >= {th}", f"D{th}")
            # The name follows D0.85, the column the bake-off, capture and ad group grid all score
            t["D_name"] = t["D0.85"].map(cname)

            # E: head-term rule -> identifier rule -> guarded PolyFuzz -> guarded embeddings (all terms embedded)
            import ce_config
            if ce in ce_config.CE:
                name_to_cid = {v: k for k, v in cname.items()}
                t["H"] = t["tn"].map(lambda x: head_rule(x, ce, name_to_cid))
                pf_ok = t.apply(lambda r: pd.notna(r["match"]) and guard_ok(r["tn"], r["match"], ce, False), axis=1)
                em_all = embed_match(t["term"].unique(), kw[kw["ce"] == ce], cc, EMBED_MODEL).rename(
                    columns={"tn": "term", "e_match": "e2_match", "e_score": "e2_score", "E_raw": "E2_raw"})
                t = t.merge(em_all, on="term", how="left")
                em_ok = t.apply(lambda r: pd.notna(r["e2_match"]) and guard_ok(r["tn"], norm(r["e2_match"]), ce, True), axis=1)
                # canonical match: same intent words after translation ("capilla sixtina entradas" = "sistine chapel tickets")
                kwc = kw[(kw["ce"] == ce) & kw["kw"].notna()].sort_values("vol", ascending=False)
                canon_map = {}
                for k, c in zip(kwc["kw"], kwc["cid"]):
                    key = frozenset(content_tokens(norm(k), ce))
                    if key and key not in canon_map:
                        canon_map[key] = c
                t["K"] = t["tn"].map(lambda x: canon_map.get(frozenset(content_tokens(x, ce))))
                for th in EMBED_THRESHOLDS:
                    e = t["H"].fillna(t["A"])
                    e = e.fillna(t["K"])
                    e = e.fillna(t["B_raw"].where((t["score"] >= REVIEW_THRESHOLD) & pf_ok))
                    e = e.fillna(t["E2_raw"].where((t["e2_score"] >= th) & em_ok))
                    t[f"E{th}"] = e
                    record(f"E head rule + guard >= {th}", f"E{th}")
                t["E_name"] = t[f"E{EMBED_THRESHOLDS[1]}"].map(cname)
                t["E_how"] = np.select([t["H"].notna(), t["A"].notna(), t["K"].notna(), t["B_raw"].where((t["score"] >= REVIEW_THRESHOLD) & pf_ok).notna()],
                                       ["head rule", "identifier", "canonical", "polyfuzz"], np.where(t[f"E{EMBED_THRESHOLDS[1]}"].notna(), "embedding", "unmapped"))
            added_e = t[t[f"C{REVIEW_THRESHOLD}"].isna() & t[f"D{EMBED_THRESHOLDS[0]}"].notna()].sort_values("clicks", ascending=False)
            added_e[["term", "clicks", "spend", "conv", "e_match", "e_score", "D_name"]].head(40).to_csv(OUT / f"review_embed_{ce}.csv", index=False)
            final = f"D{EMBED_THRESHOLDS[0]}"
        else:
            final = f"C{REVIEW_THRESHOLD}"

        both = t["A"].notna() & t[f"B{REVIEW_THRESHOLD}"].notna()
        agree = (t.loc[both, "A"] == t.loc[both, f"B{REVIEW_THRESHOLD}"])
        rows.append({"ce": ce, "method": f"A vs B{REVIEW_THRESHOLD} agreement where both map",
                     "pct_clicks_mapped": round(100 * t.loc[both & (t["A"] == t[f"B{REVIEW_THRESHOLD}"]), "clicks"].sum() / t.loc[both, "clicks"].sum(), 1),
                     "terms_mapped": int(agree.sum())})

        for col in ["A", f"B{REVIEW_THRESHOLD}", f"C{REVIEW_THRESHOLD}"]:
            t[col + "_name"] = t[col].map(cname)
        t.to_csv(OUT / f"assignments_{ce}.csv", index=False)
        # review sample: terms the hybrid adds beyond the current rule, highest clicks first
        added = t[t["A"].isna() & t[f"C{REVIEW_THRESHOLD}"].notna()].sort_values("clicks", ascending=False)
        added[["term", "clicks", "spend", "conv", "match", "score", f"C{REVIEW_THRESHOLD}_name"]].head(40).to_csv(OUT / f"review_sample_{ce}.csv", index=False)
        # disagreements: both map, different cluster
        dis = t[both & (t["A"] != t[f"B{REVIEW_THRESHOLD}"])].sort_values("clicks", ascending=False)
        dis[["term", "clicks", "A_name", "match", "score", f"B{REVIEW_THRESHOLD}_name"]].head(25).to_csv(OUT / f"disagreements_{ce}.csv", index=False)
        still = t[t[final].isna()].sort_values("clicks", ascending=False)
        still[["term", "clicks", "spend", "conv", "match", "score"]].head(30).to_csv(OUT / f"unmapped_{ce}.csv", index=False)

    if a.terms != "search_terms.csv":
        # keeps organic-query metrics apart from paid ones in the ledger
        for r in rows:
            r["method"] = f"{Path(a.terms).stem}: {r['method']}"
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "summary.csv", index=False)
    pd.set_option("display.width", 200)
    print(summary.to_string(index=False))
    for r in rows:
        for m in ["pct_clicks_mapped", "pct_spend_mapped", "pct_conv_mapped", "pct_clicks_to_transactional"]:
            if pd.notna(r.get(m)):
                run.record(r["ce"], r["method"], m, r[m])
    run.close()


if __name__ == "__main__":
    sys.exit(main())
