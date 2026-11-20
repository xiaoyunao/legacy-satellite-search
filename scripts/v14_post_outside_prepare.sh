#!/bin/bash
# Source validation/cache registration after both existing global snapshots close.
set -euo pipefail
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec 9>"$LS_SAT_DATA/runs/v14/summary.lock"
flock 9
.venv/bin/python - <<'PY'
from pathlib import Path
import json
from ls_satsearch.run import sha
terminal=json.loads(Path('results/v14/progress_ab20261120/terminal_acceptance.json').read_text())
assert terminal['all_registered_fields_terminal'] and terminal['registered_fields']==6891
assert all(sha(Path(p))==d for p,d in terminal['input_sha256'].items())
outside=json.loads(Path('results/v14/production_integration/checkpoints/outside_C_final_20261120/acceptance.json').read_text())
assert outside['all_selected_C_accepted']
PY
# The actual older Slurm snapshot lacks these later integration stages.
.venv/bin/python -u scripts/v14_production.py
.venv/bin/python -u -m scripts.v14_production_registry
.venv/bin/python -u -m scripts.v14_integrated_ledger
.venv/bin/python - <<'PY'
from pathlib import Path
import json
from ls_satsearch.run import sha
ledger=json.loads(Path('results/v14/production_integration/reconciled/manifest.json').read_text())
assert ledger['frozen75_verified_current_identities']==75
assert all(sha(Path(p))==d for p,d in ledger['inputs'].items())
PY
.venv/bin/python -u -m scripts.v14_C_coverage
"$LS_SAT_DATA/envs/area-union-20261119/bin/python" -u -m scripts.v14_mask_warm_prepare \
    --receipt results/v14/production_integration/masks/post_outside_C_registration_20261120.json
