-- Paid orders on the __NAME__ microbrand (CE __CE__), 30 Jul to 28 Oct 2026, traced to the ad click:
-- order -> booking (fct_bookings_lambda) -> gclid (stg_database_logs__attribution_logs) -> click (google_ads_click_stats:
-- ad group, targeted keyword). Same query as Vatican's paid_orders_by_click (snapshots/20261028_v4_connected/pulls.sql).
-- match_status = matched | gclid_no_click | no_gclid. Output: <out>/paid_orders_by_click___CE__.csv
WITH o AS (
    SELECT order_id, combined_entity_id AS ce, amount_revenue_usd AS rev
    FROM `headout-analytics.analytics_reporting.fct_orders_lambda`
    WHERE created_at BETWEEN '__START__' AND '__END_1__' AND combined_entity_id = '__CE__' AND channel_grouping = 'Paid'
          AND order_status NOT IN ('Dummy', 'Cancelled - Fraudulent')
),
b AS (SELECT DISTINCT order_id, booking_id FROM `headout-analytics.analytics_reporting.fct_bookings_lambda` WHERE order_id IN (SELECT order_id FROM o)),
g AS (
    SELECT booking_id, ANY_VALUE(click_id) AS gclid
    FROM `headout-analytics.analytics_staging.stg_database_logs__attribution_logs`
    WHERE booking_id IN (SELECT booking_id FROM b) AND click_id IS NOT NULL
    GROUP BY 1
),
og AS (SELECT o.order_id, o.ce, o.rev, ANY_VALUE(g.gclid) AS gclid FROM o LEFT JOIN b USING (order_id) LEFT JOIN g USING (booking_id) GROUP BY 1, 2, 3),
c AS (
    SELECT gclid, ANY_VALUE(CAST(ad_group_id AS STRING)) AS ad_group_id, ANY_VALUE(ad_group_name) AS ad_group_name,
           ANY_VALUE(campaign_name) AS campaign_name, ANY_VALUE(LOWER(keyword_text)) AS keyword_text, ANY_VALUE(keyword_match_type) AS keyword_match_type
    FROM `headout-analytics.analytics_reporting.google_ads_click_stats`
    WHERE report_date BETWEEN '__START_M6__' AND '__END_1__' AND gclid IN (SELECT gclid FROM og)
    GROUP BY 1
)
SELECT ce, IF(gclid IS NULL, 'no_gclid', IF(c.gclid IS NULL, 'gclid_no_click', 'matched')) AS match_status,
       ad_group_id, ad_group_name, campaign_name, keyword_text, keyword_match_type,
       COUNT(*) AS orders, ROUND(SUM(rev), 2) AS revenue_usd
FROM og LEFT JOIN c USING (gclid)
GROUP BY 1, 2, 3, 4, 5, 6, 7
