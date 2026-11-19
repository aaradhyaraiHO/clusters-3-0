# Dummy run: launching Milford Sound Cruises as a new CE (2 Nov 2026)

Phase 5 of the v2 plan. Parag's question (30 Oct): if we launched a new non-POI CE today, could we get from keyword
research to launched clusters in a day, instead of months? Milford Sound Cruises (CE 3945) stands in: the full page
has its real ads data, and `?preview=newce` hides it so it reads as a new CE.

Page: `milford-clusters.html`; the new-CE view is `milford-clusters.html?preview=newce`.

## What it took

Milford now runs through the same export as Vatican, with its Google Ads and Search Console data. The "new CE" view
of Parag's question is the same page with ads hidden: `milford-clusters.html?preview=newce`.

| Step | How |
|---|---|
| Clusters and keywords | 11-CE hybrid run in the pipeline: 31 clusters (plus two Other buckets), 727 keywords |
| Google Ads and Search Console rows | Already in the pipeline's `20261030_validation_v1` snapshot; copied to `pipeline_local/snapshots/20261102_milford_full` |
| Search terms, organic queries and ad keywords to clusters | The pipeline's mapper, run from this worktree (`run_pipeline_local.py`): 99.3% of paid clicks and 91.6% of organic clicks map |
| Ad keywords per ad group, weekly terms, landing pages, funnels, variants, orders | `pull_ce.py 3945` from `sql/templates/` (originally `sql/milford_*.sql`): the Vatican queries with CE 3945's campaign tag, site and collections |
| File shapes, page mapping | `prepare_ce.py 3945` (originally `prepare_milford.py`): 21 of 26 pages map by meaning |
| The page | `export_hybrid.py <clusters_3_0> 3945`, then `build.py milford` |

Not loaded for Milford: Satvik's capture numbers, paid revenue traced by click, Headout entities. Each is a separate
pull that only Vatican had.

## What the BGM sees

Full page (with ads):
- **Analysis:** 31 clusters (15 buying), $101K paid spend at 140% ROI over 90 days, 12 clusters with a page. The head
  term carries 19,475 of 42K paid clicks.
- **Own ad group:** the head term, Tours / Day Trips and Queenstown are "Mostly bid"; Weather and Stirling Falls are
  "Not bid"; Overnight Cruises is "Focus only" through a Mitre Peak ad group.
- **Opportunities (13):** keywords to add (6, e.g. day cruise and Te Anau cruise keywords), searches losing money (2,
  both Queenstown day-trip keywords at ~50% ROI), ad group landing on the wrong page (2: Overnight Cruises and Scenic
  Flight land on home), clusters that need a page (3).

New-CE view (`?preview=newce`, ads and existing pages hidden):
- **Opportunities (9):** every buying cluster with 1,000+ searches a month needs a page, the head term first.
- **Launch, a cluster with no page (Kayak + Cruise Combos):** asks to create a child collection, asks to create
  `/milford-sound-kayak`, says the new page will list the new collection's products, raises a Content ticket, and asks
  to send Perf the cluster and its keywords.
- **Launch, a cluster with a page (Mitre Peak):** keeps `/mitre-peak` ("a new page isn't needed"), shows its products,
  skips content, and has no Perf ask for an informational cluster.
- **Execution:** one line per cluster for Catalog, Content, Products and Perf.

## What stands in the way of "a day"

1. **Clustering quality.** Several focus keywords are wrong for their cluster: Underwater Observatory's is "milford sound lodges", Stirling Falls' is "places to stay milford sound", Overnight Cruises' is "doubtful sound cruises overnight", Prices, Cost & Value's is "milford track reservations". Kayak pages land on Underwater Observatory because that cluster holds kayak keywords. This is the clustering prompts (Krupa, Harsha), and it decides everything after it.
2. **Page mapping.** 21 of 26 pages map, but the RealNZ and Southern Discoveries cruise pages land on Cruise Operators and Waterfalls, so "Day / Scenic / Nature Cruises" shows no page. The pipeline's page mapper, run per CE, should replace this script's simple match.
3. **Missing product types.** Still a stand-in: it needs the product-type list per cluster (Satvik, Shivam) to say "these archetypes are missing".
4. **Nothing is created.** Launch reports what it would do; creating collections, pages, subdomains and tickets needs the agent and the APIs behind it (Yuvraj, from ~16 Nov).

## Next

- Run the pipeline's page mapper for 3945 instead of `prepare_ce.py`'s match.
- Re-run with Krupa's prompt v2.1 clusters for Milford and compare the focus keywords.
- Agree the archetype list per cluster with Satvik and Shivam.
