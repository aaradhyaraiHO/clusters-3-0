WITH cmap AS (
  SELECT campaign_id,
    CASE
      WHEN REGEXP_CONTAINS(campaign_name, r'cid189\b') THEN '189'
      WHEN REGEXP_CONTAINS(campaign_name, r'cid3111\b') THEN '3111'
      WHEN REGEXP_CONTAINS(campaign_name, r'cid325\b') THEN '325'
      WHEN REGEXP_CONTAINS(campaign_name, r'cid1516\b') AND NOT REGEXP_CONTAINS(campaign_name, r'Banksy') THEN '1516'
      WHEN STARTS_WITH(campaign_name, 'Dubai - Helicopter') THEN '176'
      WHEN STARTS_WITH(campaign_name, 'Munich - Neuschwanstein') OR STARTS_WITH(campaign_name, 'Munich - Things To Do') OR STARTS_WITH(campaign_name, 'Munich - Dachau') THEN '7842ctx'
    END AS ce
  FROM `segment-data.google_adwords_prepaid.p_ads_Campaign_6251119615`
  WHERE _PARTITIONTIME = TIMESTAMP('2026-10-27')
),
sq AS (
  SELECT cmap.ce, s.search_term_view_search_term AS term,
    TRIM(REGEXP_REPLACE(REGEXP_REPLACE(NORMALIZE(LOWER(s.search_term_view_search_term), NFD), r'\p{M}', ''), r'[^a-z0-9]+', ' ')) AS tn,
    SUM(s.metrics_clicks) clicks, SUM(s.metrics_cost_micros)/1e6 spend, SUM(s.metrics_conversions) conv, SUM(s.metrics_impressions) impr
  FROM `segment-data.google_adwords_prepaid.p_ads_SearchQueryStats_6251119615` s JOIN cmap USING (campaign_id)
  WHERE s._PARTITIONTIME BETWEEN TIMESTAMP('2026-07-30') AND TIMESTAMP('2026-10-27') AND cmap.ce IS NOT NULL
  GROUP BY 1,2,3
),
