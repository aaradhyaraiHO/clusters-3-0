"""Build the LLM prompt that folds BERTopic topics into EOS clusters (or proposes new ones), and score answers.

Embeddings alone can't separate "same intent, other language" from "different intent": on Vatican, correct and
wrong matches both score 0.66-0.68. A language model reading each topic's top terms against the cluster list can.

Usage:
  python llm_assign_prompt.py --snapshot <id> --discovery-run <run_id> --ces 189
      -> runs/<run_id>/outputs/llm_prompt_<ce>.txt (send to Claude, ask for JSON)
  python llm_assign_prompt.py --snapshot <id> --discovery-run <run_id> --ces 189 --answer <answer.json> --answer-label <name>
      -> scores the answer against reference/llm_assign_reference_<ce>.json (click-weighted) and records it
  The reference itself is recorded by passing --answer reference/llm_assign_reference_<ce>.json --answer-label reference.
"""
import json
from pathlib import Path

import pandas as pd

import runlib

PROMPT = """You are mapping Google Ads search-term topics for one attraction (CE {ce}) onto its keyword clusters.

A cluster is one customer demand intent (e.g. "Sistine Chapel Tickets & Tours"). Search terms in any language
belong to the cluster with the same intent: "capilla sixtina entradas" belongs with "sistine chapel tickets".

EXISTING CLUSTERS (name | type | top keywords):
{clusters}

TOPICS (id | paid clicks, 90 days | top search terms):
{topics}

For each topic return one decision:
- "existing": same intent as an existing cluster (name it exactly); list the languages you see.
- "new": a demand intent no cluster covers (e.g. official-site searches, tours in a named language); propose a short name.
- "other_ce": the demand is for a different attraction (name it).
- "noise": mixed or irrelevant terms.
Prefer the most specific cluster: ticket searches go to a tickets cluster, not the head-term or art clusters.
Answer only with JSON: {{"assignments": [{{"topic": <id>, "decision": "...", "cluster": "...", "languages": ["de"], "note": "..."}}]}}
"""


def build(run, ce, topics):
    kw = pd.read_csv(run.input("cluster_keywords.csv"), dtype={"ce": str})
    kw = kw[(kw["ce"] == ce) & kw["kw"].notna()].sort_values("vol", ascending=False)
    clusters = "\n".join(f"- {n} | {g['t'].iloc[0]} | " + ", ".join(g["kw"].head(5)) for n, g in kw.groupby("name", sort=False))
    lines = "\n".join(f"- {r.topic} | {int(r.clicks)} | {r.top_terms}" for r in topics[topics["topic"] != -1].itertuples())
    text = PROMPT.format(ce=ce, clusters=clusters, topics=lines)
    (run.out / f"llm_prompt_{ce}.txt").write_text(text)
    print(f"wrote llm_prompt_{ce}.txt ({len(text)} chars)")


def score(run, ce, topics, answer_path, label, reference=None):
    clicks = topics.set_index("topic")["clicks"]
    ans = {a["topic"]: a for a in json.loads(Path(answer_path).read_text())["assignments"]}
    judged = sum(clicks[t] for t in ans)
    for decision in ["existing", "new", "other_ce", "noise"]:
        run.record(ce, f"llm step: {label}", f"pct_judged_clicks_{decision}",
                   100 * sum(clicks[t] for t, a in ans.items() if a["decision"] == decision) / judged)
    # topic ids belong to one discovery run, so a reference is only comparable when it was judged on the same run
    ref_path = Path(reference) if reference else None
    if ref_path and ref_path.exists() and Path(answer_path).resolve() != ref_path.resolve():
        ref = {a["topic"]: a for a in json.loads(ref_path.read_text())["assignments"]}
        agree = sum(clicks[t] for t, r in ref.items() if t in ans and ans[t]["decision"] == r["decision"]
                    and (r["decision"] != "existing" or ans[t]["cluster"] == r["cluster"]))
        pct = 100 * agree / sum(clicks[t] for t in ref)
        run.record(ce, f"llm step: {label}", "pct_clicks_agree_with_reference", pct)
        print(f"{label}: click-weighted agreement with reference {pct:.1f}%")


def main():
    a = runlib.args("llm_step", {"--discovery-run": {"required": True}, "--answer": {"default": None},
                                 "--answer-label": {"default": "answer"},
                                 "--reference": {"default": None, "help": "answer key judged on the same discovery run"}})
    run = runlib.Run("llm_step", a.snapshot, {"ces": a.ces, "discovery_run": a.discovery_run, "answer": a.answer,
                                              "answer_label": a.answer_label, "reference": a.reference})
    for ce in a.ces.split(","):
        topics = pd.read_csv(run.upstream(a.discovery_run, f"topics_{ce}_leftovers.csv"))
        build(run, ce, topics)
        if a.answer:
            score(run, ce, topics, a.answer, a.answer_label, a.reference)
    run.close()


if __name__ == "__main__":
    main()
