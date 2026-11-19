-- Ranking Workbench pins live today on the Vatican and Milford Sound Cruises collections: the latest override event per
-- collection holds its full list (an empty list clears it); a pin counts only until its expiry. The workbench reads
-- this table since 27 Oct; the request sheet and product_rankings.ranking_overrides are retired.
WITH events AS (

    SELECT
        JSON_VALUE(payload, '$.entityId') AS collection_id,
        payload,
        event_timestamp

    FROM `segment-data.event_pipeline.product_ranking_overrides_updated`

    WHERE JSON_VALUE(payload, '$.entityType') = 'collection'
          AND JSON_VALUE(payload, '$.entityId') IN ('189', '592', '3251', '3500', '7154', '3945', '7688', '7687', '5177', '3903', '5419', '7689')

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY JSON_VALUE(payload, '$.entityId')
        ORDER BY event_timestamp DESC, server_timestamp DESC
    ) = 1

),


final AS (

    SELECT
        events.collection_id,
        events.event_timestamp,
        JSON_VALUE(item, '$.experience_id') AS experience_id,
        SAFE_CAST(JSON_VALUE(item, '$.position') AS INT64) AS position,
        JSON_VALUE(item, '$.expiry') AS expiry,
        JSON_VALUE(item, '$.reason_label') AS reason,
        JSON_VALUE(item, '$.comment') AS comment,
        JSON_VALUE(item, '$.requested_by') AS requested_by,
        JSON_VALUE(item, '$.requested_at') AS requested_at

    FROM events
    CROSS JOIN UNNEST(JSON_QUERY_ARRAY(events.payload, '$.overrides')) AS item

    WHERE SAFE_CAST(JSON_VALUE(item, '$.expiry') AS DATE) >= CURRENT_DATE()

)


SELECT * FROM final
