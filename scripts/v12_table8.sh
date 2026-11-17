#!/bin/bash
set -euo pipefail
region=$1
shift
export LS_SAT_WORKSPACE="$PWD" LS_SAT_VERSION=v12 LS_SAT_PROFILE="table8/$region" LS_SAT_V2_WORKSPACE=1
work="$PWD/table8_v12_$region"
mkdir -p "$work/logs"
cd "$work"
pids=()
for field in "$@"; do
    srun -N1 -n1 -c4 --mem=6500M --exact -o "logs/$field-%j.log" \
        bash -c '
          for depth in base deep; do
              manifest="results/summary/$1-$depth/manifest.json"
              if test -f "$manifest" && grep -Eq "\"status\": \"(complete|no_usable_gr)\"" "$manifest"; then
                  continue
              fi
              bash "$LS_SAT_WORKSPACE/scripts/v6.sh" run "$1" --depth "$depth" || exit
          done
        ' audit "$field" &
    pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
exit "$status"
