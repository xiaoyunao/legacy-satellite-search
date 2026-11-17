#!/bin/bash
set -euo pipefail
export LS_SAT_IMAGE_VERSION=v14 LS_SAT_CONFIG_DIR=configs
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
mapfile -t fields < <(tail -n +2 configs/v14/image_fields.csv | cut -d, -f1)
index=$SLURM_ARRAY_TASK_ID
case "$1" in
    blank)
        field=${fields[index]}
        .venv/bin/python -u scripts/v13_image_trials.py prepare "$field"
        bash scripts/v14_native.sh "$field" blank
        ;;
    trial)
        field=${fields[index/8]}
        printf -v phase 'trial%02d' "$((index%8))"
        bash scripts/v14_native.sh "$field" "$phase"
        ;;
    measure)
        .venv/bin/python -u scripts/v13_image_trials.py measure "${fields[index]}"
        ;;
esac
