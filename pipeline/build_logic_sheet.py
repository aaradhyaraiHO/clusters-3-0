"""The Clusters 3.0 logic book: one Google Sheet documenting goals, pipeline steps, rules, hit rates, robustness,
decisions, bugs and open questions, for the agentic keyword-clustering build and for training.
Content is kept here so the sheet can be rebuilt; numbers come from validation_plan.md and the runs it cites.
Usage: python build_logic_sheet.py [--sheet-id ID]   (creates a new sheet when no id is given)
"""
import argparse
import json

from upload_workbook import gws, write

TABS = {}

TABS["README"] = [
    ["Clusters 3.0 · logic book (backend)", ""],
    ["What this is", "Every logic, workflow, pipeline step, rule, hit rate and decision behind the Clusters 3.0 backend, for the agentic keyword-clustering build and for training."],
    ["Goal (Parag, 10 Nov)", "Enter any CE ID and get correct clusters and correct numbers automatically, before engineering builds the real tool."],
    ["Owner", "Aaradhya (pipeline). UI: the Clusters 3.0 UI session. Page-type mapping: Krupa + Harsha. Execution PRD: Krupa + Anuj. Data review: Satvik."],
    ["How to run one CE", "cd ~/analytics/.claude/worktrees/clusters-3-0/scripts/clusters_3_0 && .env-clusters/venv/bin/python run_ce_pipeline.py <CE id> [--prompt original|patched] [--runs 3] [--from <step>]"],
    ["Tabs", "Asks · Pipeline · Rules · Hit rates · Robustness · Pipeline runs · Decisions · Bugs fixed · Open questions · Agent actions · Sources"],
    ["Caveat on every accuracy number", "Test labels are AI-drafted (blind), not yet corrected by BGM / Perf / Krupa. Reviewer tabs are in the bake-off sheet."],
    ["Last updated", "19 Nov 2026"],
]

TABS["Asks"] = [
    ["#", "Ask (10 Nov call with Parag, Krupa, Satvik)", "Owner", "Status", "Where"],
    [1, "Write out every backend step with its logic (also training material)", "Aaradhya", "Done: this sheet", "Pipeline, Rules tabs"],
    [2, "Clusters you can trust, so growth needs fewer manual fixes; list improvements and the ~10 actions growth still takes", "Aaradhya", "In progress: prompt comparison, feedback note to Harsha", "Hit rates, Open questions, Agent actions"],
    [3, "Simpler data: BigQuery only, focus keyword where possible", "Aaradhya", "Done for the pipeline (pull step is BigQuery only)", "Pipeline step 1"],
    [4, "Enter a CE ID and it just works; Satvik reviews and takes over", "Aaradhya, Satvik", "Built: run_ce_pipeline.py (pull → cluster → convert → place → judge → score); Sydney runs end to end in ~3 min", "Pipeline runs"],
    [5, "Opportunities at 80% precision, checked by Perf owners before one-click actions", "Aaradhya, Perf", "Not started", "Open questions"],
    [6, "Automated decisions (own page yes/no) made robust and tested on new CEs", "Aaradhya, Krupa", "Not started", "Open questions"],
    [7, "Data behind the current-status and setup-status columns", "Aaradhya (data), UI session (columns)", "Columns mocked in the tool; backend checks not built", "Open questions"],
    [8, "Decide what stays relevant once URL-parameter clusters arrive (3–4 months)", "Parag, Aaradhya", "Not done", "Open questions"],
]

