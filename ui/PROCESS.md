# Clusters 3.0: how the work flows (draft for 5 Nov)

To agree with Krupa (10:00), test with a few growth managers (12:00) and settle with Parag (14:45). The UI is built
from this afterwards. Numbers marked *proposed* are starting points to agree, not decisions.

## 0. Agreed on 5 Nov (Krupa, Aditya from Perf)

These replace anything below that disagrees with them.

**One analysis view for growth and content, decisions made in one place.**
- The first view has about 5 columns:
  - cluster, with intent in its name
  - focus keyword and its searches
  - page
  - product (yes or no)
  - own page (suggested)
- Every deep dive is one click away: open a group or the side panel.
- No separate tabs that need syncing.
- Paid and Supply merge into one; the Supply tab goes; Demand stays as it is.
- Add organic performance, including orders from organic visits that landed on the cluster's page.

**Growth's real question:** will this cluster make money?
- That needs search volume plus a product that covers the intent.
- The product can be its own, or included in another. Sistine Chapel is covered by Vatican tickets and tours;
  Mona Lisa is covered by Louvre tickets, and content then makes that visible on the page.
- Cluster supply status is the main input content asked for, and it comes before page type.
- Do the big ones first: high searches with a product means a fast page and a fast set-up.

**Own page and subdomain are two separate fields,** with an editable slug. Growth can want a page without a subdomain.

**Content:**
- Gets the clusters growth recommends, plus supply status, focus keyword and page/mapping.
- Picks the page type at execution.
- Can go beyond growth's list.
- Changes to existing pages (layout, product mapping) stay manual and outside the tool.

**Perf thinks in clusters, not keywords** (Aditya):
- Close variants, plurals and the long tail are covered by broad match and AI Max.
- Adding keywords does not by itself add revenue, and too many long-tail keywords clutter campaigns.
- Perf does its own keyword research once a cluster is flagged.
- So the tool stops auditing keyword by keyword. "None of its keywords are bid" is enough at cluster level, and
  keyword lists in the side panel are trimmed to the top by searches.

**What growth sends Perf:** one package for Perf's tool (Rajita's ask):
- the seed keywords, all clusters and their keywords
- growth's recommendations, at cluster level or on single keywords

Perf makes the final call on every item.

**Opportunities, reworked:**

| List | Verdict |
|---|---|
| **Clusters we miss or under-cover** (new; the most important) | Build. Coverage = paid impressions ÷ searches, per cluster and sub-cluster, then the tree below |
| Keywords to add (keyword-planner keywords) | **Drop.** Decisions start from search terms, not keywords |
| Searches to add as keywords | **Rework:** search terms only (including AI Max ones), sorted by clicks, above a click threshold that gives about 10 conversions at the campaign's conversion rate; close variants of live keywords left out. Most useful for new CEs |
| Searches losing money | **Drop.** Perf does this on search terms over 13 weeks to 6 months, with high click thresholds |
| Ad group lands on the wrong page | **Keep.** Also: after a new page goes live, recommend that campaigns point to it |
| Languages with searches but no keywords | **Drop for now** |
| Searches no cluster takes | **Keep.** It is where new clusters come from |

**Coverage tree** (Aditya). Per cluster, then per sub-cluster:
1. **Coverage high:** look at the sub-clusters, e.g. Creation of Adam inside Sistine Chapel. Each goes through the
   same tree.
2. **Coverage low, keywords for it not live:** check supply first (growth). If there is supply, the Perf
   recommendation is "add this cluster's keywords". Perf decides where they go.
3. **Coverage low, keywords live:** check the set-up, from search term to keyword to a dedicated ad group to ad copy
   to landing page.
   - **Set-up incomplete:** recommend a dedicated ad group and landing page. Perf decides; not every cluster gets one.
   - **Set-up complete:** it comes back to growth on money. A cluster with higher CPC needs higher RPC (revenue per
     click) to scale at the same ROI target, so growth looks at RPC and the CPC trend per cluster, and works on RPC.

