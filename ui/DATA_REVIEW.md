# Clusters 3.0: data review for Satwik

Where the code is and what to check before the metrics are trusted. The rules themselves are in the doc
"Clusters 3.0: workflows, pipelines and logic" (sections 4, 5 and 7).

## Where it lives

- Repo `analytics`, branch `worktree-clusters-3-0-ui`, folder `thoughts/shared/clusters-3.0/parag-v1/`.
- Clustering pipeline (seeds, clusters, mapper): branch `worktree-clusters-3-0`, folder `scripts/clusters_3_0/`.
- Built pages: `<slug>-clusters.html`, one per CE (Vatican, Milford, Park Güell, Great Barrier Reef).

## Run one CE

```
python3 run_ce.py 2743            # every step; --from export to resume
```

Needs `bq` signed in and the pipeline's venv at `scripts/clusters_3_0/.env-clusters/venv` (embedding model for the
mapper and the unclustered grouping).

## What to check, in order

1. `sql/templates/*.sql`: the 13 BigQuery pulls. Filters, the 30 Jul – 27 Oct window, and dedupe on Payload pages.
2. `export_hybrid.py`, the spread: Google Ads keyword totals are split over the search terms each keyword served, then
   summed per cluster (paid clicks, spend, conversions, conversion value). Check the weights and that cluster totals
   reconcile with the CE total (Milford 42,090 clicks / $103,341).
3. `export_hybrid.py`, landing pages: per-cluster landing rows are the serving ad groups' results × this cluster's
   share of each ad group's clicks. They are estimates, so the tool shows no landing-page ROI.
4. `paid_orders_by_click.sql`: revenue traced to paid clicks (62–78% of paid revenue traced across CEs).
5. `landing_page_funnel.sql`: Mixpanel entry-page funnel, folded to the page's path; locale homes are not tracked.
6. Vatican's two spend totals for the same window: keyword totals $547K vs an earlier source $425K.

## Files written per CE

`<out>/<query>_<ce>.csv` from the pulls; `<out>/<data>.json`, `drawer.json`, `impression_share.json` from the export.
The registry is `ces.json`.
