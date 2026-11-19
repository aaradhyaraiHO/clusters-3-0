# Clusters 3.0: the workflow mapped onto the tool, screen by screen (5 Nov)

Produced by an independent review agent from the meeting transcripts, PROCESS.md, WORKFLOW.md, template.html,
export_hybrid.py and Krupa's Main.dc.html. Not yet agreed with Krupa or Perf.

**The basis:** our `template.html`, with Krupa's flow brought in and typed Perf asks instead of the ★.

**Codes:** **T** = exists in template.html today · **K** = exists in Krupa's Main.dc.html · **N** = new.

**Sections 6–9 are revised:** they map onto decisions already in PROCESS.md, and the keyword-editing flow is designed in full.

**Three findings that change the plan:**
- **Our merge loses pages.** The edit bar says "the merged cluster keeps all their pages". In fact `S.merged` only
  hides the absorbed clusters and adds up their keyword counts; their pages, supply, own-page decision and keywords
  vanish.
- **Krupa's Lock freezes nothing.** `lockedAt` only shows a banner, everything stays editable, and the Perf send is
  separate from it.
- **Milford in `?preview=newce` can't show supply.** The preview wipes pages and Milford has no product matched to any
  cluster, so every buying cluster shows "No match · set" and every own-page suggestion is No.

## Rule: search terms first (Aditya, 5 Nov)

**Keyword research draws the map; search terms tell us what is happening on it.**

**Keyword research:**
- builds the clusters
- sizes them (searches / mo)
- shows demand we don't capture yet
- is the only input a new CE has until its ads run

**Search terms** (what people actually typed, mapped to a cluster) are the evidence for every paid decision.
Keywords never sit in between: Perf chooses keywords.

**Coverage** brings the two together on purpose: paid impressions on the cluster's search terms ÷ the cluster's
searches.

**The opportunity tree, per cluster and then per sub-cluster:**

1. **Coverage high:** look one level down, at the sub-clusters (Creation of Adam inside Sistine Chapel), and run each
   one through the same tree.
2. **Coverage low, and none of the cluster's search terms are triggered by a keyword from this cluster** (they come
   through AI Max, broad match, or not at all):
   - Growth checks supply first.
   - If there is supply, the ask to Perf is **cover this cluster**. It carries the focus keyword and the search terms
     already coming in. Perf decides the keywords and where they go.
3. **Coverage low, and its own keywords do trigger its search terms:** check the set-up, from search term to keyword
   to a dedicated ad group to ad copy to landing page.
   - **Set-up incomplete:** ask for a **dedicated ad group and landing page**. Perf decides; not every cluster gets
     one.
   - **Set-up complete:** it comes back to growth as a money question. A cluster with higher CPC needs higher RPC to
     scale at the same ROI target, so growth looks at RPC and the CPC trend for that cluster.

**Low coverage is relative.** Generic POI terms run low by design; buying terms should run high. So the bar is set
low, and growth or Perf can skip an item.

**Priority:**
1. Find clusters and sub-clusters and raise their coverage.
2. Keyword coverage across clusters.
3. Negatives and losing money, only for new CEs while campaigns learn.

**Searches to add as keywords:**
- search terms only, including AI Max ones
- sorted by clicks
- only those with enough clicks for about 10 conversions at the campaign's conversion rate (5% → 200 clicks)
- close variants of live keywords left out

**What changes in the tool:**
- **"Mostly bid / Focus only / Not bid"** moves from the share of keyword volume bid to the share of the cluster's
  paid clicks its own ad group catches. We already export this as ad groups serving the cluster, with shares.
- **"Add its keywords" becomes "Cover this cluster",** carrying search terms and the focus keyword, not a list of
  keyword families.
- **"In Ads N of M spellings"** stays as data in the side panel. No decision or ask depends on it.

## 0. Undecided points and the defaults used here

