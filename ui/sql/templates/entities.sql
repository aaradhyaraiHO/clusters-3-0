-- Headout entities under __NAME__ (CE __CE__) that a cluster's page can list instead of the CE collection itself:
--   collections: the CE collection's descendant collections;
--   POIs: children of the CE collection's POI, the POIs tagged on the CE's own published pages, and the primary POIs
--   of the experiences the CE collection and its descendants list (a CE collection with no POI, like Milford Sound's,
--   still reaches Mitre Peak this way). The CE's own POI is left out.
-- sub_category is a collection's primary sub-category (what it sells), a second name for matching clusters.
-- dim_pois has no active flag, so a POI counts as active. source says how each entity was found.
-- alt_names carries every language's display name, for matching non-English keywords.
WITH parent AS (

    SELECT
        collection_id,
        poi_id,
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
        child.url_slug,
        child.primary_sub_category_name AS sub_category,
        'descendant' AS source

    FROM parent
    CROSS JOIN UNNEST(parent.descendant_collections) AS descendant
    INNER JOIN `headout-analytics.analytics_reporting.dim_collections` AS child
        ON child.collection_id = descendant.collection_id

),


page_tags AS (

    SELECT
        JSON_VALUE(categorisation, '$.poiId') AS poi_id,
        'page_tag' AS source

    FROM `segment-data.payload_cms.payload_pages_v2`

    WHERE STARTS_WITH(uid, '__HOST__')
          AND status = 'published'
          AND JSON_VALUE(categorisation, '$.poiId') IS NOT NULL

    GROUP BY 1, 2

),


experience_pois AS (

    SELECT
        experiences.primary_poi_id AS poi_id,
        'experience' AS source

    FROM ce_collections
    INNER JOIN `headout-analytics.analytics_reporting.dim_collections` AS listing
        ON listing.collection_id = ce_collections.collection_id
    CROSS JOIN UNNEST(listing.experiences) AS listed
    INNER JOIN `headout-analytics.analytics_reporting.dim_experiences` AS experiences
        ON experiences.experience_id = listed.experience_id

    WHERE experiences.primary_poi_id IS NOT NULL

    GROUP BY 1, 2

),


child_pois AS (

    SELECT
        child.poi_id,
        'child_poi' AS source

    FROM parent
    INNER JOIN `headout-analytics.analytics_reporting.dim_pois` AS child
        ON child.parent_poi_id = parent.poi_id

),


poi_ids AS (

    SELECT
        poi_id,
        STRING_AGG(DISTINCT source, ',' ORDER BY source) AS source

    FROM (
        SELECT * FROM child_pois
        UNION ALL
        SELECT * FROM page_tags
        UNION ALL
        SELECT * FROM experience_pois
    )

    WHERE poi_id NOT IN (SELECT IFNULL(poi_id, '') FROM parent)

    GROUP BY 1

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
        TRUE AS is_active,
        CAST(NULL AS STRING) AS url_slug,
        CAST(NULL AS STRING) AS sub_category,
        poi_ids.source

    FROM poi_ids
    INNER JOIN `headout-analytics.analytics_reporting.dim_pois` AS child
        ON child.poi_id = poi_ids.poi_id

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
