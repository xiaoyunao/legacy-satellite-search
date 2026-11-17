#!/bin/bash
set -euo pipefail
export LS_SAT_IMAGE_VERSION=v14
exec bash scripts/v13_native.sh "$@"
