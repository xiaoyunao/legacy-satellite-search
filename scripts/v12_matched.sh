#!/bin/bash
set -euo pipefail
region=$1
shift
export LS_SAT_WORKSPACE="$PWD" LS_SAT_VERSION=v12 LS_SAT_PROFILE="matched/$region"
work="$PWD/matched_v12_$region"
mkdir -p "$work/logs"
cd "$work"
pids=()
for field in "$@"; do
    manifest="results/matched/ps1/summary/$field-base/manifest.json"
    if test -f "$manifest" && grep -q '"status": "complete"' "$manifest"; then
        continue
    fi
    srun -N1 -n1 -c4 --mem=6200M --exact -o "logs/$field-%j.log" \
         bash "$LS_SAT_WORKSPACE/scripts/v6.sh" matched "$field" &
    pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
exit "$status"