What counts as low coverage differs by cluster: generic POI terms run low by design, buying terms should run high. So
the bar is set low and growth or Perf can skip an item.

So Perf gets two kinds of recommendation: **add this cluster's keywords**, and **set up a dedicated ad group and
landing page**, plus "lands on the wrong page" and new clusters. The rest of this doc's Opportunities section is
superseded by this.

**Also from the call** (missed in the first pass):
- **What the tool is for:**
  - launch the right new clusters with the right landing pages
  - for existing CEs, check that the clusters are well divided: one focus keyword each, no intent split across two
    clusters
- **What exists today:** growth asked to see what a CE already has (child collections, pages, mapped products, live
  pages, campaigns), because they "fly blind" at the cluster stage. The first view must show this.
- **Supply includes planned supply:** content used to ask BDMs whether supply was coming (e.g. Bridge of Sighs at
  Doge's Palace). Supply status should say: covered, coming, or none. The source for "coming" is open.
- **Seed keywords:**
  - a panel on the right (the EOS left side is taken), editable, with partners and re-run
  - people should be able to see which clusters came from which seeds, to spot a missing seed
  - seeds go to Perf in the package
- **Edit clusters:** merge or delete clusters, add or remove keywords. Merging only changes focus. Open: what happens
  to the page and Perf status when merged clusters each had a page.
- **Growth's own recommendations:** beyond accepting AI suggestions, growth must be able to recommend:
  - a whole cluster or single keywords (Krupa's star)
  - merging two clusters (Perf's sense of a cluster)
  - removing a cluster or ad group from campaigns

  How this sits next to Accept is not designed yet.
- **Decisions are recorded:** asks to Perf and what Perf changed come back to the tool, so "what did we decide then"
  is answerable. This replaces ad-hoc Slack requests that aren't raised the way Perf wants.
- **Aditya's priority order:**
  1. find clusters and sub-clusters and raise their coverage
  2. keyword coverage across clusters
  3. negatives and losing money, only for new CEs, where campaigns are still learning. Existing campaigns correct
     themselves.
- **No double work:** if growth sends 50 asks and Perf re-analyses each one, two people do the same work. Each
  recommendation must carry the reason growth already checked:
  - searches
  - product covers it
  - page exists
  - coverage
  - RPC against CPC
- **Growth needs a primer:** adding keywords is not a revenue lever; AI Max and broad match cover variants and the
  long tail. The lever is more clusters with coverage.
- **Value for Perf:** the tool maps search terms to clusters, which Perf cannot pull today (their Replit tool works at
  ad group level).
- **Clusters ≠ pages, again:**
  - Perf may run private and guided tours as one; content may still give Last Judgment its own page.
  - Page decisions merge clusters; cluster edits don't.
  - An informational page can earn from organic (David at Accademia), which is why organic orders are shown.

**Open:**
- Parag's review moved to this evening (the call was cancelled).
- Krupa wants to work from this mockup. How she gets the code is your call: the code is local only.

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

**Only pages that sell get a Perf ask (5 Nov, against the page-mapping prompt and the page planning sheet).** Each
cluster's page type comes from the mapping prompt's routing (combo, named part of the CE, named experience, named area,
then the transactional, planning and informational rules; one Landing Page per CE). The tree above runs only for
selling page types: Landing Page, the tour types, Skip-the-Line, Combos, Sub-Attraction A/B/C, the Non-POI types,
operator pages, and a buying cluster's Custom Page. Informational and planning pages (an artwork, collections, opening
hours, history) are content's alone, however many searches they have. A sub-cluster no longer inherits an ask from a
parent that sells.
- **Sub-Attraction A** (every main ticket includes it, e.g. Raphael Rooms): its keywords go into the main ticket ad
  group, with ads landing on its page. It never gets an ad group of its own.
- **Never ask Perf for a page.** A cluster without a page gets "own ad group once its page is live"; the page goes to
  content through the own-page decision.

**Opportunities view (built 5 Nov).** One list next to Analysis and Execution, in Aditya's order and biggest first (a
product before none, then searches or clicks): cluster asks; Perf's call (content pages with searches, low coverage and a
product: Perf decides case by case); ads on the wrong page; searches to add (click threshold for about 10 conversions,
ROI at target, no close variants); AI Max searches; searches no cluster takes; revenue per click when set-up is complete.
Cluster asks and Perf's call share the Perf ask column's decision; accepted items go to Perf with Review & send.

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

