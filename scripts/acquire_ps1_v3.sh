#!/bin/bash
# Run on a login node. Release an already submitted matched job when its input is ready.
set -euo pipefail
export LS_DR11_ROOT="${LS_DR11_ROOT:-/global/cfs/cdirs/cosmo/data/legacysurvey/dr11}"
export LS_SAT_DATA="${LS_SAT_DATA:-$PSCRATCH/legacy-satellite-search}"
export LS_SAT_CONFIG_DIR=configs/v3 PYTHONPATH=src
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
field=$1
job=$2
.venv/bin/python -u -m ls_satsearch.ps1_tiles "$field"
scontrol release "$job"