| # | Open point | Who decides | Default |
|---|---|---|---|
| U1 | Which buying clusters must have an own-page decision before Send | User | Buying, 1,000+ searches, no page (Vatican 3, Milford 3; Milford preview 9) |
| U2 | Who sets the subfolder slug | Krupa | Content, in Execution. Growth sets the subdomain URL in Analysis |
| U3 | Does a new cluster's Perf ask wait for its page? | User / Perf | "Start ads on the new page" waits until the page is live; every other ask goes at Send |
| U4 | Where the Perf package lands | Satvik / Rajesh / Rajita | A download (JSON + CSV) from the Send panel, until Rajita's tool can take it |
| U5 | Coverage bar | Perf | Below 10% for buying clusters with 1,000+ searches |
| U6 | Click threshold for "searches to add" | Perf | 10 ÷ the campaign's conversion rate (5% → 200 clicks) |
| U7 | Source for "supply coming" | Krupa | Growth sets it by hand, with a note (BDM name or date) |
| U8 | Merging clusters that each have a page | Krupa | Section 6 |
| U9 | Can content edit planning and informational clusters? | Krupa | Yes, in Edit mode |
| U10 | Does Perf open this tool? | Perf | No. The package carries the evidence; a read-only link is optional |
| U11 | One send for content and Perf, or two | User | One Lock & send that creates both |
| U12 | How often existing CEs are reviewed | User | Monthly |
| U13 | What must be triaged before Lock | User | The top 10 drafted Perf asks by size |
| U14 | Ask threshold for a new CE | Perf | Buying cluster with supply and 500+ searches |

## 1. What each cluster carries

- **Fields set by growth:**
  - supply state
  - own page, with the subdomain URL
  - Perf ask: type, state, origin, reason, and any keyword families dropped from it
  - flags kept with "Keep as is"
- **Fields set by content:**
  - own page for planning and informational clusters
  - page match
  - page type and slug
- **Two status lanes,** shown as chips under the cluster name:
  - **Page lane:** No page → Own page: Yes → With content → Queued → Launched → Live. Side states: Has page · No own
    page · Not now · Flagged for supply · Withdrawn.
  - **Ads lane:** Drafted → Agreed (or Set aside) → Sent (or Held until the page is live) → Done / Won't do /
    Question → Verified (or Reopened). Also: Withdrawn.
- **Header counters:**
  - **T, today:** Clusters, Live pages, Collections & POIs, Products, Campaigns or Paid, Own page decided X of Y.
  - **N:** "Flags resolved x of y", "Perf asks: n agreed · m to triage", and after Lock: "Locked <date> by <name> ·
    review #n · k to act on".

