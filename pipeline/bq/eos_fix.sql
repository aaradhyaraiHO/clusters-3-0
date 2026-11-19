-- Clusters 3.0, BigQuery step 1c: automatic fix for the two most common EOS list failures.
-- Every keyword in a catch-all cluster ("(General)", "Other", "About", "Misc", "Unassigned") moves to the specific cluster
-- the first matching rule picks; the EOS tables are never changed.
--   1 head      only CE-name, city and product words ("milford sound cruises")      -> the head-term cluster
--   2 spelling  its spelling group already sits in a specific cluster                -> that cluster
--   3 ads       Google serves this exact search mostly from one specific cluster's keywords -> that cluster
--   4 words     best score: distinctive-word hits in a specific cluster's keywords, +10 when the cluster is named after
--               the keyword's product ("tickets" -> a Tickets cluster); score 2+ -> that cluster
--   otherwise   it stays in the catch-all and is reported as left over
-- Needs bq/eos_base.sql and bq/ads_overlap.sql first. Then bq/run_fixed_checks.sh re-runs every check on the fixed list.
--   clusters_3_0_eos_keywords_fixed  same columns as clusters_3_0_eos_keywords_clean, with the moves applied
--   clusters_3_0_eos_fix_log         one row per moved (or left-over) keyword: from, to, rule

CREATE TEMP FUNCTION norm(s STRING) AS (
    TRIM(REGEXP_REPLACE(REGEXP_REPLACE(NORMALIZE(LOWER(s), NFD), r'\p{M}', ''), r'[^\p{L}\p{N}]+', ' '))
);
CREATE TEMP FUNCTION singular(w STRING) AS (
    IF(LENGTH(w) > 3 AND ENDS_WITH(w, 's') AND NOT ENDS_WITH(w, 'ss'), SUBSTR(w, 1, LENGTH(w) - 1), w)
);
CREATE TEMP FUNCTION stopword(w STRING) AS (
    w IN ('the', 'and', 'for', 'with', 'from', 'how', 'what', 'can', 'you', 'are', 'does', 'near', 'in', 'of', 'to', 'a',
          'de', 'del', 'la', 'le', 'les', 'el', 'di', 'il', 'das', 'der', 'die', 'na', 'do', 'du', 'et', 'y', 'e', 'und',
          'per', 'pour', 'para', 'at', 'on', 'is', 'it')
);
-- Generic product words: a keyword made only of these plus the CE name is the landing (head-term) demand
CREATE TEMP FUNCTION product_word(w STRING) AS (
    w IN ('ticket', 'tour', 'cruise', 'trip', 'experience', 'show', 'pass', 'entry', 'admission', 'booking', 'book',
          'boat', 'day', 'excursion', 'visit', 'price', 'cost', 'online', 'best', 'buy', 'reservation', 'guided',
          'billet', 'biglietto', 'biglietti', 'entrada', 'eintritt', 'crucero', 'croisiere', 'kreuzfahrt', 'bootstour',
          'visita', 'tickets')
);
-- The product a word names, in English as cluster names are: "biglietti", "entradas", "bilete" -> ticket
CREATE TEMP FUNCTION product_of(w STRING) AS (
    CASE
        WHEN w IN ('ticket', 'tickets', 'biglietto', 'biglietti', 'billet', 'billets', 'entrada', 'entradas', 'eintritt',
                   'bilete', 'bilet', 'bilety', 'ingresso', 'ingressos', 'boletos', 'karten', 'admission', 'entry') THEN 'ticket'
        WHEN w IN ('tour', 'tours', 'visita', 'visite', 'fuhrung', 'excursion', 'excursiones') THEN 'tour'
        WHEN w IN ('cruise', 'cruises', 'crucero', 'cruceros', 'croisiere', 'kreuzfahrt', 'boat', 'boats', 'bootstour') THEN 'cruise'
        WHEN w IN ('price', 'prices', 'cost', 'costs', 'prezzo', 'precio', 'precios', 'prix', 'preis') THEN 'price'
        WHEN w IN ('book', 'booking', 'reservation', 'reserve', 'prenotazione', 'reserva') THEN 'book'
    END
);
CREATE TEMP FUNCTION catchall(name STRING) AS (
    REGEXP_CONTAINS(LOWER(name), r'\b(general|other|others|misc|miscellaneous|unassigned|about)\b')
);