TABS["Pipeline"] = [
    ["Step", "What it does", "Input", "Output", "Method / model", "Script", "Automated?", "Confidence", "Notes"],
    ["1. Keywords", "Pull the CE's keywords and clean them", "EOS keyword research (BigQuery)", "eos_keywords.csv", "SQL: normalise spelling, spelling-variant groups (one shared volume), drop competitor spellings without their group, one cluster per keyword", "bq/eos_base.sql; run_ce_pipeline.py pull", "Yes", "High", "EOS keywords only (agreed). CEs EOS hasn't run on have no keywords yet."],
    ["1b. Searches", "Pull the CE's paid search terms and organic queries", "Google Ads SearchQueryStats, Search Console (BigQuery)", "pair_terms.csv, gsc_terms.csv", "SQL: campaigns tagged cid<CE>, last 90 days; Search Console on headout.com pages matching the CE + its microbrand sites", "run_ce_pipeline.py pull", "Yes", "High", "Organic page filters are broad for some CEs (Seine, Harry Potter)."],
    ["2a. Cluster list", "Create the list of intent clusters", "Keywords + volumes, CE name, city, country, subcategory", "Clusters: name, level, type, identifiers, focus keyword (+ definition with the patched prompt)", "Harsha's EOS clusters prompt (18 Nov), claude-opus-5-5, effort medium, 64K output, JSON only; --runs 3 keeps the run that agrees most", "run_ce_pipeline.py cluster", "Yes (CLI fallback until an API key is set)", "Medium", "Patched version adds 10 overrides (Rules tab)."],
    ["2b. Keyword → cluster", "Put every keyword into one cluster", "Cluster list + definitions, keywords", "assignments (keywords)", "Jev (TypeSafe) by meaning; EOS-style identifier matching kept only for comparison", "jev_classify.py; run_ce_pipeline.py place", "Yes", "High", "EOS's identifier matching leaves 14–246 keywords unclaimed per CE."],
    ["3. Search → cluster", "Put every paid search and organic query into a cluster", "Cluster list + definitions, searches", "assignments (paid, organic)", "Jev by meaning; paid told it came from the CE's ad (place signal); organic cut at 0.5 confidence", "jev_classify.py --context paid", "Yes", "High (paid), medium (organic)", "Organic misses come mostly from clusters that don't exist."],
    ["4. Search → keyword", "Which keyword triggered each search", "Google Ads", "search_term_pairs", "Google Ads records it; one SQL query", "pulls.sql", "Yes", "High", "Used for In Ads, own ad group, opportunities."],
    ["5. Opportunities", "Searches with clicks that aren't keywords, leftover searches as new-cluster candidates, clusters with no live keyword", "Steps 3 + 4", "Opportunities list", "Compare where a search sits (step 3) with what triggered it (step 4); leftovers grouped", "UI session export; group_unclustered.py", "Partly", "Low (precision untested)", "Target 80% precision with Perf (ask 5)."],
    ["6. Judge", "Estimate accuracy of a run", "Placements + definitions", "judge_paid.csv, judge_organic.csv", "A second model (Claude) checks 100 paid (by clicks) + 100 organic (by impressions)", "run_ce_pipeline.py judge", "Yes", "Medium (AI checking AI)", "Gives an accuracy estimate for CEs with no labelled test set."],
    ["7. Score", "Scorecard per run", "All of the above", "scorecard.json", "Clusters, unclaimed keywords, share with no cluster, low-confidence share, judged % wrong, run agreement", "run_ce_pipeline.py score", "Yes", "High", ""],
    ["8. List checks (BigQuery)", "Flag bad EOS lists before use", "EOS lists", "clusters_3_0_list_verdict", "Head term, Ads-based overlap, duplicates, catch-all", "bq/eos_base.sql, bq/ads_overlap.sql, bq/eos_fix.sql", "Yes", "Low", "Checks run on raw EOS, not on the pipeline's final list yet."],
]

