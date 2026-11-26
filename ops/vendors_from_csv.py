"""Vendor step with the internal vendors read from the tool's experiences pull instead of BigQuery."""
import json, sys
from pathlib import Path
import pandas as pd
import research_ce as rc
UI = Path("/Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0-ui/thoughts/shared/clusters-3.0/parag-v1")
ce = sys.argv[1]
reg = json.loads((UI / "ces.json").read_text())["ces"]
key, cfg = next((k, v) for k, v in reg.items() if (v.get("eos_id") or k) == ce)
f = UI / cfg["out"] / f"experiences_{key}.csv"
if f.exists():
    exp = pd.read_csv(f, dtype=str)
else:
    exp = pd.read_csv(UI / cfg["out"] / f"variant_availability_{key}.csv", dtype=str).rename(columns={"is_available": "live"})
live = {}
for vs, ok in zip(exp["vendors"].fillna(""), exp["live"].fillna("false")):
    for v in [x.strip() for x in vs.split(",") if x.strip()]:
        live[v] = live.get(v, False) or ok.lower() == "true"
sheet = [{"name": v, "status": "active" if ok else "inactive"} for v, ok in live.items()]
row = pd.read_csv("ce_sources.csv", dtype=str).set_index("ce").loc[ce].fillna("")
vendors = rc.vendors_for(row, sheet, "auto")
(rc.runlib.SNAPSHOTS / f"ce_{ce}" / "vendor_seeds.json").write_text(json.dumps({"internal": sheet, "vendors": vendors, "internal_from": "experiences pull"}, indent=1))
print(f"research: {len(vendors)} vendor seeds ({len(sheet)} internal vendors before the filter): " + ", ".join(v["keyword"] for v in vendors))
