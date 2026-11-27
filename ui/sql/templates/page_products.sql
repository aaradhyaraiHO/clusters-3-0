-- Products each __NAME__ (CE __CE__) page shows: the latest published ranking of the page's collection,
-- with each product's orders and net revenue from 29 Jul to 27 Oct 2026 (all channels) and whether it is on sale.
WITH latest_runs AS (

    SELECT
        entity_id,
        city,
        MAX(ranked_timestamp) AS ranked_timestamp

    FROM `segment-data.product_rankings.product_rankings_created_v2`

    WHERE ranked_timestamp >= TIMESTAMP('__END__')
          AND ranked_timestamp < TIMESTAMP('__END_7__')
          AND entity_type = 'COLLECTION'
          AND entity_id IN (__COLLECTIONS__)

    GROUP BY 1, 2

),


latest_city AS (

    SELECT * FROM latest_runs

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY entity_id
        ORDER BY ranked_timestamp DESC
    ) = 1

),


ranked AS (

    SELECT
        created.entity_id AS collection_id,
        CAST(created.experience_id AS STRING) AS experience_id,
        created.computed_rank,
        created.ranking_source

    FROM `segment-data.product_rankings.product_rankings_created_v2` AS created
    INNER JOIN latest_city
        ON created.entity_id = latest_city.entity_id
        AND created.city = latest_city.city
        AND created.ranked_timestamp = latest_city.ranked_timestamp

    WHERE created.ranked_timestamp >= TIMESTAMP('__END__')
          AND created.ranked_timestamp < TIMESTAMP('__END_7__')
          AND created.entity_type = 'COLLECTION'

),


orders AS (

    SELECT
        CAST(experience_id AS STRING) AS experience_id,
        COUNT(DISTINCT order_id) AS count_orders,
        SUM(amount_revenue_usd) AS sum_revenue_usd

    FROM `headout-analytics.analytics_reporting.fct_orders_lambda`

    WHERE created_at >= TIMESTAMP('__START_M1__')
          AND created_at < TIMESTAMP('__END_1__')
          AND order_status NOT IN ('Dummy', 'Cancelled - Fraudulent')

    GROUP BY 1

),


final AS (

    SELECT
        ranked.collection_id,
        ranked.experience_id,
        ranked.computed_rank,
        ranked.ranking_source,
        TO_JSON_STRING(experiences.mapped_sub_categories) AS mapped_sub_categories,
        experiences.experience_name,
        experiences.primary_sub_category_name,
        COALESCE(orders.count_orders, 0) AS count_orders,
        COALESCE(orders.sum_revenue_usd, 0) AS sum_revenue_usd

    FROM ranked
    LEFT JOIN `headout-analytics.analytics_reporting.dim_experiences` AS experiences
        ON CAST(experiences.experience_id AS STRING) = ranked.experience_id
    LEFT JOIN orders
        ON orders.experience_id = ranked.experience_id

)


SELECT * FROM final
