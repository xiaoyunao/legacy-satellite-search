#!/bin/bash
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec .venv/bin/python -u scripts/v14_review_integrity.py "$@"
