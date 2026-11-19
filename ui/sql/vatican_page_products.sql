-- Products each Vatican page shows: the latest published ranking of the page's collection in Rome (the list the
-- ranking tool reads), with each product's primary sub-category so pages filtered by sub-category can be narrowed.
WITH latest_runs AS (

    SELECT
        entity_id,
        MAX(ranked_timestamp) AS ranked_timestamp

    FROM `segment-data.product_rankings.product_rankings_created_v2`

    WHERE ranked_timestamp >= TIMESTAMP('2026-10-27')
          AND ranked_timestamp < TIMESTAMP('2026-11-03')
          AND entity_type = 'COLLECTION'
          AND city = 'ROME'
          AND entity_id IN ('189', '592', '3251', '3500', '7154')

    GROUP BY 1

),


ranked AS (

    SELECT
        created.entity_id AS collection_id,
        created.experience_id,
        created.computed_rank,
        created.ranking_source,
        latest_runs.ranked_timestamp

    FROM `segment-data.product_rankings.product_rankings_created_v2` AS created
    INNER JOIN latest_runs
        ON created.entity_id = latest_runs.entity_id
        AND created.ranked_timestamp = latest_runs.ranked_timestamp

    WHERE created.ranked_timestamp >= TIMESTAMP('2026-10-27')
          AND created.ranked_timestamp < TIMESTAMP('2026-11-03')
          AND created.entity_type = 'COLLECTION'
          AND created.city = 'ROME'

),


final AS (

    SELECT
        ranked.collection_id,
        ranked.experience_id,
        ranked.computed_rank,
        ranked.ranking_source,
        TO_JSON_STRING(experiences.mapped_sub_categories) AS mapped_sub_categories,
        ranked.ranked_timestamp,
        experiences.experience_name,
        experiences.primary_sub_category_id,
        experiences.primary_sub_category_name

    FROM ranked
    LEFT JOIN `headout-analytics.analytics_reporting.dim_experiences` AS experiences
        ON CAST(experiences.experience_id AS STRING) = CAST(ranked.experience_id AS STRING)

)


SELECT * FROM final
