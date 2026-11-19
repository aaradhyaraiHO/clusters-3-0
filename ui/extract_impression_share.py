"""Pull per-cluster impression share and catch-all spend out of Satvik's Clusters Dashboard Prototype.

Usage: python3 extract_impression_share.py "<path to Clusters Dashboard Prototype.html>"
Writes impression_share.json next to this file, keyed by EOS cluster id.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = "const DATA = "

# The prototype embeds its whole dataset as one `const DATA = {...};` line.
line = next(l for l in Path(sys.argv[1]).read_text().splitlines() if l.startswith(PREFIX))
ce = json.loads(line[len(PREFIX):].rstrip().rstrip(";"))["189"]

out = {"window": f"{ce['weeks'][0]}, {ce['windowDays']} days", "hidden_spend": ce["hidden"]["spend"],
       "total_spend": ce["totals"]["spend"], "clusters": {}}
for c in ce["clusters"]:
    p = c["paid"]
    eligible = p.get("eligible") or 0
    out["clusters"][c["id"]] = {
        "search_is": p["search_impressions"] / eligible if eligible else None,
        "lost_rank": p["rank_lost"] / eligible if eligible else None,
        "cm1_at_stake": p["rank_lost"] * p["cm1"] / p["impressions"] if eligible and p["impressions"] else None,
        "catch_all": c.get("catchAllShare"),
        "weekly_spend": c["weekly"]["spend"],
    }
(HERE / "impression_share.json").write_text(json.dumps(out, indent=1))
print(f"{len(out['clusters'])} clusters -> {HERE / 'impression_share.json'}")
