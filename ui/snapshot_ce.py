"""Pull one CE's Google Ads and Search Console rows in the shape of the 30 Oct validation snapshot, for a CE that is not
one of its 11.

  python3 snapshot_ce.py <clusters_3_0> 2405

Same queries and window as snapshots/20261030_validation_v1/pulls.sql (30 Jul - 27 Oct 2026, search network), scoped to
one CE: its campaigns by the cid<CE> tag, its Search Console rows by the gsc_sites and page_regex in the pipeline's
ce_sources.csv. A CE id that is not a number (a placeholder such as "18 - Key West") has no campaigns, so its Ads files
are written empty with their headers. Writes <clusters_3_0>/snapshots/new_<slug>/, which map_ce.build_snapshot reads in
place of the 30 Oct snapshot.
"""
from window import window
import argparse
import os
import re
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pandas as pd

WINDOW = window()
PARTITION = WINDOW[1]
HEADERS = {
    "campaigns": ["campaign_id", "campaign_name", "ce"],
    "search_term_pairs": ["ce", "kw_key", "term", "match_type", "impr", "clicks", "spend", "conv", "conv_value"],
    "keyword_totals": ["ce", "kw_key", "keyword", "keyword_match_type", "impr", "clicks", "spend", "conv", "conv_value",
                       "eligible", "lost_rank", "impr_with_share"],
    "ad_groups": ["ce", "ad_group_id", "ad_group_name", "ad_group_status", "campaign_name"],
    "gsc_terms": ["ce", "term", "clicks", "impressions", "avg_position", "clicks_microbrand", "top_page", "spend", "conv"],
}


def snapshot_dir(root, ce):
    return Path(root) / "snapshots" / ("new_" + re.sub(r"[^a-z0-9]+", "_", ce.lower()).strip("_"))


def bq(sql):
    env = dict(os.environ)
    # Copied fresh every run: a copy kept from before a `gcloud auth login` holds the expired token.
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"gcloud_snapshot_ce_{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(Path.home() / ".config" / "gcloud", tmp, ignore=shutil.ignore_patterns("virtenv", "logs"), dirs_exist_ok=True)
    env["CLOUDSDK_CONFIG"] = str(tmp)
    res = subprocess.run(["bq", "query", "--use_legacy_sql=false", "--format=csv", "--max_rows=10000000", "--quiet"],
                         input=sql, capture_output=True, text=True, env=env)
    if res.returncode:
        raise SystemExit(f"bq failed\n{res.stderr[-1500:] or res.stdout[-1500:]}")
    return pd.read_csv(StringIO(res.stdout), dtype={"ce": str, "ad_group_id": str, "campaign_id": str}) if res.stdout.strip() else None


def campaigns_cte(ce):
    return f"""campaigns AS (
    SELECT campaign_id, ANY_VALUE(campaign_name) AS campaign_name, '{ce}' AS ce
    FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`
    WHERE _PARTITIONTIME = TIMESTAMP('{PARTITION}') AND REGEXP_EXTRACT(campaign_name, r'cid(\\d+)\\b') = '{ce}'
    GROUP BY 1
)"""


