#!/bin/bash
set -euo pipefail
cohort=$1
count=$2
size=8
start=$(( SLURM_ARRAY_TASK_ID * size ))
remaining=$(( count - start ))
if (( remaining <= 0 )); then
    exit 2
fi
if (( remaining < size )); then
    size=$remaining
fi
export LS_SAT_VERSION="${LS_SAT_VERSION:-v12}"
exec bash scripts/v11_regional.sh "$cohort" "$start" "$size"
