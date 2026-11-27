"""The pages that belong to one CE, out of everything pulled from its site.

A CE on its own microbrand owns the whole site. A CE that lives in a folder of a shared site (a city site such as
cairnstickets.com, where Daintree National Park is /daintree-national-park/) shares it with every other CE there, so
its pages are the ones under its home folder, or tagged with its collection, one of its child collections or one of
its POIs. Its home is its Payload Theme page, the one that lists the CE's own collection.

Used by prepare_ce.py (the tool's page-to-cluster mapping) and page_decisions.py (the page prompts' input), so both
see the same pages.
"""
from pathlib import Path

import pandas as pd


def home_uid(pages, ce, host):
    """The CE's Theme page uid, or None when it has none."""
    theme = pages.loc[(pages["page_type"] == "Theme") & (pages["collection_id"].astype(str) == str(ce)), "uid"]
    return min(theme, key=len) if len(theme) else None


def own_pages(pages, ce, host, entities_csv):
    """pages filtered to the CE's own when its home is a folder of a shared site; unchanged otherwise."""
    home = home_uid(pages, ce, host)
    if home is None or home == host:
        return pages
    colls, pois = {str(ce)}, set()
    if Path(entities_csv).exists():
        ents = pd.read_csv(entities_csv, dtype=str)
        colls |= set(ents.loc[ents["entity_type"] == "collection", "entity_id"])
        # Only POIs from the CE's own experiences: on a shared site the POIs tagged on "its" pages (source page_tag)
        # come from every CE's pages, since the pull reads the whole site.
        poi_rows = ents[(ents["entity_type"] == "poi") & ~ents["source"].fillna("").str.fullmatch("page_tag")]
        pois = set(poi_rows["entity_id"])
    uid = pages["uid"].astype(str)
    mine = (uid == home) | uid.str.startswith(home + ".") | pages["collection_id"].astype(str).isin(colls)
    if "poi_id" in pages:
        mine |= pages["poi_id"].astype(str).str.replace(r"\.0$", "", regex=True).isin(pois)
    return pages[mine].copy()
