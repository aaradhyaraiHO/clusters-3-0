-- Product blocks on the Vatican (CE 189) and Milford Sound Cruises (CE 3945) microbrand pages, from the latest English
-- Payload extract: each block's display limit, sub-category / category filter, page-level pins (commonRanks) and
-- exclusions. The page shows its collection's ranking after these rules (ranking-mappings/00-mapping-model.md).
WITH latest AS (

    SELECT
        uid,
        product_card_blocks

    FROM `segment-data.payload_cms.payload_pages_v2`

    WHERE locale = 'en'
          AND (STARTS_WITH(uid, 'www.thevaticantickets.com') OR STARTS_WITH(uid, 'www.milford-sound-cruises.co.nz'))

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY uid
        ORDER BY extracted_at DESC
    ) = 1

),


final AS (

    SELECT
        latest.uid,
        SAFE_CAST(JSON_VALUE(block, '$.position') AS INT64) AS block_position,
        JSON_VALUE(block, '$.block_type') AS block_type,
        JSON_VALUE(block, '$.block_data.variants[0].blockType') AS variant_type,
        SAFE_CAST(JSON_VALUE(block, '$.block_data.variants[0].experienceLimit') AS INT64) AS experience_limit,
        JSON_VALUE(block, '$.block_data.variants[0].filterBySubCategoryId') AS filter_sub_category_id,
        JSON_VALUE(block, '$.block_data.variants[0].filterByCategoryId') AS filter_category_id,
        TO_JSON_STRING(JSON_QUERY(block, '$.block_data.variants[0].commonRanks')) AS common_ranks,
        TO_JSON_STRING(JSON_QUERY(block, '$.block_data.variants[0].commonExclusions')) AS common_exclusions

    FROM latest
    CROSS JOIN UNNEST(JSON_QUERY_ARRAY(latest.product_card_blocks)) AS block

)


SELECT * FROM final
