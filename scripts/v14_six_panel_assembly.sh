#!/bin/bash
set -euo pipefail
export PYTHONPATH=src:. MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
root="$PSCRATCH/legacy-satellite-search/runs/v14/human_review/final_private/six_panel_v2"
release="$PSCRATCH/legacy-satellite-search/runs/v14/human_review/final_private/final_release_v2"
if [[ -e "$root/assembly" || -e "$release" ]]; then
    echo 'Inspect the existing assembly stages before retrying.' >&2
    exit 1
fi
.venv/bin/python -u -m scripts.v14_review_science_batch assemble "$root"
mkdir -p "$release"
.venv/bin/python -u -m scripts.v14_stage1_pdf --input "$root/assembly/anonymous_plan.json" --output "$release/phase1"
.venv/bin/python -u -m scripts.v14_stage1_verify --plan "$root/assembly/anonymous_plan.json" --package "$release/phase1"
.venv/bin/python -u -m scripts.v14_held_context_pdf --key "$root/assembly/held_context_key.json" --output "$release/held_context"
.venv/bin/python -u -m scripts.v14_held_context_verify --key "$root/assembly/held_context_key.json" --package "$release/held_context"
.venv/bin/python -u -m scripts.v14_held_environment --key "$root/assembly/held_context_key.json" --output "$release/held_environment"
