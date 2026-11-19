# Adding a CE

One command does every step below: `python3 run_ce.py <CE id>`. It registers a new CE in `ces.json` (name from the
clustering snapshot, site from the CE's Payload home page, name words from its name, head cluster from the cluster
names), then runs pull, map, prepare, group, facts, export and build. `--from <step>` resumes after a fix; `--host`
names the site when the CE has no microbrand of its own (its home page sits under a city site). Great Barrier Reef
(2743) was added this way on 19 Nov 2026. The steps it runs:

Every CE except Vatican runs through the same six steps; the CE's name, site, folder and head cluster live in
`ces.json`. Park Güell (325) was set up this way on 6 Nov 2026, and the same steps rebuild Milford's inputs byte for
byte. `<clusters_3_0>` is the pipeline (`~/analytics/.claude/worktrees/clusters-3-0/scripts/clusters_3_0`); its venv
has the embedding model the mapping and page steps need.

1. Add the CE to `ces.json`: `slug`, `name`, `host`, `out`, `data`, `page`, `title`, `name_words` (words that only name
   the CE, removed before matching pages) and `head` if its head cluster is not named "... Head Term".
2. `python3 pull_ce.py <ce>`: every BigQuery input from `sql/templates/`, in dependency order (pages, then their
   collections' products, then those products' variants and orders).
3. `<clusters_3_0>/.env-clusters/venv/bin/python map_ce.py <clusters_3_0> <ce>`: the CE's snapshot from
   `20261030_validation_v1` (11-CE hybrid clusters, Google Ads and Search Console) and three mapper runs; their ids go
   into `ces.json`.
4. `<clusters_3_0>/.env-clusters/venv/bin/python prepare_ce.py <clusters_3_0> <ce>`, then
   `.../python group_unclustered.py <clusters_3_0> <ce>`: file shapes, page mapping, unclustered search groups.
5. `python3 facts_ce.py <ce>`: CE type, category and aliases from data. Its parts (sub-attractions), artworks, areas
   and operators are not derivable and stay empty, so those page types are not assigned until someone adds them.
6. `python3 export_hybrid.py <clusters_3_0> <ce>`, then `python3 build.py <slug>`.

## Limits

- The window is fixed at 30 Jul – 27 Oct 2026 in the templates and the source snapshot.
- Clusters come from the 11-CE hybrid run (189, 243, 257, 261, 325, 1695, 2010, 2640, 2743, 3176, 3945). Another CE
  needs the pipeline session to cluster it first.
- Vatican still runs on its own older inputs (Satvik's capture workbook, the v4 snapshot, the `cluster_sources` run);
  "Searches without a cluster" and capture numbers exist only for it.
- The suggested choices for unclaimed searches (`SUGGEST` in `template.html`) are written for Vatican.

## From the pipeline's output

When the pipeline session has run `run_ce_pipeline.py <CE>`, build the page from its `snapshots/ce_<CE>/final/` instead of the 11-CE mapping run:

```
python3 run_ce.py 1695 --final            # or --final patched for the patched prompt
```

`final_ce.py` turns `final/` (clusters, keywords, paid and organic placements) into the snapshot and runs the export already reads. Cluster ids come from the CE and the cluster name, so a re-run that keeps a name keeps the decisions saved against it. Vatican stays on its hybrid set until the pipeline has run on it.