## 1. Zoomed out

**What the system is for.** For every CE, turn search demand into three things, and keep them right over time:
- a page for each intent big enough to need one
- ads that bid on each intent and land on its page
- the right products on that page

**Three teams act on it:**
- **Growth** decides *what* is needed.
- **Content** builds pages.
- **Perf** builds ads.

**Parag's vision (30 Oct):**
- Launch a new CE in a day.
- Run it for about 800 CEs.
- Launch is an agent's step plan.
- Most of the data comes from BigQuery.
- An Opportunities list keeps CEs improving.
- The product push with Yuvraj starts around 16 Nov.

**How Krupa's view and Parag's fit together: the agent prepares, the owner approves.**
- Krupa's point stands: content owns page decisions, and growth should not pick entities or page types.
- Parag's point stands too: no one should do this work by hand.
- So every step is drafted by the pipeline or agent, and the team that owns the step approves it with one action.
- Ownership stays the same. The work disappears.
- "A day" then means waiting for three approvals (growth, content, Perf), not three teams doing manual work.
- 800 CEs works only if each person reviews **exceptions**, not every row. So each gate below says exactly what must
  be looked at.

## 2. The flow on one page

```
Pipeline drafts ──► GROWTH: Gate 1 clusters reviewed ──► Gate 2 own-page decisions confirmed ──► Send
                                                                                        │
                         ┌──────────────────────────────────────────────────────────────┴──────────────┐
                         ▼                                                                             ▼
               CONTENT queue (one item per "Yes")                                  PERF ask (one per CE per send)
               Gate 3 page plan approved                                           Gate 5 each item done / won't do
               Agent builds ──► page live (seen in BigQuery) ──► releases the waiting Perf item with its URL ──┘
                                                                                        │
Existing CEs, every cycle: GROWTH Gate 4 Opportunities triaged ──► accepted items join the next Perf ask
Closing the loop: BigQuery checks each "done" (keyword live, final URL changed) and reopens it if not.
```

## 3. What each team does, specifically

### Growth (per CE)

| # | Action | When | What they look at | What they do | Time *(proposed)* |
|---|---|---|---|---|---|
| G1 | Check seeds | New CE only | The seed list and partner brands | Add or remove seeds; mark generic brand names "not real" | 5 min |
| G2 | Review clusters (**Gate 1**) | After each clustering run | **Only the flagged clusters** (section 4) and a skim of the top 10 by searches | Merge, split, rename or move keywords, or "keep as is"; then sign off | 20–30 min |
| G3 | Confirm own-page decisions (**Gate 2**) | After G2 | **Only buying clusters with 1,000+ searches a month** *(proposed)*; the rest default to No | Agree with the suggestion, or change it and give a one-line reason | 10–15 min |
| G4 | Send | After G3 | A summary of what goes to content and to Perf | One click | 1 min |
| G5 | Triage Opportunities (**Gate 4**) | Existing CEs, each cycle | The top 10 of each list | Accept, or Not now with a reason | 20 min |
| G6 | Follow up | Ongoing | Status per cluster; content's questions on decisions growth changed | Answer, or reopen a decision | as needed |

Growth never picks a page type, collection, POI, ad group or match type.

### Content (per item in its queue)

