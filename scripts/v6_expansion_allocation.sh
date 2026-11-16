#!/bin/bash
# Run batches and reviews inside an existing one-node CPU allocation.
# The first batch must already have a frozen A scan and combine.
set -euo pipefail
export LS_SAT_WORKSPACE="$PWD"
root="$LS_SAT_WORKSPACE"
batch() {
    local profile=$1 task=$2
    shift 2
    srun -n1 -c8 --exact --chdir="$root/batches/$profile" \
        -o "$root/batches/$profile/logs/$task-%j.log" env LS_SAT_V6_PROFILE="$profile" \
        bash "$root/scripts/v6.sh" "$@"
}
batch batch1 review expansion_review &
review=$!

srun -n10 -c8 --exact --chdir="$root/batches/batch2" \
    -o "$root/batches/batch2/logs/scan-%j-%t.log" env LS_SAT_V6_PROFILE=batch2 \
    bash "$root/scripts/v6.sh" scan-list "$root/configs/v6/batch2/fields.list"
batch batch2 combine holdout combine
batch batch2 review expansion_review
wait "$review"

srun -n1 -c8 --exact bash "$root/scripts/v6.sh" expansion_summary \
    --batches batches --audit results/registration/external_overlap_audit.csv \
    --output results/expansion --require 2
