#!/bin/bash
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
if [[ "$1" == pack && $# == 1 ]]; then
    set -- pack --index "${SLURM_ARRAY_TASK_ID:?}"
fi
exec "$LS_SAT_DATA/envs/area-union-20261119/bin/python" -u -m scripts.v14_current_area "$@"
