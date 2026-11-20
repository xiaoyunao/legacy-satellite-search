#!/bin/bash
set -euo pipefail
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
input=results/v14/human_review/final_private/pdf_local_label_pilot_input.json
output=results/v14/human_review/final_private/pdf_nersc_runtime_pilot
.venv/bin/python -u -m scripts.v14_stage1_pdf --input "$input" --output "$output"
exec .venv/bin/python -u -m scripts.v14_stage1_verify --plan "$input" --package "$output"