TABS["Rules"] = [
    ["Area", "Rule", "Why", "Evidence", "Where"],
    ["Keywords", "Keywords come only from EOS; our clean-up runs on top", "Agreed with Aaradhya, 4 Nov", "", "bq/eos_base.sql"],
    ["Keywords", "Spelling variants that share one Keyword Planner volume are one group; volume is counted once", "Planner gives variants one bucketed volume; summing inflates demand", "Vatican: 74K ticket volume shared by 76 spellings", "graph_cluster.merge_shared_volume"],
    ["Keywords", "A competitor spelling leaves its group; the group stays", "One competitor spelling used to drop a whole group", "Vatican lost 29 ticket keywords (90.5K/mo); also HP, Cappadocia, Sydney", "graph_cluster.drop_competitors"],
    ["Clusters", "One cluster per demand intent, however small; never merge on paid data", "Clusters ≠ pages ≠ ad groups", "", "prompt v2.x rule 1"],
    ["Clusters", "Exactly one head-term cluster: the CE name alone", "Head term overlapping a product cluster was the biggest non-POI failure", "Milford 53% paid wrong on the EOS list", "prompt v2.x rule 2"],
    ["Clusters", "Every cluster gets a one-line definition (what belongs, what doesn't)", "Definitions are what make placement by meaning accurate", "Vatican paid wrong: rules mapper 22.9% → Jev with definitions 0.3%", "prompt rule 3 / patch O9"],
    ["Clusters", "Paid searches from the CE's own ads carry the CE's place", "Bare 'whale watching' on a Sydney ad is Sydney demand", "Sydney paid 6.5% → 0.0% wrong (v2.3)", "prompt v2.3 rule 14; jev --context paid"],
    ["Clusters (patch)", "O1 keep all languages", "Harsha's rule 1.1.5 was read two ways; non-English is a large share of paid demand", "Vatican: 42% of paid clicks unplaced by EOS matching", "clusters_patched.md"],
    ["Clusters (patch)", "O2 keep official-site searches as their own cluster", "High-intent buyers", "Vatican: 'vatican museum official website' 2,594 clicks", "clusters_patched.md"],
    ["Clusters (patch)", "O3 every keyword ≥ 500 searches/mo sits in a cluster", "EOS leaves high-volume keywords unclaimed", "GBR head term (301K) left in Others in EOS 18 Nov", "clusters_patched.md"],
    ["Clusters (patch)", "O4 no empty playbook clusters", "Mandatory topics produced empty clusters", "5–8 empty per CE (HP, Cappadocia, GBR, Seine)", "clusters_patched.md"],
    ["Clusters (patch)", "O5 named place/operator/variant needs ≥ 300 searches/mo for its own cluster", "1-keyword clusters inflate lists", "GBR 61–88 clusters across runs on the original prompt", "clusters_patched.md"],
    ["Clusters (patch)", "O6 a different product in the same city is off-topic", "Studio tour absorbed into the walking-tours CE", "Harry Potter", "clusters_patched.md"],
    ["Clusters (patch)", "O7 show playbook", "No playbook for shows", "Moulin Rouge", "clusters_patched.md"],
    ["Clusters (patch)", "O8 no single common words as identifiers", "'last' sent 'last minute tickets' to Last Judgment", "Vatican AI Max inflation", "clusters_patched.md; polyfuzz_mapping.distinctive_ids"],
    ["Clusters (patch)", "O10 output JSON only; no reasoning trace", "The trace made one call run over an hour", "Sydney: hang → ~3 min", "run_ce_pipeline.JSON_ONLY"],
    ["Placement", "Jev places keywords and searches by meaning, not identifier matching", "Identifier matching misplaces or drops non-English and broad searches", "Harsha lists: Vatican paid 44% (EOS) → 3.2% (Jev)", "jev_classify.py"],
    ["Placement", "No confidence cut for paid; 0.5 for organic", "A cut unplaces real paid searches; organic has off-topic noise", "Vatican: paid cut 0.6 → 12.7% wrong; organic best at 0.5", "jev_classify.py --min-prob"],
    ["Ads", "'In Ads' = live keyword in an enabled ad group of an enabled campaign; spelling groups count once", "Impressions-based 'In Ads' marked live keywords missing", "45 Vatican keywords wrongly 'Not in Ads'", "UI export (export_hybrid.py)"],
    ["Ads", "Own ad group: the live ad group holding the focus keyword; full / focus-only / missing", "Parag's method, 30 Oct", "", "export_hybrid.own_ad_group"],
    ["List checks", "Ads-based overlap: a search served by keywords of two clusters (2nd ≥ 20% of clicks)", "Catches meaning overlaps word checks miss", "Flags Milford (12.1%)", "bq/ads_overlap.sql"],
    ["Accuracy", "Pass marks: paid < 5% of clicks wrong, organic < 10% of impressions wrong, completeness ≥ 95% of Krupa's checks, stability < 3% moved", "Agreed gates (validation plan)", "", "validation_plan.md"],
]

