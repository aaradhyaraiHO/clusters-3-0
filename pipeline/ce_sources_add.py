"""Add CEs to ce_sources.csv from BigQuery, so any CE id can go through run_ce_pipeline.py without a hand-written row.

  python ce_sources_add.py 2405 "18 - Key West" 6835

Name, city and country come from the CE table (dim_combined_entities), falling back to the MMP tool for CEs it does
not hold yet; the microbrand site from the CE's Payload home page (a "Theme" page listing the CE's collection at the
root of its own site). page_regex picks the CE's Search Console pages: the CE's own name words as a URL slug, or, for a
"Category - City" placeholder, the city and the category together in either order. Rows already in the file are kept.
"""
import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

from run_ce_pipeline import bq

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "ce_sources.csv"
# Words that name the product, not the place: left out of the URL slug so "Phi Phi Island Tours" matches /phi-phi-island.
GENERIC = {"tickets", "ticket", "tours", "tour", "cruises", "cruise", "day", "trips", "trip", "the", "and", "of", "to",
           "city", "from", "in", "at", "experience", "experiences"}
HOST_RE = re.compile(r"^(www\.[a-z0-9-]+\.(?:co\.[a-z]{2}|com\.[a-z]{2}|[a-z]{2,3}))(?:\.(.*))?$")


def fold(text):
    return unicodedata.normalize("NFKD", str(text).lower()).encode("ascii", "ignore").decode()


def slug_words(text):
    return [w for w in re.split(r"[^a-z0-9]+", fold(text)) if w]


def page_regex(name, city):
    m = re.match(r"^(.+?)\s+-\s+(.+)$", name)
    if m and not name[0].isdigit():
        # "Cruises - Key West": the city's pages about the category.
        cat = "-".join(w.rstrip("s") for w in slug_words(m.group(1)))
        place = "-".join(slug_words(m.group(2)))
        return f"{place}.*{cat}|{cat}.*{place}"
    core = [w for w in slug_words(re.sub(r"^\d+\s+[^:]*:\s*", "", name)) if w not in GENERIC]
    return "-".join(core) or "-".join(slug_words(city))


def lookup(ces):
    ids = ", ".join("'" + c.replace("'", "\\'") + "'" for c in ces)
    return bq(f"""
        WITH ids AS (SELECT id FROM UNNEST([{ids}]) AS id),
        dim AS (SELECT CAST(combined_entity_id AS STRING) AS id, combined_entity_name AS name, country,
                       combined_entity_subcategory AS subcat, combined_entity_category AS cat
                FROM `headout-analytics.analytics_reporting.dim_combined_entities`),
        stats AS (SELECT CAST(combined_entity_id AS STRING) AS id, ANY_VALUE(city) AS city, ANY_VALUE(country) AS country
                  FROM `headout-analytics.analytics_reporting.combined_entity_stats`
                  WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND city IS NOT NULL GROUP BY 1),
        mmp AS (SELECT CAST(ce_id AS STRING) AS id, ANY_VALUE(TRIM(ce_name)) AS name, ANY_VALUE(city) AS city
                FROM `segment-data.retooldb_prodreplica_log.public_mmp` GROUP BY 1),
        theme AS (SELECT JSON_VALUE(categorisation, '$.collectionId') AS id, ARRAY_AGG(DISTINCT uid) AS uids
                  FROM `segment-data.payload_cms.payload_pages_v2`
                  WHERE JSON_VALUE(categorisation, '$.pageType') = 'Theme' GROUP BY 1),
        named AS (SELECT ids.id, COALESCE(dim.name, mmp.name) AS name,
                         -- "Cruises - Key West": a placeholder's city is in its name.
                         COALESCE(stats.city, mmp.city, REGEXP_EXTRACT(COALESCE(dim.name, mmp.name), r'^[^0-9][^-]*-\s*(.+)$')) AS city
                  FROM ids LEFT JOIN dim USING (id) LEFT JOIN stats USING (id) LEFT JOIN mmp USING (id)),
        city_country AS (SELECT LOWER(city) AS lcity, APPROX_TOP_COUNT(country, 1)[OFFSET(0)].value AS country
                         FROM `headout-analytics.analytics_reporting.combined_entity_stats`
                         WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND city IS NOT NULL GROUP BY 1)
        SELECT ids.id AS ce, named.name, named.city,
               COALESCE(dim.country, stats.country, city_country.country) AS country,
               COALESCE(dim.subcat, dim.cat) AS subcat, ARRAY_TO_STRING(theme.uids, ' ') AS uids
        FROM ids LEFT JOIN named USING (id) LEFT JOIN dim USING (id) LEFT JOIN stats USING (id) LEFT JOIN theme USING (id)
        LEFT JOIN city_country ON city_country.lcity = LOWER(named.city)""")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ces", nargs="+")
    a = p.parse_args()
    have = {r["ce"] for r in csv.DictReader(SOURCES.open())}
    new = [c for c in a.ces if c not in have]
    if not new:
        print("all already in ce_sources.csv")
        return
    rows, missing = [], []
    for r in lookup(new).fillna("").to_dict("records"):
        if not r["name"]:
            missing.append(r["ce"])
            continue
        # A Theme page at the root of its own site is the CE's microbrand; one under a city site's path is not.
        roots = [m.group(1) for m in (HOST_RE.match(u) for u in r["uids"].split()) if m and (m.group(2) or "") in ("", "home")]
        site = f"https://{roots[0]}/" if roots else ""
        # The microbrand's own pages count whatever their path, so its domain name is matched too.
        rx = page_regex(r["name"], r["city"]) + (f"|{re.escape(roots[0].split('.')[1])}" if roots else "")
        rows.append({"ce": r["ce"], "name": r["name"], "city": r["city"].title() if r["city"].isupper() else r["city"],
                     "country": r["country"], "subcat": r["subcat"], "gsc_sites": site, "page_regex": rx})
    with SOURCES.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ce", "name", "city", "country", "subcat", "gsc_sites", "page_regex"])
        w.writerows(rows)
    for r in rows:
        print(f"added {r['ce']}: {r['name']} · {r['city']}, {r['country']} · site {r['gsc_sites'] or 'none'} · pages /{r['page_regex']}/")
    if missing:
        sys.exit(f"not found in the CE table or the MMP tool: {', '.join(missing)}")


if __name__ == "__main__":
    main()
