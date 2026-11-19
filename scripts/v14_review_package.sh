#!/bin/bash
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
.venv/bin/python scripts/v14_review_pdf.py --status-only "$@"
exec .venv/bin/python scripts/v14_review_pdf.py "$@"