TABS["Hit rates"] = [
    ["Share of test searches in the wrong cluster (blind labels). Paid = by clicks, organic = by impressions. '' = not measured.", "", "", "", "", "", "", "", "", "", "", ""],
    ["CE", "Type", "EOS list (30 Oct) paid", "EOS list organic", "Prompt v2.1 paid", "v2.1 organic", "Prompt v2.2/2.3 paid", "v2.2/2.3 organic", "Harsha prompt + EOS matching paid", "+ EOS matching organic", "Harsha prompt + Jev paid", "+ Jev organic"],
    ["189 Vatican", "Attraction", "0.3%", "6.3%", "", "", "", "", "44.1%", "34.4%", "3.2%", "13.2%"],
    ["325 Park Güell", "Attraction", "0.5%", "2.4%", "", "", "", "", "3.1%", "5.1%", "0.0%", "0.5%"],
    ["243 Eiffel", "Attraction", "0.6%", "1.0%", "", "", "", "", "29.2%", "21.8%", "0.9%", "3.5%"],
    ["257 Moulin Rouge", "Show", "3.2%", "8.1%", "", "", "", "", "2.2%", "11.0%", "0.1%", "8.2%"],
    ["3945 Milford", "Cruise", "53.4%", "30.5%", "0.0%", "0.4%", "0.0%", "7.3%", "3.0%", "13.8%", "0.7%", "21.7%"],
    ["2743 Great Barrier Reef", "Cruise", "4.2%", "40% (12 searches)", "0.1%", "15.5%", "0.5%", "37.1%", "1.0%", "45.1%", "0.9%", "44.9%"],
    ["1695 Sydney", "Cruise", "9.2%", "9.5%", "5.0%", "6.1%", "0.0% (v2.3)", "5.4% (v2.3)", "11.6%", "85.1%", "0.3%", "4.7%"],
    ["3176 Montserrat", "Day trip", "20.0%", "42% (22 searches)", "0.3%", "23.6%", "0.7% (v2.3)", "24.5% (v2.3)", "7.9%", "32.6%", "0.2%", "24.5%"],
    ["261 Seine", "Cruise (new CE)", "", "0%", "", "0.9%", "", "0%", "", "9.4%", "", "0.0%"],
    ["2010 Harry Potter", "Tour (new CE)", "", "15.4%", "", "0.6%", "", "3.3%", "", "38.7%", "", "28.9%"],
    ["2640 Cappadocia", "Tour (new CE)", "", "1.2%", "", "0.3%", "", "0.3%", "", "69.1%", "", "1.8%"],
    ["", "", "", "", "", "", "", "", "", "", "", ""],
    ["Krupa's checks passed (completeness)", "", "EOS as-is", "Hybrid (EOS names + algorithm)", "Prompt v2.1", "Prompt v2.2", "Harsha + EOS matching", "Harsha + Jev", "EOS 18 Nov (live)", "", "", ""],
    ["Non-POI (7 CEs)", "", "56%", "50%", "70%", "82%", "64%", "61%", "Milford 62%, GBR 62%", "", "", ""],
    ["Attractions + show (4 CEs)", "", "53–55%", "67%", "", "", "65%", "65%", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", "", "", ""],
    ["Vatican, tool's mapper (3 Nov)", "", "Rules mapper paid 22.9% / organic 41%", "Jev with definitions paid 0.3% / organic 4.9%", "", "", "", "", "", "", "", ""],
]

TABS["Robustness"] = [
    ["Test", "What it shows", "Result", "Pass mark", "Status", "Date"],
    ["Jev stability", "Re-ask Jev with the cache off; share of clicks that change cluster", "Sydney 2.1%, Montserrat 0.7% (all changes were low-confidence searches)", "< 3%", "Pass", "6 Nov"],
    ["List reproducibility (prompt v2.3)", "Run the prompt 3 times; do keywords group the same way?", "ARI 0.87–0.94; Sydney 30/33/36 clusters, Montserrat 32/37/36", "≥ 0.9 ARI, stable count", "Mostly; count swings", "6 Nov"],
    ["List reproducibility (Harsha original, automated)", "3 runs per CE", "GBR 61/84/88 clusters; Milford 61/46/50; Sydney 37/36/39", "Stable count", "Fails on GBR", "19 Nov"],
    ["List reproducibility (Harsha patched, automated)", "3 runs per CE", "Milford 43/42/37; Sydney 17/16/18", "Stable count", "Better", "19 Nov"],
    ["Interpretation agreement (Harsha prompt)", "Do two careful runs read the same rule the same way?", "Non-English rule read both ways by different runs", "Same reading", "Fails → patch O1", "19 Nov"],
    ["BigQuery list checks, 663 EOS CEs", "Lists passing every check", "44 (7%); Ads overlap: 43 of 253 with paid data pass", "", "Most EOS lists need fixing", "4–6 Nov"],
    ["Catch-all fix (BigQuery)", "Effect of merging (General)/Other clusters", "Mapping-ok 292 → 300; hygiene 71 → 96 of 663", "", "Modest", "6 Nov"],
    ["Human labels", "Accuracy against people, not AI", "Reviewer tabs built; not yet filled", "≥ 90% agreement between two people", "Waiting on reviewers", "6 Nov"],
]

TABS["Pipeline runs"] = [
    ["Automated runs (run_ce_pipeline.py, 19 Nov). Judged wrong = a second model's check of 100 paid + 100 organic placements.", "", "", "", "", "", ""],
    ["CE", "Prompt", "Clusters per run (3 runs)", "Unclaimed by EOS matching", "Judged wrong paid", "Judged wrong organic", "Minutes"],
    ["1695 Sydney", "Original", "37 / 36 / 39", "44 of 256", "0.1%", "1.1%", 9],
    ["1695 Sydney", "Patched", "17 / 16 / 18", "20 of 256", "1.6%", "1.2%", 10],
    ["3945 Milford", "Original", "61 / 46 / 50", "27 of 334", "0.8%", "1.7%", 26],
    ["3945 Milford", "Patched", "43 / 42 / 37", "39 of 334", "1.1%", "16.8%", 17],
    ["2743 Great Barrier Reef", "Original", "61 / 84 / 88", "14 of 816", "0.0%", "28.8% (13 queries)", 17],
    ["2743 Great Barrier Reef", "Patched", "running", "", "", "", ""],
    ["3176 Montserrat", "Original", "pending", "", "", "", ""],
    ["3176 Montserrat", "Patched", "pending", "", "", "", ""],
]

TABS["Decisions"] = [
    ["Date", "Decision", "By", "Why"],
    ["29 Oct", "Hybrid: keep EOS's cluster list, assign keywords with our algorithm (attractions)", "Aaradhya", "Best bake-off result for Vatican (92% right intent)"],
    ["30 Oct", "Map paid data only at search-term level, never by ad group", "Abby (Perf)", "Ad groups cross-trigger"],
    ["30 Oct", "Coverage = paid impressions ÷ planner searches", "Parag, Abby", "Closest measure available"],
    ["30 Oct", "Aim for ~80% of the value from 1–2 BigQuery pulls, not many Ads API calls", "Parag", "API quota"],
    ["3 Nov", "Switch the tool's search mapping to Jev with definitions", "Aaradhya", "Vatican paid wrong 22.9% → 0.3%"],
    ["4 Nov", "Keywords from EOS only; clean-up on top", "Aaradhya", ""],
    ["4 Nov", "Build accuracy on existing EOS CEs before expanding", "Aaradhya", ""],
    ["6 Nov", "UI session builds the tool; this session makes the pipeline robust", "Aaradhya", ""],
    ["10 Nov", "Current-status column first; setup status second; launch per cluster, one send to content per CE", "Parag, Krupa", "See Asks tab"],
    ["10 Nov", "Get opportunity precision to 80% before one-click actions", "Parag", ""],
    ["19 Nov", "Use EOS's (Harsha's) prompt for clusters and Jev for placement; send overrides to Harsha", "Aaradhya", "Identifier matching is where most errors come from"],
]

TABS["Bugs fixed"] = [
    ["Date", "Bug", "Effect", "Fix"],
    ["30 Oct", "Mapper stripped non-Latin text (a–z only)", "Cyrillic/Greek searches unplaced", "Keep every script in normalisation"],
    ["2 Nov", "Single common words as identifiers ('last', 'guide')", "'last minute tickets' → Last Judgment; inflated AI Max", "Drop one-word identifiers used in an outside phrase"],
    ["3 Nov", "Jev prompt hardcoded 'Vatican Museums, Rome' for every CE", "Wrong context for 7 non-POI CEs", "Read CE name and city per CE"],
    ["3 Nov", "One competitor spelling dropped its whole keyword group", "Vatican lost 29 ticket keywords (90.5K/mo); HP, Cappadocia, Sydney too", "Drop only the competitor spelling"],
    ["3 Nov", "'In Ads' counted served keywords, not live ones; variants judged one by one", "45 Vatican keywords wrongly 'Not in Ads'", "Live keyword list; one row per spelling group"],
    ["19 Nov", "Two runs in the same second shared a folder", "Organic overwrote paid results", "Unique run IDs"],
    ["19 Nov", "Clustering call ran as a full agent with tools, then with a reasoning trace", "Hangs of 45 min to 5 h", "One tool-less turn, JSON only, pinned model and effort"],
    ["19 Nov", "Scoring counted 'unplaced' as wrong even when the right answer was 'no cluster'", "Organic EOS-style numbers too high", "Fixed comparison"],
    ["19 Nov", "Pipeline reused an expired copy of gcloud credentials", "BigQuery step failed", "Refresh the copy every run"],
]

TABS["Open questions"] = [
    ["#", "Question", "Who decides", "Status"],
    [1, "Should 'milford sound tours' sit in the head term's cluster?", "Krupa", "Open"],
    [2, "Best time to visit and timetable: one cluster or two?", "Krupa", "Open"],
    [3, "Lord of the Rings (Milford): own cluster or excluded?", "Krupa", "Open"],
    [4, "Does a state or country ('NSW', 'Australia') count as a place word in organic searches?", "Krupa", "Open"],
    [5, "Adopt the 10 overrides in EOS's clusters prompt?", "Harsha", "Feedback note drafted, not sent"],
    [6, "Opportunity buckets Perf can act on; precision test per CE", "Aaradhya + Perf owners", "Not started"],
    [7, "Own-page yes/no rule and its accuracy on new CEs", "Krupa + Aaradhya", "Not started"],
    [8, "Data checks behind current-status and setup-status columns", "Aaradhya", "Not started"],
    [9, "What stays relevant after URL-parameter clusters", "Parag", "Not started"],
    [10, "API key for the clustering step (ANTHROPIC_API_KEY or `ant auth login`)", "Aaradhya", "Open: runs on the CLI fallback"],
    [11, "Reviewers to correct the test labels (BGM, Perf, Krupa)", "Aaradhya to share", "Open"],
    [12, "Patched prompt: does folding small clusters hurt organic accuracy? (Milford organic 16.8%)", "Aaradhya", "Investigating"],
]

TABS["Agent actions"] = [
    ["Action an agent can run", "Pipeline step(s)", "Command / input", "When"],
    ["Run a CE end to end", "pull → cluster → convert → place → judge → score", "run_ce_pipeline.py <CE>", "New CE, or monthly refresh"],
    ["Re-cluster with 3 runs for stability", "cluster", "--from cluster --runs 3", "List looks unstable or too large"],
    ["Use the patched prompt", "cluster", "--prompt patched", "Testing Harsha's overrides"],
    ["Re-place searches after a list edit", "place → judge → score", "--from place", "After merge/split/rename of clusters"],
    ["Check accuracy of a run", "judge", "--from judge", "Any time"],
    ["Flag bad EOS lists across all CEs", "List checks", "bq/eos_base.sql, bq/ads_overlap.sql", "Before choosing which CEs to fix"],
    ["Fix catch-all clusters", "List fix", "bq/eos_fix.sql + bq/run_fixed_checks.py", "EOS list has (General)/Other clusters"],
    ["Score a list against Krupa's checks", "Answer keys", "score_answer_keys.py", "Comparing prompt versions"],
    ["Growth actions still manual (for agent mode)", "", "merge clusters, split, rename, add seed keywords and re-run, mark own page, send to content, send Perf ask", "See UI session's logic doc"],
]

TABS["Sources"] = [
    ["What", "Where"],
    ["Pipeline code", "~/analytics/.claude/worktrees/clusters-3-0/scripts/clusters_3_0 (branch worktree-clusters-3-0, local)"],
    ["One-command run", "run_ce_pipeline.py; CE metadata in ce_sources.csv"],
    ["EOS prompts (Harsha, 18 Nov)", "prompts/eos_harsha_2026-11-18/ (seeds, clusters, page_type); patched: clusters_patched.md"],
    ["Our prompt versions", "prompts/cluster_prompt_v2.md, v2_2, v2_3"],
    ["Blind test sets", "test_sets/, test_sets_v2/, test_sets_v22/, test_sets_v23/, test_sets_harsha/"],
    ["Krupa's answer-key checks", "answer_checks.csv; scorer score_answer_keys.py"],
    ["BigQuery tables", "headout-dev.dbt_aaradhya.clusters_3_0_* (eos_keywords, eos_keywords_clean, list_checks, ads_overlap, list_verdict, eos_fix_log, *_fixed)"],
    ["Bake-off sheet (reviewer + mapping tabs)", "https://docs.google.com/spreadsheets/d/1Q1vxM04_OUR3McrkI2ws6dDbezXKiUZ2aXlzu6aM5gc/edit"],
    ["Scorecard history", "thoughts/shared/clusters-3.0/bakeoff/validation_plan.md"],
    ["Feedback note for Harsha (draft)", "thoughts/shared/clusters-3.0/bakeoff/harsha_prompt_feedback.md"],
    ["EOS prompts doc (Harsha)", "https://docs.google.com/document/d/1smdNLJ-EpMk77IQRVnRdWFHgiqhRjDGNk3nAVQyTB9M/edit"],
    ["EOS testing ANZ (Anjali)", "https://docs.google.com/document/d/1D3dMtp5f2pdeePyaLmJ2ya2K7MgzAwGMf0BgRAE-0qQ/edit"],
    ["EOS vs Shoulder page builder", "https://docs.google.com/spreadsheets/d/17eq9jc8gYrr78vI7iAl9k-0KvAEike0-JvUPJIcjvI4/edit"],
    ["KWR Testing (Krupa)", "https://docs.google.com/spreadsheets/d/1-1adcmS6iVpNlWMp6hgxVxC4SJhswynL15BND9rI9XA/edit"],
    ["UI tool (local)", "~/analytics/.claude/worktrees/clusters-3-0-ui (Clusters 3.0 UI session)"],
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sheet-id")
    a = p.parse_args()
    if a.sheet_id:
        sid = a.sheet_id
    else:
        res = gws("sheets", "spreadsheets", "create", body={"properties": {"title": "Clusters 3.0 · logic book (backend)"},
                  "sheets": [{"properties": {"title": t, "gridProperties": {"frozenRowCount": 1}}} for t in TABS]})
        sid = res["spreadsheetId"]
    meta = gws("sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": sid, "fields": "sheets.properties(sheetId,title)"}))
    ids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    reqs = []
    for tab, rows in TABS.items():
        rows = [[str(c) for c in r] for r in rows]
        gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": sid}), body={"requests": [
            {"updateSheetProperties": {"properties": {"sheetId": ids[tab], "gridProperties": {"rowCount": len(rows) + 20, "columnCount": max(12, max(len(r) for r in rows))}},
                                       "fields": "gridProperties(rowCount,columnCount)"}}]})
        write(sid, tab, rows)
        head = 1 if tab not in ("Hit rates", "Pipeline runs") else 2
        reqs += [{"repeatCell": {"range": {"sheetId": ids[tab], "startRowIndex": head - 1, "endRowIndex": head},
                                 "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93}}},
                                 "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
                 {"repeatCell": {"range": {"sheetId": ids[tab]}, "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                                 "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
                 {"updateDimensionProperties": {"range": {"sheetId": ids[tab], "dimension": "COLUMNS", "startIndex": 0, "endIndex": 12},
                                                "properties": {"pixelSize": 220}, "fields": "pixelSize"}}]
        print(f"{tab}: {len(rows)} rows")
    gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": sid}), body={"requests": reqs})
    print(f"https://docs.google.com/spreadsheets/d/{sid}/edit")


if __name__ == "__main__":
    main()
