"""Build the mockup's data from the hybrid cluster set (arm_hybrid_eos_v5): hybrid/vatican.json (one row per cluster),
hybrid/drawer.json (each cluster's evidence) and hybrid/impression_share.json.

Usage: python3 export_hybrid.py <clusters_3_0 dir that holds runs/, snapshots/ and .env-clusters/workbook/> [ce]
Any CE other than 189 reads its folder from ces.json, filled by pull_ce.py, map_ce.py and prepare_ce.py (ADDING_A_CE.md),
and its mapping runs from pipeline_local/; inputs Vatican alone has (Satvik's workbook, the cluster_sources run) are
left empty for it.

Paid numbers are Google Ads keyword totals spread over clusters by the searches each keyword served (the analytics
session's capture method), so they reconcile with the account. Vatican's supply comes from the cluster_sources run on
the hybrid set; every CE's Headout entities from its own entities_<CE>.csv (sql/templates/entities.sql). Pages come from
the text mapper (hybrid/pages_189.csv, or pages_mapped_<CE>.csv) and are then re-placed here: Payload tags first, operator
listings to the operator cluster, pages about a place no cluster covers to no cluster, and a name check on the rest.
CE-level totals still come from the v3_rebuilt export (vatican.json).
"""
import json
import re
import unicodedata
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from english import english_checker, english_page

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1])
CE = int(sys.argv[2]) if len(sys.argv) > 2 else 189
COL, NAME = "D0.85", "D_name"
MONTHS = 3
TOP_SEARCHES = 150
WB = ROOT / ".env-clusters" / "workbook"
V4 = ROOT / "snapshots" / "20261028_v4_connected"
HSNAP = ROOT / "snapshots" / "20261029_hybrid_sources"
if CE == 189:
    OUT, RUNS, HOST, DATA = HERE / "hybrid", ROOT / "runs", "www.thevaticantickets.com", "vatican.json"
    # Jev places searches into the validated Vatican set (hybrid_11ce_v2 keywords): the 34 hybrid clusters plus five added ones (Vatican City,
    # St Peter's Basilica, Pope & papal events, Castel Gandolfo, Brand & trust). Its runs cover capture_v2's exact term
    # lists; paid and keyword runs have no confidence cut, organic is cut at 0.5.
    CLUSTERS = ROOT / "snapshots" / "20261103_hybrid_11ce_v2" / "cluster_keywords.csv"
    SNAP = ROOT / "snapshots" / "20261029_capture_v2"
    PAIR_RUN = "20261103-171359_jev_classify_20261030_validation_v1"
    ORGANIC_RUN = "20261103-171421_jev_classify_20261030_validation_v1"
    KEYWORD_RUN = "20261103-171403_jev_classify_20261030_validation_v1"
    SOURCES = ROOT / "runs" / "20261029-153401_cluster_sources_20261029_hybrid_sources" / "outputs"
    PAGES, LANDING = HERE / "hybrid" / "pages_189.csv", HERE / "landing_pages.csv"
else:
    # Every other CE is set up the same way, from ces.json: pull_ce.py, map_ce.py and prepare_ce.py fill its folder.
    CFG = json.loads((HERE / "ces.json").read_text())["ces"][str(CE)]
    OUT, RUNS, HOST, DATA = HERE / CFG["out"], HERE / "pipeline_local" / "runs", CFG["host"], CFG["data"]
    CLUSTERS = HERE / "pipeline_local" / "snapshots" / CFG["snapshot"] / "cluster_keywords.csv"
    SNAP = OUT
    PAIR_RUN, ORGANIC_RUN, KEYWORD_RUN = CFG["runs"]["pairs"], CFG["runs"]["organic"], CFG["runs"]["keywords"]
    SOURCES = None
    PAGES, LANDING = OUT / f"pages_mapped_{CE}.csv", OUT / "landing_pages.csv"
SITE = HOST.replace("www.", "")
# The head-term cluster: named "... Head Term" in Vatican's and Milford's sets, named in ces.json otherwise (Park Güell's is "Park Güell").
HEAD_NAME = None if CE == 189 else CFG.get("head")
MIN_TERM_CLICKS = 20

norm = lambda s: " ".join(str(s).lower().split())
r = lambda v, d=0: None if v is None or pd.isna(v) else round(float(v), d) if d else int(round(float(v)))
# A share of a total that is 0 (a new CE has no revenue, ads or organic clicks yet) is no value, not an error.
div = lambda a, b: a / b if b else None


def assign(run):
    a = pd.read_csv(RUNS / run / "outputs" / f"assignments_{CE}.csv", low_memory=False)
    # Jev runs carry how = jev / jev_failed and the class probability; the rules mapper writes E_how only for CEs with
    # rules in ce_config, so elsewhere the label comes from its D0.85 steps.
    # An empty run (a CE with no paid searches) has the pipeline's columns but no rows to tell the format by.
    if "how" in a and (a.empty or a["how"].astype(str).str.startswith("jev").any()):
        a["E_how"] = np.where(a[COL].notna(), "jev", "unmapped")
    elif "E_how" not in a:
        a["E_how"] = np.select([a["A"].notna(), a["B_raw"].where(a["score"] >= 0.7).notna()], ["identifier", "polyfuzz"],
                               np.where(a[COL].notna(), "embedding", "unmapped"))
    return a.assign(k=a["term"].map(norm))


kw = pd.read_csv(CLUSTERS)
kw = kw[kw["ce"] == CE].assign(k=lambda d: d["kw"].map(norm))
# English only (english.py): keywords, search terms and Perf data. Clusters left with no English keyword drop out.
CE_NAME = "Vatican Museums" if CE == 189 else CFG["name"]
is_en = english_checker([CE_NAME, *kw["name"].dropna().unique()])
# Always a bool Series: on an empty frame map() returns object dtype, and frame[object Series] selects columns, not rows.
en_mask = lambda col: col.map(is_en).astype(bool)
kw = kw[en_mask(kw["kw"])]
names = kw.drop_duplicates("cid").set_index("cid")
# Vatican carries CE totals and change log over from the v3_rebuilt export; Milford's come from its own pulls.
if CE == 189:
    v3 = json.load(open(HERE / "vatican.json"))
else:
    landed = pd.read_csv(OUT / f"orders_by_landing_{CE}.csv")
    v3 = {"ce": {"id": str(CE), "name": CFG["name"], "host": HOST, "window": "30 Jul – 27 Oct 2026",
                 "revenue": round(float(landed["sum_revenue_usd"].sum()), 2), "orders": int(landed["count_orders"].sum()),
                 "banner": "Real: clusters and keywords (11-CE hybrid run), Google Ads search terms, keywords and ad groups (30 Jul – 27 Oct), "
                           "orders, paid revenue traced by click, Mixpanel funnel, Payload pages and Search Console. Not loaded for "
                           f"{CFG['name']}: Satvik's capture numbers, Headout entities. Pages map to clusters by meaning."}, "change_log": []}
old = {c["id"]: c for c in v3.get("clusters", [])}
old_by_name = {c["name"].lower(): c for c in old.values()}

# Trust pages (about us, legal) carry no search intent; the page mapper still matches their focus keyword to something.
hpages = pd.read_csv(PAGES, dtype={"collection_id": str})
hpages = hpages[hpages["page_type"] != "Trust"].assign(path=lambda d: d["path"].fillna(""))
hpages["url"] = HOST + "/" + hpages["path"]
# Organic orders by the page they landed on. A Payload page serves every locale, so /de/sistine-chapel counts for
# sistine-chapel; orders landing on headout.com rather than the microbrand map to no page and stay at CE level.
landed_all = pd.read_csv(V4 / "orders_by_landing.csv" if CE == 189 else OUT / f"orders_by_landing_{CE}.csv").rename(
    columns={"count_orders": "orders", "sum_revenue_usd": "revenue_usd"})
org_land = landed_all[(landed_all["ce"].astype(str) == str(CE)) & (landed_all["channel_grouping"] == "Organic")
                      & landed_all["landing_path"].str.startswith(HOST)].copy()
org_land["key"] = (org_land["landing_path"].str[len(HOST):].str.strip("/")
                   .str.replace(r"^[a-z]{2}(-[a-z]{2})?(/|$)", "", regex=True).str.strip("/"))
org_by_page = org_land.groupby("key")[["orders", "revenue_usd"]].sum()
hpages["org_orders"] = hpages["path"].str.strip("/").map(org_by_page["orders"]).fillna(0)
hpages["org_revenue"] = hpages["path"].str.strip("/").map(org_by_page["revenue_usd"]).fillna(0)
# Supply for Vatican still comes from the cluster_sources run; every CE's Headout entities come from its own pull below.
if SOURCES:
    hsup = pd.read_csv(SOURCES / f"supply_{CE}.csv", dtype={"experience_id": str})
else:
    hsup = pd.DataFrame(columns=["cid", "experience_id", "experience_name", "live", "revenue_usd", "orders"])

# ---------------------------------------------------------------------------------------------------------------------
# Words. One tokenizer for entity links, page placement and supply: folded to ASCII, plural "s" and "-ing" dropped, and
# a few synonyms put on one word so "heli", "flights", "fly" and "plane" meet, and "lodging" meets "accommodation".
# ---------------------------------------------------------------------------------------------------------------------
fold = lambda t: unicodedata.normalize("NFKD", str(t).lower()).encode("ascii", "ignore").decode()
SYN = {**dict.fromkeys(["heli", "helicopter", "chopper"], "helicopter"),
       **dict.fromkeys(["flight", "fly", "flyover", "flying", "plane", "aerial", "airplane"], "flight"),
       **dict.fromkeys(["lodging", "accommodation", "accom", "stay", "hotel", "lodge", "hostel", "motel"], "lodging"),
       **dict.fromkeys(["thing", "sight", "highlight", "attraction"], "sight"),
       **dict.fromkeys(["pope", "papal"], "pope"),
       **dict.fromkeys(["coach", "bus", "transfer"], "coach"),
       **dict.fromkeys(["gett", "get", "address", "direction", "location", "transport", "drive"], "getting"),
       **dict.fromkeys(["timing", "hour", "opening"], "hour"),
       **dict.fromkeys(["price", "cost", "fee"], "price"),
       **dict.fromkeys(["luxury", "premium"], "luxury"),
       **dict.fromkeys(["rule", "regulation", "restriction"], "rule"),
       **dict.fromkeys(["waterfall", "fall"], "fall"),
       "judgement": "judgment", "maps": "map", "kayaking": "kayak", "visiting": "visit", "visitor": "visit"}
STOP = {"the", "and", "for", "from", "with", "what", "when", "where", "how", "who", "why", "near", "inside", "into", "your",
        "best", "official", "head", "term", "general", "info", "information", "guide", "vs", "its", "are", "can"}
# Product formats: say what is sold, not which part of the CE the page or cluster is about.
FORMAT = {"tour", "cruise", "trip", "ticket", "day", "package", "combo", "booking", "book", "entry", "experience", "option"}
NAME_WORDS = {"vatican", "museum", "musei", "vaticani"} if CE == 189 else set(CFG.get("name_words", []))


def word(w):
    w = w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w
    w = w[:-3] if len(w) > 6 and w.endswith("ing") and w not in SYN else w
    return SYN.get(w, w)


NAME_T = {word(w) for w in NAME_WORDS}


def toks(text, drop=frozenset()):
    """Distinctive words of a name, path or keyword: no CE name words, filler or one- and two-letter words."""
    out = set()
    for w in re.split(r"[^a-z0-9]+", fold(re.sub(r"'s\b", "", str(text)))):
        if len(w) > 2 and w not in STOP:
            w = word(w)
            if w not in NAME_T and w not in STOP and w not in drop:
                out.add(w)
    return out


# The CE's child collections and POIs (pull_ce.py: entities.sql). POIs carry no active flag in dim_pois, so they count
# as active; an inactive collection never fills a slot (it stays in the CE's entity list for Set-up to name).
ENTS_FILE = OUT / f"entities_{CE}.csv"
# bq writes an empty file, not a header, when a CE has no child collections or POIs.
ents = pd.read_csv(ENTS_FILE, dtype={"entity_id": str}) if ENTS_FILE.exists() and ENTS_FILE.stat().st_size else pd.DataFrame(
    columns=["entity_type", "entity_id", "name", "alt_names", "is_active", "sub_category"])
for c in ("alt_names", "sub_category", "source"):
    if c not in ents:
        ents[c] = None
ents["is_active"] = ents["is_active"].map(lambda v: str(v).lower() == "true" if pd.notna(v) else True)
ents.loc[ents["entity_type"] == "poi", "is_active"] = True
# Words that name a product format say nothing about which cluster an entity belongs to; "scenic" is a description.
ENT_GENERIC = FORMAT | {"scenic", "nature", "museum", "city", "of"}
ent_words = lambda t: toks(t, ENT_GENERIC)
# Every name an entity goes by: its own, its English-ish display names, and for a collection its sub-category (what it
# sells: "Milford Sound: Scenic Flights" sells Helicopter Tours). Each is a separate word set.
def ent_names(e):
    # A POI's display names are its names in use ("Vatican Gardens"); a collection's are page titles in other languages.
    alts = [e["name"]] + ([a for a in str(e["alt_names"] or "").split(" | ") if a and a.isascii()] if e["entity_type"] == "poi" else [])
    if e["entity_type"] == "collection" and pd.notna(e.get("sub_category")):
        alts.append(e["sub_category"])
    sets = [ent_words(a) for a in alts]
    return [s for s in sets if s]
