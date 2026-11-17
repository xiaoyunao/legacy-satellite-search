#!/bin/bash
set -euo pipefail
export LS_SAT_CONFIG_DIR=configs
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
site=$(sed -n "$((SLURM_ARRAY_TASK_ID+2))p" configs/v14/overlap.csv | cut -d, -f1)
exec .venv/bin/python -u scripts/v14_overlap.py "$site"
