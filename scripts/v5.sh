#!/bin/bash
#SBATCH --constraint=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=00:35:00
#SBATCH --output=logs/%x-%j.log
set -euo pipefail
export LS_SAT_V2_WORKSPACE=1 LS_SAT_RUN_VERSION=v5
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
export LS_DR11_ROOT="${LS_DR11_ROOT:-/global/cfs/cdirs/cosmo/data/legacysurvey/dr11}"
export LS_SAT_DATA="${LS_SAT_DATA:-$PSCRATCH/legacy-satellite-search}"
snapshot="$LS_SAT_DATA/jobs/${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}-${SLURM_ARRAY_TASK_ID:-0}"
mkdir -p "$snapshot" results/summary results/figures
workspace="${LS_SAT_WORKSPACE:-$PWD}"
cp -r "$workspace/src" "$workspace/configs" "$snapshot/"
export PYTHONPATH="$snapshot/src" LS_SAT_CONFIG_DIR="$snapshot/configs/v5${LS_SAT_V5_PROFILE:+/$LS_SAT_V5_PROFILE}"
module=$1
shift
if [[ "$module" == scan-list ]]; then
    field=$(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" "$1")
    test -n "$field"
    set -- "$field"
    module=holdout
fi
exec "$workspace/.venv/bin/python" -u -m "ls_satsearch.$module" "$@"
