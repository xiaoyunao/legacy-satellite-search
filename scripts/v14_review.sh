#!/bin/bash
set -euo pipefail
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
if [[ "$1" == v14 ]]; then
    export LS_SAT_DEFER_C_DIAGNOSTICS="${LS_SAT_DEFER_C_DIAGNOSTICS:-1}"
fi
exec .venv/bin/python -u scripts/v14_review.py "$1" "$2" "$SLURM_ARRAY_TASK_ID" "$3"