CREATE OR REPLACE TABLE `headout-dev.dbt_aaradhya.clusters_3_0_eos_fix_log` AS

WITH kw AS (

    SELECT * FROM `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords_clean`

    WHERE NOT is_competitor

),

ce_city AS (

    SELECT
        ce_id,
        ANY_VALUE(city) AS city

    FROM kw

    GROUP BY 1

),

ce AS (

    SELECT
        checks.ce_id,
        IF(checks.is_head_ok, checks.head_cluster, NULL) AS head_cluster,
        ARRAY(
            SELECT DISTINCT singular(w)
            FROM UNNEST(SPLIT(norm(checks.ce_name), ' ')) AS w
            WHERE w != '' AND NOT stopword(w)
        ) AS name_words,
        ARRAY(SELECT DISTINCT w FROM UNNEST(SPLIT(norm(ce_city.city), ' ')) AS w WHERE w != '') AS city_words

    FROM `headout-dev.dbt_aaradhya.clusters_3_0_list_checks` AS checks
    INNER JOIN ce_city
        USING (ce_id)

),

catch AS (

    SELECT kw.*
    FROM kw
    WHERE catchall(kw.cluster_name)

),

specific AS (

    SELECT kw.*
    FROM kw
    WHERE NOT catchall(kw.cluster_name)

),

rule_head AS (

    SELECT
        catch.ce_id,
        catch.keyword_norm,
        ce.head_cluster AS to_cluster

    FROM catch
    INNER JOIN ce
        USING (ce_id)

    WHERE ce.head_cluster IS NOT NULL
          AND (
            SELECT LOGICAL_AND(singular(w) IN UNNEST(ce.name_words) OR w IN UNNEST(ce.city_words) OR product_word(singular(w)) OR product_word(w) OR stopword(w))
            FROM UNNEST(SPLIT(catch.keyword_norm, ' ')) AS w
        )

),

rule_spelling AS (

    SELECT
        catch.ce_id,
        catch.keyword_norm,
        ARRAY_AGG(specific.cluster_name ORDER BY specific.volume DESC LIMIT 1)[OFFSET(0)] AS to_cluster

    FROM catch
    INNER JOIN specific
        ON specific.ce_id = catch.ce_id
        AND specific.spelling_group = catch.spelling_group

    GROUP BY 1, 2

),

rule_ads AS (

    SELECT
        catch.ce_id,
        catch.keyword_norm,
        terms.top_cluster AS to_cluster

    FROM catch
    INNER JOIN `headout-dev.dbt_aaradhya.clusters_3_0_ads_overlap_terms` AS terms
        ON terms.ce_id = catch.ce_id
        AND terms.term = catch.keyword_norm

    WHERE NOT catchall(terms.top_cluster)
          AND terms.top_cluster_share >= 0.5

),

word_hits AS (

    -- Distinctive words of each catch-all keyword, counted in each specific cluster's keywords
    SELECT
        catch.ce_id,
        catch.keyword_norm,
        specific.cluster_name,
        COUNT(*) AS hits

    FROM catch
    INNER JOIN ce
        USING (ce_id)
    CROSS JOIN UNNEST(SPLIT(catch.keyword_norm, ' ')) AS w
    INNER JOIN specific
        ON specific.ce_id = catch.ce_id
        AND REGEXP_CONTAINS(CONCAT(' ', specific.keyword_norm, ' '), CONCAT(' ', w, 's? '))

    WHERE LENGTH(w) > 2
          AND NOT stopword(w)
          AND NOT product_word(singular(w))
          AND NOT product_word(w)
          AND singular(w) NOT IN UNNEST(ce.name_words)
          AND w NOT IN UNNEST(ce.city_words)

    GROUP BY 1, 2, 3

),

