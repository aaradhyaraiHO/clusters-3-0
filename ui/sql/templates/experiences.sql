-- Supply for __NAME__ (CE __CE__): every experience the CE owns (dim_experiences.combined_entity_id, the old
-- cluster_sources pull) or that the CE collection or one of its descendant collections lists, with its vendors and
-- 90-day orders (30 Jul to 27 Oct 2026). live follows cluster_sources.py: is_available and not is_hidden.
WITH parent AS (

    SELECT
        collection_id,
        descendant_collections

    FROM `headout-analytics.analytics_reporting.dim_collections`

    WHERE collection_id = '__CE__'

),


ce_collections AS (

    SELECT collection_id FROM parent

    UNION DISTINCT

    SELECT descendant.collection_id

    FROM parent
    CROSS JOIN UNNEST(parent.descendant_collections) AS descendant

),


listed AS (

    SELECT
        listed.experience_id,
        STRING_AGG(DISTINCT listing.collection_id, ' ' ORDER BY listing.collection_id) AS listed_in

    FROM ce_collections
    INNER JOIN `headout-analytics.analytics_reporting.dim_collections` AS listing
        ON listing.collection_id = ce_collections.collection_id
    CROSS JOIN UNNEST(listing.experiences) AS listed

    GROUP BY 1

),


experiences AS (

    SELECT
        experiences.experience_id,
        experiences.experience_name,
        experiences.combined_entity_id,
        experiences.primary_collection_id,
        experiences.is_available,
        experiences.is_hidden,
        listed.listed_in

    FROM `headout-analytics.analytics_reporting.dim_experiences` AS experiences
    LEFT JOIN listed
        ON listed.experience_id = experiences.experience_id

    WHERE experiences.combined_entity_id = '__CE__'
          OR listed.experience_id IS NOT NULL

),


vendors AS (

    SELECT
        variants.experience_id,
        STRING_AGG(DISTINCT tours.vendor_name, ', ') AS vendors

    FROM `headout-analytics.analytics_reporting.dim_variants` AS variants
    CROSS JOIN UNNEST(variants.tours) AS tour
    INNER JOIN `headout-analytics.analytics_reporting.dim_tour_profiles` AS tours
        ON tours.tour_id = tour.tour_id

    WHERE variants.experience_id IN (SELECT experience_id FROM experiences)

    GROUP BY 1

),


experience_orders AS (

    SELECT
        experience_id,
        COUNT(*) AS orders,
        ROUND(SUM(amount_revenue_usd), 2) AS revenue_usd

    FROM `headout-analytics.analytics_reporting.fct_orders_lambda`

    WHERE created_at >= TIMESTAMP('2026-07-30')
          AND created_at < TIMESTAMP('2026-10-28')
          AND experience_id IN (SELECT experience_id FROM experiences)
          AND order_status IN ('Completed', 'Partially Completed', 'Pending')

    GROUP BY 1

)


SELECT
    '__CE__' AS ce,
    experiences.*,
    COALESCE(experiences.is_available, FALSE) AND NOT COALESCE(experiences.is_hidden, FALSE) AS live,
    vendors.vendors,
    COALESCE(experience_orders.orders, 0) AS orders,
    COALESCE(experience_orders.revenue_usd, 0) AS revenue_usd

FROM experiences
LEFT JOIN vendors
    ON vendors.experience_id = experiences.experience_id
LEFT JOIN experience_orders
    ON experience_orders.experience_id = experiences.experience_id
