-- Published microbrand pages of __NAME__ (CE __CE__): page type, the collection each page lists, and its
-- focus keyword, from the latest Payload extract per page and locale.
WITH latest AS (

    SELECT
        uid,
        locale,
        status,
        is_non_renderable,
        categorisation,
        meta

    FROM `segment-data.payload_cms.payload_pages_v2`

    WHERE STARTS_WITH(uid, '__HOST__')

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY uid, locale
        ORDER BY extracted_at DESC
    ) = 1

),


final AS (

    SELECT
        '__CE__' AS ce,
        uid,
        ANY_VALUE(JSON_VALUE(categorisation, '$.pageType')) AS page_type,
        ANY_VALUE(JSON_VALUE(categorisation, '$.pageSubType')) AS page_sub_type,
        ANY_VALUE(JSON_VALUE(categorisation, '$.collectionId')) AS collection_id,
        ANY_VALUE(JSON_VALUE(categorisation, '$.poiId')) AS poi_id,
        MAX(IF(locale = 'en', JSON_VALUE(meta, '$.title'), NULL)) AS title_en,
        MAX(IF(locale = 'en', JSON_VALUE(meta, '$.focusKeyword'), NULL)) AS focus_keyword_en,
        MAX(IF(locale = 'en', status, NULL)) AS status_en,
        LOGICAL_OR(SAFE_CAST(JSON_VALUE(meta, '$.noIndex') AS BOOL)) AS any_noindex,
        COUNTIF(status = 'published') AS published_locales

    FROM latest

    GROUP BY 1, 2

)


SELECT * FROM final
