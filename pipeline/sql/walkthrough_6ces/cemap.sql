cmap AS (
  SELECT campaign_id, campaign_name, campaign_status, campaign_advertising_channel_type AS ch,
    CASE
      WHEN REGEXP_CONTAINS(campaign_name, r'cid189\b') THEN '189'
      WHEN REGEXP_CONTAINS(campaign_name, r'cid3111\b') THEN '3111'
      WHEN REGEXP_CONTAINS(campaign_name, r'cid325\b') THEN '325'
      WHEN REGEXP_CONTAINS(campaign_name, r'cid1516\b') THEN '1516'
      WHEN STARTS_WITH(campaign_name, 'Dubai - Helicopter') THEN '176'
      WHEN STARTS_WITH(campaign_name, 'Munich - Neuschwanstein') OR STARTS_WITH(campaign_name, 'Munich - Things To Do') OR STARTS_WITH(campaign_name, 'Munich - Dachau') THEN '7842ctx'
    END AS ce
  FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`
  WHERE _PARTITIONTIME = TIMESTAMP('2026-10-27')
)