ents["wsets"] = [ent_names(e) for _, e in ents.iterrows()] if len(ents) else []
ents["words"] = [ent_words(n) for n in ents["name"]] if len(ents) else []
# For the keyword-share test the whole name counts ("scenic flight", not "flight", which "coach cruise fly" also has).
ents["kwords"] = [toks(n, FORMAT) for n in ents["name"]] if len(ents) else []

# Operator collections: a child collection named after a supplier of the CE's products ("southern-discoveries",
# "RealNZ", "Pure milford") is the operator's own listing. Its page and its slot go to the operator cluster, never to
# the cluster about a place or format that the operator's name happens to sit in.
vendors_file = OUT / f"variant_availability_{CE}.csv"
squash = lambda t: re.sub(r"[^a-z0-9]", "", fold(t))
VENDORS = set()
if vendors_file.exists():
    for v in pd.read_csv(vendors_file, usecols=["vendors"])["vendors"].dropna():
        VENDORS |= {squash(x) for x in str(v).split(",") if squash(x)}
# A collection with a sub-category is a category listing even when a supplier shares its name ("Milford Sound: Scenic
# Flights" lists Helicopter Tours); operator listings carry none.
ents["operator"] = [t == "collection" and squash(n) in VENDORS and pd.isna(sc)
                    for t, n, sc in zip(ents["entity_type"], ents["name"], ents["sub_category"])] if len(ents) else []
OPERATOR_RE = re.compile(r"operator|compan|brand|vendor|partner|provider|supplier", re.I)
real_cids = [c for c in names.index if not str(names.at[c, "name"]).startswith("Other")]
HEAD_CIDS = {c for c in real_cids if "head term" in str(names.at[c, "name"]).lower() or norm(names.at[c, "name"]) == norm(HEAD_NAME or "")}
operator_cid = next((c for c in real_cids if OPERATOR_RE.search(str(names.at[c, "name"])) and not re.search(r"brand\s*&\s*trust", str(names.at[c, "name"]), re.I)), None)
cname_t = {c: toks(names.at[c, "name"]) for c in real_cids}


def operator_cluster(e):
    """The cluster that names this operator ("Realnz Milford Sound Cruise" for RealNZ), else a combined operator
    cluster ("Cruise Operators & Companies"), else none. Ties go to the shortest name, then volume."""
    own = [c for c in real_cids if c not in HEAD_CIDS and squash(e.name) in squash(names.at[c, "name"])]
    if own:
        return min(own, key=lambda c: (len(cname_t[c]), -kw.loc[kw["cid"] == c, "vol"].max()))
    return operator_cid


kw_toks = kw.groupby("cid")["kw"].agg(lambda s: [toks(k) for k in s.dropna()])


def named_by(cid):
    """Entities a cluster's name names: every word of one of the entity's names is in the cluster name."""
    if cid in HEAD_CIDS or not len(ents):
        return ents.iloc[0:0]
    m = [any(ws <= cname_t[cid] for ws in e.wsets) and not e.operator for e in ents.itertuples()]
    return ents[m]


# An entity belongs to a cluster when the cluster's name names it; only a cluster that names no entity can take one
# whose words are in at least a quarter of its keywords (one stray keyword must not tie a cluster to a place). So
# "Combo: Vatican Museums + St Peter's Basilica" holds St Peter's, not the Sistine Chapel its keywords also mention.
# Operator collections go to the operator cluster only; inactive collections go nowhere.
links = []
for cid in real_cids:
    if cid in HEAD_CIDS:
        continue
    nb = named_by(cid)
    for e in nb.itertuples():
        links.append({"cid": cid, "entity_type": e.entity_type, "entity_id": e.entity_id, "name": e.name, "is_active": e.is_active, "from": "name"})
    if len(nb) or not len(ents):
        continue
    ks = kw_toks.get(cid, [])
    for e in ents.itertuples():
        if e.operator or not e.kwords or not ks:
            continue
        if sum(e.kwords <= k for k in ks) / len(ks) >= 0.25:
            links.append({"cid": cid, "entity_type": e.entity_type, "entity_id": e.entity_id, "name": e.name, "is_active": e.is_active, "from": "keywords"})
for e in (ents[ents["operator"]].itertuples() if len(ents) else []):
    oc = operator_cluster(e)
    if oc is not None:
        links.append({"cid": oc, "entity_type": e.entity_type, "entity_id": e.entity_id, "name": e.name, "is_active": e.is_active, "from": "operator"})
hent = pd.DataFrame(links, columns=["cid", "entity_type", "entity_id", "name", "is_active", "from"])
hent = hent[~((hent["entity_type"] == "collection") & ~hent["is_active"].astype(bool))]
# Which products each collection's ranking lists; a collection whose products mostly do not name the CE is about another
# place (Doubtful Sound Cruises under Milford Sound).
_pp = pd.read_csv(OUT / f"page_products_{CE}.csv", dtype={"collection_id": str}, usecols=["collection_id", "experience_name"])
# The CE's first name word ("milford", "vatican"): "sound" alone would count Doubtful Sound's products as Milford's.
CE_WORD = fold(re.split(r"[^A-Za-z0-9]+", "Vatican" if CE == 189 else CFG["name"])[0])
_names_ce = lambda n: CE_WORD in set(re.split(r"[^a-z0-9]+", fold(n)))
coll_names_ce = _pp.groupby("collection_id")["experience_name"].agg(lambda s: s.map(_names_ce).mean())
other_place = lambda t, i: t == "collection" and coll_names_ce.get(str(i), 1) < 0.5
CMP_RE = re.compile(r"\b(vs|versus|compare|comparison|compared|oder)\b", re.I)
is_cmp_cluster = lambda c: bool(CMP_RE.search(str(names.at[c, "name"])))
names_ce = lambda c: CE_WORD in set(re.split(r"[^a-z0-9]+", fold(names.at[c, "name"])))
is_combo = lambda c: bool(re.search(r"\+|\bcombo", str(names.at[c, "name"]), re.I))
# A collection about another place belongs only to a cluster about that place alone, to a comparison of the two, or to an
# explicit combo ("Combo: Vatican Museums + St Peter's Basilica"); not to "Milford and Doubtful Sound Cruise", whose name
# also holds the CE.
mixes_ce = lambda c: names_ce(c) and not is_cmp_cluster(c) and not is_combo(c)
# A boolean Series, not a list: an empty list would select no columns from an empty frame (a CE with no entities).
hent = hent[pd.Series([not (other_place(t, i) and mixes_ce(c))
                       for t, i, c in zip(hent["entity_type"], hent["entity_id"], hent["cid"])], index=hent.index, dtype=bool)]
print(f"entities: {len(ents)} under the CE ({int(ents['operator'].sum()) if len(ents) else 0} operators); "
      f"{hent['cid'].nunique()} clusters linked by name or keywords")

# ---------------------------------------------------------------------------------------------------------------------
# Pages -> clusters. Metadata first (Parag, 30 Oct: link by the page's Payload tags, not its text), then a name check on
# the text mapper's pick. A page about a place no cluster covers goes to no cluster and says why, rather than to the
# nearest cluster by meaning.
# ---------------------------------------------------------------------------------------------------------------------
ROOT_IDS = {"poi": {"1"}, "collection": {"189", "3945", str(CE)}}
tag_names = pd.read_csv(HERE / "hybrid" / "page_entities.csv", dtype=str).set_index(["entity_type", "entity_id"])["name"]
if len(ents):
    tag_names = pd.concat([tag_names, ents.astype({"entity_id": str}).set_index(["entity_type", "entity_id"])["name"]])
    tag_names = tag_names[~tag_names.index.duplicated(keep="last")]
ent_by_key = {(e.entity_type, str(e.entity_id)): e for e in ents.itertuples()} if len(ents) else {}
cvol = kw.groupby("cid")["vol"].max()
cid_name = lambda c: names.at[c, "name"] if c in names.index else None
def page_tags(row):
    """The page's Payload place tags that are not the CE itself: its POI, then its collection."""
    out = []
    poi = None if pd.isna(row.get("poi_id")) else str(row["poi_id"]).split(".")[0]
    coll = None if pd.isna(row.get("collection_id")) else str(row["collection_id"]).split(".")[0]
    if poi and poi not in ROOT_IDS["poi"]:
        out.append(("poi", poi))
    if coll and coll not in ROOT_IDS["collection"]:
        out.append(("collection", coll))
    return out


def tag_label(tag):
    name = tag_names.get(tag, "")
    return f"{'POI' if tag[0] == 'poi' else 'Collection'} {tag[1]}" + (f" · {name}" if name else "")


def tag_wsets(tag):
    e = ent_by_key.get(tag)
    return e.wsets if e is not None else [s for s in [ent_words(tag_names.get(tag, ""))] if s]


def own_words(tag):
    e = ent_by_key.get(tag)
    return e.words if e is not None else ent_words(tag_names.get(tag, ""))


def page_words(row):
    focus = str(row.get("focus_keyword_en") or "").split(",")[0]
    return toks(str(row["path"]).replace("-", " ").replace("/", " ") + " " + focus)


# Entities with a cluster of their own (named or linked): a page about any other place has no cluster to go to.
# An entity counts as covered when it, or an entity of the same name, has a cluster (the inactive Underwater Observatory
# collection 5597 is covered by POI 1294's cluster). Inactive collections never mark a page as being about another place.
covered = {(x.entity_type, str(x.entity_id)) for x in hent.itertuples()}
_covered_words = [frozenset(ent_by_key[k].words) for k in covered if k in ent_by_key and ent_by_key[k].words]
covered |= {(e.entity_type, str(e.entity_id)) for e in ents.itertuples() if e.words and frozenset(e.words) in _covered_words} if len(ents) else set()
place_ents = [e for e in ents.itertuples() if e.words and not e.operator and e.is_active] if len(ents) else []
# Comparison clusters ("Milford Sound vs Doubtful Sound") take only comparison pages, and a comparison page goes only to
# a comparison cluster.
is_cmp_page = lambda row: bool(CMP_RE.search(str(row["path"]).replace("-", " ").replace("/", " ") + " "
                                             + str(row.get("focus_keyword_en") or "").split(",")[0]))


def bigrams(text):
    w = [x for x in re.split(r"[^a-z0-9]+", fold(re.sub(r"'s\b", "", re.sub(r"\(.*?\)", " ", str(text))))) if x]
    return {(a, b) for a, b in zip(w, w[1:])}


def phrase_hits(cid, row):
    page = bigrams(str(row["path"]).replace("/", " ") + " " + str(row.get("focus_keyword_en") or "").split(",")[0])
    return len(bigrams(names.at[cid, "name"]) & page)


def fits(cid, pw, cmp=None):
    """A cluster fits a page when the page names every place the cluster's name names, and shares a distinctive word
    with the cluster's name (or the page has none beyond the CE's own name and product formats). A comparison cluster
    fits only a comparison page, and the other way round."""
    if cmp is not None and is_cmp_cluster(cid) != cmp:
        return False
    # A page about another place (it names one) never goes to a cluster that mixes it with the CE.
    if mixes_ce(cid) and any(other_place(e.entity_type, e.entity_id) and any(ws <= pw for ws in e.wsets) for e in place_ents):
        return False
    if any(not any(ws <= pw for ws in e.wsets) for e in named_by(cid).itertuples()):
        return False
    dist = pw - FORMAT
    return not dist or bool(dist & cname_t[cid])


