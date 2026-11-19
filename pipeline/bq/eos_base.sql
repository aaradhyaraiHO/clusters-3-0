-- Clusters 3.0, BigQuery step 1: EOS base, clean-up and list checks for every CE with an EOS cluster list.
-- Writes to headout-dev.dbt_aaradhya (prefix clusters_3_0_); reads segment-data.retooldb_prodreplica_log (EU).
-- Run: bq query --use_legacy_sql=false --location=EU --project_id=headout-dev < bq/eos_base.sql
--   clusters_3_0_eos_keywords        latest EOS list per CE, one row per cluster x keyword (as EOS stores it)
--   clusters_3_0_eos_keywords_clean  normalised keyword, spelling group, competitor flag, one cluster per keyword
--   clusters_3_0_list_checks         head term, overlap, duplicates, catch-all (pass/fail) + scope flag, per CE

-- Lowercase, accents removed, every non-letter/digit run becomes one space (keeps every script, as the Python mapper does)
CREATE TEMP FUNCTION norm(s STRING) AS (
    TRIM(REGEXP_REPLACE(REGEXP_REPLACE(NORMALIZE(LOWER(s), NFD), r'\p{M}', ''), r'[^\p{L}\p{N}]+', ' '))
);
-- Plural folded so "tickets" and "ticket" fall in one spelling group
CREATE TEMP FUNCTION singular(w STRING) AS (
    IF(LENGTH(w) > 3 AND ENDS_WITH(w, 's') AND NOT ENDS_WITH(w, 'ss'), SUBSTR(w, 1, LENGTH(w) - 1), w)
);
CREATE TEMP FUNCTION stopword(w STRING) AS (
    w IN ('the', 'and', 'for', 'with', 'from', 'how', 'what', 'can', 'you', 'are', 'does', 'near', 'in', 'of', 'to', 'a',
          'de', 'del', 'la', 'le', 'les', 'el', 'di', 'il', 'das', 'der', 'die', 'na', 'do', 'du', 'et', 'y', 'e', 'und',
          'per', 'pour', 'para', 'at', 'on', 'is', 'it')
);
-- Product words in CE names ("Milford Sound Cruises", "Eiffel Tower Tickets"): the head term is the name without them
CREATE TEMP FUNCTION product_word(w STRING) AS (
    w IN ('ticket', 'tour', 'cruise', 'trip', 'experience', 'show', 'pass', 'entry', 'admission', 'booking')
);

CREATE OR REPLACE TABLE `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords` AS

WITH mmp AS (

    SELECT * FROM `segment-data.retooldb_prodreplica_log.public_mmp`

    QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY datastream_metadata.source_timestamp DESC) = 1
            AND datastream_metadata.change_type != 'DELETE'

),

research AS (

    SELECT * FROM `segment-data.retooldb_prodreplica_log.public_mmp_keyword_research`

    QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY datastream_metadata.source_timestamp DESC) = 1
            AND datastream_metadata.change_type != 'DELETE'

),

latest_research AS (

    SELECT * FROM research

    QUALIFY ROW_NUMBER() OVER (PARTITION BY mmp_id ORDER BY updated_at DESC) = 1

),

clusters AS (

    SELECT * FROM `segment-data.retooldb_prodreplica_log.public_mmp_keyword_cluster`

    QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY datastream_metadata.source_timestamp DESC) = 1
            AND datastream_metadata.change_type != 'DELETE'

)

SELECT
    CAST(mmp.ce_id AS STRING) AS ce_id,
    mmp.ce_name,
    mmp.city,
    mmp.id AS mmp_id,
    clusters.id AS cluster_id,
    clusters.rank AS cluster_rank,
    clusters.cluster_type,
    clusters.name AS cluster_name,
    JSON_VALUE(kw, '$.keyword') AS keyword,
    SAFE_CAST(JSON_VALUE(kw, '$.volume') AS INT64) AS volume,
    kw_pos AS keyword_position

FROM clusters
INNER JOIN latest_research
    ON latest_research.id = clusters.mmp_keyword_research_id
INNER JOIN mmp
    ON mmp.id = latest_research.mmp_id
CROSS JOIN UNNEST(JSON_QUERY_ARRAY(clusters.keywords_volumes)) AS kw WITH OFFSET AS kw_pos

WHERE mmp.ce_id IS NOT NULL
      AND JSON_VALUE(kw, '$.keyword') IS NOT NULL;


