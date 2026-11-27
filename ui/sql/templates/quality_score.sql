-- Latest keyword snapshot for the __NAME__ (cid__CE__) campaigns: Quality Score and its parts per keyword.
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
        keywords.ad_group_id,
        keywords.ad_group_criterion_criterion_id AS criterion_id,
        keywords.ad_group_criterion_keyword_text AS keyword,
        keywords.ad_group_criterion_keyword_match_type AS match_type,
        keywords.ad_group_criterion_quality_info_quality_score AS quality_score,
        keywords.ad_group_criterion_quality_info_search_predicted_ctr AS predicted_ctr,
        keywords.ad_group_criterion_quality_info_creative_quality_score AS ad_relevance,
        keywords.ad_group_criterion_quality_info_post_click_quality_score AS landing_page_experience,
        campaigns.campaign_name

    FROM `segment-data.google_adwords_prepaid.p_ads_Keyword_6251119615` AS keywords
    INNER JOIN campaigns
        ON keywords.campaign_id = campaigns.campaign_id

    WHERE keywords._PARTITIONTIME = TIMESTAMP('__END_1__')
          AND keywords.ad_group_criterion_status = 'ENABLED'

)


SELECT * FROM final
