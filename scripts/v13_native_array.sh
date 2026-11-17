#!/bin/bash
set -euo pipefail
mapfile -t fields < <(tail -n +2 configs/v13/image_fields.csv | cut -d, -f1)
ntrial=6
index=$SLURM_ARRAY_TASK_ID
printf -v phase 'trial%02d' "$((index%ntrial))"
exec bash scripts/v13_native.sh "${fields[index/ntrial]}" "$phase"