CREATE OR REPLACE TABLE `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords_clean` AS

WITH base AS (

    SELECT
        *,
        norm(keyword) AS keyword_norm,
        -- Spelling group: the keyword's distinct words, plural folded, stopwords dropped, in alphabetical order
        (
            SELECT STRING_AGG(DISTINCT singular(w), ' ' ORDER BY singular(w))
            FROM UNNEST(SPLIT(norm(keyword), ' ')) AS w
            WHERE w != '' AND NOT stopword(w)
        ) AS spelling_group,
        REGEXP_CONTAINS(norm(keyword), r'\b(tiqets|getyourguide|get your guide|gyg|klook|viator|musement|civitatis|tripadvisor|city wonders|walks of italy|headout|go city|isango)\b') AS is_competitor

    FROM `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords`

),

dedup AS (

    -- A keyword EOS put in two clusters stays in the one holding more of its spelling group's volume
    SELECT
        base.*,
        COUNT(DISTINCT cluster_id) OVER (PARTITION BY ce_id, keyword_norm) AS clusters_holding_keyword

    FROM base

    WHERE keyword_norm != ''

),

group_volume AS (

    SELECT
        ce_id,
        cluster_id,
        spelling_group,
        SUM(COALESCE(volume, 0)) AS group_volume_in_cluster

    FROM dedup

    GROUP BY 1, 2, 3

)

SELECT
    dedup.*

FROM dedup
LEFT JOIN group_volume
    USING (ce_id, cluster_id, spelling_group)

QUALIFY ROW_NUMBER() OVER (
    PARTITION BY dedup.ce_id, dedup.keyword_norm
    ORDER BY group_volume.group_volume_in_cluster DESC, dedup.cluster_rank ASC, dedup.keyword_position ASC
) = 1;


CREATE OR REPLACE TABLE `headout-dev.dbt_aaradhya.clusters_3_0_list_checks` AS

WITH kw AS (

    -- The checks run on the cleaned list: competitor keywords removed, one cluster per keyword
    SELECT
        *,
        GREATEST(COALESCE(volume, 0), 10) AS weight

    FROM `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords_clean`

    WHERE NOT is_competitor

),

ce_totals AS (

    SELECT
        ce_id,
        ANY_VALUE(ce_name) AS ce_name,
        ANY_VALUE(city) AS city,
        COUNT(DISTINCT cluster_id) AS clusters,
        COUNT(*) AS keywords

    FROM kw

    GROUP BY 1

),

ce AS (

    SELECT
        *,
        -- Head-term words: the CE name without product words, plural folded
        ARRAY(
            SELECT DISTINCT singular(w)
            FROM UNNEST(SPLIT(norm(ce_name), ' ')) AS w
            WHERE w != '' AND NOT stopword(w) AND NOT product_word(singular(w))
        ) AS name_words,
        ARRAY(SELECT DISTINCT w FROM UNNEST(SPLIT(norm(city), ' ')) AS w WHERE w != '') AS city_words

    FROM ce_totals

),

head AS (

    -- Head keywords: every word is a CE-name or city word, and the whole name is there ("milford sound", "musei vaticani" do not count)
    SELECT
        kw.ce_id,
        kw.cluster_name,
        SUM(kw.weight) AS head_weight

    FROM kw
    INNER JOIN ce
        USING (ce_id)

    WHERE (
            SELECT LOGICAL_AND(singular(w) IN UNNEST(ce.name_words) OR w IN UNNEST(ce.city_words) OR stopword(w))
            FROM UNNEST(SPLIT(kw.keyword_norm, ' ')) AS w
        )
          AND (
            SELECT LOGICAL_AND(n IN UNNEST(ARRAY(SELECT singular(w) FROM UNNEST(SPLIT(kw.keyword_norm, ' ')) AS w)))
            FROM UNNEST(ce.name_words) AS n
        )

    GROUP BY 1, 2

),

head_check AS (

    SELECT
        ce_id,
        SUM(head_weight) AS head_weight,
        MAX(head_weight) / SUM(head_weight) AS head_share_top_cluster,
        ARRAY_AGG(cluster_name ORDER BY head_weight DESC LIMIT 1)[OFFSET(0)] AS head_cluster,
        STRING_AGG(FORMAT('%s (%.0f%%)', cluster_name, 100 * head_weight / total), '; ' ORDER BY head_weight DESC) AS head_spread

    FROM (SELECT *, SUM(head_weight) OVER (PARTITION BY ce_id) AS total FROM head)

    GROUP BY 1

),

