#!/bin/bash
# Bounded release-compatible optical processing on a compute node.
set -euo pipefail
id=$1
phase=$2
workspace=$PWD
row=$(awk -F, -v id="$id" '$1==id {print $2, $4, $5, $6}' configs/v13/image_fields.csv)
read -r region ra dec size <<< "$row"
test -n "$size"
survey=/global/cfs/cdirs/cosmo/work/legacysurvey/dr11
output="$PSCRATCH/legacy-satellite-search/image-v13/$id/$phase"
mkdir -p "$output"
export GAIA_CAT_DIR=/global/cfs/cdirs/cosmo/data/gaia/dr3/healpix GAIA_CAT_VER=3 GAIA_CAT_PREFIX=healpix GAIA_CAT_SCHEME="${LS13_GAIA_SCHEME:-nested}"
export TYCHO2_KD_DIR=/global/cfs/cdirs/cosmo/staging/tycho2
export LARGEGALAXIES_CAT="/global/cfs/cdirs/cosmo/data/legacysurvey/dr11/masking/SGA2025-ellipse-v1.6-dr11-$region.kd.fits"
export DUST_DIR=/global/cfs/cdirs/cosmo/data/dust/v0_0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export LS13_NATIVE_DIR="$output" LS13_TRUTH="$output/truth.npy"
if [[ "$region" == south ]]; then
    bands=g,r,z,i
else
    bands=g,r,z
fi
if [[ "$phase" != blank ]]; then
    test -s "$LS13_TRUTH"
fi
cd "$output"
shifter --image=docker:legacysurvey/legacypipe:DR11.1.0 python "$workspace/scripts/v13_native.py" \
  --run "$region" --radec "$ra" "$dec" --width "$size" --height "$size" \
  --bands "$bands" --survey-dir "$survey" --outdir "$output" --threads "${SLURM_CPUS_PER_TASK:-4}" \
  --skip-calibs --old-calibs-ok --no-wise --no-write --skip-metrics
