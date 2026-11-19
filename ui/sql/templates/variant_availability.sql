-- Every variant of the experiences shown on a __NAME__ (CE __CE__) page, with tours, vendor and whether
-- inventory is open in the next 7 and 30 days (dim_tour_profiles, latest profile per tour).
WITH variants AS (

    SELECT
        experience_id,
        variant_id,
        variant_name,
        variant_status,
        is_available,
        next_available_date,
        listing_final_price,
        average_rating,
        count_ratings,
        tours

    FROM `headout-analytics.analytics_reporting.dim_variants`

    WHERE experience_id IN UNNEST(SPLIT('__EXPERIENCES__'))

),


tour_status AS (

    SELECT
        tour_id,
        ANY_VALUE(vendor_name) AS vendor_name,
        LOGICAL_OR(vendor_tour_is_available_7d = 'Available') AS is_available_7d,
        LOGICAL_OR(vendor_tour_is_available_30d = 'Available') AS is_available_30d,
        MIN(vendor_tour_next_available_date) AS next_available_date

    FROM `headout-analytics.analytics_reporting.dim_tour_profiles`

    WHERE tour_id IN (SELECT tour.tour_id FROM variants, UNNEST(tours) AS tour)

    GROUP BY 1

),


final AS (

    SELECT
        variants.experience_id,
        variants.variant_id,
        variants.variant_name,
        variants.variant_status,
        variants.is_available,
        variants.next_available_date,
        variants.listing_final_price,
        variants.average_rating,
        variants.count_ratings,
        STRING_AGG(tour.tour_id, ' ' ORDER BY tour.tour_priority) AS tour_ids,
        STRING_AGG(DISTINCT tour_status.vendor_name, ', ') AS vendors,
        LOGICAL_OR(tour_status.is_available_7d) AS is_available_7d,
        LOGICAL_OR(tour_status.is_available_30d) AS is_available_30d

    FROM variants
    LEFT JOIN UNNEST(variants.tours) AS tour
    LEFT JOIN tour_status
        ON tour.tour_id = tour_status.tour_id

    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9

)


SELECT * FROM final
