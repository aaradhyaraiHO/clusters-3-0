-- Headout entities under __NAME__ (CE __CE__): the CE collection's descendant collections and the POIs whose parent is
-- the CE collection's POI. These are what a cluster's page can list instead of the CE collection itself.
-- alt_names carries every language's display name, for matching non-English keywords.
WITH parent AS (

    SELECT
        collection_id,
        poi_id,
        descendant_collections

    FROM `headout-analytics.analytics_reporting.dim_collections`

    WHERE collection_id = '__CE__'

),


collections AS (

    SELECT
        'collection' AS entity_type,
        child.collection_id AS entity_id,
        child.collection_name AS name,
        ARRAY_TO_STRING(ARRAY(
            SELECT DISTINCT content.display_name
            FROM UNNEST(child.language_content_data) AS content
            WHERE content.display_name IS NOT NULL
        ), ' | ') AS alt_names,
        child.is_active,
        child.url_slug

    FROM parent
    CROSS JOIN UNNEST(parent.descendant_collections) AS descendant
    INNER JOIN `headout-analytics.analytics_reporting.dim_collections` AS child
        ON child.collection_id = descendant.collection_id

),


pois AS (

    SELECT
        'poi' AS entity_type,
        child.poi_id AS entity_id,
        child.poi_name AS name,
        ARRAY_TO_STRING(ARRAY(
            SELECT DISTINCT display.display_name
            FROM UNNEST(child.display_name) AS display
            WHERE display.display_name IS NOT NULL
        ), ' | ') AS alt_names,
        CAST(NULL AS BOOL) AS is_active,
        CAST(NULL AS STRING) AS url_slug

    FROM parent
    INNER JOIN `headout-analytics.analytics_reporting.dim_pois` AS child
        ON child.parent_poi_id = parent.poi_id

),


final AS (

    SELECT * FROM collections

    UNION ALL

    SELECT * FROM pois

)


SELECT
    '__CE__' AS ce,
    *

FROM final
