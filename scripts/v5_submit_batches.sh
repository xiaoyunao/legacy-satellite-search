#!/bin/bash
# Submit in the v5 home checkout. Registry is produced by the selection job.
set -euo pipefail
selector=$1
export LS_SAT_WORKSPACE="$PWD"
prerequisite=$selector
for n in 1 2 3; do
    batch="batches/batch$n"
    mkdir -p "$batch/logs"
    ln -sn ../../references "$batch/references"
    export LS_SAT_V5_PROFILE="batch$n"
    count=12
    if [[ "$n" == 1 ]]; then count=14; fi
    scan=$(sbatch --parsable --dependency=afterok:"$prerequisite" --array="0-$((count-1))%12" \
        --chdir="$PWD/$batch" -A desi -q shared -J "lsv5-b$n-scan" scripts/v5.sh scan-list \
        "$PWD/configs/v5/batch$n/fields.list")
    group=$(sbatch --parsable --dependency=afterok:"$scan" --chdir="$PWD/$batch" \
        -A desi -q shared --time=00:12:00 -J "lsv5-b$n-combine" scripts/v5.sh holdout combine)
    review=$(sbatch --parsable --dependency=afterok:"$group" --chdir="$PWD/$batch" \
        -A desi -q shared --time=00:45:00 -J "lsv5-b$n-review" scripts/v5.sh expansion_review)
    printf "batch%s %s %s %s\n" "$n" "$scan" "$group" "$review"
    prerequisite=$group
done
