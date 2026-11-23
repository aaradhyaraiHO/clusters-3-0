-- __NAME__ (cid__CE__) Google Ads totals by campaign and network, 30 Jul to 27 Oct 2026: the campaign-level numbers
-- (every click, including traffic Google ties to no keyword) next to the keyword-level sums the cluster split uses.
WITH campaigns AS (

    SELECT
        campaign_id,
        ANY_VALUE(campaign_name) AS campaign_name,
        '__CE__' AS ce

    FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`

    WHERE _PARTITIONTIME = TIMESTAMP('2026-10-27')
          AND REGEXP_CONTAINS(campaign_name, r'cid__CE__\b')

    GROUP BY 1

),


campaign_stats AS (

    SELECT
        campaign_id,
        segments_ad_network_type AS network,
        SUM(metrics_impressions) AS impr,
        SUM(metrics_clicks) AS clicks,
        SUM(metrics_cost_micros) / 1e6 AS spend,
        SUM(metrics_conversions) AS conv,
        SUM(metrics_conversions_value) AS conv_value

    FROM `segment-data.google_adwords_prepaid.p_ads_CampaignBasicStats_6251119615`

    WHERE _PARTITIONTIME BETWEEN TIMESTAMP('2026-07-30') AND TIMESTAMP('2026-10-28')
          AND segments_date BETWEEN '2026-07-30' AND '2026-10-27'
          AND campaign_id IN (SELECT campaign_id FROM campaigns)

    GROUP BY 1, 2

),


keyword_stats AS (

    SELECT
        campaign_id,
        SUM(metrics_impressions) AS kw_impr,
        SUM(metrics_clicks) AS kw_clicks,
        SUM(metrics_cost_micros) / 1e6 AS kw_spend,
        SUM(metrics_conversions_value) AS kw_conv_value

    FROM `segment-data.google_adwords_prepaid.p_ads_KeywordBasicStats_6251119615`

    WHERE _PARTITIONTIME BETWEEN TIMESTAMP('2026-07-30') AND TIMESTAMP('2026-10-28')
          AND segments_date BETWEEN '2026-07-30' AND '2026-10-27'
          AND segments_ad_network_type = 'SEARCH'
          AND campaign_id IN (SELECT campaign_id FROM campaigns)

    GROUP BY 1

),


final AS (

    SELECT
        campaigns.ce,
        campaigns.campaign_id,
        campaigns.campaign_name,
        campaign_stats.network,
        campaign_stats.impr,
        campaign_stats.clicks,
        ROUND(campaign_stats.spend, 2) AS spend,
        ROUND(campaign_stats.conv, 2) AS conv,
        ROUND(campaign_stats.conv_value, 2) AS conv_value,
        keyword_stats.kw_impr,
        keyword_stats.kw_clicks,
        ROUND(keyword_stats.kw_spend, 2) AS kw_spend,
        ROUND(keyword_stats.kw_conv_value, 2) AS kw_conv_value

    FROM campaigns
    INNER JOIN campaign_stats USING (campaign_id)
    LEFT JOIN keyword_stats USING (campaign_id)

)


SELECT * FROM final
