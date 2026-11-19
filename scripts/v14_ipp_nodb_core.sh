#!/bin/bash
# Use documented optional-feature switches through an isolated Autoconf site file.
set -eo pipefail
if [[ -z "${SLURM_JOB_ID:-}" ]]; then exit 2; fi
ipp_task_probe="$PSCRATCH/legacy-satellite-search/software/ipp/probe_nodb_core"
mkdir -p "$ipp_task_probe"
cat > "$ipp_task_probe/config.site" <<'SITE'
# Equivalent to --without-mysql --enable-debug-build; no algorithm/source patch.
with_mysql=no
enable_debug_build=yes
SITE
export LS_SAT_IPP_RECONFIGURE=1
export CONFIG_SITE="$ipp_task_probe/config.site"
export LS_SAT_IPP_PROBE_NAME=probe_nodb_core LS_SAT_IPP_FIX_LIBS=0 LS_SAT_IPP_OUTPUT=build_nodb_core.json
exec bash scripts/v14_ipp_build_probe.sh