def place(row):
    """(cluster, how, tag label, why-not) for one page."""
    cid, how = row["cid"], row.get("how")
    if row.get("page_type") == "Theme":
        return cid, how, None, None
    tags = page_tags(row)
    label = tag_label(tags[0]) if tags else None
    pw = page_words(row)
    cmp = is_cmp_page(row)
    # 1. Operator listings go to the operator cluster.
    for t in tags:
        e = ent_by_key.get(t)
        if e is not None and e.operator:
            oc = operator_cluster(e)
            return (oc, "operator", tag_label(t), None) if oc is not None else (None, "operator", tag_label(t), "operator page; no operator cluster")
    # 2. Tagged with a place: a cluster linked to it or named for it, the one sharing most words with the page path.
    if tags:
        named = {c for c in real_cids for t in tags for ws in tag_wsets(t) if ws <= cname_t[c]}
        linked = set(hent.loc[[(x.entity_type, str(x.entity_id)) in tags for x in hent.itertuples()], "cid"]) if len(hent) else set()
        cands = {c for c in (named | linked) & set(real_cids) if is_cmp_cluster(c) == cmp}
        coll = next((t[1] for t in tags if t[0] == "collection"), None)
        away = bool(coll) and other_place("collection", coll)
        if away:
            # A collection about another place (Doubtful Sound under Milford) goes only to a cluster about that place
            # alone: not one whose name also holds the CE ("Milford and Doubtful Sound Cruise").
            cands = {c for c in cands if not mixes_ce(c)}
        if cands:
            # Most words shared with the page; then the cluster that is the place itself (its name, formats aside, is
            # one of the place's names: "St Peter's Basilica" over "Combo: ... + St Peter's Basilica"); then the text
            # mapper's pick; then the fewest extra words; then volume.
            wsets = [ws for t in tags for ws in tag_wsets(t)]
            want = set().union(*wsets) if wsets else set()
            best = max(cands, key=lambda c: (len(pw & cname_t[c]), cname_t[c] in wsets, c == cid,
                                             -len(cname_t[c] - FORMAT - want), cvol.get(c, 0)))
            return best, tags[0][0], label, None
        if any(own_words(t) for t in tags):
            if away:
                return None, "tag", label, f"about another place ({tag_names.get(('collection', coll), coll)}); no cluster for it"
            # The text pick stands only when its own keywords mention the tagged place by its own name (a translated
            # name like "Vatikan" would tie the Grottoes to any German ticket search).
            words = set().union(*[own_words(t) for t in tags])
            if pd.notna(cid) and any(words & k for k in kw_toks.get(cid, [])):
                return cid, "text+tag", label, None
            return None, "tag", label, f"no cluster about {tag_names.get(tags[0], tags[0][1])}"
    # 3. A page that names a place with no cluster of its own (another place the CE sells, like the Colosseum).
    for e in place_ents:
        if (e.entity_type, str(e.entity_id)) not in covered and any(ws <= pw for ws in e.wsets) \
                and not any(ws <= cname_t[c] for c in real_cids for ws in e.wsets):
            return None, "place", label, f"about {e.name}; no cluster for it"
    # 3b. A page that names a place with a cluster of its own goes there when the text pick is missing or does not fit:
    # /underwater-observatory names POI 1294, which "Milford Sound Underwater" holds.
    if pd.isna(cid) or (cid in cname_t and not fits(cid, pw, cmp)):
        hits = {}
        for e in place_ents:
            if any(ws <= pw for ws in e.wsets):
                for c in hent.loc[(hent["entity_type"] == e.entity_type) & (hent["entity_id"].astype(str) == str(e.entity_id)), "cid"]:
                    if c in cname_t and c not in HEAD_CIDS and is_cmp_cluster(c) == cmp \
                            and not (other_place(e.entity_type, e.entity_id) and mixes_ce(c)):
                        hits[c] = max(hits.get(c, 0), len(pw & cname_t[c]))
        if hits:
            return max(hits, key=lambda c: (hits[c], cvol.get(c, 0))), "entity", label, None
    # 4. Name check on the text mapper's pick; else the cluster whose name shares most of the page's words. A page the
    # text mapper left out gets the same name search (/kayaking -> "Milford Sound Kayak Tour").
    dist = pw - FORMAT
    if pd.isna(cid):
        scored = [(len(dist & cname_t[c]), c) for c in real_cids if c not in HEAD_CIDS and fits(c, pw, cmp)] if dist else []
        scored = [(sc, c) for sc, c in scored if sc and sc * 2 >= len(dist)]
        if scored:
            top = max(sc for sc, _ in scored)
            return max((c for sc, c in scored if sc == top), key=lambda c: (phrase_hits(c, row), cvol.get(c, 0))), "name", label, None
        return cid, how, label, None
    if not dist and pw:
        # A page that names only the CE and a format ("tours"): the cluster for that format in general, the one whose
        # name holds the format and nothing more specific, over "Queenstown to ... Tours" the text matched.
        plain = [c for c in real_cids if c not in HEAD_CIDS and pw & cname_t[c] and not (cname_t[c] - FORMAT)]
        if plain and cid not in plain:
            return max(plain, key=lambda c: cvol.get(c, 0)), "name", label, None
    if cid not in cname_t or fits(cid, pw, cmp):
        return cid, how, label, None
    scored = [(len(dist & cname_t[c]), c) for c in real_cids if c not in HEAD_CIDS and fits(c, pw, cmp)]
    scored = [(s, c) for s, c in scored if s and s * 2 >= len(dist)]
    if scored:
        top = max(s for s, _ in scored)
        # Ties go to the cluster whose name appears in the page as a phrase ("vatican-city" is "Vatican City (the
        # state)", not "Passes & City Passes"), then to volume.
        best = max((c for s, c in scored if s == top), key=lambda c: (phrase_hits(c, row), cvol.get(c, 0)))
        return best, "name", label, None
    return None, how, label, f"no cluster named for it (text match was {cid_name(cid)})"


placed = hpages.apply(place, axis=1, result_type="expand")
before = hpages["cid"].copy()
# apply() on a CE with no pages returns no columns to unpack.
hpages[["cid", "how", "tag", "why_no_cluster"]] = placed.values if len(hpages) else np.empty((0, 4), dtype=object)
hpages["text_cid"] = before
moved = (hpages["cid"].fillna("") != before.fillna(""))
print(f"pages: {int(hpages['tag'].notna().sum())} tagged; {int(moved.sum())} moved from the text mapping "
      f"({int((moved & hpages['cid'].isna()).sum())} to no cluster)")

# A cluster's entity items: the tags on its own pages first (the slot's first source), then what its name or keywords
# name. Each item says where it came from.
page_items = []
for x in hpages.dropna(subset=["cid"]).itertuples():
    for t in page_tags(x._asdict()):
        e = ent_by_key.get(t)
        page_items.append({"cid": x.cid, "entity_type": t[0], "entity_id": t[1], "name": tag_names.get(t, e.name if e is not None else None),
                           "is_active": True if e is None else bool(e.is_active), "from": "page"})
# Name links to an entity that already serves another cluster's live page come after those that do not: the Scenic
# Flight cluster's page lists 5177, so Helicopter Tours offers 7167 first.
on_pages = {(x["entity_type"], x["entity_id"]): x["cid"] for x in page_items}
hent["rank"] = [int(on_pages.get((t, i), c) != c) for t, i, c in zip(hent["entity_type"], hent["entity_id"], hent["cid"])]
hent = hent.sort_values(["cid", "rank"], kind="stable").drop(columns="rank")
hent = pd.concat([pd.DataFrame(page_items, columns=hent.columns), hent]).drop_duplicates(["cid", "entity_type", "entity_id"])
col = hent[(hent["entity_type"] == "collection") & hent["is_active"].astype(bool)].groupby("cid").size()
poi = hent[hent["entity_type"] == "poi"].groupby("cid").size()
hsrc = pd.DataFrame({"entity_status": ["Child collection" if c in col.index else "POI only" for c in sorted(set(col.index) | set(poi.index))]},
                    index=pd.Index(sorted(set(col.index) | set(poi.index)), name="cid"))


# ---------------------------------------------------------------------------------------------------------------------
# Supply: the CE's experiences matched to each cluster (the Supply column's "n of n matched selling").
#   Experiences: experiences_<CE>.csv (sql/templates/experiences.sql: what the CE owns or its collections list; live =
#   available and not hidden, as cluster_sources.py). Without that pull, the products the CE's pages list stand in, live
#   when an active variant is on sale.
#   A cluster takes, in order: (a) the products its own pages put there on purpose, i.e. a page's pins, or the ranking
#   of a page whose collection is not the CE's own (an operator's or a sub-collection's listing); (b) for a cluster
#   named after an operator (a supplier of the CE's products or an operator collection), that operator's experiences;
#   (c) experiences whose name or variant names hold every word of one part of the cluster's name ("kayak", "glow worm",
#   "overnight"), with the same synonyms and formats set aside as everywhere else. A name with no word beyond the CE
#   and a format matches nothing here (the template's searched products handle it).
# ---------------------------------------------------------------------------------------------------------------------
SP_DROP = FORMAT | {"cheap", "online", "site", "website", "price", "value", "deal", "discount", "near", "top", "list", "new", "way"}
sp_alts = lambda t: [toks(part, SP_DROP) for part in re.split(r"[/&,()]", str(t or ""))]
_vav = pd.read_csv(OUT / f"variant_availability_{CE}.csv", dtype={"experience_id": str, "variant_id": str})
_vord = pd.read_csv(OUT / f"variant_orders_{CE}.csv", dtype={"experience_id": str})
_ppx = pd.read_csv(OUT / f"page_products_{CE}.csv", dtype={"collection_id": str, "experience_id": str})
EXP_FILE = OUT / f"experiences_{CE}.csv"
if EXP_FILE.exists() and EXP_FILE.stat().st_size:
    xp = pd.read_csv(EXP_FILE, dtype={"experience_id": str, "listed_in": str})
    xp = xp[~xp["experience_name"].str.contains(r"\[DUMMY|Test ILF", regex=True, na=False)].copy()
    xp["live"] = xp["live"].astype(str).str.lower().eq("true")
    SUPPLY_FROM = EXP_FILE.name
else:
    _sale = _vav[(_vav["variant_status"] == "Active") & _vav["is_available"].astype(str).str.lower().eq("true")]
    _o = _vord.groupby("experience_id")[["count_orders", "sum_revenue_usd"]].sum()
    xp = _ppx.drop_duplicates("experience_id")[["experience_id", "experience_name"]].copy()
    xp["live"] = xp["experience_id"].isin(set(_sale["experience_id"]))
    xp["orders"] = xp["experience_id"].map(_o["count_orders"]).fillna(0).astype(int)
    xp["revenue_usd"] = xp["experience_id"].map(_o["sum_revenue_usd"]).fillna(0)
    xp["vendors"] = None
    SUPPLY_FROM = "page_products (experiences pull missing)"
_vend = _vav.groupby("experience_id")["vendors"].agg(lambda s: ", ".join(s.dropna()))
xp["vendors"] = [v if isinstance(v, str) and v else _vend.get(e, "") for e, v in zip(xp["experience_id"], xp["vendors"])]
_vnames = _vav.groupby("experience_id")["variant_name"].agg(lambda s: " | ".join(s.dropna().astype(str)))
xp["w"] = [toks(n) for n in xp["experience_name"]]
xp["wv"] = [toks(str(n) + " " + _vnames.get(e, "")) for e, n in zip(xp["experience_id"], xp["experience_name"])]
xp["sq"] = [squash(str(n) + " " + _vnames.get(e, "")) for e, n in zip(xp["experience_id"], xp["experience_name"])]
xp_by_id = xp.drop_duplicates("experience_id").set_index("experience_id")

# (a) Products a page puts there on purpose.
_blocks = pd.read_csv(HERE / "hybrid" / "page_product_blocks.csv", dtype=str)
_blocks = _blocks[_blocks["uid"].str.startswith(HOST)]
_pins = {u: [str(i) for i in json.loads(v)] for u, v in zip(_blocks["uid"], _blocks["common_ranks"]) if isinstance(v, str) and v.startswith("[")}


def page_listed(row):
    key = str(row["path"] or "").strip("/")
    out = list(_pins.get(HOST + ("." + key.replace("/", ".") if key else ""), []))
    coll = None if pd.isna(row.get("collection_id")) else str(row["collection_id"]).split(".")[0]
    if coll and coll not in ROOT_IDS["collection"]:
        out += list(_ppx.loc[_ppx["collection_id"] == coll].sort_values("computed_rank")["experience_id"])
    return out


# (b) Operators: suppliers of the CE's products and the CE's operator collections, by the words of their name once
# legal and trade words are set aside ("Cheeky Kiwi Travel Limited" -> cheeky kiwi).
LEGAL = {"limited", "ltd", "pty", "inc", "llc", "travel", "group", "company", "nz", "iii", "ii"}
_ops = {}
for v in set(", ".join(xp["vendors"].fillna("")).split(", ")) - {""}:
    _ops.setdefault(squash(v), {"name": v, "w": toks(v, LEGAL), "vendors": set(), "colls": set()})["vendors"].add(v)
for e in (ents[ents["operator"]].itertuples() if len(ents) else []):
    _ops.setdefault(squash(e.name), {"name": e.name, "w": toks(e.name, LEGAL), "vendors": set(), "colls": set()})["colls"].add(str(e.entity_id))


def cluster_operator(cid):
    """The operator a cluster is named after: its squashed name holds the operator's, or the operator's words are all in
    its name. "Mitre Peak" is not "Mitre Peak Cruises"; "Mitre Peak Cruises Milford Sound" is."""
    n, nt = squash(names.at[cid, "name"]), toks(names.at[cid, "name"])
    hits = [o for k, o in _ops.items() if (len(k) > 4 and k in n) or (o["w"] and len(o["w"]) > 1 and o["w"] <= nt)]
    return max(hits, key=lambda o: len(squash(o["name"])), default=None)


def operator_experiences(o):
    ids = set(xp.loc[[bool(o["vendors"] & set(str(v).split(", "))) for v in xp["vendors"]], "experience_id"])
    ids |= set(_ppx.loc[_ppx["collection_id"].isin(o["colls"]), "experience_id"])
    ow = toks(o["name"], LEGAL)
    if ow:
        ids |= set(xp.loc[[ow <= w for w in xp["w"]], "experience_id"])
    return ids


sup_rows = []
_page_rows = hpages.dropna(subset=["cid"])
for cid in real_cids:
    found = {}
    if cid not in HEAD_CIDS:
        for _, prow in _page_rows[_page_rows["cid"] == cid].iterrows():
            if prow.get("page_type") == "Theme":
                continue
            for e in page_listed(prow):
                found.setdefault(e, "page")
    op = cluster_operator(cid)
    if op:
        for e in operator_experiences(op):
            found.setdefault(e, "operator")
    if cid not in HEAD_CIDS:
        alts = [a for a in sp_alts(names.at[cid, "name"]) if a]
        alts = [a - (op["w"] if op else set()) for a in alts]
        for a in [a for a in alts if a]:
            # Words also count inside a run-together name ("Glowworm" holds glow and worm).
            for e in xp.loc[[a <= w or all(len(t) > 3 and t in sq for t in a) for w, sq in zip(xp["wv"], xp["sq"])], "experience_id"]:
                found.setdefault(e, "name")
    for e, how_found in found.items():
        if e in xp_by_id.index:
            x = xp_by_id.loc[e]
            sup_rows.append({"cid": cid, "experience_id": e, "experience_name": x["experience_name"], "live": bool(x["live"]),
                             "revenue_usd": float(x["revenue_usd"] or 0), "orders": int(x["orders"] or 0), "how": how_found})
