-- __NAME__ (cid__CE__) search terms by week, 13 full weeks to 26 Oct 2026, summed over ad groups.
WITH campaigns AS (

    SELECT
        campaign_id,
        campaign_name

    FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`

    WHERE _PARTITIONTIME = TIMESTAMP('__END_1__')
          AND REGEXP_CONTAINS(campaign_name, r'cid__CE__\b')

),


final AS (

    SELECT
        stats.segments_week AS week,
        stats.search_term_view_search_term AS term,
        SUM(stats.metrics_impressions) AS impr,
        SUM(stats.metrics_clicks) AS clicks,
        SUM(stats.metrics_cost_micros) / 1e6 AS spend,
        SUM(stats.metrics_conversions) AS conv,
        SUM(stats.metrics_conversions_value) AS conv_value

    FROM `segment-data.google_adwords_prepaid.p_ads_SearchQueryStats_6251119615` AS stats
    INNER JOIN campaigns
        ON stats.campaign_id = campaigns.campaign_id

    WHERE stats._PARTITIONTIME >= TIMESTAMP('__WEEK_START__')
          AND stats._PARTITIONTIME < TIMESTAMP('__END__')
          AND stats.segments_date >= '__WEEK_START__'
          AND stats.segments_date < '__WEEK_END__'

    GROUP BY 1, 2

)


SELECT * FROM final
