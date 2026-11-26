#!/bin/sh
# Move the newest Keyword Planner download into a CE's pipeline folder as planner_ideas_<n>.csv.
sleep 2
W=/Users/aaradhyarai/analytics/.claude/worktrees/clusters-3-0/scripts/clusters_3_0
f=$(ls -t "$HOME"/Downloads/Keyword\ Stats*.csv 2>/dev/null | head -1)
n=$(ls "$HOME"/Downloads/Keyword\ Stats*.csv 2>/dev/null | wc -l | tr -d ' ')
if [ -n "$f" ]; then mv "$f" "$W/snapshots/ce_$1/planner_ideas_$2.csv" && echo "$1 #$2: $(wc -c < "$W/snapshots/ce_$1/planner_ideas_$2.csv") bytes (downloads waiting before move: $n)"; else echo "$1 #$2: no download"; fi
