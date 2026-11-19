-- EOS keyword clusters for the snapshot's MMPs: one row per cluster x keyword (latest keyword-research run per MMP).
-- Params: {mmp_cases} (CASE arms mapping mmp_id -> ce), {mmp_ids} (quoted, comma-separated)
-- The retool replica tables are change logs: keep the latest row per id and drop DELETEs.
WITH research AS (

    SELECT *

    FROM `segment-data.retooldb_prodreplica_log.public_mmp_keyword_research`

    WHERE mmp_id IN ({mmp_ids})

    QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY datastream_metadata.source_timestamp DESC) = 1
            AND datastream_metadata.change_type != 'DELETE'

),

latest_research AS (

    SELECT * FROM research

    QUALIFY ROW_NUMBER() OVER (PARTITION BY mmp_id ORDER BY updated_at DESC) = 1

),

clusters AS (

    SELECT cluster.*

    FROM `segment-data.retooldb_prodreplica_log.public_mmp_keyword_cluster` AS cluster
    INNER JOIN latest_research
        ON latest_research.id = cluster.mmp_keyword_research_id

    QUALIFY ROW_NUMBER() OVER (PARTITION BY cluster.id ORDER BY cluster.datastream_metadata.source_timestamp DESC) = 1
            AND cluster.datastream_metadata.change_type != 'DELETE'

)

SELECT
    CASE
        {mmp_cases}
    END AS ce,
    clusters.id AS cid,
    clusters.rank,
    clusters.cluster_type AS t,
    clusters.name,
    TO_JSON_STRING(clusters.cluster_identifiers) AS ids,
    JSON_VALUE(kw, '$.keyword') AS kw,
    SAFE_CAST(JSON_VALUE(kw, '$.volume') AS INT64) AS vol

FROM clusters
INNER JOIN latest_research
    ON latest_research.id = clusters.mmp_keyword_research_id
LEFT JOIN UNNEST(JSON_QUERY_ARRAY(clusters.keywords_volumes)) AS kw
