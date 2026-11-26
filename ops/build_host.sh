#!/bin/sh
# Build a CE whose page sits on a city site: run_ce.py <ce> --final --host <site>, under the shared lock.
U=/Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0-ui/thoughts/shared/clusters-3.0/parag-v1
R=${RUNS:-/tmp/claude-501/runs32}
export MPLCONFIGDIR=/tmp/claude-501/mpl NUMBA_CACHE_DIR=/tmp/claude-501/numba HF_HUB_OFFLINE=1
cd "$U" || exit 1
while [ $# -ge 2 ]; do
  ce="$1"; host="$2"; shift 2
  until mkdir "$R/full.lock" 2>/dev/null; do sleep 15; done
  log="$R/build_$ce.log"
  if python3 run_ce.py "$ce" --final --host "$host" > "$log" 2>&1; then echo "$(date +%H:%M) $ce: DONE: $(grep '^done:' "$log")" | tee -a "$R/live_status.txt"
  else echo "$(date +%H:%M) $ce: FAILED ($(grep '^stopped at' "$log" | tail -1) $(tail -1 "$log"))" | tee -a "$R/live_status.txt"; fi
  rmdir "$R/full.lock"
done
