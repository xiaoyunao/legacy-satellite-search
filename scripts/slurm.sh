#!/bin/bash
#SBATCH --job-name=ls-satellite
#SBATCH --constraint=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --output=logs/%x-%j.log
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
export LS_DR11_ROOT="${LS_DR11_ROOT:-/global/cfs/cdirs/cosmo/data/legacysurvey/dr11}"
export LS_SAT_DATA="${LS_SAT_DATA:-$PSCRATCH/legacy-satellite-search}"
job_snapshot="$LS_SAT_DATA/jobs/$SLURM_JOB_ID"
mkdir -p "$job_snapshot"
cp -r src configs "$job_snapshot/"
export PYTHONPATH="$job_snapshot/src" LS_SAT_CONFIG_DIR="$job_snapshot/configs"
if [[ ${1:-} == --both-depths ]]; then
    shift
    .venv/bin/python -u -m ls_satsearch.run "$@"
    exec .venv/bin/python -u -m ls_satsearch.run --depth deep "$@"
fi
exec .venv/bin/python -u -m ls_satsearch.run "$@"
