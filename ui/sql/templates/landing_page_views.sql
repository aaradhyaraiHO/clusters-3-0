-- Where __NAME__'s (cid__CE__) paid clicks really landed, by campaign and ad group, the pull window (window.py). An
-- ad's final URL is not where its clicks go: sitelinks and AI Max final-URL expansion send them to other pages, so
-- landing_page_results.sql's ad join is kept only for conversions, which this view does not report.
WITH final AS (

    SELECT
        campaign_name,
        ad_group_name,
        landing_page_view_unexpanded_final_url AS landing_url,
        SUM(metrics_clicks) AS clicks,
        SUM(metrics_impressions) AS impr,
        SUM(metrics_cost_micros) / 1e6 AS spend

    FROM `segment-data.google_adwords_prepaid.p_ads_LandingPageStats_6251119615`

    WHERE _PARTITIONTIME >= TIMESTAMP('__START__')
          AND _PARTITIONTIME < TIMESTAMP('__END_2__')
          AND segments_date >= '__START__'
          AND segments_date <= '__END__'
          AND REGEXP_CONTAINS(campaign_name, r'cid__CE__\b')

    GROUP BY 1, 2, 3

)


SELECT * FROM final
