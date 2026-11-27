-- Orders and net revenue per variant of the experiences shown on a __NAME__ (CE __CE__) page,
-- the pull window (window.py), all channels and paid search alone.
SELECT
    experience_id,
    variant_id,
    COUNT(*) AS count_orders,
    SUM(amount_revenue_usd) AS sum_revenue_usd,
    COUNTIF(channel_grouping = 'Paid') AS count_paid_orders

FROM `headout-analytics.analytics_reporting.fct_orders_lambda`

WHERE created_at >= TIMESTAMP('__START__')
      AND created_at < TIMESTAMP('__END_1__')
      AND experience_id IN UNNEST(SPLIT('__EXPERIENCES__'))
      AND order_status IN ('Completed', 'Partially Completed', 'Pending')

GROUP BY 1, 2
