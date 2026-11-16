#!/bin/bash
# Dispatch one registered field per Slurm task within an allocated CPU node.
set -euo pipefail
first_index=$1
field_list=$2
export SLURM_ARRAY_TASK_ID=$((first_index + SLURM_PROCID))
exec bash "$LS_SAT_WORKSPACE/scripts/v5.sh" scan-list "$field_list"
