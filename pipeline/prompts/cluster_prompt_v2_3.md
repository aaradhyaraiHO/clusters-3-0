# Clustering prompt v2.3 (Clusters 3.0)

v2.1: examples 1-10 instead of 5-10 (the minimum forced small intents to merge, against rule 1).
v2.2: rules 11-17 from the blind labelling of the v2.1 lists (bakeoff/prompt_v2_2_notes.md) and the answer-key misses:
reseller searches, precedence between cues, "A to B" searches, place signals, examples that fit their own definition,
intent of ticketed / closed / "best X" searches, in-place sights, and noise that shares the CE's name.
v2.3: rule 14's place signal applies to organic queries and research keywords only; a paid search from the CE's own
campaigns already carries the campaign's place (bare "whale watching" on a Sydney ad is Sydney demand).

You build the list of search-intent clusters for one Headout CE (an attraction, show, cruise, day trip or tour that
Headout sells). Code, not you, places every keyword and search into your clusters afterwards, using the definitions you
write. Your job is a clean, complete list of intents, each with a definition precise enough to place any search.

## Input (one JSON object)
- `ce`: id, name, city, type (attraction | show | cruise | day_trip | tour), and a one-line description of what is sold.
- `keyword_families`: Keyword Planner research keywords grouped into spelling-variant families. Each has a
  representative, its members and one volume (variants share Keyword Planner's bucketed volume; never add them up).
  These are the source of truth for which clusters exist.
- `paid_search_terms`: the top searches that triggered our ads, with clicks (existing CEs only). Use them to find intents
  real demand has that the research missed. They are in many languages.
- `organic_queries`: top Search Console queries with impressions (may be noisy: some belong to other attractions).
- `checklist`: the standard intents for this CE type.

## Rules
1. One cluster per demand intent, however small, but never two clusters for the same intent. Before finishing, check
   every pair: if a searcher typing the top keyword of one would be equally happy on the other, merge them.
2. Exactly one head-term cluster: the CE's name alone, in any language, with nothing added. Product clusters (tickets,
   cruises, tours) hold searches that add something to the name. The head term is the parent of nothing; it stands alone.
3. Every cluster gets a one-line definition stating what belongs and what does not, written for any language (name the
   intent, give foreign-language cue words where they matter, e.g. "entrada, eintritt, biglietti").
4. Name clusters after the intent, in plain English, never after one sample keyword or a sight the keywords are not about.
5. Cover the checklist for the CE's type. For every checklist item, either create a cluster or list it under
   `not_applicable` with a reason (no demand in the inputs, or not sold).
6. Operators and supply partners (companies that run the product we sell) get a cluster: one per operator with clear
   demand, or one "Operators & brands" cluster. Competitor resellers (GetYourGuide, Viator, Tiqets, Klook, Tripadvisor)
   are out of scope: list them under `out_of_scope`.
7. No "General", "Other", "Misc" or "Unassigned" clusters.
8. Give every cluster a parent (the bigger intent it belongs to) or null. Use parents for sub-intents of one sight or
   product (e.g. "Sistine Chapel" -> "Last Judgment", "Sistine Chapel tickets").
9. Stay in scope: intents a buyer of this CE might have. Other attractions, cities or products are out of scope unless
   the CE sells a combo with them; note big out-of-scope themes under `out_of_scope` with an example.
10. Keep the list readable: typically 12-35 clusters. Prefer fewer, sharper clusters over many thin ones, but never
    merge two different intents just to save a row.
11. Resellers: a reseller name plus a product ("viator milford sound cruise") belongs to that product's cluster; a reseller
    name alone belongs nowhere. Never exclude a search from a definition only because it names a reseller.
12. Precedence: when a search carries two cues (operator + format, species + "tour", departure town + "cruise", reviews +
    operator), the definitions must settle it. State the order in the definitions, using this default unless the CE
    needs another: operator > format or sub-product > departure point > generic product > head term. Reviews and
    "is it worth it" always go to the reviews cluster.
13. "A to B" searches with no product word ("queenstown to milford sound", "barcelona to montserrat") belong to the
    getting-there cluster; product clusters need a product word. Write this into both definitions.
14. Place signal: when the product's name also exists elsewhere (another city's studio tour, the bus vs the boat, a
    balloon ride in another country), a cluster's definition says which place signal organic searches and research
    keywords need; those without it belong nowhere. A paid search that triggered the CE's own ads already has the place:
    a bare "whale watching" or "black madonna tickets" from those ads belongs to the cluster it would join with the
    place added. Write definitions so both readings are clear.
15. Every example must satisfy its own cluster's definition and appear in exactly one cluster.
16. Intent: a ticketed or bookable sight inside the CE is TRANSACTIONAL; "best X" / "best X from Y" where X is the product
    sold is TRANSACTIONAL (the searcher is choosing what to buy); a permanently closed attraction is INFORMATIONAL.
17. In-place sights and noise: named sights, trails, parks and landmarks in the same place that the CE's visitors search
    for (a trail on the fiord, the national park around it, things to do there) get a cluster when the inputs show
    demand, even if Headout does not sell them; another place is out of scope (rule 9). Searches that share a word with
    the CE but mean something else (a film, a different natural feature, a game) are out of scope; list them under
    `out_of_scope`.

## Output (JSON only, no prose)
{
  "clusters": [
    {"name": str, "parent": str|null, "intent_type": "TRANSACTIONAL"|"PLANNING"|"INFORMATIONAL",
     "definition": str, "examples": [1-10 keywords copied from the inputs: all of them for a small intent, up to 10 for a
     big one; a small intent is never merged or dropped just because it has few examples], "is_operator": bool}
  ],
  "not_applicable": [{"checklist_item": str, "reason": str}],
  "out_of_scope": [{"theme": str, "examples": [str]}]
}

## Checklist by CE type
- All types: head term; tickets / booking; official site; prices; discounts and deals; opening hours or schedule;
  best time / season; weather; location, map, directions and getting there; things to do and what to see; rules, dress
  code, what to bring; safety; reviews and "is it worth it"; comparisons ("X vs Y"); operators and brands.
- attraction: each major sight inside; combos with nearby sights; the place itself if it is also a city or country.
- show: show-only vs dinner show; seating categories; dates and times; dress code; age rules.
- cruise: departure points; operators; durations and formats (day, overnight, fly-cruise, coach-cruise); seasons and
  weather; wildlife or sights seen; transfers and getting there; accommodation nearby.
- day_trip: departure city; transport options (train, bus, car, cogwheel/cable car); combos; guided vs independent;
  duration.
- tour: tour formats (walking, bus, private, group); themes and stops; meeting points; duration; languages.
