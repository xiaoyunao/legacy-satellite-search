#!/bin/bash
set -euo pipefail
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
if [[ "${1:-}" == reuse ]]; then
    exec .venv/bin/python -u scripts/v14_shortlist.py reuse
fi
if [[ "${1:-}" == smoke ]]; then
    exec .venv/bin/python -u scripts/v14_shortlist.py review --case P001
fi
exec .venv/bin/python -u scripts/v14_shortlist.py review --index "$SLURM_ARRAY_TASK_ID" --count "$1"
