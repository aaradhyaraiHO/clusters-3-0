"""Per-CE summary of the full Keyword Planner passes, read from the pipeline's files."""
import json, re
from pathlib import Path
import pandas as pd
S = Path("/Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0/scripts/clusters_3_0/snapshots")
R = Path("/tmp/claude-501/runs32")
NAMES = {"3097": "Everglades", "6756": "Fiji", "1642": "Great Ocean Road", "528": "Grand Canyon", "6072": "Pearl Harbor",
         "2554": "Niagara", "2402": "James Bond", "3697": "Fraser", "6677": "Kangaroo Island", "3646": "Port Arthur"}
REMOVED = {"3097": ["everglades with kids"], "6756": ["mana island fiji"], "1642": ["great ocean road with kids"],
           "528": ["grand canyon with kids"], "6072": ["pearl harbor with kids", "pearl harbor attack"],
           "2554": ["niagara falls with kids", "niagara falls fireworks"], "2402": [], "3697": ["fraser island with kids"],
           "6677": ["kangaroo island with kids"], "3646": ["port arthur with kids", "point puer boys prison"]}
status = (R / "full_status.txt").read_text() + (R / "live_status.txt").read_text()
rows = []
for ce, name in NAMES.items():
    d = S / f"ce_{ce}"
    seeds = len(json.loads((d / "seeds.json").read_text()))
    r = json.loads((d / "research.json").read_text())
    t = json.loads((d / "research_top10.json").read_text())
    t_vol = pd.read_csv(d / "eos_keywords_top10.csv").vol.sum()
    kv = pd.read_csv(d / "eos_keywords.csv").vol.sum()
    row = {"CE": f"{name} {ce}", "seeds": f"{seeds - len(REMOVED[ce])}/{seeds}", "searches": len(list(d.glob("planner_ideas_*.csv"))),
           "ideas": r["ideas"], "kept": r["kept"], "kept_vol": kv, "top10_ideas": t["ideas"], "top10_kept": t["kept"], "top10_vol": t_vol}
    final = d / "final"
    fresh = final.exists() and (final / "scorecard.json").stat().st_mtime > (d / "research.json").stat().st_mtime
    if fresh:
        sc = json.loads((final / "scorecard.json").read_text())
        k = pd.read_csv(final / "keywords.csv")
        row.update(clusters=sc["clusters"], agreement="–".join(f"{a:.2f}" for a in (min(sc["run_agreement"]), max(sc["run_agreement"]))),
                   clustered_vol=k[k.cluster.notna()].volume.sum(), organic_wrong=sc.get("organic_judged_wrong"),
                   paid_wrong=sc.get("paid_judged_wrong"))
    top = d / "final_top10" / "clusters.csv"
    row["top10_clusters"] = len(pd.read_csv(top)) if top.exists() else None
    page = re.findall(rf"^\d\d:\d\d {ce}: DONE: .*?([a-z0-9]+-clusters\.html)", status, re.M)
    row["page"] = page[-1] if page else ""
    rows.append(row)
df = pd.DataFrame(rows)
print(df.to_string(index=False))
df.to_csv(R / "full_report.csv", index=False)
