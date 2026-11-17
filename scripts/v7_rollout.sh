#!/bin/bash
#SBATCH --constraint=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=10
#SBATCH --cpus-per-task=8
#SBATCH --time=00:35:00
#SBATCH --output=logs/%x-%A-%a.log

# Submit from the v7 revision root after the frozen cohort is installed.
set -euo pipefail
export LS_SAT_WORKSPACE="$PWD" LS_SAT_VERSION=v7
section=${1:-rollout}
case "$section" in rollout|gaps) ;; *) exit 2 ;; esac
index=${SLURM_ARRAY_TASK_ID:?Slurm array index required}
export LS_SAT_PROFILE="$section/batch$index"
fields="$LS_SAT_WORKSPACE/configs/v7/$LS_SAT_PROFILE/fields.list"
count=$(wc -l < "$fields")
test "$count" -gt 0
test "$count" -le "$SLURM_NTASKS"
batch="$LS_SAT_WORKSPACE/wide_$section/batch$index"
mkdir -p "$batch/logs"
ln -sfn ../../references "$batch/references"
cd "$batch"
launcher="$LS_SAT_WORKSPACE/scripts/v6.sh"
pending="$batch/logs/scan-list-$SLURM_JOB_ID.txt"
"$LS_SAT_WORKSPACE/.venv/bin/python" - "$fields" > "$pending" <<'PYEOF'
import json
from pathlib import Path
import sys

for name in Path(sys.argv[1]).read_text().splitlines():
    manifest = Path('results/summary')/f'{name}-base'/'manifest.json'
    if manifest.exists():
        try:
            record = json.loads(manifest.read_text())
            if record['status']=='complete' and record['field']['id']==name:
                continue
        except (KeyError,ValueError):
            pass
    print(name)
PYEOF
needed=$(wc -l < "$pending")
if (( needed )); then
    srun -n "$needed" -c 8 --exact -o 'logs/scan-%j-%t.log' bash "$launcher" scan-list "$pending"
fi
srun -n 1 -c 8 --exact -o 'logs/combine-%j.log' bash "$launcher" holdout combine
srun -n 1 -c 8 --exact -o 'logs/review-%j.log' bash "$launcher" expansion_review
