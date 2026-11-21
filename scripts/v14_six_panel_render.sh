#!/bin/bash
set -euo pipefail
export PYTHONPATH=src:. LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search" MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
root="$LS_SAT_DATA/runs/v14/human_review/final_private/six_panel_v2"
test -s "$root/blank_pilot/manifest.json"
.venv/bin/python -u -m scripts.v14_review_science_batch pack "$root" --index "${SLURM_ARRAY_TASK_ID:?}"