| # | Action | What they get | What they do |
|---|---|---|---|
| C1 | Pick up | One item per cluster growth marked Yes with no live page:<br>• cluster, focus keyword, searches, keywords<br>• growth's decision and its reason if changed<br>• suggested page type and slug<br>• subdomain yes or no<br>• matched products | Assign an owner |
| C2 | Approve the page plan (**Gate 3**) | The agent's plan. The page type sets everything else (page planning rules). The agent has already searched for an existing collection or POI. | Confirm or change the page type and slug, then Approve; or Push back to growth with a reason |
| C3 | Build | Approved plan | Agent creates the collection, POI, subfolder, subdomain and product fetching (Yuvraj). Until the agent exists, content does it by hand from the same plan. |
| C4 | Write | The content brief the agent raises | Content, media, localisation |
| C5 | Own pickups | Informational and planning clusters, and buying clusters growth left at No | Add pages of their own. Logged like any other decision. |

### Perf (per Perf ask)

| # | Action | What they get | What they do |
|---|---|---|---|
| P1 | New cluster set-up | Cluster, focus keyword, keyword families with searches (and which are already live), landing page URL, language. No IDs, match types or CSV. | Set up in Perf's own tool; mark Done or Won't do (reason) |
| P2 | Improvements | Opportunities growth accepted, each with its evidence: the search term, clicks, spend and ROI | Same: Done, Won't do or Question, per item |

## 4. Gates: how we know each step really happened

**Gate 1, clusters reviewed.** The pipeline flags what a person must look at, from data we already have:
- the focus keyword doesn't fit the cluster. Milford examples: "milford sound lodges" as Underwater Observatory's focus keyword.
- a keyword family is split across two clusters (the "Belongs in" check)
- two clusters share the same focus keyword family
- the Other bucket holds more than 10% of searches *(proposed)*
- paid searches no cluster takes, with 50+ clicks
- a cluster mixes buying and informational keywords

To pass the gate:
- every flag is resolved, either fixed or "keep as is"
- growth clicks **Clusters reviewed**; their name and the date go to the Changes log
- the progress shows as "Flags resolved 9 of 12"

A re-run resets the gate only for clusters that changed.

**Gate 2, own-page decisions confirmed.** Every buying cluster above the threshold has a decision someone confirmed.
"Suggested" doesn't count until a person agrees with it. A change from the suggestion needs a reason, so content
sees why. Send stays disabled until gates 1 and 2 pass.

**Gate 3, page plan approved.** Content approves each plan before anything is created. A push-back returns the item
to growth, and the status shows it.

**Gate 4, Opportunities triaged.** Each cycle, the top 10 of every list must be Accepted or Not now.
- Not now needs one reason: policy/brand, too small, already handled, or disagree.
- It comes back after 90 days *(proposed)*.
- Items left untriaged past the cycle show as overdue on the CE.

**Gate 5, Perf items closed.** Perf marks each item. Where BigQuery can check it, the tool checks the next day:
- **Keyword to add:** done when the family has a live keyword in an enabled ad group.
- **Wrong landing page:** done when the ad group's final URL is the cluster's page.
- **Losing money and languages:** Perf's mark is final; we can't verify these from data.

An item marked done that the data contradicts reopens with a note.

## 5. Handoffs, specifically

**Growth to content.**
- Send creates one content item per Yes cluster with no live page. It lands in Execution → Content: a queue with an
  owner, a status and the reason.
- Content sees growth's changed decisions with their reasons and the Changes log.
- A decision growth changes after Send updates the item, or withdraws it if it is not built yet.

**Content to Perf.**
- When a new page goes live, the pipeline sees it in the pages table (published), maps it to its cluster and sets
  the status to Page live.
- Any Perf item waiting on that page is released with the URL.
- Until then a new cluster's Perf item either waits or goes now to an existing page. This is open question 3.

**Growth to Perf.**
- One Perf ask per CE per Send. It holds the new cluster set-ups and the accepted Opportunities.
- Where it lands is open (question 4): a queue here, a ticket, or Perf's tool directly.
- Growth sees each item move: sent → done / won't do / question.

**Back to growth.** Content's push-backs, Perf's "won't do" and questions, and reopened items all land on the CE as
items to act on. The "N to act on" count includes them.

