#!/bin/bash
#SBATCH --job-name=ls-sat-analysis
#SBATCH --constraint=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --output=logs/%x-%j.log
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
export PYTHONPATH="$PWD/src"
export LS_DR11_ROOT="${LS_DR11_ROOT:-/global/cfs/cdirs/cosmo/data/legacysurvey/dr11}"
export LS_SAT_DATA="${LS_SAT_DATA:-$PSCRATCH/legacy-satellite-search}"
.venv/bin/python -m ls_satsearch.evaluate
if [[ -f results/summary/pilot_candidate_summary.csv ]]; then
    .venv/bin/python - <<'PY'
from pathlib import Path
from ls_satsearch.review import review
from ls_satsearch.run import read_csv

peaks = read_csv(Path("results/summary/pilot_candidate_summary.csv"))
for field, depth in sorted({(r["field_id"], r["depth"]) for r in peaks}):
    print(f"Reviewing {field} at {depth} depth", flush=True)
    review(field, depth)
PY
    .venv/bin/python -m ls_satsearch.evaluate
fi
.venv/bin/python -m ls_satsearch.inject
.venv/bin/python -m ls_satsearch.summarize
