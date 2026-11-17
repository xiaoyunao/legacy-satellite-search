#!/bin/bash
# Invoke from the home-directory revision. Each task runs one independent core.
set -euo pipefail
cohort=$1
start=$2
length=$3
export LS_SAT_WORKSPACE="$PWD" LS_SAT_VERSION=v11 LS_SAT_PROFILE="cohorts/$cohort" LS_SAT_V2_WORKSPACE=1
work="$LS_SAT_WORKSPACE/regional_$cohort"
mkdir -p "$work/logs"
ln -sfn ../references "$work/references"
cd "$work"
fields="$LS_SAT_WORKSPACE/configs/v11/cohorts/$cohort/fields.yaml"
mapfile -t names < <("$LS_SAT_WORKSPACE/.venv/bin/python" - "$fields" <<'PY'
import sys,yaml
for f in yaml.safe_load(open(sys.argv[1]))['fields']:
    print(f['id'])
PY
)
if (( start + length > ${#names[@]} )); then
    exit 2
fi
pids=()
for ((i=start;i<start+length;i++)); do
    field=${names[i]}
    manifest="results/summary/$field-base/manifest.json"
    if test -f "$manifest" && grep -q '"status": "complete"' "$manifest"; then
        continue
    fi
    srun -N1 -n1 -c4 --mem=5500M --exact -o "logs/$field-%j.log" \
         bash "$LS_SAT_WORKSPACE/scripts/v6.sh" run "$field" &
    pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
exit "$status"
