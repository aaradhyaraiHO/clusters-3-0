#!/bin/sh
# Full-seed run for one CE: merge every Keyword Planner CSV, cluster, build its page. Only the page build (which writes
# ces.json) takes the shared lock. Each step's outcome goes to full_status.txt.
ce="$1"
W=/Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0/scripts/clusters_3_0
U=/Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0-ui/thoughts/shared/clusters-3.0/parag-v1
R=${RUNS:-/tmp/claude-501/runs32}
LOG="$R/full_$ce.log"
export MPLCONFIGDIR=/tmp/claude-501/mpl NUMBA_CACHE_DIR=/tmp/claude-501/numba HF_HUB_OFFLINE=1
status() { echo "$(date +%H:%M) $ce: $1" | tee -a "$R/full_status.txt"; }
cd "$W" || exit 1
if [ -d "snapshots/ce_$ce/final" ] && [ ! -d "snapshots/ce_$ce/final_top10" ]; then cp -r "snapshots/ce_$ce/final" "snapshots/ce_$ce/final_top10"; fi
# Files 1-8 come from the CE's seeds, 9 onward from its vendor seeds.
ideas=$(ls snapshots/ce_$ce/planner_ideas_*.csv | sort -t_ -k4 -n | awk -F_ '$NF+0 <= 8' | paste -sd, -)
vendor=$(ls snapshots/ce_$ce/planner_ideas_*.csv | sort -t_ -k4 -n | awk -F_ '$NF+0 >= 9' | paste -sd, -)
.env-clusters/venv/bin/python research_ce.py "$ce" --stage finish --ideas "$ideas" ${vendor:+--vendor-ideas "$vendor"} > "$LOG" 2>&1 || { status "FAILED at merge"; exit 1; }
status "merged: $(tail -1 "$LOG")"
.env-clusters/venv/bin/python run_ce_pipeline.py "$ce" --keywords own --runs 3 >> "$LOG" 2>&1 || { status "FAILED at clustering ($(grep '^== ' "$LOG" | tail -1))"; exit 1; }
status "clustered: $(grep -E 'agreement between runs|^convert:' "$LOG" | tr '\n' ' ')"
until mkdir "$R/full.lock" 2>/dev/null; do sleep 15; done
trap 'rmdir "$R/full.lock" 2>/dev/null' EXIT
cd "$U" || exit 1

if ! python3 run_ce.py "$ce" --final >> "$LOG" 2>&1; then
  # A CE with no microbrand: run_ce names the city site its home page sits under; build on that.
  host=$(grep -o 'its home page sits under [^ ]*\.' "$LOG" | tail -1 | sed 's/its home page sits under //; s/\.$//')
  [ -n "$host" ] && python3 run_ce.py "$ce" --final --host "$host" >> "$LOG" 2>&1 || { status "FAILED at page build ($(grep '^stopped at' "$LOG" | tail -1))"; exit 1; }
fi
status "DONE: page built ($(grep '^done:' "$LOG" | tail -1))"