group_split AS (

    -- Overlap: a spelling group whose variants sit in two or more clusters ("milford sound cruise" vs "cruise milford sound")
    SELECT
        ce_id,
        spelling_group,
        COUNT(DISTINCT cluster_name) AS clusters_holding_group,
        SUM(weight) AS group_weight,
        STRING_AGG(DISTINCT cluster_name, ' | ') AS clusters

    FROM kw

    GROUP BY 1, 2

),

overlap_check AS (

    SELECT
        group_split.ce_id,
        SUM(IF(clusters_holding_group > 1, group_weight, 0)) / SUM(group_weight) AS split_share,
        COUNTIF(clusters_holding_group > 1) AS split_groups,
        STRING_AGG(IF(clusters_holding_group > 1, FORMAT('"%s": %s', spelling_group, clusters), NULL), '; ' ORDER BY group_weight DESC LIMIT 5) AS top_splits

    FROM group_split

    GROUP BY 1

),

dup_check AS (

    SELECT
        ce_id,
        COUNTIF(clusters_holding_keyword > 1) AS keywords_in_two_clusters,
        COUNTIF(is_competitor) AS competitor_keywords

    FROM `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords_clean`

    GROUP BY 1

),

cluster_size AS (

    SELECT
        ce_id,
        cluster_name,
        COUNT(*) AS cluster_keywords,
        -- Scope flag: share of the cluster's volume whose keywords carry no CE-name or city word (review, not pass/fail)
        SUM(IF((
            SELECT LOGICAL_OR(singular(w) IN UNNEST(ce.name_words) OR w IN UNNEST(ce.city_words))
            FROM UNNEST(SPLIT(kw.keyword_norm, ' ')) AS w
        ), 0, kw.weight)) / SUM(kw.weight) AS share_without_ce_words

    FROM kw
    INNER JOIN ce
        USING (ce_id)

    GROUP BY 1, 2

),

catchall_check AS (

    SELECT
        cluster_size.ce_id,
        MAX(cluster_keywords) / ANY_VALUE(ce.keywords) AS largest_cluster_share,
        ARRAY_AGG(cluster_name ORDER BY cluster_keywords DESC LIMIT 1)[OFFSET(0)] AS largest_cluster,
        STRING_AGG(IF(REGEXP_CONTAINS(LOWER(cluster_name), r'\b(general|other|misc|miscellaneous|unassigned|about)\b'), cluster_name, NULL), '; ') AS catchall_named,
        STRING_AGG(IF(share_without_ce_words > 0.5, cluster_name, NULL), '; ' ORDER BY cluster_name) AS scope_review

    FROM cluster_size
    INNER JOIN ce
        USING (ce_id)

    GROUP BY 1

)

SELECT
    ce.ce_id,
    ce.ce_name,
    ce.clusters,
    ce.keywords,
    COALESCE(head_check.head_share_top_cluster >= 0.8, FALSE) AS is_head_ok,
    head_check.head_cluster,
    head_check.head_spread,
    overlap_check.split_share < 0.05 AS is_overlap_ok,
    overlap_check.split_share,
    overlap_check.split_groups,
    overlap_check.top_splits,
    dup_check.keywords_in_two_clusters = 0 AS is_duplicates_ok,
    dup_check.keywords_in_two_clusters,
    dup_check.competitor_keywords,
    catchall_check.largest_cluster_share <= 0.25 AND catchall_check.catchall_named IS NULL AS is_catchall_ok,
    catchall_check.largest_cluster,
    catchall_check.largest_cluster_share,
    catchall_check.catchall_named,
    catchall_check.scope_review,
    COALESCE(head_check.head_share_top_cluster >= 0.8, FALSE)
        AND overlap_check.split_share < 0.05
        AND dup_check.keywords_in_two_clusters = 0
        AND catchall_check.largest_cluster_share <= 0.25
        AND catchall_check.catchall_named IS NULL AS is_list_ok

FROM ce
LEFT JOIN head_check
    USING (ce_id)
LEFT JOIN overlap_check
    USING (ce_id)
LEFT JOIN dup_check
    USING (ce_id)
LEFT JOIN catchall_check
    USING (ce_id);