new_sup = pd.DataFrame(sup_rows, columns=["cid", "experience_id", "experience_name", "live", "revenue_usd", "orders", "how"])
# Vatican keeps the 28 Oct cluster_sources supply where it found any and takes the new match only where it found none;
# every other CE uses the new match.
if CE == 189 and len(hsup):
    _old_live = hsup.groupby("cid")["live"].apply(lambda v: v.astype(str).str.lower().eq("true").sum())
    keep_new = new_sup[~new_sup["cid"].isin(set(_old_live[_old_live > 0].index))]
    hsup = pd.concat([hsup.assign(how="cluster_sources"), keep_new], ignore_index=True)
else:
    hsup = new_sup
hsup["live"] = hsup["live"].astype(str).str.lower().eq("true")
print(f"supply: {SUPPLY_FROM}; {hsup['cid'].nunique()} clusters matched, {hsup.loc[hsup['live'], 'cid'].nunique()} with one live "
      f"({', '.join(f'{k} {v}' for k, v in hsup.drop_duplicates(['cid', 'experience_id'])['how'].value_counts().items())})")


def sources(cid):
    """Pages, products and Headout entities for one hybrid cluster, in the shape the mockup reads."""
    pg = hpages[hpages["cid"] == cid].sort_values("revenue", ascending=False)
    sx = hsup[hsup["cid"] == cid].sort_values(["live", "revenue_usd"], ascending=False)
    sr = hsrc.loc[cid] if cid in hsrc.index else pd.Series(dtype=object)
    return {
        "page_revenue": r(pg["revenue"].sum(), 2), "pct_ce_revenue": r(div(pg["revenue"].sum(), v3["ce"]["revenue"]), 4),
        "organic_orders": r(pg["org_orders"].sum()), "organic_revenue": r(pg["org_revenue"].sum(), 2),
        "pages": [{"path": x.url, "type": x.page_sub_type, "collection": None if pd.isna(x.collection_id) else str(x.collection_id).split(".")[0],
                   "noindex": bool(x.any_noindex), "revenue": r(x.revenue, 2), "orders": r(x.orders),
                   "organic_orders": r(x.org_orders), "organic_revenue": r(x.org_revenue, 2),
                   "tag": None if pd.isna(x.tag) else x.tag, "how": None if pd.isna(x.how) else x.how} for x in pg.itertuples()],
        "supply": {"n": int(sx["experience_id"].nunique()), "live": int(sx["live"].sum()), "revenue": r(sx["revenue_usd"].sum(), 2),
                   "orders": int(sx["orders"].sum()),
                   "experiences": [{"name": x.experience_name, "live": bool(x.live), "revenue": r(x.revenue_usd, 2), "orders": int(x.orders)}
                                   for x in sx.itertuples()]},
        "entity": {"status": sr.get("entity_status", "CE collection") if pd.notna(sr.get("entity_status")) else "CE collection",
                   "items": [{"type": x.entity_type, "id": str(x.entity_id), "name": None if pd.isna(x.name) else x.name,
                              "active": bool(x.is_active), "from": x[5]}
                             for x in hent[hent["cid"] == cid].itertuples(index=False)]},
    }

pair_cid = assign(PAIR_RUN).drop_duplicates("k").set_index("k")
pairs = pd.read_csv(SNAP / "keyword_search_terms.csv").assign(k=lambda d: d["term"].map(norm))
pairs["cid"] = pairs["k"].map(pair_cid[COL])
pairs["how"] = pairs["k"].map(pair_cid["E_how"])
pairs["ag"] = pairs["kw_key"].str.split("~").str[0]
totals = pd.read_csv(SNAP / "keyword_totals.csv").assign(k=lambda d: d["keyword"].map(norm), ag=lambda d: d["kw_key"].str.split("~").str[0])
# Vatican's capture snapshot was pulled without conversions. The 30 Oct validation pull is the same query and window
# (identical keyword keys and clicks), so its conversions join on kw_key.
if "conv" not in totals:
    vconv = pd.read_csv(ROOT / "snapshots" / "20261030_validation_v1" / "keyword_totals.csv", dtype={"ce": str})
    totals = totals.merge(vconv.loc[vconv["ce"] == str(CE), ["kw_key", "conv"]], on="kw_key", how="left")
kw_text_cid = assign(KEYWORD_RUN).drop_duplicates("k").set_index("k")[COL]
ads = pd.read_csv(SNAP / "ad_groups.csv").assign(ag=lambda d: d["ad_group_id"].astype(str)).drop_duplicates("ag").set_index("ag")
# Search terms first: a keyword's totals cover every search it served in any language, so each keeps its English part,
# in proportion to its visible searches (searches Google does not report are taken to follow the same mix). A keyword
# with no visible search counts in full if its own text is English. Its English searches then split it over clusters.
METRICS = ["impr", "clicks", "spend", "conv_value"]
pairs["en"] = pairs["term"].map(is_en).astype(bool)
vis = pairs.groupby("kw_key")[METRICS].sum()
en_frac = (pairs[pairs["en"]].groupby("kw_key")[METRICS].sum().reindex(vis.index, fill_value=0) / vis.replace(0, np.nan))
en_frac = en_frac.apply(lambda col: col.fillna(en_frac["clicks"]).fillna(en_frac["impr"]))
kw_en = totals.set_index("kw_key")["keyword"].map(lambda t: 1.0 if is_en(t) else 0.0)
totals_all = totals[["kw_key", "keyword", *METRICS]].copy()
for c, m in [("impr", "impr"), ("eligible", "impr"), ("lost_rank", "impr"), ("impr_with_share", "impr"),
             ("clicks", "clicks"), ("spend", "spend"), ("conv_value", "conv_value"), ("conv", "conv_value")]:
    if c in totals:
        totals[c] = totals[c].fillna(0) * totals["kw_key"].map(en_frac[m]).fillna(totals["kw_key"].map(kw_en)).fillna(1.0).values
ag_en = pairs.assign(**{c: pairs[c] * pairs["en"] for c in ["conv_value"]}).groupby("ag")["conv_value"].sum() / pairs.groupby("ag")["conv_value"].sum().replace(0, np.nan)
EN_SHARE_VALUE = pairs.loc[pairs["en"], "conv_value"].sum() / pairs["conv_value"].sum() if pairs["conv_value"].sum() else 1.0
pairs = pairs[pairs["en"]].drop(columns="en")

# Own ad group, Parag's method: find the live ad groups that bid on the cluster's focus keyword (or a close variant that
# shares its Keyword Planner volume), take the one with the most clicks as the core, then check how much of the
# cluster's keyword volume that ad group also bids on.
# Google matches a keyword to its close variants (the same words in another order, singular or plural, small
# function words), and Keyword Planner reports them as one keyword "in account". vkey() is that comparison.
VK_STOP = {"a", "an", "the", "to", "in", "of", "for", "from", "at", "on", "and", "with", "by"}
singular = lambda w: w[:-3] + "y" if len(w) > 4 and w.endswith("ies") else w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
vkey = lambda s: " ".join(sorted({singular(w) for w in re.findall(r"[a-z0-9]+", str(s).lower()) if w not in VK_STOP}))
KS_FILE = OUT / f"keyword_status_{CE}.csv"
if KS_FILE.exists():
    # The latest daily snapshot of every keyword in the CE's campaigns: live only when keyword, ad group and campaign
    # are all enabled; paused when it exists but one of them is paused (removed ones are not in the account).
    kstat = pd.read_csv(KS_FILE, dtype={"ad_group_id": str}).assign(k=lambda d: d["keyword"].map(norm))
    on = lambda s: s.eq("ENABLED")
    # Close-variant evidence counts a live keyword in any language: an English search Google served through the Dutch
    # keyword is covered. The keywords the tool lists are English only.
    live_any = set(kstat.loc[on(kstat["keyword_status"]) & on(kstat["ad_group_status"]) & on(kstat["campaign_status"]), "k"])
    kstat = kstat[en_mask(kstat["keyword"])]
    is_live = on(kstat["keyword_status"]) & on(kstat["ad_group_status"]) & on(kstat["campaign_status"])
    bids = kstat[is_live]
    held = kstat[~is_live & kstat["ad_group_status"].ne("REMOVED") & kstat["campaign_status"].ne("REMOVED")]
    KW_SNAPSHOT = str(kstat["snapshot_date"].iloc[0]) if len(kstat) else None
    live_ags = set(bids["ad_group_id"])
    ag_meta = pd.concat([kstat.drop_duplicates("ad_group_id").set_index("ad_group_id")[["ad_group_name", "campaign_name"]],
                         ads[["ad_group_name", "campaign_name"]]])
    ag_meta = ag_meta[~ag_meta.index.duplicated()]
else:
    live_ags = set(ads.index[(ads["ad_group_status"] == "ENABLED") & (ads["campaign_status"] == "ENABLED")])
    bids = pd.read_csv(OUT / f"quality_score_{CE}.csv", dtype={"ad_group_id": str})
    bids = bids[bids["ad_group_id"].isin(live_ags) & en_mask(bids["keyword"])].assign(k=lambda d: d["keyword"].map(norm))
    held, KW_SNAPSHOT = bids.iloc[0:0], None
    live_any = set(bids["k"])
    ag_meta = ads[["ad_group_name", "campaign_name"]]
ag_bids = bids.groupby("ad_group_id")["k"].agg(set)
kw_ags = bids.groupby("k")["ad_group_id"].agg(set)
live_by_v = bids.assign(v=bids["k"].map(vkey)).groupby("v")["k"].agg(lambda s: sorted(set(s)))
v_ags = bids.assign(v=bids["k"].map(vkey)).groupby("v")["ad_group_id"].agg(set)
ag_bids_v = bids.assign(v=bids["k"].map(vkey)).groupby("ad_group_id")["v"].agg(set)
held_keys, held_v = set(held["k"]), set(held["k"].map(vkey))
# Google's own evidence of close variants: a cluster keyword seen as a search in the last 30 days, served by a live
# keyword under a close-variant match type (misspellings and same-meaning words, which vkey() cannot see).
STR_FILE = OUT / f"search_terms_recent_{CE}.csv"
served_as = {}
if STR_FILE.exists():
    srv = pd.read_csv(STR_FILE)
    srv = srv[srv["match_type"].isin(["NEAR_EXACT", "NEAR_PHRASE"]) & srv["served_by"].notna()]
    srv = srv.assign(term=srv["term"].map(norm), served_by=srv["served_by"].map(norm))
    srv = srv[en_mask(srv["term"])]
    srv = srv[srv["served_by"].isin(live_any) & (srv["term"] != srv["served_by"])].sort_values("impr", ascending=False)
    served_as = srv.drop_duplicates("term").set_index("term")["served_by"].to_dict()


def bid_state(k):
    """bid (this exact keyword is live), variant (a close variant is live), paused (in the account, not live), none."""
    if k in kw_ags.index:
        return "bid", None
    live_as = live_by_v.get(vkey(k))
    if live_as:
        return "variant", live_as[0]
    if k in served_as:
        return "variant", served_as[k]
    if k in held_keys or vkey(k) in held_v:
        return "paused", None
    return "none", None


# A keyword family: Planner's same-volume family from 1,000 searches, otherwise the keyword with its close variants.
fam_of = lambda v, k: f"v{v:.0f}" if pd.notna(v) and v >= 1000 else f"w{vkey(k)}"
ag_clicks = totals.groupby("ag")["clicks"].sum()


def own_ad_group(cluster_kw, focus):
    """State of the cluster in Google Ads: full (core ad group holds its focus keyword and most of its volume), focus
    (only the focus keyword), or missing (no live ad group bids on the focus keyword)."""
    if focus is None or not len(cluster_kw):
        return {"state": "missing"}
    fam = cluster_kw.assign(f=[fam_of(v, key) for v, key in zip(cluster_kw["vol"].fillna(0), cluster_kw["k"])])
    focus_fam = fam.loc[fam["k"] == norm(focus), "f"]
    focus_keys = set(fam.loc[fam["f"].isin(focus_fam), "k"]) | {norm(focus)}
    holders = set().union(*[kw_ags.get(key, set()) | v_ags.get(vkey(key), set()) for key in focus_keys])
    families = fam.groupby("f").agg(vol=("vol", "first"), keys=("k", lambda ks: set(ks)))
    families["vol"] = families["vol"].fillna(0).clip(lower=1)
    if not holders:
        bid = families["keys"].map(lambda ks: any(bid_state(key)[0] in ("bid", "variant") for key in ks))
        return {"state": "missing", "focus": focus, "held": int(bid.sum()), "of": int(len(families))}
    core = max(holders, key=lambda a: (ag_clicks.get(a, 0), len(ag_bids.get(a, ()))))
    in_core = ag_bids_v.get(core, set())
    held = families["keys"].map(lambda ks: any(vkey(key) in in_core for key in ks))
    share = families.loc[held, "vol"].sum() / families["vol"].sum()
    return {"state": "full" if share >= 0.5 else "focus", "focus": focus, "share": r(share, 3),
            "ag": ag_meta.at[core, "ad_group_name"], "campaign": ag_meta.at[core, "campaign_name"], "clicks": r(ag_clicks.get(core, 0)),
            "held": int(held.sum()), "of": int(len(families)), "groups": len(holders)}

pairs = pairs.join(ads[["ad_group_name", "campaign_name"]], on="ag")
match_types = pd.read_csv(SNAP / "keyword_shares.csv")
match_types = match_types[(match_types["ce"] == CE) & (match_types["impr"] > 0)].assign(k=lambda d: d["keyword"].map(norm)).set_index("k")["match_types"]

# Each keyword's complete totals split over clusters by its served searches: clicks by their clicks, spend by their
# spend, CM1 and conversions by their CM1, impression measures by their impressions. Keywords with no visible search
# follow their text. The search-term pairs carry no conversion count, so conversions ride on the CM1 weight.
by = pairs.dropna(subset=["cid"]).groupby(["kw_key", "cid"])[["impr", "clicks", "spend", "conv_value"]].sum()
w = by / by.groupby(level=0).transform("sum")
for c in ("clicks", "spend", "conv_value"):
    w[c] = w[c].fillna(w["impr"])
