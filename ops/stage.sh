#!/bin/zsh
# Rebuild every registered page (so each switcher lists every built CE) under the shared lock, then stage the deploy folder.
cd /Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0-ui/thoughts/shared/clusters-3.0/parag-v1
until mkdir ${RUNS:-/tmp/claude-501/runs32}/full.lock 2>/dev/null; do sleep 5; done
trap 'rmdir ${RUNS:-/tmp/claude-501/runs32}/full.lock' EXIT
for s in $(python3 -c "import json;from pathlib import Path;d=json.load(open('ces.json'))['ces'];print(' '.join(v['slug'] for v in d.values() if (Path(v['out'])/v['data']).exists()))"); do
  python3.14 build.py $s >/dev/null || echo "build failed: $s"
  page=$(python3 -c "import json;d=json.load(open('ces.json'))['ces'];print(next(v['page'] for v in d.values() if v['slug']=='$s'))")
  cp $page /tmp/claude-501/clusters-deploy/
  echo "staged $page"
done
cp /tmp/claude-501/clusters-deploy/vatican-clusters.html /tmp/claude-501/clusters-deploy/index.html
cp /tmp/claude-501/clusters-deploy/milford-clusters.html /tmp/claude-501/clusters-deploy/milford.html