def ads_queries(ce):
    start, end = WINDOW
    cte = campaigns_cte(ce)
    return {
        "campaigns": f"WITH {cte} SELECT campaign_id, campaign_name, ce FROM campaigns",
        "search_term_pairs": f"""WITH {cte}
SELECT campaigns.ce, REGEXP_EXTRACT(stats.segments_keyword_ad_group_criterion, r'adGroupCriteria/(.*)$') AS kw_key,
    LOWER(stats.search_term_view_search_term) AS term, stats.segments_search_term_match_type AS match_type,
    SUM(stats.metrics_impressions) AS impr, SUM(stats.metrics_clicks) AS clicks, ROUND(SUM(stats.metrics_cost_micros) / 1e6, 2) AS spend,
    ROUND(SUM(stats.metrics_conversions), 2) AS conv, ROUND(SUM(stats.metrics_conversions_value), 2) AS conv_value
FROM `segment-data.google_adwords_prepaid.p_ads_SearchQueryStats_6251119615` AS stats
INNER JOIN campaigns USING (campaign_id)
WHERE stats._PARTITIONTIME BETWEEN TIMESTAMP('{start}') AND TIMESTAMP('{end}') AND stats.segments_ad_network_type = 'SEARCH'
GROUP BY 1, 2, 3, 4
HAVING impr >= 3 OR clicks > 0""",
        "keyword_totals": f"""WITH {cte},
keywords AS (
    SELECT DISTINCT campaign_id, ad_group_id, ad_group_criterion_criterion_id,
        LOWER(ad_group_criterion_keyword_text) AS keyword, ad_group_criterion_keyword_match_type AS keyword_match_type
    FROM `segment-data.google_adwords_prepaid.p_ads_Keyword_6251119615`
    WHERE _PARTITIONTIME = TIMESTAMP('{PARTITION}') AND campaign_id IN (SELECT campaign_id FROM campaigns)
),
stats AS (
    SELECT campaign_id, ad_group_id, ad_group_criterion_criterion_id, segments_date,
        SUM(metrics_impressions) AS impr, SUM(metrics_clicks) AS clicks, SUM(metrics_cost_micros) / 1e6 AS spend,
        SUM(metrics_conversions) AS conv, SUM(metrics_conversions_value) AS conv_value
    FROM `segment-data.google_adwords_prepaid.p_ads_KeywordBasicStats_6251119615`
    WHERE _PARTITIONTIME BETWEEN TIMESTAMP('{start}') AND TIMESTAMP('2026-10-28') AND segments_date BETWEEN '{start}' AND '{end}'
          AND segments_ad_network_type = 'SEARCH' AND campaign_id IN (SELECT campaign_id FROM campaigns)
    GROUP BY 1, 2, 3, 4
),
shares AS (
    SELECT campaign_id, ad_group_id, ad_group_criterion_criterion_id, segments_date,
        MAX(metrics_search_impression_share) AS imp_share, MAX(metrics_search_rank_lost_impression_share) AS rank_lost
    FROM `segment-data.google_adwords_prepaid.p_ads_KeywordCrossDeviceStats_6251119615`
    WHERE _PARTITIONTIME BETWEEN TIMESTAMP('{start}') AND TIMESTAMP('2026-10-28') AND segments_date BETWEEN '{start}' AND '{end}'
          AND segments_ad_network_type = 'SEARCH' AND campaign_id IN (SELECT campaign_id FROM campaigns)
    GROUP BY 1, 2, 3, 4
)
SELECT campaigns.ce, CONCAT(CAST(stats.ad_group_id AS STRING), '~', CAST(stats.ad_group_criterion_criterion_id AS STRING)) AS kw_key,
    ANY_VALUE(keywords.keyword) AS keyword, ANY_VALUE(keywords.keyword_match_type) AS keyword_match_type,
    SUM(stats.impr) AS impr, SUM(stats.clicks) AS clicks, ROUND(SUM(stats.spend), 2) AS spend,
    ROUND(SUM(stats.conv), 2) AS conv, ROUND(SUM(stats.conv_value), 2) AS conv_value,
    ROUND(SUM(IF(shares.imp_share > 0, stats.impr / shares.imp_share, NULL))) AS eligible,
    ROUND(SUM(IF(shares.imp_share > 0, stats.impr / shares.imp_share * shares.rank_lost, NULL))) AS lost_rank,
    SUM(IF(shares.imp_share > 0, stats.impr, 0)) AS impr_with_share
FROM stats
INNER JOIN campaigns USING (campaign_id)
LEFT JOIN keywords USING (campaign_id, ad_group_id, ad_group_criterion_criterion_id)
LEFT JOIN shares USING (campaign_id, ad_group_id, ad_group_criterion_criterion_id, segments_date)
GROUP BY 1, 2
HAVING impr > 0""",
        "ad_groups": f"""WITH {cte}
SELECT campaigns.ce, CAST(ad_groups.ad_group_id AS STRING) AS ad_group_id, ANY_VALUE(ad_groups.ad_group_name) AS ad_group_name,
    ANY_VALUE(ad_groups.ad_group_status) AS ad_group_status, ANY_VALUE(campaigns.campaign_name) AS campaign_name
FROM `segment-data.google_adwords_prepaid.p_ads_AdGroup_6251119615` AS ad_groups
INNER JOIN campaigns USING (campaign_id)
WHERE ad_groups._PARTITIONTIME = TIMESTAMP('{PARTITION}')
GROUP BY 1, 2""",
    }


