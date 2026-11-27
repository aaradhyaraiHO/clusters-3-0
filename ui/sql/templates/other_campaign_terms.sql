-- __NAME__'s searches bought by campaigns not tagged cid__CE__ (Grand Canyon's by a Las Vegas helicopter campaign), the
-- pull window (window.py). Only searches matching the CE's other_terms (ces.json), so a campaign's other searches stay
-- out. Run only for a CE that sets other_terms.
WITH campaigns AS (

    SELECT
        campaign_id,
        ANY_VALUE(campaign_name) AS campaign_name

    FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`

    WHERE _PARTITIONTIME = TIMESTAMP('__END_1__')
          AND NOT REGEXP_CONTAINS(campaign_name, r'cid__CE__\b')

    GROUP BY 1

),


final AS (

    SELECT
        campaigns.campaign_name,
        stats.ad_group_id,
        LOWER(stats.search_term_view_search_term) AS term,
        SUM(stats.metrics_impressions) AS impr,
        SUM(stats.metrics_clicks) AS clicks,
        SUM(stats.metrics_cost_micros) / 1e6 AS spend,
        SUM(stats.metrics_conversions) AS conv,
        SUM(stats.metrics_conversions_value) AS conv_value

    FROM `segment-data.google_adwords_prepaid.p_ads_SearchQueryStats_6251119615` AS stats
    INNER JOIN campaigns
        ON stats.campaign_id = campaigns.campaign_id

    WHERE stats._PARTITIONTIME >= TIMESTAMP('__START__')
          AND stats._PARTITIONTIME < TIMESTAMP('__END_1__')
          AND stats.segments_ad_network_type = 'SEARCH'
          AND REGEXP_CONTAINS(LOWER(stats.search_term_view_search_term), r'__OTHER_TERMS__')

    GROUP BY 1, 2, 3

)


SELECT * FROM final
