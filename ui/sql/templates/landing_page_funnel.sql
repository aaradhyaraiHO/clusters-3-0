-- Google Ads search sessions on the __NAME__ microbrand (CE __CE__) by entry page, the pull window (window.py): how many
-- reach a product (select) page, start checkout and order. The funnel model has one row per page event, so a
-- session is rebuilt here and its entry page is its first page.
-- Filtered by the microbrand's domain, not combined_entity_id: Mixpanel files a page under its own collection
-- (/fly-to-milford-sound/ under 5177), so a CE filter drops every page with a collection of its own.
WITH events AS (

    SELECT
        session_id,
        user_id,
        event_timestamp,
        page_url,
        has_select_page_viewed,
        has_checkout_started,
        has_order_completed

    FROM `headout-analytics.analytics_reporting.mixpanel_user_page_funnel_progression`

    WHERE event_date >= '__START__'
          AND event_date <= '__END__'
          AND REGEXP_CONTAINS(page_url, r'^https?://(www\.)?__SITE_RE__/')
          AND channel_name = 'Google Ads'
          AND advertising_channel_type = 'SEARCH'
          AND is_microbrand_page

),


sessions AS (

    SELECT
        session_id,
        user_id,
        ARRAY_AGG(page_url ORDER BY event_timestamp LIMIT 1)[OFFSET(0)] AS entry_url,
        LOGICAL_OR(has_select_page_viewed) AS has_select,
        LOGICAL_OR(has_checkout_started) AS has_checkout,
        LOGICAL_OR(has_order_completed) AS has_order

    FROM events

    GROUP BY 1, 2

),


final AS (

    SELECT
        REGEXP_REPLACE(REGEXP_REPLACE(entry_url, r'[?#].*$', ''), r'^https?://(www\.)?', '') AS entry_page,
        COUNT(*) AS sessions,
        COUNTIF(has_select) AS select_sessions,
        COUNTIF(has_checkout) AS checkout_sessions,
        COUNTIF(has_order) AS order_sessions

    FROM sessions

    GROUP BY 1

)


SELECT * FROM final WHERE sessions >= 1