w = w.add_prefix("w_").reset_index()
unseen = totals[~totals["kw_key"].isin(w["kw_key"])]
w = pd.concat([w, pd.DataFrame({"kw_key": unseen["kw_key"], "cid": unseen["k"].map(kw_text_cid),
                                **{f"w_{c}": 1.0 for c in ("impr", "clicks", "spend", "conv_value")}})]).dropna(subset=["cid"])
spread = totals.merge(w, on="kw_key")
for c, wc in [("impr", "w_impr"), ("eligible", "w_impr"), ("lost_rank", "w_impr"), ("impr_with_share", "w_impr"),
              ("clicks", "w_clicks"), ("spend", "w_spend"), ("conv_value", "w_conv_value"), ("conv", "w_conv_value")]:
    spread[c] = spread[c].fillna(0) * spread[wc]

# AI Max is flagged per search term x ad group in the search-term report; a pair inherits that flag.
stba = pd.read_csv(SNAP / "search_terms_by_adgroup.csv")
stba = stba[(stba["ce"] == CE) & en_mask(stba["term"])]
stba = stba.assign(k=lambda d: d["term"].map(norm), ag=lambda d: d["ad_group_id"].astype(str))
ai_share = (stba.assign(ai=stba["match_type"].eq("AI_MAX") * stba["clicks"]).groupby(["k", "ag"])[["ai", "clicks"]].sum())
ai_share = (ai_share["ai"] / ai_share["clicks"]).fillna(0)
pairs["ai"] = [ai_share.get((k, g), 0) for k, g in zip(pairs["k"], pairs["ag"])]

# Paid revenue: paid orders traced by gclid to an ad group and targeted keyword (paid_orders_by_click), then over
# clusters by that keyword's click weights; orders with an ad group but no keyword follow the ad group's cluster mix.
po = pd.read_csv(V4 / "paid_orders_by_click.csv" if CE == 189 else OUT / f"paid_orders_by_click_{CE}.csv")
po = po[po["ce"] == CE]
# The traced share is of the English part of paid revenue, so orders with no gclid or no matching click count against
# it. Orders link to a keyword, not a search, so their English part is the English share of Google's conversion value
# (per keyword or ad group below, CE-wide here).
paid_total = po["revenue_usd"].sum() * EN_SHARE_VALUE
po = po[po["match_status"] == "matched"].assign(ag=lambda d: d["ad_group_id"].astype(str).str.replace(r"\.0$", "", regex=True),
                                                                    k=lambda d: d["keyword_text"].map(norm))
key_of = totals.drop_duplicates(["ag", "k"]).set_index(["ag", "k"])["kw_key"]
po["kw_key"] = pd.Series([key_of.get((g, k)) for g, k in zip(po["ag"], po["k"])], index=po.index, dtype=object)
rev_kw = po.dropna(subset=["kw_key"]).merge(w[["kw_key", "cid", "w_clicks"]], on="kw_key")
rev_kw["rev"] = rev_kw["revenue_usd"] * rev_kw["w_clicks"] * rev_kw["kw_key"].map(en_frac["conv_value"]).fillna(1.0)
ag_mix = pairs.dropna(subset=["cid"]).groupby(["ag", "cid"])["clicks"].sum()
ag_mix = (ag_mix / ag_mix.groupby(level=0).transform("sum")).rename("share").reset_index()
rev_ag = po[po["kw_key"].isna()].merge(ag_mix, on="ag")
rev_ag["rev"] = rev_ag["revenue_usd"] * rev_ag["share"] * rev_ag["ag"].map(ag_en).fillna(1.0)
paid_rev = pd.concat([rev_kw[["cid", "rev"]], rev_ag[["cid", "rev"]]]).groupby("cid")["rev"].sum()
traced_share = paid_rev.sum() / paid_total if paid_total else None

# Satvik's capture workbook covers Vatican only.
cap = pd.read_csv(WB / "capture.csv").set_index("Cluster") if CE == 189 else pd.DataFrame().rename_axis("Cluster")
cov = pd.read_csv(WB / "cluster_adgroups.csv").set_index("Cluster") if CE == 189 else pd.DataFrame().rename_axis("Cluster")
org = assign(ORGANIC_RUN)
org = org[en_mask(org["term"]) & org["top_page"].map(english_page).astype(bool)]
org_cid = org.dropna(subset=[COL])

lp = pd.read_csv(LANDING)
lp["host"] = lp["host"].str.replace(r"^www\.", "", regex=True)
lp["top_path"] = lp["top_path"].str.replace("{ignore}", "", regex=False)
lp = lp.groupby(["campaign_name", "ad_group_name", "host", "top_path"], as_index=False)[["clicks", "spend"]].sum()
ag_landing = lp.sort_values("clicks", ascending=False).drop_duplicates(["campaign_name", "ad_group_name"]).set_index(["campaign_name", "ad_group_name"])["top_path"]


def theme_of(name):
    # Vatican ad groups are "<intent> - <match> - <language> - <sub-theme>".
    p = str(name).split(" - ")
    return p[0] + ("" if len(p) < 4 or p[3] == "All" else " · " + p[3])


def ag_label(name):
    p = str(name).split(" - ")
    return f"{theme_of(name)} · {p[2]}" if len(p) > 2 else str(name)


def land_label(path, own):
    bare = re.sub(r"^/[a-z]{2}/", "/", str(path)).rstrip("/")
    if bare in own:
        return "its own page"
    return "home page" if re.fullmatch(r"/([a-z]{2}/)?", str(path)) else "other page"


def page_kind(url):
    path = "/" + str(url).split("/", 3)[3] if str(url).count("/") >= 3 else "/"
    if "/blog/" in path:
        return "Blog"
    return "Home page" if len(path.strip("/")) <= 5 and "-" not in path else "Dedicated page"


def cap_get(name, col, scale=1.0):
    if name not in cap.index or pd.isna(cap.at[name, col]):
        return None
    return float(cap.at[name, col]) * scale


ag_total_clicks = pairs.groupby("ag")["clicks"].sum()
targeted_all = set(match_types.index)
clusters, drawer = [], {}

