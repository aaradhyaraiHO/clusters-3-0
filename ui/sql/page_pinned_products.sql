-- Products named in the Vatican and Milford Sound Cruises pages' Payload pins (commonRanks) and exclusions, with their
-- sub-category and orders from 30 Jul to 27 Oct 2026, so the page pop-up can name products outside its collection ranking.
WITH orders AS (

    SELECT
        CAST(experience_id AS STRING) AS experience_id,
        COUNT(DISTINCT order_id) AS count_orders,
        SUM(amount_revenue_usd) AS sum_revenue_usd

    FROM `headout-analytics.analytics_reporting.fct_orders_lambda`

    WHERE created_at >= TIMESTAMP('2026-07-30')
          AND created_at < TIMESTAMP('2026-10-28')
          AND order_status NOT IN ('Dummy', 'Cancelled - Fraudulent')
          AND CAST(experience_id AS STRING) IN UNNEST(SPLIT('3163,3241,3361,6732,6786,6796,7698,7968,7998,8847,9379,10479,10480,10497,10644,15143,15144,15487,15588,15947,16466,17708,17798,18103,18125,18300,23887,24162,26563,26586,26899,26901,28428,28429,28870,28963,29116,29277,29695,29729,29756,29961,29972,30319,30358,30359,30793,30794,31528,31786,32197,36203,36204,36205,36523,36641,36702,37156,38583,38585,40298,55218,55219,55226'))

    GROUP BY 1

),


final AS (

    SELECT
        CAST(experiences.experience_id AS STRING) AS experience_id,
        experiences.experience_name,
        experiences.primary_sub_category_name,
        TO_JSON_STRING(experiences.mapped_sub_categories) AS mapped_sub_categories,
        COALESCE(orders.count_orders, 0) AS count_orders,
        COALESCE(orders.sum_revenue_usd, 0) AS sum_revenue_usd

    FROM `headout-analytics.analytics_reporting.dim_experiences` AS experiences
    LEFT JOIN orders
        ON orders.experience_id = CAST(experiences.experience_id AS STRING)

    WHERE CAST(experiences.experience_id AS STRING) IN UNNEST(SPLIT('3163,3241,3361,6732,6786,6796,7698,7968,7998,8847,9379,10479,10480,10497,10644,15143,15144,15487,15588,15947,16466,17708,17798,18103,18125,18300,23887,24162,26563,26586,26899,26901,28428,28429,28870,28963,29116,29277,29695,29729,29756,29961,29972,30319,30358,30359,30793,30794,31528,31786,32197,36203,36204,36205,36523,36641,36702,37156,38583,38585,40298,55218,55219,55226'))

)


SELECT * FROM final
