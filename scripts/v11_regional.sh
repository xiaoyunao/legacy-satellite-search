#!/bin/bash
# Invoke from the home-directory revision. Each task runs one independent core.
set -euo pipefail
cohort=$1
start=$2
length=$3
export LS_SAT_VERSION="${LS_SAT_VERSION:-v11}"
export LS_SAT_WORKSPACE="$PWD" LS_SAT_PROFILE="cohorts/$cohort" LS_SAT_V2_WORKSPACE=1
work="$LS_SAT_WORKSPACE/regional_$cohort"
if [[ "$LS_SAT_VERSION" != v11 ]]; then
    work="$LS_SAT_WORKSPACE/regional_${LS_SAT_VERSION}_$cohort"
fi
if [[ "$LS_SAT_VERSION" == v14 && -s "$LS_SAT_WORKSPACE/results/v14/footprint/coadd_cache_validation.json" ]]; then
    export LS_SAT_COADD_CACHE="$PSCRATCH/legacy-satellite-search/cache/v14_packed_masks"
fi
mkdir -p "$work/logs"
ln -sfn ../references "$work/references"
cd "$work"
fields="$LS_SAT_WORKSPACE/configs/$LS_SAT_VERSION/cohorts/$cohort/fields.yaml"
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
status=0
for ((i=start;i<start+length;i++)); do
    field=${names[i]}
    manifest="results/summary/$field-base/manifest.json"
    if test -f "$manifest" && grep -q '"status": "complete"' "$manifest"; then
        continue
    fi
    if [[ "${LS_SAT_SKIP_EMPTY:-0}" == 1 ]] && test -f "$manifest" && grep -q '"status": "no_usable_gr"' "$manifest"; then
        continue
    fi
    srun -N1 -n1 -c4 --mem="${LS_SAT_STEP_MEM:-5500M}" --exact -o "logs/$field-%j.log" \
         bash "$LS_SAT_WORKSPACE/scripts/v6.sh" run "$field" &
    pids+=("$!")
    if (( ${#pids[@]} >= ${LS_SAT_FIELD_WORKERS:-8} )); then
        for pid in "${pids[@]}"; do
            wait "$pid" || status=1
        done
        pids=()
    fi
done
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
exit "$status"