for cid, meta in names.iterrows():
    name, k = meta["name"], kw[kw["cid"] == cid]
    in_eos = (old.get(cid) or old_by_name.get(name.lower())) is not None
    src = sources(cid)
    p = pairs[pairs["cid"] == cid]
    sp = spread[spread["cid"] == cid]
    o = org_cid[org_cid[COL] == cid]
    clicks, spend, cm1, impr, conv = sp["clicks"].sum(), sp["spend"].sum(), sp["conv_value"].sum(), sp["impr"].sum(), sp["conv"].sum()
    eligible = sp["eligible"].sum()
    top_kw = k.sort_values("vol", ascending=False)

    # Ad groups serving the cluster, from its searches' clicks.
    ag = p.groupby(["ag", "ad_group_name", "campaign_name"]).agg(clicks=("clicks", "sum"), spend=("spend", "sum"), cm1=("conv_value", "sum"),
                                                                 terms=("k", "nunique")).reset_index().sort_values("clicks", ascending=False)
    ag["share"] = ag["clicks"] / ag["ag"].map(ag_total_clicks)
    ded = ag[ag["share"] >= 0.5]
    catch_all = ag.loc[ag["ad_group_name"].str.endswith(" - All"), "spend"].sum() / ag["spend"].sum() if ag["spend"].sum() else None

    own = set()
    for pg in (src or {}).get("pages", []):
        own.add(("/" + pg["path"].split("/", 1)[1]).rstrip("/") if "/" in pg["path"] else "")

    # How each paid click was caught, by theme, and where it landed.
    pc = p.assign(theme=p["ad_group_name"].map(theme_of),
                  how=["AI Max, no keyword" if a >= 0.5 else ("Its own exact keyword" if norm(kt) == t else "A different keyword")
                       for a, kt, t in zip(p["ai"], p["kw_key"].map(totals.drop_duplicates("kw_key").set_index("kw_key")["k"]), p["k"])],
                  land=[land_label(ag_landing.get((cn, an), ""), own) for cn, an in zip(p["campaign_name"], p["ad_group_name"])])
    themes = pc.groupby("theme")["clicks"].sum().sort_values(ascending=False)
    keep = themes.head(4).index
    pc["theme2"] = pc["theme"].where(pc["theme"].isin(keep), "Other themes")
    bars = [{"theme": t, "clicks": r(g["clicks"].sum()),
             "how": {h: r(v) for h, v in g.groupby("how")["clicks"].sum().items()}}
            for t, g in pc.groupby("theme2")]
    bars.sort(key=lambda b: (b["theme"] == "Other themes", -b["clicks"]))
    land_mix = {h: r(v) for h, v in pc.groupby("land")["clicks"].sum().items()}
    how_mix = {h: r(v) for h, v in pc.groupby("how")["clicks"].sum().items()}
    # Which cluster owns the keyword that caught each paid click: Aditya's "is the keyword present" test, read from search
    # terms. A keyword maps to a cluster through the keyword mapping run, so own = caught by one of this cluster's keywords.
    trig_cid = p["kw_key"].map(totals.drop_duplicates("kw_key").set_index("kw_key")["k"]).map(kw_text_cid)
    is_ai = p["ai"].fillna(0) >= 0.5
    is_own = ~is_ai & (trig_cid == cid)
    trig = {"own": r(p.loc[is_own, "clicks"].sum()), "other": r(p.loc[~is_ai & ~is_own, "clicks"].sum()), "ai": r(p.loc[is_ai, "clicks"].sum())}

    pt = pc.groupby("k").agg(term=("term", "first"), clicks=("clicks", "sum"), spend=("spend", "sum"), cm1=("conv_value", "sum"),
                             ai=("ai", "mean"), groups=("ag", "nunique"), how=("how", "first"))
    ot = o.groupby("k").agg(oterm=("term", "first"), oclicks=("clicks", "sum"), oimpr=("impressions", "sum"), pos=("avg_position", "mean"),
                            page=("top_page", "first"), ohow=("E_how", "first"))
    s = pt.join(ot, how="outer")
    s["term"] = s["term"].fillna(s["oterm"])
    s["is_kw"] = s.index.isin(set(k["k"]))
    s["weight"] = s["clicks"].fillna(0) + s["oclicks"].fillna(0)
    s = s.sort_values("weight", ascending=False)
    caught = (pc.assign(kwt=pc["kw_key"].map(totals.drop_duplicates("kw_key").set_index("kw_key")["keyword"]), agl=pc["ad_group_name"].map(ag_label))
              .groupby(["term", "kwt", "agl", "land"]).agg(clicks=("clicks", "sum"), spend=("spend", "sum"), ai=("ai", "mean")).reset_index()
              .sort_values("clicks", ascending=False).head(200))
    pages = o.groupby("top_page")["clicks"].sum().sort_values(ascending=False)
    tg = sp[sp["w_clicks"] >= 0.5].groupby("k").agg(kw=("keyword", "first"), impr=("impr", "sum"), clicks=("clicks", "sum"), spend=("spend", "sum"),
                                                    cm1=("conv_value", "sum"), eligible=("eligible", "sum"), lost=("lost_rank", "sum"),
                                                    iws=("impr_with_share", "sum"), groups=("ag", "nunique")).sort_values("impr", ascending=False)
    eos_vol = k["vol"].fillna(0)
    targeted_eos = k["k"].isin(targeted_all)
    vol_share = (eos_vol[targeted_eos].sum() / eos_vol.sum()) if eos_vol.sum() else (targeted_eos.mean() if len(k) else 0)

    untargeted = pt[~pt.index.isin(targeted_all) & (pt["clicks"] >= MIN_TERM_CLICKS)].sort_values("clicks", ascending=False)
    neg = pairs[pairs["ag"].isin(set(ded["ag"])) & pairs["cid"].notna() & (pairs["cid"] != cid)]
    neg = neg.groupby(["k", "cid"]).agg(term=("term", "first"), clicks=("clicks", "sum"), spend=("spend", "sum")).reset_index().sort_values("clicks", ascending=False)
    neg = neg[neg["clicks"] >= MIN_TERM_CLICKS]
    top_theme = themes.index[0] if len(themes) else None
    camps = p.groupby("campaign_name")["clicks"].sum().sort_values(ascending=False)

    cv = lambda col: None if name not in cov.index or pd.isna(cov.at[name, col]) else cov.at[name, col]
    cl = {
        "id": cid, "name": name, "type": meta["t"], "seeded": not in_eos, "head": name == HEAD_NAME or "Head Term" in name,
        "n_kw": int(len(k)), "vol": r(top_kw["vol"].iloc[0]) if len(top_kw) and pd.notna(top_kw["vol"].iloc[0]) else None,
        "vol_source": "eos", "focus_kw": top_kw["kw"].iloc[0] if len(top_kw) else None,
        "adg": own_ad_group(k, top_kw["kw"].iloc[0] if len(top_kw) else None),
        "impr": r(impr), "clicks": r(clicks), "spend": r(spend, 2), "google_value": r(cm1, 2), "conv": r(conv, 1),
        "paid_revenue": r(paid_rev.get(cid), 2), "n_ad_groups": int(len(ag)),
        "top_ad_group": ag["ad_group_name"].iloc[0] if len(ag) else None,
        "top_ag_purity": r(ag["share"].iloc[0], 3) if len(ag) else None,
        "ai_max_share": r((pc["clicks"] * pc["ai"]).sum() / pc["clicks"].sum(), 3) if pc["clicks"].sum() else None,
        "catch_all": r(catch_all, 3),
        "demand": {"month": cap_get(name, "Demand / month"), "from": cap.at[name, "Demand from"] if name in cap.index else None,
                   "planner": cap_get(name, "Keyword Planner volume / month"), "eligible": cap_get(name, "Paid eligible impressions / month"),
                   "organic_impr": cap_get(name, "Organic impressions / month")},
        "capture": {"paid": cap_get(name, "Paid capture %"), "organic": cap_get(name, "Organic click capture %"),
                    "missed": cap_get(name, "Impressions missed / month"), "stake": cap_get(name, "CM1 at stake / month"),
                    "status": cap.at[name, "Status"] if name in cap.index and pd.notna(cap.at[name, "Status"]) else None},
        "theme": {"coverage": cv("Theme coverage"), "top": cv("Top theme"), "reach": cv("Top theme reach %"), "focus": cv("Top theme focus %"),
                  "mix": cv("Themes (share of cluster clicks)")},
        "page_revenue": (src or {}).get("page_revenue"), "pct_ce_revenue": (src or {}).get("pct_ce_revenue"),
        "pages": (src or {}).get("pages", []),
        "organic_orders": (src or {}).get("organic_orders"), "organic_revenue": (src or {}).get("organic_revenue"),
        "supply": (src or {}).get("supply") or {"n": 0, "live": 0, "revenue": 0, "experiences": []},
        "entity": (src or {}).get("entity") or {"status": "CE collection", "items": []},
        "organic": {"clicks": r(o["clicks"].sum()), "impr": r(o["impressions"].sum()),
                    "position": r((o["avg_position"] * o["impressions"]).sum() / o["impressions"].sum(), 1) if o["impressions"].sum() else None,
                    "queries": int(o["k"].nunique()), "top": []},
        "keywords": [{"kw": x.kw, "vol": r(x.vol)} for x in top_kw.head(8).itertuples()],
        "changes": {"why_added": None if in_eos else "Added to the validated set (seed cluster): no EOS cluster covered it"},
    }
    clusters.append(cl)

    sis = sp["impr_with_share"].sum() / eligible if eligible else None
    drawer[cid] = {
        # live = a live keyword in an enabled ad group of an enabled campaign (own_ad_group's list); targeted keeps the
        # match types it served with. fam groups close variants the way own_ad_group does.
        "keywords": [{"kw": x.kw, "vol": r(x.vol), "clicks": r(s.at[x.k, "clicks"]) if x.k in s.index else None,
                      "oclicks": r(s.at[x.k, "oclicks"]) if x.k in s.index else None, "pos": r(s.at[x.k, "pos"], 1) if x.k in s.index else None,
                      "targeted": match_types.get(x.k), "live": bid_state(x.k)[0] in ("bid", "variant"),
                      "bid": bid_state(x.k)[0], "as": bid_state(x.k)[1], "fam": fam_of(x.vol, x.k)} for x in top_kw.itertuples()],
        "searches": [{"term": x.term, "kw": bool(x.is_kw), "clicks": r(x.clicks), "spend": r(x.spend, 2), "cm1": r(x.cm1, 2),
                      "ai": r((x.ai or 0) * (x.clicks or 0)), "groups": r(x.groups), "oclicks": r(x.oclicks), "impr": r(x.oimpr), "pos": r(x.pos, 1),
                      "page": None if pd.isna(x.page) else str(x.page).replace("https://", ""),
                      "how": None if pd.isna(x.ohow) else x.ohow} for x in s.head(TOP_SEARCHES).itertuples()],
        "search_totals": {"n": int(len(s)), "paid_terms": int(pt.shape[0]), "organic_queries": int(ot.shape[0]),
                          "rest_clicks": r(s["clicks"].iloc[TOP_SEARCHES:].sum()), "rest_oclicks": r(s["oclicks"].iloc[TOP_SEARCHES:].sum())},
        "ad_groups": [{"name": x.ad_group_name, "label": ag_label(x.ad_group_name), "campaign": x.campaign_name, "clicks": r(x.clicks),
                       "spend": r(x.spend, 2), "cm1": r(x.cm1, 2), "terms": int(x.terms), "share": r(x.share, 3),
                       "landing": [ag_landing.get((x.campaign_name, x.ad_group_name), "")] if (x.campaign_name, x.ad_group_name) in ag_landing.index else [],
                       "top_terms": []} for x in ag.head(30).itertuples()],
        "ad_group_count": int(len(ag)),
        "dedicated": {"groups": int(len(ded)), "of": int(len(ag)),
                      "share": r(ded["clicks"].sum() / ag["clicks"].sum(), 3) if ag["clicks"].sum() else None},
        "targeted": {"n": int(len(tg)), "vol_share": r(vol_share, 3), "eos_targeted": int(targeted_eos.sum()),
                     "list": [{"kw": x.kw, "match": match_types.get(i, ""), "impr": r(x.impr), "clicks": r(x.clicks), "spend": r(x.spend, 2),
                               "cm1": r(x.cm1, 2), "sis": r(x.iws / x.eligible, 3) if x.eligible else None,
                               "lost": r(x.lost / x.eligible, 3) if x.eligible else None, "groups": r(x.groups),
                               "eos": i in set(k["k"])} for i, x in tg.head(60).iterrows()]},
        "impression_share": {"sis": r(sis, 3), "lost": r(sp["lost_rank"].sum() / eligible, 3) if eligible else None,
                             "stake": r(cap_get(name, "CM1 at stake / month", MONTHS), 2)},
        "bars": bars, "land_mix": land_mix, "how_mix": how_mix, "trig": trig,
        "caught": [{"term": x.term, "kw": "AI Max, no keyword" if x.ai >= 0.5 else x.kwt, "ag": x.agl, "land": x.land,
                    "clicks": r(x.clicks), "spend": r(x.spend, 2)} for x in caught.itertuples()],
        "ranking_page": {"url": str(pages.index[0]).replace("https://", ""), "kind": page_kind(pages.index[0]),
                         "share": r(pages.iloc[0] / pages.sum(), 3)} if len(pages) and pages.iloc[0] > 0 else None,
        "landing": None,
        "perf": {
            "home_ad_group": None if ded.empty and ag.empty else {"name": (ded if len(ded) else ag).iloc[0]["ad_group_name"],
                                                                  "campaign": (ded if len(ded) else ag).iloc[0]["campaign_name"], "dedicated": bool(len(ded))},
            "theme": top_theme,
            "untargeted": [{"term": x.term, "clicks": r(x.clicks), "spend": r(x.spend, 2), "cm1": r(x.cm1, 2)} for x in untargeted.head(10).itertuples()],
            "untargeted_spend": r(untargeted["spend"].sum(), 2), "untargeted_clicks": r(untargeted["clicks"].sum()),
            "eos_untargeted": [{"kw": x.kw, "vol": r(x.vol)} for x in k[~targeted_eos].sort_values("vol", ascending=False).head(5).itertuples()],
            "campaigns": [{"name": c, "share": r(v / camps.sum(), 3)} for c, v in camps.head(5).items()] if camps.sum() else [],
            "negatives": [{"term": x.term, "clicks": r(x.clicks), "spend": r(x.spend, 2), "belongs": names.at[x.cid, "name"] if x.cid in names.index else "another cluster"}
                          for x in neg.head(8).itertuples()],
            "negatives_spend": r(neg["spend"].sum(), 2),
            "shared_ad_groups": [{"name": x.ad_group_name, "campaign": x.campaign_name, "clicks": r(x.clicks), "share": r(x.share, 3)}
                                 for x in ag[ag["share"] < 0.1].head(5).itertuples()],
        },
        "products": [],
    }
    # Landing mix in the shape the Paid lands on column reads.
    lm = pc.assign(path=[ag_landing.get((cn, an), "") for cn, an in zip(pc["campaign_name"], pc["ad_group_name"])]).groupby("path")["clicks"].sum()
    if lm.sum():
        lm = lm.sort_values(ascending=False)
        drawer[cid]["landing"] = {"hosts": [], "pages": [{"host": SITE, "path": pth or "/", "share": r(v / lm.sum(), 3)} for pth, v in lm.head(6).items()]}

# Search-term view of each cluster (what Perf reads): the share Google shows, conversions for CM1 per order, and the
# language split. The campaign's language is the third part of its name ("Rome - Vatican - German - All - ...").
stba["cid"] = stba["k"].map(pair_cid[COL])
stba["lang"] = stba["campaign_name"].str.split(" - ").str[2]
st_cid = stba.dropna(subset=["cid"]).groupby("cid")[["impr", "clicks", "spend", "conv", "conv_value"]].sum()
lang_cid = stba.dropna(subset=["cid"]).groupby(["cid", "lang"])["clicks"].sum()
st_shown = div(stba["clicks"].sum(), totals["clicks"].sum())

# Ad groups serving a cluster (Paid tab): its search-term clicks by ad group, with the same ad group name in one
# language counted once across country campaigns (Perf edits them as a set). share_of_group = this cluster's part
# of that ad group's clicks, which says whether the group is built for the cluster or the cluster rides a generic one.
group_clicks = stba.groupby(["ad_group_name", "lang"])["clicks"].sum()


def ad_groups_serving(cid, cluster_keys):
    mine = stba[stba["cid"] == cid]
    if not mine["clicks"].sum():
        return None
    g = mine.groupby(["ad_group_name", "lang"]).agg(clicks=("clicks", "sum"), spend=("spend", "sum"), cv=("conv_value", "sum"),
                                                    countries=("campaign_name", "nunique"), ags=("ag", lambda a: set(a))).reset_index()
    g["share_of_cluster"] = g["clicks"] / mine["clicks"].sum()
    g["share_of_group"] = [c / group_clicks[(a, l)] for a, l, c in zip(g["ad_group_name"], g["lang"], g["clicks"])]
    g = g.sort_values("clicks", ascending=False)
    rows = []
    for x in g.head(5).itertuples():
        bid = set().union(*[ag_bids.get(a, set()) for a in x.ags])
        loose = mine[mine["ag"].isin(x.ags) & ~mine["k"].isin(bid)].groupby("term")["clicks"].sum().sort_values(ascending=False)
        rows.append({"name": x.ad_group_name, "lang": x.lang, "countries": int(x.countries), "clicks": r(x.clicks), "spend": r(x.spend, 2),
                     "cv": r(x.cv, 2), "share_of_cluster": r(x.share_of_cluster, 3), "share_of_group": r(x.share_of_group, 3),
                     "keywords": sorted(cluster_keys & bid)[:8], "keywords_n": len(cluster_keys & bid),
                     "loose": [{"term": t, "clicks": r(v)} for t, v in loose.head(4).items()]})
    return {"clicks": r(mine["clicks"].sum()), "groups": int(len(g)), "keys": len(cluster_keys),
            "own_share": r(g.loc[g["share_of_group"] >= 0.5, "clicks"].sum() / mine["clicks"].sum(), 3), "rows": rows}


# Campaign targets. Portfolio-strategy campaigns carry 0 in the export, so they keep the strategy name.
troas = pd.read_csv(OUT / f"campaign_troas_{CE}.csv")
troas = {x.campaign_name: (r(x.target_roas, 2) if x.target_roas else None, None if pd.isna(x.bidding_strategy_name) else x.bidding_strategy_name)
         for x in troas.itertuples()}
camp_cid = stba.dropna(subset=["cid"]).groupby(["cid", "campaign_name"])[["clicks", "spend", "conv_value"]].sum()

# Weekly search terms (13 full weeks), mapped with the same term assignments.
wk = pd.read_csv(OUT / f"search_terms_weekly_{CE}.csv").assign(k=lambda d: d["term"].map(norm))
wk = wk[en_mask(wk["term"])]
wk["cid"] = wk["k"].map(pair_cid[COL])
weeks = sorted(wk["week"].unique())
wk_cid = wk.dropna(subset=["cid"]).groupby(["cid", "week"])[["impr", "clicks", "spend", "conv_value"]].sum()
wk_mapped = div(wk.dropna(subset=["cid"])["clicks"].sum(), wk["clicks"].sum())
# Search terms that cost more than they earned over the 13 weeks, per cluster: the watch list Aditya wants only while a
# new CE's campaigns learn. 30 clicks keeps noise out; the tool applies Perf's own click floor on top.
wk_t = (wk.dropna(subset=["cid"]).groupby(["cid", "k"]).agg(term=("term", "first"), clicks=("clicks", "sum"), spend=("spend", "sum"),
        cv=("conv_value", "sum")).reset_index())
wk_t = wk_t[(wk_t["clicks"] >= 30) & (wk_t["cv"] < wk_t["spend"])].sort_values("spend", ascending=False)
for cid, g in wk_t.groupby("cid"):
    if cid in drawer:
        drawer[cid]["loss13"] = [{"term": x.term, "clicks": int(x.clicks), "spend": r(x.spend, 2), "cv": r(x.cv, 2)} for x in g.head(40).itertuples()]

# Quality Score: keywords with a score (0 = not enough traffic), weighted by the keyword's impressions in the window.
qs = pd.read_csv(OUT / f"quality_score_{CE}.csv")
qs = qs[(qs["quality_score"] > 0) & en_mask(qs["keyword"])].assign(kw_key=lambda d: d["ad_group_id"].astype(str) + "~" + d["criterion_id"].astype(str),
                                        k=lambda d: d["keyword"].map(norm))
