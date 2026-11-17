#!/bin/bash
set -euo pipefail
cohort=$1
export LS_SAT_VERSION=v11 LS_SAT_PROFILE="cohorts/$cohort"
args=()
case "$cohort" in
  north) args+=(--controls regional_north_controls/results/summary) ;;
  south_ps1) args+=(--policy "configs/v11/cohorts/$cohort/production.json") ;;
esac
exec bash scripts/v6.sh regional_pilot combine "regional_$cohort/results/summary" \
    "configs/v11/cohorts/$cohort/fields.yaml" "results/v11/$cohort" "${args[@]}"
