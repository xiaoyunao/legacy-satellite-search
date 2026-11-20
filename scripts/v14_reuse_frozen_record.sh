#!/bin/bash
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search" PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec .venv/bin/python -u -m scripts.v14_reuse_frozen_record --plan results/v14/human_review/final_private/final_record_preparation/plan.json