qs = qs.merge(totals[["kw_key", "impr"]], on="kw_key", how="left").fillna({"impr": 0})
qs["cid"] = qs["k"].map(kw_text_cid)
qs_kw = qs.groupby("k")[["quality_score", "impr"]].apply(lambda g: (g["quality_score"] * (g["impr"] + 1)).sum() / (g["impr"] + 1).sum())
qs_cid = qs.dropna(subset=["cid"]).groupby("cid")[["quality_score", "impr"]].apply(lambda g: (g["quality_score"] * g["impr"]).sum() / g["impr"].sum() if g["impr"].sum() else None)

# Landing pages: ad-level results joined to each ad's final URL, shared out to clusters by each cluster's part of
# the ad group's search-term clicks. Path keeps the language folder (/de/ is its own page).
def lp_path(u):
    u = re.sub(r"\{[^}]*\}|\?.*$", "", str(u or ""))
    host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
    path = "/" + "/".join(re.sub(r"^https?://[^/]+/?", "", u).strip("/").split("/")) if u else ""
    return host, ("/" if path in ("/", "") else path.rstrip("/") + "/")
lpr = pd.read_csv(OUT / f"landing_page_results_{CE}.csv").assign(ag=lambda d: d["ad_group_id"].astype(str))
lpr[["host", "path"]] = pd.DataFrame([lp_path(u) for u in lpr["landing_url"]], index=lpr.index, columns=["host", "path"])
# Where the cluster's core ad group sends its clicks: the final URL with most clicks across that ad group's ads.
core_lp = lpr.assign(ag_name=lpr["ag"].map(ads["ad_group_name"])).groupby(["ag", "host", "path"])["clicks"].sum().reset_index()
for cl in clusters:
    adg = cl["adg"]
    if not adg.get("ag"):
        continue
    core = next((a for a in live_ags if a in ag_meta.index and ag_meta.at[a, "ad_group_name"] == adg["ag"] and ag_meta.at[a, "campaign_name"] == adg["campaign"]), None)
    rows = core_lp[core_lp["ag"] == core].sort_values("clicks", ascending=False)
    if len(rows) and rows["clicks"].sum():
        adg["landing"] = {"host": rows["host"].iloc[0], "path": rows["path"].iloc[0], "share": r(rows["clicks"].iloc[0] / rows["clicks"].sum(), 3)}
# Google rates landing page experience per keyword; an ad group takes the rating most of its impressions carry.
lpx = qs[qs["landing_page_experience"] != "UNSPECIFIED"].assign(ag=lambda d: d["ad_group_id"].astype(str)) \
    .groupby(["ag", "landing_page_experience"])["impr"].sum().reset_index().sort_values("impr").drop_duplicates("ag", keep="last").set_index("ag")["landing_page_experience"]
ag_cid = pairs.dropna(subset=["cid"]).groupby(["ag", "cid"])["clicks"].sum().reset_index()
ag_cid["w"] = ag_cid["clicks"] / ag_cid["ag"].map(ag_total_clicks)
lp_cid = lpr.merge(ag_cid[["ag", "cid", "w"]], on="ag")
for col in ("clicks", "impr", "spend", "conv", "conv_value"):
    lp_cid[col] = lp_cid[col] * lp_cid["w"]
lp_cid["lpx"] = lp_cid["ag"].map(lpx)
RATING = {"BELOW_AVERAGE": 0, "AVERAGE": 1, "ABOVE_AVERAGE": 2}
# Paid search sessions by entry page (Mixpanel): page-level, all clusters together; the funnel has no ad group.
# A new site can have no Mixpanel sessions yet; bq then writes an empty file, read here as no funnel rows.
try:
    fun = pd.read_csv(OUT / f"landing_page_funnel_{CE}.csv")
except pd.errors.EmptyDataError:
    fun = pd.DataFrame(columns=["entry_page", "sessions", "select_sessions", "checkout_sessions", "order_sessions"])
fun["path"] = ["/" if p in ("", "/") else p.rstrip("/") + "/" for p in fun["entry_page"].str.replace(r"^[^/]+", "", regex=True)]
fun = fun.groupby("path")[["sessions", "select_sessions", "checkout_sessions", "order_sessions"]].sum()
# Products: every matched experience with its TGID, why it is not live, variants and price.
var = pd.read_csv(OUT / f"experience_variants_{CE}.csv", dtype={"experience_id": str}).set_index("experience_id")
vav = pd.read_csv(OUT / f"variant_availability_{CE}.csv", dtype={"experience_id": str, "variant_id": str, "tour_ids": str})
VSTATUS = {"Active": 0, "Under Curation": 1, "Disabled": 2, "Deleted": 3}
vord = pd.read_csv(OUT / f"variant_orders_{CE}.csv", dtype={"experience_id": str, "variant_id": str}).set_index("variant_id")
pfun = pd.read_csv(OUT / f"product_funnel_{CE}.csv", dtype={"experience_id": str}).set_index("experience_id")

# Products for a cluster are the ones its landing page shows (Parag, 30 Oct): the core ad group's landing page, else the
# cluster's own page; that page's collection ranking in Rome. Payload's sub_category_id is not a listing filter (most
# info pages carry 1002 whatever their topic), so the ranking is not narrowed by it.
pp = pd.read_csv(OUT / f"page_products_{CE}.csv", dtype={"collection_id": str, "experience_id": str, "primary_sub_category_id": str})
pp["computed_rank"] = pd.to_numeric(pp["computed_rank"])
page_ids = hpages.assign(key=hpages["path"].fillna("").str.strip("/"))
page_ids = page_ids.drop_duplicates("key").set_index("key")
ent_id = lambda v: None if pd.isna(v) else str(v).split(".")[0]


def page_key(path):
    key = str(path or "").replace(HOST, "").strip("/")
    return "" if re.fullmatch(r"[a-z]{2}", key) else key


GENERIC = {"the", "and", "tickets", "vatican", "museums", "museum", "milford", "sound", "tours", "tour", "cruises", "cruise"}
words = lambda t: {w for w in re.split(r"[^a-z0-9]+", re.sub(r"\(.*?\)", " ", str(t).lower())) if len(w) > 2 and w not in GENERIC}


def own_page(cl):
    """The cluster's main page, as the table's Page column picks it: the most words shared with its name and focus
    keyword, then the most revenue."""
    want = words(cl["name"]) | words(cl["focus_kw"])
    return max(cl["pages"], key=lambda pg: (len(words(page_key(pg["path"]).replace("-", " ")) & want), pg["revenue"] or 0))


def page_products(cl):
    """The products the cluster's landing page shows (the core ad group's landing page, else its own page), in the
    page's order after its rules: the same list as the page pop-up."""
    land = cl["adg"].get("landing")
    key = page_key(land["path"]) if land else page_key(own_page(cl)["path"]) if cl["pages"] else None
    if key is None or key not in page_ids.index:
        return None, []
    x = shows["/" + key if key else "/"]
    return {"page": x["page"], "collection": x["collection"], "n": len(x["items"]), "ranked": x["ranked"]}, x["items"]


def funnel_rate(experience_id, num, den):
    if experience_id not in pfun.index or not pfun.at[experience_id, den]:
        return None
    return r(pfun.at[experience_id, num] / pfun.at[experience_id, den], 3)



def variants_of(eid):
    g = vav[vav["experience_id"] == eid].assign(o=lambda d: d["variant_status"].map(VSTATUS).fillna(9)).sort_values(["o", "is_available"], ascending=[True, False])
    return [{"id": x.variant_id, "name": None if pd.isna(x.variant_name) else x.variant_name, "status": x.variant_status, "live": bool(x.is_available),
             "orders": int(vord.at[x.variant_id, "count_orders"]) if x.variant_id in vord.index else 0,
             "revenue": r(vord.at[x.variant_id, "sum_revenue_usd"], 2) if x.variant_id in vord.index else 0,
             "paid_orders": int(vord.at[x.variant_id, "count_paid_orders"]) if x.variant_id in vord.index else 0,
             "next": None if pd.isna(x.next_available_date) else str(x.next_available_date),
             "price": None if pd.isna(x.listing_final_price) else r(float(x.listing_final_price), 2),
             "rating": None if pd.isna(x.average_rating) else r(x.average_rating, 1), "ratings": None if pd.isna(x.count_ratings) else int(x.count_ratings),
             "tours": [] if pd.isna(x.tour_ids) else str(x.tour_ids).split(), "vendors": None if pd.isna(x.vendors) else x.vendors,
             "open7": bool(x.is_available_7d) if pd.notna(x.is_available_7d) else False, "open30": bool(x.is_available_30d) if pd.notna(x.is_available_30d) else False}
            for x in g.itertuples()]


# What each page shows (the page pop-up): its collection's published ranking (already after Ranking Workbench pins),
# then the page's Payload block rules in the order the site applies them: exclusions, sub-category filter, page pins
# (commonRanks) on top, products not on sale dropped, cut at the block's display limit (no limit set = 10).
# ranking-mappings/00-mapping-model.md has the rules; grid blocks that name their own entity are not modelled.
blocks = pd.read_csv(HERE / "hybrid" / "page_product_blocks.csv", dtype={"filter_sub_category_id": str, "filter_category_id": str})
blocks = blocks[blocks["uid"].str.startswith(HOST)].sort_values("block_position")
pins_named = pd.read_csv(HERE / "hybrid" / "page_pinned_products.csv", dtype={"experience_id": str}).set_index("experience_id")
tool_pins = pd.read_csv(HERE / "hybrid" / "collection_overrides.csv", dtype={"collection_id": str, "experience_id": str})
coll_name = tag_names.xs("collection", level=0) if "collection" in tag_names.index.get_level_values(0) else pd.Series(dtype=str)
ids_of = lambda v: [str(i) for i in json.loads(v)] if isinstance(v, str) and v.startswith("[") else []
subcats_of = lambda v: {str(x.get("sub_category_id")) for x in json.loads(v)} if isinstance(v, str) and v.startswith("[") else set()


def on_sale(eid):
    vl = variants_of(eid)
    return any(v["status"] == "Active" and v["live"] for v in vl) if vl else None


def page_shows(key, row):
    uid = HOST + ("." + key.replace("/", ".") if key else "")
    coll = ent_id(row["collection_id"])
    b = blocks[blocks["uid"] == uid]
    blk = b.iloc[0] if len(b) else None
    limit = int(blk["experience_limit"]) if blk is not None and pd.notna(blk["experience_limit"]) else 10
    sub = None if blk is None or pd.isna(blk["filter_sub_category_id"]) else str(blk["filter_sub_category_id"]).split(".")[0]
    pins = ids_of(blk["common_ranks"]) if blk is not None else []
    excl = set(ids_of(blk["common_exclusions"])) if blk is not None else set()
    ranked = pp[pp["collection_id"] == coll].sort_values("computed_rank")
    items, dropped = [], 0
    for x in ranked.itertuples():
        if x.experience_id in excl or x.experience_id in pins:
            continue
        if sub and sub not in subcats_of(x.mapped_sub_categories) and str(getattr(x, "primary_sub_category_id", "")).split(".")[0] != sub:
            continue
        items.append({"tgid": x.experience_id, "name": x.experience_name, "source": x.ranking_source, "rank": int(x.computed_rank)})
    for i, t in enumerate(pins):
        known = pp[pp["experience_id"] == t]
        name = known["experience_name"].iloc[0] if len(known) else (pins_named.at[t, "experience_name"] if t in pins_named.index else None)
        items.insert(i, {"tgid": t, "name": name, "source": "Page pin", "rank": None})
    shown = []
    for it in items:
        live = on_sale(it["tgid"])
        if live is False:
            dropped += 1
            continue
        tot = vord[vord["experience_id"] == it["tgid"]]
        orders = int(tot["count_orders"].sum()) if len(tot) else (int(pins_named.at[it["tgid"], "count_orders"]) if it["tgid"] in pins_named.index else 0)
        revenue = r(tot["sum_revenue_usd"].sum(), 2) if len(tot) else (r(pins_named.at[it["tgid"], "sum_revenue_usd"], 2) if it["tgid"] in pins_named.index else 0)
        shown.append({**it, "orders": orders, "revenue": revenue})
        if len(shown) == limit:
            break
    tp = tool_pins[tool_pins["collection_id"] == coll]
    return {"page": "/" + key if key else "/", "collection": coll, "collection_name": coll_name.get(coll),
            "tag": None if pd.isna(row.get("tag")) else row.get("tag"), "has_block": blk is not None,
            "block": None if blk is None else {"type": blk["variant_type"], "limit": limit, "sub_category": sub, "pins": pins, "exclusions": sorted(excl)},
            "ranked": int(len(ranked)), "dropped": dropped, "items": shown,
            "tool_pins": [{"tgid": t.experience_id, "position": int(t.position), "expiry": t.expiry, "reason": None if pd.isna(t.reason) else t.reason}
                          for t in tp.itertuples()]}


# Products a cluster's searches ask for, matched by name across every product any page of the CE lists. A cluster name
# is read as alternatives split at "/", "&", "," and brackets ("Helicopter Tours & Flights" = helicopter, or flights;
# "Small Boat / Boutique / Luxury / Private" = any of them; "+" joins, so a combo needs both sides). A product matches an
# alternative when it has all its words, after the CE's name, filler and product formats are set aside and synonyms meet
# (heli = helicopter, flights = fly = flyover = plane, coach = bus = transfer). The focus keyword is tried when the name
# finds nothing. A cluster whose name and focus keyword hold nothing beyond the CE's name and a format ("Cruise Tickets &
# Booking", "Deals & Discounts", "Milford Sound Tours / Day Trips (General)") asks for the CE's product itself: its supply is what the CE's
# own collection sells.
catalog = pp.drop_duplicates("experience_id")[["experience_id", "experience_name"]].assign(w=lambda d: d["experience_name"].map(toks))
_exp_orders = vord.groupby("experience_id")["count_orders"].sum()
ce_sold = (pp[pp["collection_id"] == str(CE)].assign(o=lambda d: d["experience_id"].map(_exp_orders).fillna(0))
           .sort_values("o", ascending=False)["experience_id"].drop_duplicates())


