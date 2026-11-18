#!/bin/bash
# Submit with afterany:<prior-job> so successful snapshots are not repeated.
set -euo pipefail
[[ "$1" =~ ^[0-9]+$ ]]
state=$(sacct -j "$1" -X -n -P -o State)
case "$state" in
    COMPLETED) exit 0 ;;
    FAILED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL|CANCELLED*)
        exec bash scripts/v14_finalize.sh snapshot
        ;;
    *) printf 'Unresolved predecessor state: %s\n' "$state" >&2; exit 2 ;;
esac
