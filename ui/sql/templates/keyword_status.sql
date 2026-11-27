-- Every keyword in the __NAME__ (cid__CE__) campaigns as Google Ads holds it now: the latest daily snapshot of the
-- keyword, its ad group and its campaign, with each one's status. Removed keywords are left out. A keyword is live
-- only when keyword, ad group and campaign are all enabled; the tool reads "bid", "bid as a close variant", "paused"
-- and "not in account" from this.
WITH latest AS (

    SELECT MAX(_PARTITIONTIME) AS snapshot_at

    FROM `segment-data.google_adwords_prepaid.p_ads_Keyword_6251119615`

    WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)

),


campaigns AS (

    SELECT
        campaign_id,
        campaign_name,
        campaign_status

    FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`

    WHERE _PARTITIONTIME = (SELECT snapshot_at FROM latest)
          AND REGEXP_CONTAINS(campaign_name, r'cid__CE__\b')

),


ad_groups AS (

    SELECT
        ad_group_id,
        ad_group_name,
        ad_group_status

    FROM `segment-data.google_adwords_prepaid.p_ads_AdGroup_6251119615`

    WHERE _PARTITIONTIME = (SELECT snapshot_at FROM latest)

),


final AS (

    SELECT
        DATE((SELECT snapshot_at FROM latest)) AS snapshot_date,
        keywords.ad_group_id,
        keywords.ad_group_criterion_criterion_id AS criterion_id,
        LOWER(keywords.ad_group_criterion_keyword_text) AS keyword,
        keywords.ad_group_criterion_keyword_match_type AS match_type,
        keywords.ad_group_criterion_status AS keyword_status,
        ad_groups.ad_group_name,
        ad_groups.ad_group_status,
        campaigns.campaign_name,
        campaigns.campaign_status

    FROM `segment-data.google_adwords_prepaid.p_ads_Keyword_6251119615` AS keywords
    INNER JOIN campaigns
        ON keywords.campaign_id = campaigns.campaign_id
    INNER JOIN ad_groups
        ON keywords.ad_group_id = ad_groups.ad_group_id

    WHERE keywords._PARTITIONTIME = (SELECT snapshot_at FROM latest)
          AND keywords.ad_group_criterion_status != 'REMOVED'
          AND keywords.ad_group_criterion_negative IS NOT TRUE

)


SELECT * FROM final
