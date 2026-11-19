# Clusters 3.0: where every number comes from

Phase 2.1 of the v2 plan. Goal from Parag (30 Oct): about 80% of the value from BigQuery and at most one or two
downloads, not many Google Ads API calls.

**Finding:** every P0 column already comes from BigQuery. No Ads API download is needed for the default table.
The Ads API is only needed for things not built yet: Google's search-term categories, Keyword Planner trends and bid
ranges.

Priority: **P0** = default table, **P1** = behind "+N" or in the side panel, **P2** = rarely read; candidate to drop.

## Clusters and demand

| Column | Rule | Source | Priority |
|---|---|---|---|
| Cluster, keywords, intent | EOS clusters re-assigned by the hybrid run | `segment-data.retooldb_prodreplica_log.public_mmp_keyword_cluster` + hybrid run (`clusters-3-0` worktree) | P0 |
| Searches / mo | Keyword Planner volume of the focus keyword; variants sharing one volume count once | Same EOS table (volume is monthly) | P0 |
| Keywords (count) | Keywords in the cluster after edits | Same | P1 |
| Organic capture | Organic clicks ÷ monthly demand | Satvik's capture run | P2 |

## Paid (search terms mapped to clusters)

Search terms map to clusters with the mapping run (exact keyword, translation, meaning match; single words only when
distinctive). Google names the search behind about 78% of paid clicks; the rest are hidden.

| Column | Rule | Source | Priority |
|---|---|---|---|
| Coverage | Paid impressions a month ÷ searches a month | `p_ads_SearchQueryStats_6251119615` | P0 |
| Paid clicks, Paid ROI | Clicks; conversion value ÷ spend | Same | P0 |
| CVR, CPC, Spend, Impressions, Conversion value, Avg CM1 | Ratios of the same rows | Same | P1 |
| AI Max share | Clicks with match type AI_MAX ÷ clicks | Same (match type) | P1 |
| Clicks, 13 weeks / ROI last week | Same rows by `segments_week` | Same | P1 |
| RPC, Paid revenue | Paid orders traced by gclid to a keyword, spread over clusters (74% traces) | `fct_orders_lambda` + click data | P1 |
| Quality Score | Impression-weighted keyword Quality Score | `p_ads_Keyword_6251119615` (`quality_info_*`) | P2 |
| Searches shown | Named search-term clicks ÷ keyword clicks | SearchQueryStats vs keyword totals | P2 |
| Keywords in Ads | Active keywords mapped to the cluster | `p_ads_Keyword_6251119615` | P2 |
| Target ROAS (side panel) | Campaign target | `p_ads_Campaign_6251119615` | P2 |
| Impression share, lost to rank (side panel) | Keyword report | `keyword_shares.csv` in the snapshot; source to confirm with Satvik | P2 |

## Own ad group

| Column | Rule | Source | Priority |
|---|---|---|---|
| Own ad group | Live ad groups bidding on the focus keyword (or a variant sharing its volume); core = the one with most clicks. Mostly bid: core holds 50%+ of the cluster's keyword volume. Focus only: less. Not bid: no live ad group bids on the focus keyword | `p_ads_Keyword_6251119615` (enabled keywords, 28 Oct) + keyword clicks + ad group / campaign status | P0 |

## Page and products

| Column | Rule | Source | Priority |
|---|---|---|---|
| Page | Cluster's main microbrand page (home for the head term) | `segment-data.payload_cms.payload_pages_v2` + page mapper | P0 |
| Where its ad group lands | Final URL with most clicks across the core ad group's ads | `p_ads_Ad_6251119615` (`final_urls`) + `p_ads_AdBasicStats_6251119615` | P0 |
| Products (sold of shown) | The landing page's collection ranking in Rome, latest run; sold = had orders in the window | `segment-data.product_rankings.product_rankings_created_v2` + `dim_experiences` + `fct_orders_lambda` | P0 |
| Product funnel S2C / C2O | Users, all channels | `mixpanel_user_page_funnel_progression` | P1 |
| Variants, availability, next date | Active variants with inventory open in 7 / 30 days | `dim_variants` + `dim_tour_profiles` | P1 |
| Organic clicks, position | Search Console on mapped queries | `gsc_terms.csv` in the snapshot | P1 |
| Headout entity, page revenue, share of CE | Collection / POI by name; orders landing on its pages | `dim_collections`, `dim_pois`, `fct_orders_lambda` | P1 |
| LP2S (side panel) | Paid sessions landing on a page that open a product | `mixpanel_user_page_funnel_progression` | P1 |

## What a new CE needs

1. The hybrid clustering run and the mapping run (pipeline, no Ads calls).
2. The SQL files in `sql/` with the CE's `cid` and collection ids swapped in.
3. No Ads API download for the default table. P2 columns can be dropped if their source is a problem.

## Known limits

- Products are per page, so every cluster landing on home shows the same list. That is what visitors see.
- Collection 7154 (Sistine Chapel) has no published ranking, so its pages show "No ranking".
- A generic focus keyword puts a cluster in a generic ad group (Tickets, Generic), which reads "Mostly bid". The ad group name under the label shows when that happens.
- Payload's `sub_category_id` on a page is not a listing filter, so products are not narrowed by it.
