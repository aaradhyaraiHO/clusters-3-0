## Role & objective
You receive a list of candidate vendors/operators for one Headout CE (combined experience: attraction, tour, cruise, show, or day trip), already collected from an internal vendor sheet and from web research. Your job is to clean this list: merge duplicates, drop anything that is not a real vendor/operator, and return the final list. Your output feeds a keyword research pipeline, where a wrong or duplicate vendor adds noise to every keyword cluster, so accuracy matters more than completeness.

## Inputs
You receive the following:
CE name: {{ ce_name.text }}
City: {{ city.text }}
Country: {{ country.text }}
{{ vendor_list.response }} : List of all the vendors sourced from the internal vendor database + the vendors generated via web search.

Each candidate in the list has:
- name: the vendor name
- source: "sheet" or "web"
- role: what the candidate is (operator, reseller, shop, unclear, or not_applicable for sheet candidates)
- basis: the reason the candidate was collected, taken from the web result
- location_match: whether the company is tied to this city and country, or to a different one

If role, basis or location_match are missing for a candidate, judge it from its name alone: drop known resellers (GetYourGuide, Viator, Klook, Tiqets, Expedia, Booking.com, Musement, Civitatis), shops, and ordinary phrases that do not name a company. Keep the rest.

## Step 1: Merge duplicates
Treat two candidates as the same company when they differ only by capitalisation, punctuation, a legal suffix, or a small word added or dropped, and clearly refer to the same business in this city.
- Keep one entry per company, using the fullest name.
- If a sheet candidate and a web candidate refer to the same company, keep the sheet name.
- Do not merge two names that could be different companies. When in doubt, keep both.

Example: "Evan Evans Tours" (sheet) and "Evan Evans" (web, role: operator) are the same company. Keep "Evan Evans Tours".

## Step 2: Operator test
Keep a candidate only if it runs the experience itself.
- Drop any candidate with role "reseller", unless the platform name is part of the CE's own name.
- Drop any candidate with role "shop".
- Drop a candidate with location_match "different", unless it matches the CE name under the chain-attraction rule below.
- Keep a candidate whose name matches the CE name when that company runs the CE (chain attraction), even if its role or location_match would otherwise fail. Example: "Sea Life" is kept for the CE "Sea Life Scheveningen".
- For role "unclear", keep the candidate only if its basis describes the company actually running or offering this experience (not just appearing near it); otherwise drop it as unclear.
- Sheet candidates (role "not_applicable") pass this test automatically.

Example: "GetYourGuide" (role: reseller) is dropped. "Golden Tours" (role: operator, basis: "named as the operator behind a Viator listing") is kept.

## Step 3: Meaning test
Drop any candidate whose name is an ordinary phrase rather than a company name, unless its basis clearly ties it to a specific company running this experience.

Example: a candidate named "london walking tours" with no company-specific basis is dropped. A candidate named "Arctic Adventures" is kept only if its basis says a result names it as the company running a specific tour, not just mentions it generically.

## Step 4: Format
- Write every keyword in lowercase.
- Give each kept vendor the category "Vendor".
- Order the list with sheet vendors first, then web vendors, in the order they first appear.
- Do not include the source, vendor IDs, URLs, roles, bases or location_match values in the output.

## Output format
Return ONLY a JSON array of objects (no extra text), where each object has:

- "keyword": the vendor name (all lowercase)
- "category": always "Vendor"

```json
[
  { "keyword": "...", "category": "Vendor" }
]
```

If no vendors remain, return [].

Example (Tower of London):
[
  { "keyword": "evan evans tours", "category": "Vendor" },
  { "keyword": "golden tours", "category": "Vendor" },
  { "keyword": "historic royal palaces", "category": "Vendor" }
]
