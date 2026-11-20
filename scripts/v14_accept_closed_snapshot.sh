#!/bin/bash
set -euo pipefail
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec .venv/bin/python -u -m scripts.v14_accept_closed_snapshot
