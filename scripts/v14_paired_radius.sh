#!/bin/bash
set -euo pipefail
export LS_SAT_IMAGE_VERSION=v14_paired_radius LS_SAT_CONFIG_DIR=configs
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
case "$1" in
  pilot)
    exec .venv/bin/python -u scripts/v14_paired_radius.py pilot
    ;;
  remaining_pack)
    test -s results/v14/paired_radius/pilot_stage_acceptance.json
    start=$((3+7*SLURM_ARRAY_TASK_ID))
    for ((i=start;i<start+7;i++)); do
      .venv/bin/python -u scripts/v14_paired_radius.py native --index "$i"
    done
    ;;
  full_stages)
    exec .venv/bin/python -u scripts/v14_paired_radius.py full_stages
    ;;
  *) exit 2 ;;
esac
