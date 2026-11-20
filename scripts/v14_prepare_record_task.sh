#!/bin/bash
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search" LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
exec .venv/bin/python -u -m scripts.v14_prepare_record_task "$@"
