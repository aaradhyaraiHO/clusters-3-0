-- Orders and net revenue of __NAME__ (CE __CE__) by landing page and channel, 30 Jul to 27 Oct 2026, for
-- page revenue per cluster. landing_page is filled on most orders; the path is lower-cased without query or #.
WITH final AS (

    SELECT
        combined_entity_id AS ce,
        REGEXP_REPLACE(LOWER(REGEXP_EXTRACT(landing_page, r'^(?:https?://)?([^?#]*)')), r'/+$', '/') AS landing_path,
        channel_grouping,
        COUNT(*) AS count_orders,
        ROUND(SUM(amount_revenue_usd), 2) AS sum_revenue_usd

    FROM `headout-analytics.analytics_reporting.fct_orders_lambda`

    WHERE created_at >= TIMESTAMP('2026-07-30')
          AND created_at < TIMESTAMP('2026-10-28')
          AND combined_entity_id = '__CE__'
          AND order_status NOT IN ('Dummy', 'Cancelled - Fraudulent')

    GROUP BY 1, 2, 3

)


SELECT * FROM final
