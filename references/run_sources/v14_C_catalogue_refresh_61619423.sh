#!/bin/bash
# Refresh closed-source candidate/C accounting while outstanding scans continue.
set -euo pipefail
export LS_DR11_ROOT=/global/cfs/cdirs/cosmo/data/legacysurvey/dr11
export LS_SAT_DATA="$PSCRATCH/legacy-satellite-search"
export PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg
mkdir -p "$LS_SAT_DATA/runs/v14"
exec 9>"$LS_SAT_DATA/runs/v14/summary.lock"
flock 9
case "$1" in
 catalogue)
  .venv/bin/python - <<'PY'
from pathlib import Path
import shutil,os
from ls_satsearch.run import sha,write_json
out=Path('results/v14/production_integration/checkpoints')/os.getenv('LS_SAT_C_REFRESH_KEY','C_refresh_20261120');out.mkdir(parents=True,exist_ok=True)
if (out/'catalogue_completion.json').exists():raise ValueError('Preserve accepted catalogue checkpoint; choose a new refresh key')
backup=out/'previous_catalogue';backup.mkdir(exist_ok=True)
for name in ('candidate_catalogue.csv','candidate_modes.csv','manifest.json','potential_associations_within_5arcmin.csv'):
 source=Path('results/v14/catalogue')/name;target=backup/name
 if target.exists():
  continue
 shutil.copy2(source,target)
write_json(out/'backup_manifest.json',dict(job=os.environ['SLURM_JOB_ID'],files={str(p):sha(p) for p in backup.iterdir() if p.is_file()},scope='Preserved previous aggregate catalogue before C refresh; not raw or stellar data.'))
PY
  .venv/bin/python -u scripts/v14_catalog.py
  .venv/bin/python - <<'PY'
from pathlib import Path
import os,json
from ls_satsearch.run import sha,write_json
out=Path('results/v14/production_integration/checkpoints')/os.getenv('LS_SAT_C_REFRESH_KEY','C_refresh_20261120')
paths=[Path('results/v14/catalogue')/n for n in ('candidate_catalogue.csv','candidate_modes.csv','manifest.json','potential_associations_within_5arcmin.csv')]
write_json(out/'catalogue_completion.json',dict(job=os.environ['SLURM_JOB_ID'],files={str(p):sha(p) for p in paths},scope='Accepted catalogue source clock; final full-search convergence and final human evidence remain separate.'))
PY
  ;;
 ledger)
  test -s results/v14/production_integration/checkpoints/C_refresh_20261120/catalogue_completion.json
  .venv/bin/python - <<'PY'
from pathlib import Path
import json,os
from ls_satsearch.run import sha
proof=Path('results/v14/production_integration/checkpoints')/os.getenv('LS_SAT_C_REFRESH_KEY','C_refresh_20261120')/'catalogue_completion.json'
if proof.with_name('ledger_completion.json').exists():raise ValueError('Preserve accepted ledger checkpoint')
for name,digest in json.loads(proof.read_text())['files'].items():
 if sha(Path(name))!=digest:raise ValueError('Catalogue source clock changed before ledger refresh')
PY
  .venv/bin/python -u scripts/v14_production.py
  .venv/bin/python -m scripts.v14_production_registry
  .venv/bin/python -m scripts.v14_integrated_ledger
  .venv/bin/python -m scripts.v14_C_coverage
  .venv/bin/python - <<'PY'
from pathlib import Path
import json,os
from ls_satsearch.run import sha,write_json
out=Path('results/v14/production_integration/checkpoints')/os.getenv('LS_SAT_C_REFRESH_KEY','C_refresh_20261120')
files=[Path(p) for p in ['results/v14/production_integration/manifest.json','results/v14/production_integration/reconciled/manifest.json','results/v14/production_integration/C_seed_coverage/summary.json']]
if json.loads(files[1].read_text())['frozen75_verified_current_identities']!=75:
 raise ValueError('Original75 identity preservation failed; no checkpoint acceptance')
code=[Path('scripts')/p for p in ('v14_production.py','v14_production_registry.py','v14_integrated_ledger.py','v14_C_coverage.py','v14_C_catalogue_refresh.sh')]
write_json(out/'ledger_completion.json',dict(job=os.environ['SLURM_JOB_ID'],files={str(p):sha(p) for p in files},code={str(p):sha(p) for p in code},C_seed_coverage=json.loads(files[-1].read_text()),scope='Completed-source interim integration only, not final full-search production/sample/area freeze or review release.'))
PY
  ;;
 *) exit 2 ;;
esac