**Cluster status line** (shown in the table and the log):
Analysed → Reviewed → Own page decided → With content → Page live → Sent to Perf → Live in ads,
or Flagged for supply, or No own page (served by …).

## 6. What can be automated

| Work | Today | Next (Krupa / us) | Agent (Yuvraj, ~16 Nov) | Stays human |
|---|---|---|---|---|
| Keyword research and clustering | Pipeline | Prompt v2.1 (Krupa, Harsha) | | Review flags (G2) |
| Searches, organic queries and ad keywords to clusters | Pipeline mapper | | | |
| Cluster to existing page | Stand-in: tag, then name | **Krupa's page-mapping prompt** | | |
| Products per cluster | From the page's real list | Shivam's match when there's no page | | |
| Quality flags for Gate 1 | Partly (family split, unclustered) | **Build all six** | | |
| Own-page suggestion | none | **Krupa's pipeline** (DRD + searches + page exists) | | Confirm (G3) |
| Page type and slug suggestion | none | Rules from the cluster (POI exists → sub-attraction, etc.) | | Approve (C2) |
| Collection, POI, subdomain, product fetching | Rules known (page planning sheet) | | **Creates them** | |
| Content brief | Manual | | **Raised** | Writing (C4) |
| Opportunities | Pipeline (6 types) | Missing types: "grew enough for a page", supply | | Triage (G5) |
| Perf ask | none | **Bundle and Send** | Could file the ticket | Set-up (P1, P2) |
| Done checks (Gate 5), page live detection | none | **From BigQuery, daily** | | |

The only work a person must do: review flags, confirm page decisions, approve page plans, triage Opportunities, set
up ads, and write content. Everything else is drafted.

## 7. A new CE in a day (target)

| Time | Who | Step |
|---|---|---|
| 09:00 | Pipeline | Keywords, clusters, mapping, flags, suggestions (about 1–2 h, unattended) |
| 11:00 | Growth | G1–G4 (about 1 h). Send. |
| 12:00 | Content | C1–C2: approve plans (about 30 min) |
| 12:30 | Agent | Builds pages; raises briefs |
| afternoon | Perf | P1 on the Perf ask. Pages go live as they are built. |

What stops this today:
- clustering quality, which is why Gate 1 exists
- page mapping (waiting on Krupa's prompt)
- the own-page suggestion (Krupa's pipeline)
- the agent (Yuvraj)
- the Perf ask destination (question 4)

**800 CEs:** run the pipeline for all of them, then work through the queue in order of opportunity size. A CE with no
flags and no big decisions could clear the gates in minutes.

## 8. Plan

**5 Nov, decide (Krupa at 10:00, Parag at 14:45):**
1. The principle "agent prepares, owner approves", and the end state: does content still approve page plans (Gate 3)
   once the agent exists?
2. The thresholds: own-page decisions for buying clusters with 1,000+ searches; top 10 per list for triage; Not now
   comes back after 90 days.
3. Does a new cluster's Perf ask wait for its page to go live?
4. Where does the Perf ask land: a queue here, a ticket, or Perf's tool? (Satvik and Rajesh)
5. How often are existing CEs reviewed: monthly, or on a trigger?
6. Who maps live pages that no cluster takes: growth or content?
7. Does content keep its own view (queue only), apart from the analysis table?

**Then build, in this order (each step mocked up, approved, then built):**
1. Gate 1: the six quality flags and the "Clusters reviewed" sign-off.
2. Gate 2: the own-page column. Use a rule as a stand-in until Krupa's pipeline is ready.
3. Send: the content queue and the Perf ask bundle with statuses.
4. Gate 4: triage rules (top 10, reasons, return after 90 days, overdue).
5. Daily BigQuery checks: page live, keyword live, final URL.
6. Hand Yuvraj the step plan for C2–C3, built on the page planning rules.

**Mine to do:**
- Send Krupa my prompt learnings for Harsha.
- Share the mockup with Krupa: an HTML file or a private artifact (your call).
