#!/bin/bash
#SBATCH --constraint=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --output=logs/%x-%j.log
set -euo pipefail
export LS_SAT_RUN_VERSION=v6 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
workspace="${LS_SAT_WORKSPACE:-$PWD}"
export LS_SAT_CONFIG_DIR="$workspace/configs/v6${LS_SAT_V6_PROFILE:+/$LS_SAT_V6_PROFILE}"
export PYTHONPATH="$workspace/src"
export LS_SAT_V5="$workspace/../discovery-v5"
module=$1
shift
if [[ "$module" == scan-list ]]; then
    field=$(sed -n "$((SLURM_PROCID+1))p" "$1")
    test -n "$field"
    module=holdout
    set -- "$field"
fi
exec "$workspace/.venv/bin/python" -u -m "ls_satsearch.$module" "$@"