def gsc_query(ce, sites, page_regex):
    start, end = WINDOW
    site_list = ", ".join(f"'{s}'" for s in ["https://www.headout.com/", *sites])
    return f"""SELECT '{ce}' AS ce, LOWER(keyword) AS term, SUM(count_clicks) AS clicks, SUM(count_impressions) AS impressions,
    ROUND(SAFE_DIVIDE(SUM(avg_position * count_impressions), SUM(count_impressions)), 1) AS avg_position,
    SUM(IF(site != 'https://www.headout.com/', count_clicks, 0)) AS clicks_microbrand,
    ARRAY_AGG(page ORDER BY count_clicks DESC LIMIT 1)[OFFSET(0)] AS top_page, 0 AS spend, 0 AS conv
FROM `headout-analytics.analytics_staging.stg_search_console__keyword_page_performance`
WHERE report_date BETWEEN '{start}' AND '{end}' AND search_type = 'web' AND site IN ({site_list})
      AND REGEXP_CONTAINS(page, r'{page_regex}')
GROUP BY 1, 2
HAVING SUM(count_clicks) > 0 OR SUM(count_impressions) >= 50"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("ce")
    a = p.parse_args()
    src = pd.read_csv(Path(a.root) / "ce_sources.csv", dtype=str).set_index("ce")
    if a.ce not in src.index:
        raise SystemExit(f"CE {a.ce} is not in ce_sources.csv")
    row = src.loc[a.ce]
    out = snapshot_dir(a.root, a.ce)
    out.mkdir(parents=True, exist_ok=True)
    frames = {}
    for name, sql in (ads_queries(a.ce).items() if a.ce.isdigit() else []):
        frames[name] = bq(sql)
    for name, cols in HEADERS.items():
        if frames.get(name) is None and name != "gsc_terms":
            frames[name] = pd.DataFrame(columns=cols)
    sites = [s for s in str(row.get("gsc_sites") or "").split() if s and s != "nan"]
    frames["gsc_terms"] = bq(gsc_query(a.ce, sites, row["page_regex"])) if isinstance(row["page_regex"], str) else None
    if frames["gsc_terms"] is None:
        frames["gsc_terms"] = pd.DataFrame(columns=HEADERS["gsc_terms"])
    stp = frames["search_term_pairs"]
    frames["pair_terms"] = (stp.groupby(["ce", "term"], as_index=False)[["impr", "clicks", "spend", "conv", "conv_value"]].sum()
                            if len(stp) else pd.DataFrame(columns=["ce", "term", "impr", "clicks", "spend", "conv", "conv_value"]))
    kt = frames["keyword_totals"]
    frames["keyword_terms"] = (kt.groupby(["ce", "keyword"], as_index=False)[["impr", "clicks"]].sum().rename(columns={"keyword": "term"})
                               if len(kt) else pd.DataFrame(columns=["ce", "term", "impr", "clicks"]))
    frames["ce_names"] = pd.DataFrame([{"ce": a.ce, "name": row["name"], "city": row["city"]}])
    # final_ce.py replaces this with the pipeline's clusters; it is here so the snapshot has every file map_ce copies.
    frames["cluster_keywords"] = pd.DataFrame(columns=["ce", "cid", "rank", "t", "name", "ids", "kw", "vol"])
    for name, df in frames.items():
        df.to_csv(out / f"{name}.csv", index=False)
    print(f"snapshot {out.name}: " + ", ".join(f"{k} {len(v)}" for k, v in frames.items()))


if __name__ == "__main__":
    sys.exit(main())
