#!/bin/bash
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
exec .venv/bin/python -u -m scripts.v14_accept_deeper_replay "$@"
