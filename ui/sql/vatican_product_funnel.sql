-- Select → checkout → order per matched experience on the Vatican CE, 30 Jul to 27 Oct 2026, counted in distinct
-- users across every channel, as the TGID funnel in scripts/market_weekly_review_v5.py (q_tgid_funnel) counts them.
-- That script reads mixpanel_user_funnel_progression, which only keeps about 18 days, so a 90-day window has to come
-- from the page-level table instead.
WITH funnel AS (

    SELECT
        experience_id,
        COUNT(DISTINCT IF(has_select_page_viewed, user_id, NULL)) AS count_select_users,
        COUNT(DISTINCT IF(has_checkout_started, user_id, NULL)) AS count_checkout_users,
        COUNT(DISTINCT IF(has_order_completed, user_id, NULL)) AS count_order_users

    FROM `headout-analytics.analytics_reporting.mixpanel_user_page_funnel_progression`

    WHERE event_date >= '2026-07-30'
          AND event_date <= '2026-10-27'
          AND combined_entity_id = '189'

    GROUP BY 1

)


SELECT * FROM funnel
