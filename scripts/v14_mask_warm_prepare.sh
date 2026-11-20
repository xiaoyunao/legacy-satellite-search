#!/bin/bash
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec "$LS_SAT_DATA/envs/area-union-20261119/bin/python" -u -m scripts.v14_mask_warm_prepare