product_hits AS (

    -- A product word in the keyword points to the specific cluster named after that product ("tickets" -> a Tickets
    -- cluster), so "sixtijnse kapel tickets" is not pulled into "Sistine Chapel Art & Ceiling" by the place words alone
    SELECT DISTINCT
        catch.ce_id,
        catch.keyword_norm,
        specific.cluster_name,
        1 AS is_product

    FROM catch
    CROSS JOIN UNNEST(SPLIT(catch.keyword_norm, ' ')) AS w
    INNER JOIN specific
        ON specific.ce_id = catch.ce_id
        AND REGEXP_CONTAINS(LOWER(specific.cluster_name), CONCAT(r'\b', product_of(w)))

    WHERE product_of(w) IS NOT NULL

),

cluster_volume AS (

    SELECT
        ce_id,
        cluster_name,
        SUM(COALESCE(volume, 0)) AS cluster_volume

    FROM specific

    GROUP BY 1, 2

),

scored AS (

    SELECT
        ce_id,
        keyword_norm,
        cluster_name,
        COALESCE(word_hits.hits, 0) + 10 * COALESCE(product_hits.is_product, 0) AS score,
        cluster_volume.cluster_volume

    FROM word_hits
    FULL OUTER JOIN product_hits
        USING (ce_id, keyword_norm, cluster_name)
    LEFT JOIN cluster_volume
        USING (ce_id, cluster_name)

),

rule_words AS (

    SELECT
        ce_id,
        keyword_norm,
        ARRAY_AGG(cluster_name ORDER BY score DESC, cluster_volume DESC LIMIT 1)[OFFSET(0)] AS to_cluster

    FROM scored

    WHERE score >= 2

    GROUP BY 1, 2

)

SELECT
    catch.ce_id,
    catch.keyword,
    catch.keyword_norm,
    catch.volume,
    catch.cluster_name AS from_cluster,
    COALESCE(rule_head.to_cluster, rule_spelling.to_cluster, rule_ads.to_cluster, rule_words.to_cluster, catch.cluster_name) AS to_cluster,
    CASE
        WHEN rule_head.to_cluster IS NOT NULL THEN 'head'
        WHEN rule_spelling.to_cluster IS NOT NULL THEN 'spelling'
        WHEN rule_ads.to_cluster IS NOT NULL THEN 'ads'
        WHEN rule_words.to_cluster IS NOT NULL THEN 'words'
        ELSE 'left over'
    END AS rule

FROM catch
LEFT JOIN rule_head
    USING (ce_id, keyword_norm)
LEFT JOIN rule_spelling
    USING (ce_id, keyword_norm)
LEFT JOIN rule_ads
    USING (ce_id, keyword_norm)
LEFT JOIN rule_words
    USING (ce_id, keyword_norm);


CREATE OR REPLACE TABLE `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords_fixed` AS

WITH cluster_meta AS (

    SELECT
        ce_id,
        cluster_name,
        ANY_VALUE(cluster_id) AS cluster_id,
        ANY_VALUE(cluster_rank) AS cluster_rank,
        ANY_VALUE(cluster_type) AS cluster_type

    FROM `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords_clean`

    GROUP BY 1, 2

)

SELECT
    clean.* REPLACE (
        COALESCE(cluster_meta.cluster_id, clean.cluster_id) AS cluster_id,
        COALESCE(cluster_meta.cluster_rank, clean.cluster_rank) AS cluster_rank,
        COALESCE(cluster_meta.cluster_type, clean.cluster_type) AS cluster_type,
        COALESCE(fix.to_cluster, clean.cluster_name) AS cluster_name,
        1 AS clusters_holding_keyword
    )

FROM `headout-dev.dbt_aaradhya.clusters_3_0_eos_keywords_clean` AS clean
LEFT JOIN `headout-dev.dbt_aaradhya.clusters_3_0_eos_fix_log` AS fix
    ON fix.ce_id = clean.ce_id
    AND fix.keyword_norm = clean.keyword_norm
    AND NOT clean.is_competitor
LEFT JOIN cluster_meta
    ON cluster_meta.ce_id = clean.ce_id
    AND cluster_meta.cluster_name = fix.to_cluster;
