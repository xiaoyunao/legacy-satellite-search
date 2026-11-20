#!/bin/bash
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
export PSCONFDIR="$LS_SAT_DATA/software/ipp/install" PSVERSION=lssat
source "$PSCONFDIR/psconfig.bash" lssat
exec .venv/bin/python -u -m scripts.v14_ps1_operator_preflight
