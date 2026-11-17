#!/bin/bash
set -euo pipefail
field=$1
export LS_SAT_VERSION=v3
exec bash scripts/v6.sh response_trials "$field" --version v3 \
  --archive ../group-v3/results/matched \
  --policy-archive ../holdout-v4/results/matched \
  --physical-plan configs/v10/compact_trials.yaml --output results/v10/compact_trials
