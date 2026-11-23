-- Target ROAS of each __NAME__ (cid__CE__) campaign. Campaigns on a portfolio strategy carry 0 here; the portfolio's
-- own target is not in the BidGoal export, so they keep the strategy name instead.
SELECT
    campaign_name,
    campaign_status,
    campaign_maximize_conversion_value_target_roas AS target_roas,
    bidding_strategy_name

FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`

WHERE _PARTITIONTIME = TIMESTAMP('2026-10-28')
      AND REGEXP_CONTAINS(campaign_name, r'cid__CE__\b')
