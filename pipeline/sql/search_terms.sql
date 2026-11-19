-- Google Ads search terms for the CEs in the snapshot, aggregated over the window.
-- Params: {ce_cases} (CASE arms mapping campaign_name -> ce), {start}, {end}, {campaign_partition}, {lo}, {hi}
-- Campaign -> CE uses the cid<id> tag in the campaign name (same rule as stg_google_ads__campaigns).
-- The BigQuery MCP returns at most 3,000 rows per call, so pull in pages of rn BETWEEN {lo} AND {hi}.
-- Cost: ~2.8 GB per call (SearchQueryStats is partitioned by day).
WITH cmap AS (

    SELECT DISTINCT
        campaign_id,
        CASE
            {ce_cases}
        END AS ce

    FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`

    WHERE _PARTITIONTIME = TIMESTAMP('{campaign_partition}')

),

terms AS (

    SELECT
        cmap.ce,
        LOWER(stats.search_term_view_search_term) AS term,
        SUM(stats.metrics_clicks) AS clicks,
        ROUND(SUM(stats.metrics_cost_micros) / 1e6, 2) AS spend,
        ROUND(SUM(stats.metrics_conversions), 2) AS conv,
        SUM(stats.metrics_impressions) AS impr

    FROM `segment-data.google_adwords_prepaid.p_ads_SearchQueryStats_6251119615` AS stats
    INNER JOIN cmap USING (campaign_id)

    WHERE stats._PARTITIONTIME BETWEEN TIMESTAMP('{start}') AND TIMESTAMP('{end}')
          AND cmap.ce IS NOT NULL

    GROUP BY 1, 2

    HAVING clicks > 0

)

SELECT * EXCEPT (rn)

FROM (SELECT *, ROW_NUMBER() OVER (ORDER BY clicks DESC, ce, term) AS rn FROM terms)

WHERE rn BETWEEN {lo} AND {hi}
