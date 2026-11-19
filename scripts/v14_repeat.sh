#!/bin/bash
set -euo pipefail
export LS_SAT_IMAGE_VERSION=v14_repeat LS_SAT_CONFIG_DIR=configs
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
case "$1" in
    smoke)
        .venv/bin/python -u scripts/v14_repeat.py prepare
        bash scripts/v13_native.sh v14_south_response_1 trial02
        exec .venv/bin/python scripts/v14_repeat.py validate --field v14_south_response_1 --phase trial02
        ;;
    trial)
        read -r field phase < <(.venv/bin/python scripts/v14_repeat.py task "$SLURM_ARRAY_TASK_ID")
        if [[ "$field" != v14_south_response_1 || "$phase" != trial02 ]]; then
            bash scripts/v13_native.sh "$field" "$phase"
        fi
        exec .venv/bin/python scripts/v14_repeat.py validate --field "$field" --phase "$phase"
        ;;
    remaining)
        read -r field phase < <(.venv/bin/python scripts/v14_repeat.py remaining "$SLURM_ARRAY_TASK_ID")
        if [[ -s "results/v14/repeat/validation/$field-$phase.json" ]]; then
            exec .venv/bin/python scripts/v14_repeat.py validate --field "$field" --phase "$phase"
        fi
        bash scripts/v13_native.sh "$field" "$phase"
        exec .venv/bin/python scripts/v14_repeat.py validate --field "$field" --phase "$phase"
        ;;
    measure_full)
        exec .venv/bin/python -u scripts/v14_repeat.py measure_full
        ;;
    measure_complete)
        .venv/bin/python -u scripts/v14_repeat.py measure_complete
        exec .venv/bin/python scripts/v14_repeat_accept.py --full
        ;;
    measure_site)
        exec .venv/bin/python -u scripts/v14_repeat.py measure_site --field "$2"
        ;;
    measure)
        .venv/bin/python -u scripts/v14_repeat.py measure
        ;;
esac
