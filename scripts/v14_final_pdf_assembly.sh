#!/bin/bash
# Assemble only after every registered original-source material is accepted.
set -euo pipefail
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
private=results/v14/human_review/final_private
assembly="$private/final_assembly"
release="$PSCRATCH/legacy-satellite-search/runs/v14/human_review/final_private/final_release_v1"
if [[ -e "$assembly" || -e "$release" ]]; then
    echo 'Preserve existing assembly/permutation/release; inspect its manifest before resuming.' >&2
    exit 1
fi
.venv/bin/python -u -m scripts.v14_final_material_plan --material-plan "$private/final_record_preparation/plan.json"
mkdir -p "$release"
.venv/bin/python -u -m scripts.v14_stage1_pdf --input "$assembly/anonymous_plan.json" --output "$release/phase1"
.venv/bin/python -u -m scripts.v14_stage1_verify --plan "$assembly/anonymous_plan.json" --package "$release/phase1"
.venv/bin/python -u -m scripts.v14_held_context_pdf --key "$assembly/held_context_key.json" --output "$release/held_context"
.venv/bin/python -u -m scripts.v14_held_context_verify --key "$assembly/held_context_key.json" --package "$release/held_context"
echo 'Assembly and pixel/text/ZIP checks complete; all-page render/privacy/layout and durable-copy gates remain.'
