-- __NAME__ (cid__CE__) searches over the last 30 days of data, each with the keyword that served it and Google's match
-- type. NEAR_EXACT and NEAR_PHRASE mean Google served the search as a close variant of that keyword (reordering,
-- plurals, misspellings, same meaning), so a cluster keyword seen here as a search is covered even when its exact text
-- is not in the account.
WITH latest AS (

    SELECT MAX(_PARTITIONTIME) AS snapshot_at

    FROM `segment-data.google_adwords_prepaid.p_ads_SearchQueryStats_6251119615`

    WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)

),


campaigns AS (

    SELECT campaign_id

    FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`

    WHERE _PARTITIONTIME = (SELECT snapshot_at FROM latest)
          AND REGEXP_CONTAINS(campaign_name, r'cid__CE__\b')

    GROUP BY 1

),


keywords AS (

    SELECT
        CONCAT(CAST(ad_group_id AS STRING), '~', CAST(ad_group_criterion_criterion_id AS STRING)) AS kw_key,
        ANY_VALUE(LOWER(ad_group_criterion_keyword_text)) AS keyword

    FROM `segment-data.google_adwords_prepaid.p_ads_Keyword_6251119615`

    WHERE _PARTITIONTIME BETWEEN TIMESTAMP_SUB((SELECT snapshot_at FROM latest), INTERVAL 30 DAY) AND (SELECT snapshot_at FROM latest)
          AND campaign_id IN (SELECT campaign_id FROM campaigns)

    GROUP BY 1

),


served AS (

    SELECT
        LOWER(stats.search_term_view_search_term) AS term,
        REGEXP_EXTRACT(stats.segments_keyword_ad_group_criterion, r'adGroupCriteria/(.*)$') AS kw_key,
        stats.segments_search_term_match_type AS match_type,
        SUM(stats.metrics_impressions) AS impr,
        SUM(stats.metrics_clicks) AS clicks

    FROM `segment-data.google_adwords_prepaid.p_ads_SearchQueryStats_6251119615` AS stats

    WHERE stats._PARTITIONTIME BETWEEN TIMESTAMP_SUB((SELECT snapshot_at FROM latest), INTERVAL 30 DAY) AND (SELECT snapshot_at FROM latest)
          AND stats.segments_ad_network_type = 'SEARCH'
          AND stats.campaign_id IN (SELECT campaign_id FROM campaigns)

    GROUP BY 1, 2, 3

),


final AS (

    SELECT
        DATE((SELECT snapshot_at FROM latest)) AS snapshot_date,
        served.term,
        keywords.keyword AS served_by,
        served.match_type,
        SUM(served.impr) AS impr,
        SUM(served.clicks) AS clicks

    FROM served
    LEFT JOIN keywords USING (kw_key)

    GROUP BY 1, 2, 3, 4

)


SELECT * FROM final
