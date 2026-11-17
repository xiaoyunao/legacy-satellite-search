#!/bin/bash
set -euo pipefail
pids=()
for target in survey63 survey14 delve4 delve5 hercules blank_control depth_control; do
    srun -n1 -c2 --mem=2900M --exact -o "logs/ls11-figure-$target-%j.log" \
        bash scripts/v6.sh paper_diagnostic configs/v11/figure_cases.yaml "$target" results/v11/figures &
    pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do wait "$pid" || status=1; done
exit "$status"
