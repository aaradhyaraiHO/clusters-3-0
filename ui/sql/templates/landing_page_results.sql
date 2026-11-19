-- __NAME__ (cid__CE__) results by ad group and landing page, 30 Jul to 27 Oct 2026. Google Ads has no conversions in
-- its landing-page view, so ad-level stats are joined to each ad's final URL.
WITH campaigns AS (

    SELECT
        campaign_id,
        campaign_name

    FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`

    WHERE _PARTITIONTIME = TIMESTAMP('2026-10-28')
          AND REGEXP_CONTAINS(campaign_name, r'cid__CE__$')

),


ads AS (

    SELECT
        ad_group_ad_ad_id AS ad_id,
        ad_group_id,
        JSON_VALUE(ad_group_ad_ad_final_urls, '$[0]') AS landing_url

    FROM `segment-data.google_adwords_prepaid.p_ads_Ad_6251119615`

    WHERE _PARTITIONTIME = TIMESTAMP('2026-10-28')

),


ad_stats AS (

    SELECT
        stats.ad_group_ad_ad_id AS ad_id,
        stats.ad_group_id,
        campaigns.campaign_name,
        SUM(stats.metrics_clicks) AS clicks,
        SUM(stats.metrics_impressions) AS impr,
        SUM(stats.metrics_cost_micros) / 1e6 AS spend,
        SUM(stats.metrics_conversions) AS conv,
        SUM(stats.metrics_conversions_value) AS conv_value

    FROM `segment-data.google_adwords_prepaid.p_ads_AdBasicStats_6251119615` AS stats
    INNER JOIN campaigns
        ON stats.campaign_id = campaigns.campaign_id

    WHERE stats._PARTITIONTIME >= TIMESTAMP('2026-07-30')
          AND stats._PARTITIONTIME < TIMESTAMP('2026-10-29')
          AND stats.segments_date >= '2026-07-30'
          AND stats.segments_date <= '2026-10-27'

    GROUP BY 1, 2, 3

),


final AS (

    SELECT
        ad_stats.campaign_name,
        ad_stats.ad_group_id,
        ads.landing_url,
        SUM(ad_stats.clicks) AS clicks,
        SUM(ad_stats.impr) AS impr,
        SUM(ad_stats.spend) AS spend,
        SUM(ad_stats.conv) AS conv,
        SUM(ad_stats.conv_value) AS conv_value

    FROM ad_stats
    LEFT JOIN ads
        ON ad_stats.ad_id = ads.ad_id
        AND ad_stats.ad_group_id = ads.ad_group_id

    GROUP BY 1, 2, 3

)


SELECT * FROM final
