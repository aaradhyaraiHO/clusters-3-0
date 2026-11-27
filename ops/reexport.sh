#!/bin/zsh
# Re-run the page export and build for the given ces.json keys, each under the shared lock, and report what changed.
cd /Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0-ui/thoughts/shared/clusters-3.0/parag-v1
R=/Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0/scripts/clusters_3_0
for key in "$@"; do
  read out data slug <<< $(python3 -c "import json;v=json.load(open('ces.json'))['ces']['$key'];print(v['out'],v['data'],v['slug'])")
  [ -f /tmp/claude-501/fixbak/${slug}_before.json ] || cp $out/$data /tmp/claude-501/fixbak/${slug}_before.json 2>/dev/null
  until mkdir ${RUNS:-/tmp/claude-501/runs32}/full.lock 2>/dev/null; do sleep 5; done
  if python3 export_hybrid.py $R $key > ${RUNS:-/tmp/claude-501/runs32}/reexport_$slug.log 2>&1 && python3.14 build.py $slug >> ${RUNS:-/tmp/claude-501/runs32}/reexport_$slug.log 2>&1; then
    python3 - "$slug" "$out/$data" <<'PY'
import json, sys
slug, path = sys.argv[1], sys.argv[2]
try:
    b = {c["id"]: c for c in json.load(open(f"/tmp/claude-501/fixbak/{slug}_before.json"))["clusters"]}
except FileNotFoundError:
    b = {}
a = json.load(open(path))["clusters"]
types = [f"{c['name']}" for c in a if c["id"] in b and b[c["id"]]["type"] != c["type"]]
focus = sum(1 for c in a if c["id"] in b and b[c["id"]]["focus_kw"] != c["focus_kw"])
print(f"{slug}: {len(a)} clusters; to Informational {len(types)} {types[:6]}; focus changed {focus}")
PY
  else
    echo "$slug: FAILED $(tail -2 ${RUNS:-/tmp/claude-501/runs32}/reexport_$slug.log | tr '\n' ' ')"
  fi
  rmdir ${RUNS:-/tmp/claude-501/runs32}/full.lock
done
