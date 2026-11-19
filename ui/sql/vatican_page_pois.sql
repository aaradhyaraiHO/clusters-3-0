-- Names of the POIs and collections Vatican (CE 189) and Milford Sound Cruises (CE 3945) pages are tagged with in
-- Payload, so a page can be linked to the cluster about the same place by its tag rather than by its text.
WITH pois AS (

    SELECT
        'poi' AS entity_type,
        CAST(poi_id AS STRING) AS entity_id,
        poi_name AS name,
        CAST(parent_poi_id AS STRING) AS parent_id

    FROM `headout-analytics.analytics_reporting.dim_pois`

    WHERE poi_id IN ('1', '247', '766', '1025', '1034', '1338', '1373', '2794', '2795', '2796', '2797')

),


collections AS (

    SELECT
        'collection' AS entity_type,
        CAST(collection_id AS STRING) AS entity_id,
        collection_name AS name,
        CAST(NULL AS STRING) AS parent_id

    FROM `headout-analytics.analytics_reporting.dim_collections`

    WHERE collection_id IN ('189', '592', '3251', '3500', '7154', '3945', '7688', '7687', '5177', '3903', '5419', '7689')

),


final AS (

    SELECT * FROM pois

    UNION ALL

    SELECT * FROM collections

)


SELECT * FROM final
