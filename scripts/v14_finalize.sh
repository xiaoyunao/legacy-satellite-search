#!/bin/bash
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search" LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
mkdir -p "$LS_SAT_DATA/runs/v14"
exec 9>"$LS_SAT_DATA/runs/v14/summary.lock"
flock 9
case "$1" in
    regional)
        shift
        .venv/bin/python -u scripts/v14_results.py "$@"
        ;;
    science)
        .venv/bin/python -u scripts/v14_efficiency.py
        .venv/bin/python -u scripts/v14_native_summary.py
        ;;
    catalogue)
        .venv/bin/python -u scripts/v14_catalog.py
        .venv/bin/python -u scripts/v14_production.py
        .venv/bin/python -m scripts.v14_production_registry
        .venv/bin/python -m scripts.v14_integrated_ledger
        .venv/bin/python -u scripts/v14_atlas.py
        ;;
    snapshot)
        .venv/bin/python -u scripts/v14_results.py
        .venv/bin/python -u scripts/v14_catalog.py
        .venv/bin/python -u scripts/v14_production.py
        .venv/bin/python -m scripts.v14_production_registry
        .venv/bin/python -m scripts.v14_integrated_ledger
        .venv/bin/python -u scripts/v14_atlas.py
        .venv/bin/python -u scripts/v14_efficiency.py
        .venv/bin/python -u scripts/v14_native_summary.py
        ;;
esac
