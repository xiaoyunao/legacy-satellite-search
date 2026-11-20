#!/bin/bash
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search" LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
.venv/bin/python -u -m scripts.v14_selected_C collect
exec .venv/bin/python -u -m scripts.v14_register_record_materials \
    --selected-records results/v14/human_review/final_private/selected_C/selected_records.csv \
    --supplement results/v14/human_review/final_private/selected_C \
    --output results/v14/human_review/final_private/final_record_preparation
