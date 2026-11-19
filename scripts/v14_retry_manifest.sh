#!/bin/bash
set -euo pipefail
export LS_SAT_VERSION=v14 LS_SAT_SKIP_EMPTY=1 LS_SAT_FIELD_WORKERS=1
export LS_SAT_STEP_MEM="${LS_SAT_STEP_MEM:-52000M}"
if [[ "$1" == *.csv ]]; then
    read -r cohort index < <(.venv/bin/python - "$1" "$SLURM_ARRAY_TASK_ID" <<'PYCODE'
import csv
import sys
with open(sys.argv[1], newline='') as handle:
    row = list(csv.DictReader(handle))[int(sys.argv[2])]
print(row['cohort'], int(row['index']))
PYCODE
)
else
    read -r cohort index < <(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "$1")
fi
[[ -n "$cohort" && "$index" =~ ^[0-9]+$ ]]
exec bash scripts/v11_regional.sh "$cohort" "$index" 1