def searched_products(cl):
    hit, want = catalog.iloc[0:0], set()
    # Only the name decides "the CE's product itself": a focus keyword can be a misspelling ("millford sound tour").
    tried = any(sp_alts(cl["name"]))
    for text in (cl["name"], cl["focus_kw"]):
        alts = [a for a in sp_alts(text) if a]
        for a in alts:
            m = catalog[catalog["w"].map(lambda w: a <= w)]
            if len(m):
                hit, want = pd.concat([hit, m]).drop_duplicates("experience_id"), want | a
        if len(hit):
            break
    if not tried:
        hit = catalog[catalog["experience_id"].isin(set(ce_sold.head(8)))]
    if not len(hit):
        return []
    out = []
    for x in hit.itertuples():
        vl = variants_of(x.experience_id)
        sale = [v for v in vl if v["status"] == "Active" and v["live"]]
        out.append({"tgid": x.experience_id, "name": x.experience_name, "words": sorted(want),
                    "orders": sum(v["orders"] for v in vl), "revenue": r(sum(v["revenue"] for v in vl), 2),
                    "paid_orders": sum(v["paid_orders"] for v in vl), "on_sale": bool(sale),
                    "price": min((v["price"] for v in sale if v["price"] is not None), default=None),
                    "next": min((v["next"] for v in sale if v["next"]), default=None),
                    "shown": [{"page": pg, "pos": i + 1} for pg, sh in shows.items() for i, it in enumerate(sh["items"]) if it["tgid"] == x.experience_id][:4]})
    return sorted(out, key=lambda d: -d["orders"])[:8]


# The CE's home is its Payload "Theme" page: the bare host on most sites, /home on Park Güell's.
_pg_all = pd.read_csv(HERE / "hybrid" / "pages_189.csv" if CE == 189 else OUT / f"pages_{CE}.csv", usecols=["uid", "page_type"])
_theme = _pg_all.loc[_pg_all["page_type"] == "Theme", "uid"]
HOME_PATH = "/" + "/".join(_theme.iloc[0].split(".")[len(HOST.split(".")):]) if len(_theme) else "/"


def page_funnel(path):
    key = "/" + page_key(path) + "/" if page_key(path) else "/"
    if key not in fun.index or not fun.at[key, "sessions"]:
        return None
    f = fun.loc[key]
    return {"sessions": int(f["sessions"]), "select": r(f["select_sessions"] / f["sessions"], 3), "order": r(f["order_sessions"] / f["sessions"], 3)}


shows = {}
for _, prow in page_ids.iterrows():
    shows["/" + prow.name if prow.name else "/"] = page_shows(prow.name, prow)

for cl in clusters:
    cid = cl["id"]
    st = st_cid.loc[cid] if cid in st_cid.index else None
    cl["st"] = None if st is None else {"impr": r(st["impr"]), "clicks": r(st["clicks"]), "spend": r(st["spend"], 2), "conv": r(st["conv"], 1),
                                       "cv": r(st["conv_value"], 2), "shown": r(st["clicks"] / cl["clicks"], 3) if cl["clicks"] else None}
    cl["qs"] = r(qs_cid.get(cid), 1) if cid in qs_cid.index and pd.notna(qs_cid.get(cid)) else None
    cl["weekly"] = [{"w": w, **({k2: r(v, 2 if k2 in ("spend", "conv_value") else 0) for k2, v in wk_cid.loc[(cid, w)].items()} if (cid, w) in wk_cid.index else {})}
                    for w in weeks]
    dr = drawer[cid]
    dr["ag_serving"] = ad_groups_serving(cid, set(kw.loc[kw["cid"] == cid, "k"]))
    dr["langs"] = [{"lang": l, "clicks": r(v)} for l, v in lang_cid.loc[cid].sort_values(ascending=False).items()] if cid in lang_cid.index.get_level_values(0) else []
    dr["campaigns"] = [{"name": n, "clicks": r(v["clicks"]), "spend": r(v["spend"], 2), "cv": r(v["conv_value"], 2),
                        "troas": troas.get(n, (None, None))[0], "portfolio": troas.get(n, (None, None))[1]}
                       for n, v in camp_cid.loc[cid].sort_values("clicks", ascending=False).head(12).iterrows()] if cid in camp_cid.index.get_level_values(0) else []
    g = lp_cid[lp_cid["cid"] == cid]
    if len(g):
        tot = g["clicks"].sum() or 1
        rows = []
        for (host, path), x in g.groupby(["host", "path"]):
            rated = x.dropna(subset=["lpx"])
            score = (rated["lpx"].map(RATING) * rated["clicks"]).sum() / rated["clicks"].sum() if rated["clicks"].sum() else None
            rows.append({"host": host, "path": path, "share": r(x["clicks"].sum() / tot, 3), "clicks": r(x["clicks"].sum()),
                         "spend": r(x["spend"].sum(), 2), "conv": r(x["conv"].sum(), 1), "cv": r(x["conv_value"].sum(), 2),
                         "lpx": None if score is None else ["Below average", "Average", "Above average"][int(round(score))]})
        for row in rows:
            f = fun.loc[row["path"]] if row["host"] == SITE and row["path"] in fun.index else None
            row["sessions"] = None if f is None else int(f["sessions"])
            row["select"] = None if f is None else r(f["select_sessions"] / f["sessions"], 3)
        dr["lp"] = sorted(rows, key=lambda d: -d["clicks"])[:10]
    dr["searched_products"] = searched_products(cl)
    for pg in cl["pages"]:
        pg["funnel"] = page_funnel(pg["path"])
    on_page, shown = page_products(cl)
    dr["products_page"] = on_page
    dr["products"] = []
    for pos, it in enumerate(shown, start=1):
        eid = it["tgid"]
        x = pp[pp["experience_id"] == eid].head(1)
        vl = variants_of(eid)
        live = any(v["status"] == "Active" and v["live"] for v in vl)
        dr["products"].append({
            "tgid": eid, "name": it["name"], "rank": pos, "source": it["source"], "live": live, "why": None if live else "unavailable",
            "orders": it["orders"],
            "revenue": it["revenue"],
            "paid_orders": int(vord.loc[vord["experience_id"] == eid, "count_paid_orders"].sum()),
            "selects": int(pfun.at[eid, "count_select_users"]) if eid in pfun.index else None,
            "s2c": funnel_rate(eid, "count_checkout_users", "count_select_users"),
            "c2o": funnel_rate(eid, "count_order_users", "count_checkout_users"),
            "variants": int(var.at[eid, "variants"]) if eid in var.index else None,
            "live_variants": int(var.at[eid, "live_variants"]) if eid in var.index else None,
            "from_price": r(var.at[eid, "from_price"], 2) if eid in var.index and pd.notna(var.at[eid, "from_price"]) else None,
            "sub_category": x["primary_sub_category_name"].iloc[0] if len(x) and pd.notna(x["primary_sub_category_name"].iloc[0]) else (pins_named.at[eid, "primary_sub_category_name"] if eid in pins_named.index and pd.notna(pins_named.at[eid, "primary_sub_category_name"]) else None),
            "vlist": vl})
    for kw_row in dr["keywords"]:
        v = qs_kw.get(norm(kw_row["kw"]))
        kw_row["qs"] = r(v, 1) if v is not None and pd.notna(v) else None

unc = pd.read_csv(WB / "uncaptured.csv").sort_values("Paid impressions / month", ascending=False) if CE == 189 else pd.DataFrame()
if len(unc):
    unc = unc[en_mask(unc["Search-term cluster"])].assign(
        **{"Top searches": lambda d: d["Top searches"].fillna("").map(lambda v: " | ".join(t for t in v.split(" | ") if is_en(t)))})
total_paid_clicks = pairs["clicks"].sum()
mapped_paid_clicks = pairs.loc[pairs["cid"].notna(), "clicks"].sum()
ce = dict(v3["ce"])
# The CE's paid totals as Google Ads reports them by campaign (search network), which includes clicks Google ties to
# no keyword; the clusters split the keyword-level totals, so the gap between the two is shown, not hidden.
CT_FILE = OUT / f"campaign_totals_{CE}.csv"
if CT_FILE.exists():
    ct = pd.read_csv(CT_FILE)
    ct = ct[ct["network"] == "SEARCH"]
    all_paid = {"clicks": r(ct["clicks"].sum()), "spend": r(ct["spend"].sum(), 2), "conv_value": r(ct["conv_value"].sum(), 2)}
else:
    all_paid = None
# The header is the English searches' share of every keyword's totals, across all the CE's campaigns; the CE's whole
# Google Ads total (every language, and clicks tied to no keyword) is kept beside it.
paid_ce = {"clicks": r(totals["clicks"].sum()), "spend": r(totals["spend"].sum(), 2), "conv_value": r(totals["conv_value"].sum(), 2),
           "from": "searches", "all": all_paid, "campaigns": int(pairs.loc[pairs["clicks"] > 0, "campaign_name"].nunique())}
ce.update({"search_terms_shown": r(st_shown, 3), "weeks": [str(w) for w in weeks], "weekly_mapped": r(wk_mapped, 3), "paid_clicks_mapped": r(div(mapped_paid_clicks, total_paid_clicks), 3), "organic_clicks_mapped": r(div(org_cid["clicks"].sum(), org["clicks"].sum()), 3),
           "home": HOME_PATH,
           # The CE's own Google Ads totals and live keywords, account-wide: the header reads these, not a sum over clusters
           # (clusters share searches), and a search that is already a live keyword anywhere is never suggested as one to add.
           "paid": paid_ce, "scope": "English",
           # A placeholder CE ("18 - Key West") is keyed by a stand-in number; its real id is what people know it by.
           "label": None if CE == 189 else CFG.get("eos_id"),
           "paid_keyword": {"clicks": r(totals["clicks"].sum()), "spend": r(totals["spend"].sum(), 2), "conv_value": r(totals["conv_value"].sum(), 2)},
           "kw_snapshot": KW_SNAPSHOT,
           "live_keywords": sorted(kw_ags.index), "home_funnel": page_funnel(HOME_PATH), "paid_revenue_traced": r(traced_share, 3), "clusters_from": "hybrid_eos_v5" if CE == 189 else "hybrid_11ce",
           # Every child collection and POI under the CE, so Set-up can name the entity a live page lists.
           "entities": [{"type": x.entity_type, "id": str(x.entity_id), "name": x.name, "active": bool(x.is_active),
                         **({"operator": True} if x.operator else {})} for x in ents.itertuples()]})
if len(ents):
    ce["banner"] = ce.get("banner", "").replace(", Headout entities.", ".")
data = {"ce": ce, "clusters": clusters, "page_shows": shows, "pages_no_cluster": [{"path": x.url, "type": x.page_sub_type, "focus": x.text, "revenue": r(x.revenue, 2),
                                                                                    "why": None if pd.isna(x.why_no_cluster) else x.why_no_cluster,
                                                                                    "tag": None if pd.isna(x.tag) else x.tag}
                             for x in hpages[hpages["cid"].isna()].sort_values("revenue", ascending=False).itertuples()],
        "uncaptured": [{"name": x._3, "intent": x.Intent, "searches": x.Searches, "paid_impr": r(x._6), "organic_impr": r(x._7),
                        "organic_clicks": r(x._8), "top": x._9} for x in unc.head(30).itertuples()],
        "unmapped_terms": [], "unmapped_organic": [], "change_log": v3.get("change_log", []),
        "sources": {"clusters": CLUSTERS.parent.name, "paid": f"{SNAP.name} keyword totals, spread by served searches",
                    "pairs": PAIR_RUN, "organic": ORGANIC_RUN, "pages_products_entities": f"supply: {SOURCES.parent.name if SOURCES else 'none'}; pages: {PAGES.name}; entities: {ENTS_FILE.name}"}}
OUT.mkdir(exist_ok=True)
(OUT / DATA).write_text(json.dumps(data, separators=(",", ":")))
# The working behind every paid number, for audit_paid.py: each keyword's totals as split over clusters, and each
# search term (with the keyword Google says served it) and the cluster it was placed in.
spread[["kw_key", "cid", "impr", "clicks", "spend", "conv_value", "w_clicks"]].to_csv(OUT / f"audit_spread_{CE}.csv", index=False)
pairs[["kw_key", "ag", "term", "impr", "clicks", "spend", "conv_value", "cid", "how"]].to_csv(OUT / f"audit_terms_{CE}.csv", index=False)
totals_all.merge(totals[["kw_key", *METRICS]], on="kw_key", suffixes=("_all", "_en")).to_csv(OUT / f"audit_keywords_{CE}.csv", index=False)
(OUT / "drawer.json").write_text(json.dumps({"clusters": drawer}, separators=(",", ":")))
(OUT / "impression_share.json").write_text(json.dumps({"window": "30 Jul - 27 Oct", "hidden_spend": 0, "total_spend": r(spread["spend"].sum(), 2),
                                                        "clusters": {c["id"]: {"catch_all": c["catch_all"]} for c in clusters}}))
print(f"{len(clusters)} clusters; paid clicks {r(spread['clicks'].sum())}, spend {r(spread['spend'].sum())}, CM1 {r(spread['conv_value'].sum())}; "
      f"paid revenue traced {'n/a' if traced_share is None else f'{traced_share:.0%}'}; clusters with a page {sum(bool(c['pages']) for c in clusters)}")
