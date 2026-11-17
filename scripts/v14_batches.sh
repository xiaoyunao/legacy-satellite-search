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
export LS_SAT_VERSION=v14 LS_SAT_STEP_MEM=12500M LS_SAT_SKIP_EMPTY=1
exec bash scripts/v11_regional.sh "$cohort" "$start" "$size"
