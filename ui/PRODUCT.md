# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary: growth manager (BGM) at Headout**, working one combined entity (CE) at a time, such as Milford Sound
  Cruises or the Vatican. Their job: check the keyword clusters for the CE, decide which buying clusters need their
  own page, and send one package to Perf and one ticket to content.
- **Secondary: content team member**, arriving from that ticket. Their job: decide own pages for planning and
  informational clusters, correct page matches, set page type and subfolder slug, then launch pages from Execution.
- **Read-only: Perf.** Perf works in its own tool from the package and may open this one only for evidence.

## Product Purpose

Clusters 3.0 replaces the EOS keyword-cluster tool (7 tabs) with one cluster table per CE. A pipeline drafts
clusters, page mappings, own-page suggestions and Perf recommendations; each team approves its own part. Growth
decides what is needed, content decides how the page is built, Perf decides how the ads run.

Success, equally weighted:
- A new non-POI CE is launched end to end in a day, with every buying cluster's own-page decision confirmed before
  Send.
- Existing CEs are reviewed each cycle and their coverage gaps, wrong landing pages and untaken searches are acted on.

## Positioning

One row per demand intent, with demand, paid, supply and page evidence side by side, so a BGM decides from data
already joined (EOS clusters, Google Ads search terms and ad groups, Payload pages, products) instead of across 7
tabs and separate sheets.

## Operating Context

- Opened per CE. Views: Analysis (Clusters | Opportunities) for growth and content; Execution (content's queue of
  pages to launch).
- Lenses swap columns: Demand, Paid, Supply. Intent filter: Transactional, Planning, Informational.
- Outputs: Send to Perf (one package into Perf's tool) and Send to content (a ticket). A Changes log records every
  decision with who and why.
- Status flows back: Own page decided → With content → Launched → Sent to Perf → Live in ads, updated by a daily
  BigQuery check.
- Detail: thoughts/shared/clusters-3.0/parag-v1/WORKFLOW.md and PROCESS.md.

## Capabilities and Constraints

- Clusters stay one per demand intent however small; they are never merged on paid data. Cluster, page and ad
  group are three separate groupings.
- This is not a Perf execution tool: no match types, campaign or ad group IDs, Editor CSVs or bid asks. Perf gets
  clusters, final keywords, the BGM's flags and a one-line why.
- The system suggests; people decide. Suggestions show as suggestions until a person confirms them. Nothing goes
  to Perf pre-ticked.
- One source per metric column; no blended metrics.
- Volumes are monthly searches, with spelling families counted once.
- Open: the page-mapping prompt, own-page and page-type suggestions are stand-ins; the launch agent (Anuj /
  Yuvraj) and where the Perf package lands (Rajita's tool) are undecided.
- Current build: static HTML mockups (template.html, milford-clusters.html, vatican-clusters.html) built by
  build.py; engineering (Akash) starts 9 Nov 2026.

## Brand Commitments

Headout internal tool on the Oak / Eevee design system (Halyard type, Oak tokens). Plain, factual labels named
after the underlying data.

## Evidence on Hand

Real pipeline data for Milford Sound (CE 3945) and the Vatican, in the mockup HTML files and the hybrid/ and
hybrid_milford/ folders. No user-testing results yet.

## Product Principles

1. Each team sees and acts on its own step; nobody approves another team's part.
2. Suggest, never pre-decide: every send is authored by a person.
3. Evidence beside the decision: the row carries what is needed to decide; the open row carries the rest.
4. Plain terms grounded in the data's own names, one source per number.
