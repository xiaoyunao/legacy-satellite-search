#!/bin/bash
# Run on a NERSC data-transfer node with the actual Perlmutter scratch path.
set -euo pipefail
region=$1
export PSCRATCH=$2
shift 2
export LS_SAT_WORKSPACE="$PWD" LS_SAT_VERSION=v12 LS_SAT_PROFILE="matched/$region"
mkdir -p logs/v12
mapfile -t names < <(.venv/bin/python - "configs/v12/matched/$region/matched.yaml" <<'PY'
import sys
import yaml
with open(sys.argv[1]) as stream:
    for field in yaml.safe_load(stream)['fields']:
        print(field['id'])
PY
)
if (( $# )); then names=("$@"); fi
for field in "${names[@]}"; do
    printf '%s\n' "$field"
    bash scripts/v6.sh ps1_tiles "$field" --workers 2 >> "logs/v12/ps1-$field.log" 2>&1 || printf 'failed: %s\n' "$field"
done
