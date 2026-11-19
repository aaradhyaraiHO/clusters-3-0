-- Clusters 3.0, BigQuery step 1b: overlap in meaning between EOS clusters, read from Google Ads.
-- A search with clicks that Google serves on exact or phrase keywords from two EOS clusters (or that is itself a keyword of one cluster
-- but mostly served by another's keywords) means those clusters claim the same demand: Milford's "milford sound cruise"
-- sits between the head term and "Day / Scenic / Nature Cruises" although the two share no spelling group.
-- Needs bq/eos_base.sql first. Run: bq query --use_legacy_sql=false --location=EU --project_id=headout-dev < bq/ads_overlap.sql
--   clusters_3_0_ads_overlap_terms  one row per CE x search term served by EOS keywords, with its clusters
--   clusters_3_0_ads_overlap        per CE: overlap share of clicks, top cluster pairs
--   clusters_3_0_list_verdict       per CE: checks that block mapping (head term, Ads overlap) vs hygiene (catch-all, General)

DECLARE latest TIMESTAMP DEFAULT (
    SELECT MAX(_PARTITIONTIME) FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`
    WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
);

CREATE TEMP FUNCTION norm(s STRING) AS (
    TRIM(REGEXP_REPLACE(REGEXP_REPLACE(NORMALIZE(LOWER(s), NFD), r'\p{M}', ''), r'[^\p{L}\p{N}]+', ' '))
);

CREATE OR REPLACE TABLE `headout-dev.dbt_aaradhya.clusters_3_0_ads_overlap_terms` AS

WITH eos AS (

    SELECT DISTINCT
        ce_id,
        keyword_norm,
        cluster_name

    FROM `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords_clean`

    WHERE NOT is_competitor

),

campaigns AS (

    SELECT DISTINCT
        campaign_id,
        REGEXP_EXTRACT(campaign_name, r'cid(\d+)\b') AS ce_id

    FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`

    WHERE _PARTITIONTIME = latest
          AND REGEXP_EXTRACT(campaign_name, r'cid(\d+)\b') IN (SELECT DISTINCT ce_id FROM eos)

),

ads_keywords AS (

    SELECT DISTINCT
        CONCAT(CAST(ad_group_id AS STRING), '~', CAST(ad_group_criterion_criterion_id AS STRING)) AS kw_key,
        norm(ad_group_criterion_keyword_text) AS keyword_norm,
        ad_group_criterion_keyword_match_type AS match_type

    FROM `segment-data.google_adwords_prepaid.p_ads_Keyword_6251119615`

    WHERE _PARTITIONTIME = latest
          AND campaign_id IN (SELECT campaign_id FROM campaigns)

),

served AS (

    -- Last 90 days of search terms with the keyword that served each one
    SELECT
        campaigns.ce_id,
        norm(stats.search_term_view_search_term) AS term,
        REGEXP_EXTRACT(stats.segments_keyword_ad_group_criterion, r'adGroupCriteria/(.*)$') AS kw_key,
        SUM(stats.metrics_clicks) AS clicks

    FROM `segment-data.google_adwords_prepaid.p_ads_SearchQueryStats_6251119615` AS stats
    INNER JOIN campaigns
        USING (campaign_id)

    WHERE stats._PARTITIONTIME BETWEEN TIMESTAMP_SUB(latest, INTERVAL 90 DAY) AND latest
          AND stats.segments_ad_network_type = 'SEARCH'

    GROUP BY 1, 2, 3

    HAVING clicks > 0

),

served_clusters AS (

    -- The EOS cluster of the serving keyword; keywords not in the EOS list are left out. Only exact and phrase keywords
    -- count: a broad head keyword ("vatican museum") serving "vatican museum reservation" is the account's match-type
    -- setup, not two clusters claiming the same search.
    SELECT
        served.ce_id,
        served.term,
        eos.cluster_name,
        SUM(served.clicks) AS clicks

    FROM served
    INNER JOIN ads_keywords
        USING (kw_key)
    INNER JOIN eos
        ON eos.ce_id = served.ce_id
        AND eos.keyword_norm = ads_keywords.keyword_norm

    WHERE ads_keywords.match_type IN ('EXACT', 'PHRASE')

    GROUP BY 1, 2, 3

),

term_rollup AS (

    SELECT
        ce_id,
        term,
        SUM(clicks) AS clicks,
        ARRAY_AGG(STRUCT(cluster_name, clicks) ORDER BY clicks DESC) AS by_cluster

    FROM served_clusters

    GROUP BY 1, 2

)

SELECT
    term_rollup.ce_id,
    term_rollup.term,
    term_rollup.clicks,
    term_rollup.by_cluster[OFFSET(0)].cluster_name AS top_cluster,
    term_rollup.by_cluster[OFFSET(0)].clicks / term_rollup.clicks AS top_cluster_share,
    IF(ARRAY_LENGTH(term_rollup.by_cluster) > 1, term_rollup.by_cluster[OFFSET(1)].cluster_name, NULL) AS second_cluster,
    IF(ARRAY_LENGTH(term_rollup.by_cluster) > 1, term_rollup.by_cluster[OFFSET(1)].clicks / term_rollup.clicks, 0) AS second_cluster_share,
    own.cluster_name AS own_cluster,
    -- Overlap: a second cluster serves at least 20% of the term's clicks, or the term is one cluster's own keyword
    -- while another cluster's keywords serve most of it
    (
        IF(ARRAY_LENGTH(term_rollup.by_cluster) > 1, term_rollup.by_cluster[OFFSET(1)].clicks / term_rollup.clicks, 0) >= 0.2
        OR (own.cluster_name IS NOT NULL
            AND own.cluster_name != term_rollup.by_cluster[OFFSET(0)].cluster_name
            AND term_rollup.by_cluster[OFFSET(0)].clicks / term_rollup.clicks >= 0.5)
    ) AS is_overlap

FROM term_rollup
LEFT JOIN `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords_clean` AS own
    ON own.ce_id = term_rollup.ce_id
    AND own.keyword_norm = term_rollup.term
    AND NOT own.is_competitor;


CREATE OR REPLACE TABLE `headout-dev.dbt_aaradhya.clusters_3_0_ads_overlap` AS

WITH pairs AS (

    SELECT
        ce_id,
        IF(second_cluster_share >= 0.2, LEAST(top_cluster, second_cluster), LEAST(top_cluster, own_cluster)) AS cluster_a,
        IF(second_cluster_share >= 0.2, GREATEST(top_cluster, second_cluster), GREATEST(top_cluster, own_cluster)) AS cluster_b,
        SUM(clicks) AS clicks,
        ARRAY_AGG(term ORDER BY clicks DESC LIMIT 1)[OFFSET(0)] AS top_term

    FROM `headout-dev.dbt_aaradhya.clusters_3_0_ads_overlap_terms`

    WHERE is_overlap

    GROUP BY 1, 2, 3

),

pair_text AS (

    SELECT
        ce_id,
        STRING_AGG(FORMAT('%s <> %s (%d clicks, e.g. "%s")', cluster_a, cluster_b, clicks, top_term), '; ' ORDER BY clicks DESC LIMIT 5) AS top_pairs

    FROM pairs

    GROUP BY 1

),

totals AS (

    SELECT
        ce_id,
        SUM(clicks) AS clicks_on_eos_keywords,
        SUM(IF(is_overlap, clicks, 0)) AS overlap_clicks

    FROM `headout-dev.dbt_aaradhya.clusters_3_0_ads_overlap_terms`

    GROUP BY 1

)

SELECT
    totals.ce_id,
    totals.clicks_on_eos_keywords,
    totals.overlap_clicks,
    SAFE_DIVIDE(totals.overlap_clicks, totals.clicks_on_eos_keywords) AS overlap_share,
    pair_text.top_pairs

FROM totals
LEFT JOIN pair_text
    USING (ce_id);


CREATE OR REPLACE TABLE `headout-dev.dbt_aaradhya.clusters_3_0_list_verdict` AS

SELECT
    checks.ce_id,
    checks.ce_name,
    checks.clusters,
    checks.keywords,
    checks.is_head_ok,
    overlap.overlap_share,
    overlap.clicks_on_eos_keywords,
    -- Blocks mapping: no single head term, or clusters that Ads shows claim the same searches (no paid data = not checked)
    CASE
        WHEN overlap.clicks_on_eos_keywords IS NULL OR overlap.clicks_on_eos_keywords < 200 THEN NULL
        ELSE overlap.overlap_share < 0.05
    END AS is_ads_overlap_ok,
    checks.is_head_ok
        AND COALESCE(overlap.overlap_share < 0.05 OR overlap.clicks_on_eos_keywords < 200, TRUE) AS is_mapping_ok,
    -- Hygiene: Krupa's list rules that do not break mapping
    checks.is_catchall_ok AND checks.is_duplicates_ok AND checks.is_overlap_ok AS is_hygiene_ok,
    overlap.top_pairs,
    checks.head_spread,
    checks.top_splits AS spelling_splits,
    checks.largest_cluster,
    checks.largest_cluster_share,
    checks.catchall_named,
    checks.scope_review

FROM `headout-dev.dbt_aaradhya.clusters_3_0_list_checks` AS checks
LEFT JOIN `headout-dev.dbt_aaradhya.clusters_3_0_ads_overlap` AS overlap
    USING (ce_id);
