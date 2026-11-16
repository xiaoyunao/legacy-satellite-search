#!/bin/bash
#SBATCH --constraint=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=00:35:00
#SBATCH --output=logs/%x-%j.log
set -euo pipefail
export LS_SAT_V2_WORKSPACE=1 LS_SAT_RUN_VERSION=v4
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
export LS_DR11_ROOT="${LS_DR11_ROOT:-/global/cfs/cdirs/cosmo/data/legacysurvey/dr11}"
export LS_SAT_DATA="${LS_SAT_DATA:-$PSCRATCH/legacy-satellite-search}"
snapshot="$LS_SAT_DATA/jobs/$SLURM_JOB_ID"
mkdir -p "$snapshot" results/summary results/figures
cp -r src configs "$snapshot/"
export PYTHONPATH="$snapshot/src" LS_SAT_CONFIG_DIR="$snapshot/configs/v4${LS_SAT_V4_PROFILE:+/$LS_SAT_V4_PROFILE}"
module=$1
shift
exec .venv/bin/python -u -m "ls_satsearch.$module" "$@"
