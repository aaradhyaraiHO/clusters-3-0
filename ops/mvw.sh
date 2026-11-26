#!/bin/sh
# Wait up to 90 s for a Keyword Planner download, then file it as planner_ideas_<n>.csv for the CE.
for i in $(seq 1 45); do ls "$HOME"/Downloads/Keyword\ Stats*.csv >/dev/null 2>&1 && break; sleep 2; done
exec "$(dirname "$0")/mvn.sh" "$1" "$2"
