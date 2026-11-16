#!/bin/bash
#SBATCH --job-name=ls-sat-fields
#SBATCH --constraint=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:35:00
#SBATCH --output=logs/%x-%j.log
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH="$PWD/src"
export LS_DR11_ROOT="${LS_DR11_ROOT:-/global/cfs/cdirs/cosmo/data/legacysurvey/dr11}"
export LS_SAT_DATA="${LS_SAT_DATA:-$PSCRATCH/legacy-satellite-search}"
census="$LS_SAT_DATA/resources/census.fits"
if [[ ! -f "$census" ]]; then
    gzip -dc "$census.gz" > "$census.tmp"
    mv "$census.tmp" "$census"
fi
exec .venv/bin/python -u -m ls_satsearch.fields "${1:-configs/fields-frozen.yaml}"
