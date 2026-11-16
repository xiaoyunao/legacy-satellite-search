#!/bin/bash
#SBATCH --job-name=ls-sat-inj
#SBATCH --constraint=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:25:00
#SBATCH --output=logs/%x-%A-%a.log
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH="$PWD/src"
export LS_DR11_ROOT="${LS_DR11_ROOT:-/global/cfs/cdirs/cosmo/data/legacysurvey/dr11}"
export LS_SAT_DATA="${LS_SAT_DATA:-$PSCRATCH/legacy-satellite-search}"
exec .venv/bin/python -u -m ls_satsearch.inject "$1" "$SLURM_ARRAY_TASK_ID"
