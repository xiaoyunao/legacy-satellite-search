#!/bin/bash
# Build only the bundled Ohana libraries required by IPP, not its application suite.
set -eo pipefail
if [[ -z "${SLURM_JOB_ID:-}" ]]; then exit 2; fi
workspace=$PWD
ipp_task_root="$PSCRATCH/legacy-satellite-search/software/ipp"
ipp_task_probe="$ipp_task_root/probe_ohana_core"
export PSCONFDIR="$ipp_task_root/install" PSVERSION=lssat
export MAKEFLAGS="-j${SLURM_CPUS_PER_TASK:-4}"
mkdir -p "$ipp_task_probe"
source "$PSCONFDIR/psconfig.bash" lssat
cd "$ipp_task_root/ipp-20190404/Ohana"
./configure --prefix="$PSCONFDIR/lssat.lin64" > "$ipp_task_probe/ohana_configure.log" 2>&1
make libs > "$ipp_task_probe/ohana_libraries.log" 2>&1
cd "$workspace"
cat > "$ipp_task_probe/config.site" <<'SITE'
with_mysql=no
enable_debug_build=yes
SITE
export CONFIG_SITE="$ipp_task_probe/config.site" LS_SAT_IPP_RECONFIGURE=1
export LS_SAT_IPP_PROBE_NAME=probe_ohana_core LS_SAT_IPP_FIX_LIBS=0 LS_SAT_IPP_OUTPUT=build_ohana_core.json
exec bash scripts/v14_ipp_build_probe.sh
