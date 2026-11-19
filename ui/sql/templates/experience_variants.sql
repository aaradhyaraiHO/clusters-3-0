-- Variants, live variants and price per experience shown on a __NAME__ (CE __CE__) page.
SELECT
    CAST(experience_id AS STRING) AS experience_id,
    ANY_VALUE(primary_sub_category_name) AS sub_category,
    COUNT(DISTINCT variant_id) AS variants,
    COUNT(DISTINCT IF(is_available, variant_id, NULL)) AS live_variants,
    MIN(IF(is_available, listing_final_price, NULL)) AS from_price

FROM `headout-analytics.analytics_reporting.dim_variants`

WHERE CAST(experience_id AS STRING) IN UNNEST(SPLIT('__EXPERIENCES__'))

GROUP BY 1
