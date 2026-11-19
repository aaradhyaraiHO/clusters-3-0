# Clusters 3.0: final workflow and how it shows in the UI (5 Nov)

Pulled together from:
- Parag, 30 Oct
- Krupa, 4 Nov
- Krupa and Aditya (Perf), 5 Nov
- the growth walk-through with Krupa, 5 Nov

The base is Krupa's UI with this pipeline's data in it. Gates, thresholds and automation are in PROCESS.md.

## 1. The workflow

**Principle:** the pipeline drafts everything and each team approves its own part. Growth decides *what* is needed,
content decides *how the page is built*, Perf decides *how the ads run*.

### Stage 0: Pipeline (automatic, before anyone opens the CE)
1. Seeds become keywords, then clusters, each with a focus keyword and intent.
2. Mapped to each cluster:
   - searches and organic queries
   - ad keywords and the ad groups serving it
   - the page it maps to (Krupa's mapping prompt)
   - products that cover it
3. Drafts:
   - **own page** (DRD decision tree + cluster searches + supply)
   - **page type** (page planning rules)
   - **recommendations to Perf** (Aditya's coverage tree)

### Stage 1: Growth (Analysis)
1. **Scan the clusters.** If they look wrong, open **Seeds** beside the table, edit, re-run. Fix single clusters in
   **Edit**: merge, delete, add or remove keywords.
2. **Read each cluster's top row:**
   - searches
   - supply status
   - the page mapped to it, and where its ads land
   - the own-page suggestion
3. **When the row isn't enough, open the cluster.** Paid shows keywords, search terms, ad groups, coverage, RPC,
   CPC and ROI; Organic and Supply show the rest.
4. **Decide own page** for buying clusters: agree with the suggestion, or change it to Yes, Yes + subdomain, No or
   Not now.
5. **Mark recommendations while browsing:**
   - ★ a cluster or a keyword
   - accept or set aside what the pipeline flagged
   - list keywords not to use
6. **Send to Perf** (one package) and **Send to content** (a ticket).

Before Send, every buying cluster with 1,000+ searches and no page must have a confirmed own-page decision.

### Stage 2: Perf (in their own tool)
- **What arrives:** the package, with seeds, every cluster and its keywords, and the recommendations, each with the
  checks growth made.
- **What Perf does:**
  - marks each item done or won't do
  - talks through disagreements with growth on a call
  - can open this tool read-only for the evidence
- **What comes back:** Perf's changes show on the cluster as status.

### Stage 3: Content (Analysis, then Execution)
1. **The ticket opens the CE in Analysis.** Content reviews planning and informational clusters using demand and
   organic, including orders from organic visits.
   - It sets their own-page decision; those clusters show "Content's call".
   - It can add pages growth didn't ask for.
2. **Content corrects page matches:**
   - **Change** or **Map existing** on a cluster's page
   - map **pages with no cluster**
3. **Execution:** one row per cluster with own page Yes and no live page.
   - Content **cross-checks the page type**.
   - Collection and POI are fetched if they exist, otherwise created.
   - Content sets the subfolder slug. The subdomain URL is growth's and is shown read-only.
4. **Launch** one page, or **Launch all**.
   - The agent creates the entities, subfolder, subdomain and product fetching, and raises the brief.
   - Once a page shows Launched, content works in Payload.

### Stage 4: The loop
- **A new page goes live:** that cluster's Perf item is released with its URL.
- **Daily BigQuery check:** sees what is live (page, keyword, final URL) and updates each cluster's status.
- **Changes log:** keeps every decision, with who made it and why.
- **Existing CEs:** reviewed again each cycle, led by the coverage recommendations.

## 2. How it shows in the UI

```
┌ Milford Sound Cruises · CE 3945          [Analysis | Execution]   Seeds 31 · Changes 4 · Edit · Send to Perf ★6 ┐
│ Clusters 31 · Live pages 26 · Collections & POIs · Products selling · Campaigns $101K ROI 140% · Own page 3 of 5 │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Look at: [Demand | Paid | Supply]      Intent: [Transactional][Planning][Informational]     Pages with no cluster 5 │
├──┬──────────────┬───────────────┬──────┬──────┬──────────┬──────────┬───────────────────┬─────────┬──────────┬──┤
│▸ │ Cluster      │ Focus keyword │ FKW  │ Clus │ lens col │ lens col │ Page              │ Supply  │ Own page │★ │
│  │ intent·status│               │ vol  │ vol  │    1     │    2     │ mapped · ads land │ 4 state │ sugg/conf│  │
└──┴──────────────┴───────────────┴──────┴──────┴──────────┴──────────┴───────────────────┴─────────┴──────────┴──┘
   open row ▾ : what the selected lens needs to decide (below)
```

### Header
- **Tabs:** Analysis (growth and content) | Execution (content).
- **Seeds:** opens on the right, beside the table: seeds by bucket, partners, re-run.
- **Changes:** every decision, who made it and why, with undo.
- **Edit:** adds Merge / Delete to each row, and add / remove keyword in the open row.
- **Send to Perf ★N:** the Perf panel (below).
- **What the CE already has** (growth asked for this before deciding anything):
  - clusters
  - live pages
  - collections and POIs
  - products selling
  - campaigns, with spend and ROI
  - own-page decisions done (X of Y), which is the Send gate

### The table: the columns that never change
| Column | Shows | Who acts |
|---|---|---|
| Cluster | Name, intent, status line (Own page decided → With content → Launched → Sent to Perf → Live in ads) | — |
| Focus keyword · FKW vol | The focus keyword and its searches | — |
| Cluster vol | Searches for the cluster, each spelling family counted once | — |
| **Page** | The page mapped to the cluster by its focus keyword (full URL; subdomain URL if one exists; "+N more"). Under it: **where its ads land**, with ✓ when that's this page, or "ads land on /x, not this page". No page: "No page". | Content: Change / Map existing |
| **Supply** | Unique experience, supply available (with product count) · Unique experience, no supply · Covered by a broader product · n/a | Growth (asks BDMs when unsure) |
| **Own page** | Suggested (shown as a suggestion until confirmed) or confirmed: Yes · Yes + subdomain (URL box) · No · Not now. Planning and informational: "Content's call". | Growth (buying), content (others) |
| **★** | Recommend this cluster to Perf. A dot shows when the pipeline flagged something for it. | Growth |
| Merge / Delete | Only in Edit | Growth |

### The table: "Look at" swaps two columns and what the open row shows

| Lens | Column 1 | Column 2 | Open row shows |
|---|---|---|---|
| **Demand** | Keywords (count) | Organic: clicks and orders from organic visits | Top keywords (★ or × each, add one) · pages mapped and how each was matched, with revenue landed |
| **Paid** | Coverage: paid impressions ÷ searches (Covered / Partial / Not bid) | Conversion value · ROI | Keywords we run ads on · search terms and what caught them · ad groups serving it and its share of each · RPC vs CPC · what the pipeline recommends, and why |
| **Supply** | Products: matched to the cluster, and how many differ from the page | Page revenue (paid / organic / other) | Products in the cluster vs on the page, with revenue · what the page lists and why (ranking, pins, filters) |

**Content's starting point:** the same table, with Planning and Informational on and the Demand lens. It is not a
separate view.

### Send to Perf (a panel from the header)
- **Pipeline recommendations:** sorted by coverage gap × searches. Each says what it asks (add this cluster's
  keywords · set up a dedicated ad group and page · fix the landing page · a new cluster from untaken searches) and
  carries the checks: searches, supply, page, coverage, RPC vs CPC. Each can be accepted, or set aside with a
  reason.
- **Growth's own ★** on clusters and keywords.
- **Keywords not to use.**
- **What the package holds:** seeds, every cluster and its keywords, and the items above. Then **Send**.
- **Item statuses** after sending: done, won't do, question.

### Execution (content)
- **Rows:** clusters with own page Yes and no live page. Clusters with no supply show "Flag supply" instead of
  Launch.
- **Columns:**
  - Page type (suggested; content cross-checks)
  - Collection and POI: "Exists · ID", "Will create" or "Not needed", from the page planning rules
  - Subfolder slug (content)
  - Subdomain (growth's, read-only)
  - Experiences fetched by
  - Launch
- **Launch all** at the top. Status per row: Queued → Launched.
- **Pages with no cluster:** a panel, opened from Analysis, to map each page or make it a cluster.

## 3. Changes to Krupa's UI this needs

Her layout, tabs, lenses, Seeds, Edit, Execution and Launch stay as they are. The changes:
1. **Supply:** 4 states plus a product count. Hers has 3.
2. **Page cell:** the "where ads land" line, the subdomain URL, and how the page was matched.
3. **Own page:** a suggested-vs-confirmed state, an Agree action, and "Not now". The confirmed count goes in the
   header.
4. **Lenses:**
   - Demand: organic clicks and orders.
   - Paid: coverage from impressions ÷ searches, replacing her bid-keyword rule.
   - Every open row gets real search terms, ad groups serving, and RPC vs CPC.
5. **★ on keywords** in the open row, and the **Send to Perf panel**: pipeline recommendations with accept / set
   aside, plus keywords not to use.
6. **Header strip:** what the CE already has.
7. **Execution:** fetch-or-create for collection and POI, and the subdomain read-only. Launch and Launch all are
   already there.

## 4. Still open

- **Suggestions are stand-ins until these are ready:**
  - Krupa's page-mapping prompt
  - the DRD own-page suggestion
  - the page-type suggestion
- **The agent that creates entities and pages:** Anuj / Yuvraj.
- **Where the Perf package lands:** Rajita's tool, to confirm with Satvik and Rajesh.
- **The click threshold** for "searches to add", and the low bar for coverage per CE type.
