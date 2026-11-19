-- Every variant of the experiences shown on a Vatican (CE 189) page or matched to its clusters, with tours, vendor and whether
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

    WHERE experience_id IN UNNEST(SPLIT('3063,3137,3161,3166,3225,3228,3241,3361,3383,3725,3832,3853,3865,3876,3937,4019,6706,6707,6730,6732,6796,7022,7023,7422,7451,7464,7491,7761,7818,7827,7953,7955,7967,7968,7969,7971,7998,8846,8847,9092,9264,9267,9378,9379,9682,9910,9993,10253,10424,10479,10480,10644,10757,15084,15143,15144,15248,15249,15315,15414,15436,15438,15487,15839,15847,15856,15947,16135,16466,16551,16552,17798,18300,20032,20082,20195,25598,28530,28867,28869,28870,29116,29277,29998,31786,32197,33032,36101,36212,36265,36297,36641,36702,38585,39151,39152,42091,42093,42095,42741,42841,42842,43592,45695,46090,47039,47113,47114,47134,48055,48477,48825,50331,53876,54121,54334,54814,56096,56793,57134,57182,57897,58104,58636,59617,59961,59995,60100'))

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
