#!/bin/bash
set -euo pipefail
export LS_SAT_VERSION=v7
plans=(configs/v10/secondary/*.yaml)
if [[ -n ${SLURM_ARRAY_TASK_ID:-} ]]; then
    exec bash scripts/v6.sh verify_candidate --plan "${plans[SLURM_ARRAY_TASK_ID]}"
fi
pids=()
for plan in "${plans[@]}"; do
    field=$(basename "$plan" .yaml)
    srun -N1 -n1 -c2 --exact -o "logs/v10-ps1-$field-%j.log" \
        bash scripts/v6.sh verify_candidate --plan "$plan" &
    pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
exit "$status"
