#!/bin/bash
set -euo pipefail
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec .venv/bin/python -u scripts/v14_shortlist_context.py