**How Perf asks are drafted** (N; `askOf(c)` reuses today's OPPS logic):

| Ask | Drafted when | Fields |
|---|---|---|
| Add its keywords | Coverage under the bar, none of its keywords bid, supply Yes or covered | `c.cover` (`st.impr`÷`vol`), `c.adg.state=missing`, `drawer.targeted.n`, `families()` |
| Dedicated ad group + landing page (Perf decides) | Coverage under the bar, keywords live, set-up incomplete: `dedicated.share<0.5`, or `theme.focus<0.1`, or it lands off its page | `drawer.dedicated`, `c.theme`, `c.adg.landing` |
| Point its ad group to its page | It has its own page, its core ad group lands elsewhere, 100+ clicks | `mainPage(c)`, `c.adg.landing` |
| Start ads on the new page | Own page Yes and the page has gone live | Pages table (published) |
| Set up this cluster (new CE) | No ads on the CE, buying cluster, supply, U14 | `HASPAID=false`, `prodState`, `vol` |
| New cluster | Growth made a cluster from searches no cluster takes | Unclaimed, Pages with no cluster |
| Remove from campaigns / Run with <cluster> in ads | Growth adds it; never drafted | — |
| *Not an ask:* raise RPC | Full set-up and coverage still low | `c.rpc`, `c.cpc`, weekly data |

## 2. Flow A: growth reviews an existing CE (Vatican, 39 clusters, 14 buying)

**A1 · Open the CE** (growth)
- **Where:** Analysis tab.
- **Sees:**
  - title, CE id and window (`D.ce`)
  - tiles: Collections & POIs from `entity.items`, Campaigns from `drawer.campaigns`, Live pages from `pages` and
    `pages_no_cluster`, "Own page decided 0 of 3"
- **Next:** A2 if the clusters look wrong, otherwise A3.
- **Built:** T for the tiles. N: Flags and Perf-ask counters.

**A2 · Seeds** (growth)
- **Where:** header **Seeds · N** opens a drawer on the right.
  - **Keywords tab:** seed, searches, "Led to cluster", ×, **Add**, the **Leave out** list.
  - **Supply partners tab:** Cluster it / Not real.
  - **Re-run clustering** button.
- **Does:** adds or removes seeds, leave-out words and partners, then re-runs.
- **Result:**
  - "N changes since the last run" is shown.
  - A real re-run keeps edits as overrides, and resets Gate 1 only for clusters that changed.
- **Built:** T, with stand-in data. K has Milford's real seeds by bucket and partners with brand volume.
- **Smallest change:** export the pipeline's real seed list, grouped by bucket as K does.

**A3 · Gate 1: review the clusters** (growth)
- **Where:**
  - ⚑ count in the Cluster cell (N)
  - toolbar chip **Flags · n** (N), next to Low coverage and No page (T)
  - **Edit clusters** → tick boxes → Merge / Delete (T)
  - side panel **Edit cluster** select: Rename, Group under, Merge into, Change intent (T)
  - Keywords tab **Belongs in** (T)
  - header **Clusters reviewed** button (N)
- **Does:** fixes each flag (section 8b) through Edit, or chooses **Keep as is** with a reason.
- **Result:** "Flags resolved x of y"; Clusters reviewed records the name and date.
- **Gate:** Gate 1 blocks Lock.
- **Built:** T for editing, N for the flags.
- **Smallest change:** `flagsOf(c)` with the 5 rules we can compute, plus `S.flagOk` and `S.reviewed`.

**A4 · Supply** (growth)
- **Where:** first-view **Supply** column (today's Product column, renamed).
- **Sees:**
  - "Yes · N selling" from `c.supply.live`, or from what its page sells
  - otherwise a select: Covered by a broader product · Unique, supply coming (with a note) · Unique, no supply
  - "n/a" for planning and informational
  - evidence in the side panel Products tab and the page pop-up
- **Result:** `S.supply` set and logged; the own-page suggestion and Perf-ask drafts recompute.
- **Built:** T (3 options), K (3 states plus ↻).
- **Smallest change:** relabel to Krupa's 4 states, keep "coming" as a sub-state, and show a product count.

**A5 · Page, and where its ads land** (growth reads; content corrects in C3)
- **Where:** the Page cell. Its link opens the "What this page shows" pop-up (T); "+N" opens more pages.
- **Sub-line:** "✓ Its ad group lands here" or "⚠ Its ad group lands on home" (T).
- **Growth can't re-map a page,** only comment on it.
- **Result:** a ⚠ feeds the "Point its ad group to its page" draft.
- **Built:** T.

**A6 · Deep dive** (growth)
- **Where:** click a row → side panel: summary tiles, then tabs **Paid · Keywords · Products · Pages**.
- **Built:** T.
- **N:**
  - organic orders on the Pages tab (Milford has the channel split in `orders_by_landing_3945.csv`; Vatican needs the
    SQL)
  - an RPC vs CPC trend
  - keywords trimmed to the top 10, with Show all

**A7 · Own page** (growth for buying clusters)
- **Where:** Own page cell.
  - Yes / No select with **Agree** (T)
  - Subdomain tick box (T) and URL box (K)
  - **Not now** option (N)
  - reason box when changing the suggestion (N)
- **Result:** `S.sep` confirmed; "Own page decided X of Y" updates; logged; Page lane shows "Own page: Yes".
- **Gate:** Gate 2 blocks Lock.

**A8 · Perf asks** (growth)
- **Where:** first-view **Perf ask** column (N).
  - The cell shows the ask type and a one-line reason ("Add its keywords · 74K searches · product yes · 0% coverage")
    and a select: **Agree** · **Change ▸** · **Not now** (with a reason).
  - A cluster with no draft shows "+ Ask".
  - The side panel Paid tab gets a **Perf ask** box: missing keyword families, each with a tick box, for "Add its
    keywords".
  - A cluster whose coverage is fine but has sub-clusters drafts asks on the sub-clusters.
- **Result:** `S.ask[c]` set; Ads lane Agreed or Set aside; logged; header "n agreed · m to triage".
- **Gate:** the top-10 triage (U13) blocks Lock.
- **Built:** N. It reuses T's OPPS rules, and replaces the Opportunities tab.

**A9 · Lock & send** (growth). See section 9.
- **Where:** header **Review & send** → checklist panel → **Lock & send**.
- **Result:** creates the content ticket and the Perf package; freezes growth's fields; Page lane "With content";
  Ads lane "Sent" or "Held".
- **Built:** N.

**A10 · Follow-ups** (growth)
- **Where:** header "k to act on" filters to clusters with Won't do, Question, Reopened, or content push-backs.
- **Does:** answers, or reopens the cluster.
- **Built:** N.

## 3. Flow B: growth launches a new CE (Milford, `?preview=newce`, 31 clusters, 15 buying)

- **B1 · Open the CE.** Banner "Preview: how a new CE looks"; Paid tile "No ads yet"; every cluster shows "No page".
  *T.*
- **B2 · Seeds.** This matters most for a new CE.
  - Krupa's file has Milford's real seeds by bucket and real partners (Southern Discoveries 6,600, RealNZ 4,400…); ours
    has stand-ins.
  - *Smallest change:* write K's lists into `milford.json`.
- **B3 · Gate 1.** Only the clustering flags apply.
  - Good demo flags: Underwater Observatory's focus keyword is "milford sound lodges"; Stirling Falls' is "places to
    stay milford sound".
- **B4 · Supply. Blocked today.**
  - No Milford cluster has matched supply, and the preview wipes pages, so all 15 buying clusters ask for a manual
    setting and every suggestion is No.
  - *Smallest change:* port Krupa's TGID-to-cluster name match (her `EXP`) into `prepare_ce.py` as a stand-in for
    Shivam's matching, and stop the preview wiping product matches.
- **B5 · Own page.** Same as A7; "0 of 9".
- **B6 · Perf asks.** One type only: "Set up this cluster".
  - It carries the focus keyword, keyword families with searches, and the landing page: the new page (held until
    live) or the CE home page meanwhile.
  - K's ★ is the same rule, pre-set.
- **B7 · Lock & send.** Same as A9. The package holds seeds, all clusters and their keywords, and the set-up asks.

## 4. Flow C: content after the ticket

**C1 · Pick up the ticket.** The ticket links to Analysis with a **Sent to content · n** chip on (N), and a lock
banner showing who locked it, when, and the review number (K).

**C2 · Planning and informational clusters.**
- **Where:**
  - Intent selector (T)
  - Demand "+4": Keywords, Organic clicks, Position, Organic capture (T)
  - Page "+4": Ranking page, Page revenue (T)
  - new **Organic orders** column (N)
  - Own page cell: content gets Yes / No / Not now (N; today it's "Content's call" with "Ask for a page")
- **Content can also say Yes to a buying cluster growth left at No.** It's logged as a "content pickup" and counts in
  growth's "to act on".

**C3 · Correct page matches.**
- **Where:** Page cell **Change** (another live page, or No page) and **Map existing** (K); how each page was
  matched (T).
- **Result:**
  - `c.pages` updated; a page taken off goes to Pages with no cluster.
  - Perf drafts recompute.
  - An already-sent Perf item goes to Perf as a change.
  - Logged.

**C4 · Pages with no cluster.**
- **Where:** toolbar button and panel (K; in T it's a footnote).
- **For each page:** Map to <cluster> · Make it a cluster · Not a cluster page.

**C5 · Execution queue.**
- **Rows:** own page Yes (confirmed), no live page, both intents.
- **Columns:** Cluster · Supply (N) · Page type · Collection · POI · Subfolder slug · Subdomain (growth's, read-only)
  · Experiences fetched by · Launch.
- **Built:** Krupa's table replaces T's "Set-up by team".

**C6 · Page type.**
- **Where:** a select from K's `ENT` list. T's list has "Vendor page", which `ENT` lacks; Krupa to reconcile.
- **Suggestion (N, stand-in):** POI exists → Sub-attraction; partner cluster → Branded collection; otherwise
  Subcategory.
- **Result:** `ENT` fills in the collection, POI, subdomain and fetch cells.

**C7 · Entities.**
- **Collection and POI cells:** "Exists · ID", "Will create", "Not needed" or "Optional", from the `ENT` rule plus a
  name match. "Pick IDs" shows when it's unresolved.
- **Data:** Vatican's `entity.items` and `page_entities.csv` are real; Milford's aren't loaded.

**C8 · Slug and subdomain.** The slug is pre-filled from the focus keyword (content); the subdomain URL is read-only
(growth's).

**C9 · Launch / Launch all.**
- **Where:**
  - per row: **Launch**, **Pick IDs**, or **Flag supply**
  - header: **Launch all ready · n**
- **What Launch shows:** a confirm with the step plan. T's agent-log modal can render it.
- **Result:**
  - Page lane: Queued → Launched → content works in Payload.
  - Flag supply logs a supply request instead.

## 5. Flow D: Perf, and the loop back

- **D1 · What arrives:** the package (section 11). Default: JSON + CSV.
- **D2 · Perf marks each item:** Done · Won't do (reason) · Question.
  - Until Rajita's tool can send statuses back, growth records the result in the Send panel.
- **D3 · Disagreements** go to a call; the result is logged as the status.
- **D4 · Status comes back:** the Ads lane chip and the Send panel's Sent asks. Won't do and Question count in "to
  act on".
- **D5 · A page goes live** (daily BigQuery check):
  - Page lane shows Live.
  - The held "Start ads on the new page" ask is released with the URL as a change to Perf, with no new approval.
- **D6 · Daily done-checks:**

  | Ask | Done when |
  |---|---|
  | Add its keywords | A keyword of the cluster is live in an enabled ad group |
  | Dedicated ad group | `dedicated.share ≥ 0.5` |
  | Point its ad group to its page | `adg.landing` = its page |
  | Start ads on the new page | An ad group's final URL is the new page |

  A Done that the data contradicts becomes Reopened.
- **D7 · Lanes:** hovering a chip shows its history.
- **D8 · Next cycle** (monthly):
  - Drafts recompute; Done asks show coverage before and after.
  - Set-aside asks return only if searches or coverage moved by 20% or more.

## 6. Merge clusters (revised: keep today's edit-bar merge and fix two problems)

**Today (T):**
- Edit clusters → tick boxes → **Merge N into <biggest by searches>**, with a warning when more than one has a page.
- Each merge can be undone from Changes.
- Searches stay as the focus keyword's volume. This matches PROCESS §0: merging only changes focus.

**Problem 1: the warning is false.**
- It says "the merged cluster keeps all their pages". The code only sets `S.merged` and adds keyword counts.
- The absorbed clusters' pages, supply, own-page decision and keyword rows disappear from the table and the panel.
- **Fix:** carry them onto the keeper wherever the table and panel read them, or change the warning to what really
  happens.

**Problem 2: two merge rules.**
- The side panel's "Edit cluster → Merge into <X>" keeps X's name; the edit bar keeps the biggest.
- **Fix:** make the side-panel option use the edit bar's rule.

**Don't port from Krupa:**
- Her merge adds cluster volumes together (`v += o.v`), which counts close variants twice.
- It drops the absorbed clusters' decisions without a warning.

**Which page survives (open in PROCESS §0).** Until Krupa decides, the default follows "page decisions merge
clusters, cluster edits don't":
- Both pages stay. The keeper's page is the main one, and the Page cell shows "+1".
- **Own-page decisions:** one already With content beats an unbuilt one. Two different confirmed decisions go back to
  the suggestion and back into Gate 2.
- **Perf items already sent** stay on their old cluster and carry "merged into X".

## 7. Editing keywords (the flow to design)

**What exists**

| | Krupa (K) | Ours (T) |
|---|---|---|
| Where | Inline open row, Edit mode only | Side panel Keywords tab, always on |
| What's listed | Top keywords only | All: Vatican has 1,217 keywords in 731 families; one cluster alone has 263 in 102 |
| Remove | × per keyword; the keyword disappears | "Remove (goes to Unclaimed)" per spelling |
| Move | None | "Move to X" per spelling; "Moved in" rows on the receiving cluster |
| Add | Text box; volume shows "[vol]" | None |
| Family | None | Family rows group spellings, but the **family row itself has no control** |
| Takes effect | Immediately | Unclaimed: "nothing applies until you re-run" |

**A hidden conflict: "family" is defined twice.** The panel groups by the export's `fam` field, while `families()`
(used for the focus label and keyword gaps) groups by shared Planner volume. They can disagree.

**Starting principle.** Growth edits keywords for one reason: **to make each cluster hold one intent**. That covers
split families, a wrong focus keyword, and junk or other-CE keywords.

Keyword editing is never how growth tells Perf what to bid; Perf does its own keyword research once a cluster is
flagged. So there's no keyword star and no "don't use" list. Keyword choices reach Perf in two ways only:
- as each cluster's keyword membership in the package
- as families growth drops inside an agreed "Add its keywords" ask

**Flow**
1. **One place:** side panel → Keywords tab. The controls appear only in **Edit mode**; it's read-only otherwise.
2. **One unit: the keyword family.**
   - Each row is a family: best spelling, "+N spellings", searches, In Ads.
   - **The row's control acts on every spelling at once.** This is the main gap in T.
   - Opening a family exposes its spellings, for the rare one that's misgrouped.
   - Use one family definition everywhere: the export's `fam`.
3. **Trim:** the top 10 families by searches, then "Show all N". A Gate 1 flag opens the panel scrolled to the
   flagged family.
4. **Actions per family:**
   - **This cluster** (the default).
   - **Move to <cluster>.** The list is searchable. When a split-family flag points to another cluster, that cluster
     is pre-selected as "suggested". The receiving cluster shows "Moved in from X".
   - **Make focus keyword.** The focus keyword drives the page match, Searches, the own-page suggestion and the Perf
     ask, so it gets its own action.
     - It resolves the "focus doesn't fit" flag.
     - A confirmed own-page decision asks "Focus changed: re-confirm?" rather than resetting.
   - **Remove → Unclaimed.**
     - Removing the focus family first asks for a new focus.
     - Removing the last family offers Delete cluster.
5. **Add: route it, don't type it in blind.** One box, "Add a keyword or search", looks the text up in order:
   1. A keyword in another cluster of this CE → **Move here**.
   2. A search in Unclaimed → **Assign here**.
   3. Neither → **Add as a seed for this cluster**. It shows as "pending · after re-run" and appears in Seeds tagged
      with this cluster.

   This avoids keywords with no volume or search data (Krupa's "[vol]").
6. **Removed keywords** wait in Unclaimed (T): assign, New cluster, or **Leave out**. Leave out works per keyword and
   is kept as an exclusion at the next re-run. Seeds' Leave out works on words (OTA names).
7. **Two speeds, shown honestly.**
   - **Now, in the tool:**
     - which cluster holds which keywords, and the counts
     - Gate 1 flags
     - the "families not in Ads" list inside "Add its keywords"
     - keyword lists in the package and the ticket
     - Searches changes only if the focus changes, because it is the focus family's volume, never a sum
   - **At the next re-run:**
     - paid and organic numbers, coverage, and the page match
     - edited clusters carry an "Edited · numbers as of last run" pill until then
   - **Re-run** (Seeds, T) sends moves, focus choices, exclusions and merges to the pipeline as pinned overrides
     (pipeline work, N), and resets Gate 1 only for clusters that changed.
8. **After Send:** an edit to a sent cluster marks it "Changed since Send" and goes out in the next **Send changes**.
   - Perf gets the updated keyword list, and any changed ask.
   - Content gets the updated top keywords, or a new focus.
9. **Log:** "Moved 'vatican night tour' (+3 spellings) from X to Y", "Focus of X → '…'", "Removed '…' → Unclaimed".
   Each has Undo.
10. **Who:** growth, and content on planning and informational clusters, if Krupa agrees (U9).

**Smallest changes in template.html, in order:**
1. a select on the family row that acts on all its spellings
2. one family definition
3. the top-10 trim
4. controls only in Edit mode
5. Make focus keyword
6. the routed Add box
7. the "Edited · numbers as of last run" pill
8. Leave out persisted to the re-run

## 8. Opportunity flags, mapped from PROCESS §0 and §4

OPPORTUNITIES.md predates Aditya. The template's Opportunities tab still shows the old six lists, including "Keywords
to add", "Searches losing money" and "Languages". That is the first gap.

**PROCESS §0, Aditya's verdicts:**

| §0 item | Where it lands | Built? |
|---|---|---|
| Clusters we miss or under-cover (the coverage tree) | The Perf ask column, drafted per cluster from `c.cover`, `c.adg.state` and `drawer.dedicated` / `c.adg.landing`. Branches:<br>• low coverage, no keywords live → "Add its keywords"<br>• low, set-up incomplete → "Dedicated ad group + landing page"<br>• set-up complete → RPC vs CPC note to growth in the Paid tab<br>• high → the same tree on sub-clusters, in the Grouped view's thread rows | Coverage is in the table (T); drafts are N; sub-clusters are inferred from names (stand-in) |
| Keywords to add | Removed. Its "families not in Ads" list lives on inside "Add its keywords" | T has it; delete |
| Searches to add (search terms only) | A list attached to that cluster's ask. Click threshold **[Perf]**; close variants of live keywords left out (N). Mostly for new CEs | T has it at 50 clicks with ROI; rework |
| Searches losing money | Removed | T; delete |
| Ad group lands on the wrong page | The "Point its ad group to its page" ask, plus the ⚠ in the Page cell | T has the logic |
| A new page went live | "Start ads on the new page", released with the URL | N |
| Languages | Removed | T; delete |
| Searches no cluster takes | Only one home: the Gate 1 flag below, resolved in Unclaimed. A new cluster made from it then gets a drafted ask | T (Unclaimed) |

**PROCESS §4, Gate 1 flags.** Show a ⚑ in the Cluster cell and a **Flags · n** chip. Resolve each by fixing it or
choosing "Keep as is".

| Flag | Computable today? |
|---|---|
| Focus keyword doesn't fit | Yes, from focus keyword vs name words (heuristic) |
| Family split across clusters | Yes |
| Two clusters with the same focus family | Yes |
| "Other" holds more than 10% of searches | Yes |
| Paid searches no cluster takes, 50+ clicks | Yes |
| Cluster mixes buying and informational | No: needs keyword-level intent from the pipeline |

The "Flags resolved x of y" counter and the **Clusters reviewed** button are N.

**Conflicts inside PROCESS.md to settle:**
- **§4 Gate 5 is stale.** Done-checks should be per cluster: a keyword live, a dedicated ad group, the final URL is
  the cluster's page. Not per keyword family, and with no losing-money or language checks.
- **§4 Gate 4** (top 10 per list, Not now returns after 90 days, overdue) was written for the six old lists. Default:
  Send doesn't wait for it, and drafts nobody reviewed simply aren't sent.

## 9. Send (revised: map PROCESS §4 and §5 onto controls)

**What PROCESS.md says, and where it goes:**
- **Gate 1:** a header **Clusters reviewed** button with the reviewer's name and date, plus "Flags resolved 9 of 12"
  (N).
- **Gate 2:** the "Own page decided X of Y" tile and Agree (T).
- **Send** is disabled until Gates 1 and 2 pass, with a tooltip naming what's missing (N).
- **Send creates:**
  - one content item per own-page-Yes cluster with no live page, in Execution's queue
  - one Perf ask per CE per Send
- **Lanes:** Page → With content; Ads → Sent.
- **Back to growth:** push-backs, Won't do, Questions and reopened items feed "N to act on" (N).

**Gaps and conflicts:**
1. **Nothing is rendered.** The template has `data-sendperf` and `data-pagelaunch` handlers but no button uses them.
   Build one **Send** in the header.
2. **Krupa's Lock vs §5.** Her Lock only stamps `lockedAt` and shows "Unlock to change decisions"; nothing is frozen,
   and Perf is a separate ★ send.
   - **Default: follow §5, with no hard lock.**
   - Keep her banner as the record: "Sent 5 Nov 16:10 by X · send #1 · content n, Perf n".
   - An edit to a sent cluster marks it **"Changed since Send"**, and the header shows **Send changes (n)**. That sends
     one batch of updates and withdrawals to both teams.
   - **Already launched:** an item can't be withdrawn; content gets "changed after launch".
   - The Changes log gets one entry per Send and per batch.
3. **One Send or two?** §5 implies one; Krupa has two buttons. The user to confirm. Default: one Send, and an empty
   output is skipped.

## 10. Screens: every element and the step that uses it

**No data is removed.** Every number the pipeline exports stays in the tool. This section only decides where each
thing sits: in the first view, one click away (column group "+", side panel, pop-up), or in a panel. ↓ = moves out
of the first view and stays one click away.

**Analysis, first view**

| Element | Used by | Code |
|---|---|---|
| Title, CE, window | A1, B1 | T |
| Edit clusters + edit bar | A3, §6–7, C2 | T |
| Seeds · N | A2, B2 | T |
| Changes · N | all | T |
| Tabs: Analysis · Execution | all, C5 | T + K |
| Opportunities tab | ↓ Its items become the Perf ask column and the Send panel; the dropped flag types stay visible as data in the side panel (search terms with ROI, clicks by language) | T |
| Tiles (6) | A1, B1 | T |
| Flags and Perf-ask counters; Lock status | A3, A8, §9 | N |
| Review & send | A9 | N |
| "k to act on" | A10, D4 | N |
| Search box; Intent selector | A3, C2 | T |
| List / Grouped | A8 (sub-clusters) only | T |
| Expand all columns | Kept: one click to every column | T |
| Chips: Low coverage, No page | A8, A7 | T |
| Chips: Flags, Sent to content | A3, C1 | N |
| Pages with no cluster button | C4 | K / N |
| Cluster cell (name, intent, ⚑, lane chips) | A3, D7 | T + N |
| Searches / mo | A3, A7 | T |
| Demand "+4" | C2 | T |
| Organic orders | C2 | N |
| Page cell | A5, C3 | T + K |
| Page "+4": Headout entity, Ranking page, Page revenue | C7, C2 | T |
| Page "+4": Share of CE | Kept in the Page group | T |
| Supply | A4, B4 | T, relabelled |
| Own page | A7, B5, C2 | T + N |
| Perf ask | A8, B6 | N |
| Paid "+18": coverage, own ad group, clicks, ROI, CPC, RPC | A8 evidence | T |
| Paid "+18": the other 12 columns | Kept in the Paid group (folded) and in the panel | T |
| Totals row | Kept when a paid column is open | T |
| Unclaimed section | moves into a "Without a cluster" panel opened from the Flags chip | T |

**Side panel**

| Element | Used by | Code |
|---|---|---|
| Header: intent, parent, sub-cluster count | A3, A8 | T |
| Edit cluster select (Merge opens the dialog) | A3, §6 | T |
| Tiles: Searches, Coverage, Paid clicks, Lands on, Organic clicks, Page revenue, Products sold | A6 | T |
| Tiles: Avg CM1, AI Max share | Kept | T |
| Paid: status, what the data shows, how clicks were caught, ad groups serving it | A6, A8 | T |
| Paid: Perf ask box, RPC vs CPC trend | A8 | N |
| Paid: weekly bars, clicks by language | Kept as data. Languages are only dropped as an Opportunities flag | T |
| Keywords: families, Belongs in, Moved in, searches | A3, §7, D8 | T |
| Keywords: Add, Make focus keyword, top-10 trim | §7 | N |
| Products tab; page pop-up | A4, C7, A5 | T |
| Pages: its pages, how matched, orders, revenue, organic, where paid lands | A5, C3 | T |
| Pages: organic orders | C2 | N |
| Comments tab | Kept | T |

**Send to Perf** (inside Review & send; N; Krupa has a modal)
- package summary: seeds n, clusters n, keywords n
- agreed asks, each with type, reason, evidence and ×
- drafts not reviewed; set aside with their reasons
- asks held until a page is live
- sent asks with Perf's status
- Lock & send; Download package

**Execution** (Krupa's table)
- intent toggles
- Supply (N)
- Page type
- Collection and POI
- Subfolder slug, and the subdomain (read-only)
- Experiences fetched by
- Launch / Pick IDs / Flag supply / Queued; Launch all ready

T's "Set-up by team" table and the growth-facing Launch step plan are cut. The agent-log modal is reused for Launch.

**Seeds:** seeds (searches, led to cluster, ×, Add) · bucket grouping (K) · Leave out · Supply partners · Re-run.

**Changes:**
- entries with Undo (T)
- who did it, by role, and the reason (N; today it always says "You")
- Review # markers (N)

**Pages with no cluster** (K; N in T): path, page type, focus keyword and revenue, each with Map to cluster / Make it a
cluster / Not a cluster page.

**Krupa elements to cut:** the "Look at" lenses (replaced by column groups), "Ask EOS", and the ★ column.

## 11. Hand-off objects

**Content ticket** (one per Lock, then change sets)
- **Header:** CE, Review #, locked by and when, a link to Analysis filtered to these clusters.
- **Per item:**
  - cluster id, name, intent
  - focus keyword and its searches
  - top 10 keyword families with searches
  - supply state, product count and TGIDs
  - the own-page decision, who made it, and the reason if it differs from the suggestion
  - subdomain: yes/no, and its URL
  - suggested page type and slug
  - existing collection and POI IDs
  - the current page, if any, and where its ads land
  - status
- **Content's own pickups** are added with origin "content".

**Perf package**
- **Header:** CE, Review #, by and when, data window.
- **Seeds,** with bucket, plus the leave-out list and partners.
- **Every cluster:** id, name, intent, focus keyword, searches, page URL and subdomain, supply, and all keywords
  (family, searches, in-ads flag, "edited by growth").
- **Each ask:**
  - id, cluster id, type, origin (drafted / changed / added by growth), reason line
  - evidence: searches, supply, page and where ads land, coverage, families in Ads x of y, top 3 ad groups serving it
    with their share, RPC, CPC, ROI
  - for "Add its keywords": the missing families, minus the ones growth dropped
  - for "New cluster": search terms with clicks
  - landing URL, and whether it's held until the page is live
- **Coming back per ask:** status, reason or question, by, date, verification result.

## 12. Empty and edge states

- **No page and no supply:**
  - Supply "Unique, no supply"; the suggestion is No ("no product yet"); no ask is drafted. A growth-added ask warns
    "no supply".
  - A growth Yes shows **Flag supply** in Execution, and the Page lane becomes "Flagged for supply".
  - "Supply coming" allows Yes, but Launch waits.
- **Merged clusters that both had pages:** see section 6.
- **New CE with no paid data:**
  - The Paid group, coverage and the ads line are hidden.
  - The side panel opens on Keywords.
  - The only ask is "Set up this cluster".
- **Ask set aside:**
  - Not now needs a reason: too small · no supply · already handled · disagree · policy/brand.
  - It shows "Set aside · reason", is left out of the package, and is listed in the Set aside section.
  - It returns only if the data moved.
- **Perf says Won't do:** shown on the lane, and it counts in "to act on". Growth accepts it or reopens it.
- **Done but the data disagrees:** Reopened, and it goes to Perf in the next change set.
