#!/bin/bash
set -euo pipefail
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search" PYTHONPATH="$PWD/src"
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1
pids=()
for cohort in north south_ps1 south_delve south_des; do
    srun -n1 -c2 --mem=4500M --exact .venv/bin/python scripts/v11_priority_figures.py "$cohort" &
    pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do wait "$pid" || status=1; done
exit "$status"
